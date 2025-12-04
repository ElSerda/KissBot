#!/usr/bin/env python3
"""
Memory Profiler - Profilage RAM/CPU des features KissBot

Système de mesure de la consommation mémoire et CPU par feature.
Fournit un décorateur @log_feature_mem pour instrumenter les initialisations.

Usage:
    from core.memory_profiler import log_feature_mem, get_profiler
    
    @log_feature_mem("translator")
    def init_translator():
        ...
    
    # Ou async
    @log_feature_mem("llm_handler")
    async def init_llm():
        ...

Logs générés:
    [MEM] Feature translator: +53.2 MB (total: 89.4 MB)
    [CPU] Feature translator: 12.3% (init: 0.34s)

Architecture:
    - Compatible psutil (optionnel, graceful degradation)
    - Centralisé dans un Profiler singleton
    - Préparé pour migration Rust (PyO3 bindings)
"""

import asyncio
import functools
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Any, TypeVar, Union
from datetime import datetime

# psutil est optionnel
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False

LOGGER = logging.getLogger(__name__)

# Type vars pour décorateurs génériques
F = TypeVar('F', bound=Callable[..., Any])


@dataclass
class FeatureProfile:
    """Profil mémoire/CPU d'une feature"""
    name: str
    memory_before_mb: float = 0.0
    memory_after_mb: float = 0.0
    memory_delta_mb: float = 0.0
    cpu_percent: float = 0.0
    init_duration_s: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    success: bool = True
    error: Optional[str] = None
    
    @property
    def memory_formatted(self) -> str:
        """Format la différence mémoire avec signe"""
        sign = "+" if self.memory_delta_mb >= 0 else ""
        return f"{sign}{self.memory_delta_mb:.2f} MB"


class MemoryProfiler:
    """
    Profiler centralisé pour mesurer RAM/CPU des features.
    
    Singleton qui collecte les profils de toutes les features
    et fournit des rapports agrégés.
    
    Compatible avec:
        - Fonctions synchrones
        - Fonctions asynchrones
        - Méthodes de classe
    """
    
    _instance: Optional['MemoryProfiler'] = None
    
    def __new__(cls, enabled: bool = True):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, enabled: bool = True):
        if self._initialized:
            return
            
        self._enabled = enabled
        self._profiles: Dict[str, FeatureProfile] = {}
        self._process: Optional[Any] = None
        self._initialized = True
        
        # Initialiser psutil process si disponible
        if PSUTIL_AVAILABLE and enabled:
            try:
                self._process = psutil.Process()
                LOGGER.debug("📊 MemoryProfiler: psutil initialized")
            except Exception as e:
                LOGGER.warning(f"⚠️ MemoryProfiler: psutil init failed: {e}")
                self._process = None
        
        if not PSUTIL_AVAILABLE:
            LOGGER.info("📊 MemoryProfiler: psutil not available, profiling disabled")
    
    @property
    def is_available(self) -> bool:
        """Vérifie si le profiling est disponible"""
        return self._enabled and PSUTIL_AVAILABLE and self._process is not None
    
    def get_current_memory_mb(self) -> float:
        """
        Retourne la mémoire RSS actuelle du process en MB.
        
        Returns:
            Mémoire en MB ou 0.0 si non disponible
        """
        if not self.is_available:
            return 0.0
        try:
            return self._process.memory_info().rss / (1024 * 1024)
        except Exception:
            return 0.0
    
    def get_current_cpu_percent(self) -> float:
        """
        Retourne le CPU% actuel du process.
        
        Returns:
            CPU% ou 0.0 si non disponible
        """
        if not self.is_available:
            return 0.0
        try:
            # interval=None pour non-blocking (compare avec dernier appel)
            return self._process.cpu_percent(interval=None)
        except Exception:
            return 0.0
    
    def start_profile(self, feature_name: str) -> Dict[str, Any]:
        """
        Démarre le profiling d'une feature.
        
        Args:
            feature_name: Nom de la feature
            
        Returns:
            Dict avec les métriques de départ
        """
        context = {
            "name": feature_name,
            "memory_before": self.get_current_memory_mb(),
            "time_start": time.perf_counter(),
            "cpu_start": self.get_current_cpu_percent(),
        }
        
        # Pré-sample CPU pour avoir une baseline
        if self.is_available:
            try:
                self._process.cpu_percent(interval=None)
            except Exception:
                pass
        
        return context
    
    def end_profile(self, context: Dict[str, Any], success: bool = True, error: Optional[str] = None) -> FeatureProfile:
        """
        Termine le profiling et enregistre le résultat.
        
        Args:
            context: Contexte retourné par start_profile
            success: Si l'init a réussi
            error: Message d'erreur si échec
            
        Returns:
            FeatureProfile avec les métriques
        """
        memory_after = self.get_current_memory_mb()
        time_end = time.perf_counter()
        cpu_percent = self.get_current_cpu_percent()
        
        profile = FeatureProfile(
            name=context["name"],
            memory_before_mb=context["memory_before"],
            memory_after_mb=memory_after,
            memory_delta_mb=memory_after - context["memory_before"],
            cpu_percent=cpu_percent,
            init_duration_s=time_end - context["time_start"],
            success=success,
            error=error,
        )
        
        # Enregistrer le profil
        self._profiles[profile.name] = profile
        
        # Logger les résultats
        self._log_profile(profile)
        
        return profile
    
    def _log_profile(self, profile: FeatureProfile) -> None:
        """Log le profil au format standardisé"""
        if not profile.success:
            LOGGER.error(
                f"[MEM] Feature {profile.name}: FAILED - {profile.error}"
            )
            return
        
        # Log mémoire
        total_mem = profile.memory_after_mb
        LOGGER.info(
            f"[MEM] Feature {profile.name}: {profile.memory_formatted} "
            f"(total: {total_mem:.1f} MB)"
        )
        
        # Log CPU si significatif
        if profile.cpu_percent > 0.5:
            LOGGER.info(
                f"[CPU] Feature {profile.name}: {profile.cpu_percent:.1f}% "
                f"(init: {profile.init_duration_s:.2f}s)"
            )
    
    def get_profile(self, feature_name: str) -> Optional[FeatureProfile]:
        """Retourne le profil d'une feature"""
        return self._profiles.get(feature_name)
    
    def get_all_profiles(self) -> List[FeatureProfile]:
        """Retourne tous les profils enregistrés"""
        return list(self._profiles.values())
    
    def get_total_memory_delta(self) -> float:
        """Retourne la somme des deltas mémoire"""
        return sum(p.memory_delta_mb for p in self._profiles.values())
    
    def get_heavy_features(self, threshold_mb: float = 10.0) -> List[FeatureProfile]:
        """
        Retourne les features qui consomment plus de threshold_mb.
        
        Args:
            threshold_mb: Seuil en MB
            
        Returns:
            Liste des profils dépassant le seuil
        """
        return [
            p for p in self._profiles.values()
            if p.memory_delta_mb >= threshold_mb
        ]
    
    def get_report(self) -> str:
        """
        Génère un rapport de profiling complet.
        
        Returns:
            Rapport formaté en string
        """
        if not self._profiles:
            return "📊 No features profiled yet"
        
        lines = [
            "📊 Memory Profiler Report",
            "=" * 50,
            "",
        ]
        
        # Trier par delta mémoire décroissant
        sorted_profiles = sorted(
            self._profiles.values(),
            key=lambda p: p.memory_delta_mb,
            reverse=True
        )
        
        for p in sorted_profiles:
            status = "✅" if p.success else "❌"
            heavy = " 🔴" if p.memory_delta_mb >= 10 else ""
            lines.append(
                f"{status} {p.name}: {p.memory_formatted}{heavy} "
                f"(init: {p.init_duration_s:.2f}s, CPU: {p.cpu_percent:.1f}%)"
            )
        
        lines.extend([
            "",
            "-" * 50,
            f"📈 Total delta: +{self.get_total_memory_delta():.1f} MB",
            f"📍 Current RSS: {self.get_current_memory_mb():.1f} MB",
        ])
        
        # Alertes pour features lourdes
        heavy = self.get_heavy_features()
        if heavy:
            lines.extend([
                "",
                "⚠️ Heavy features (>10MB):",
            ])
            for p in heavy:
                lines.append(f"   - {p.name}: {p.memory_formatted}")
        
        return "\n".join(lines)
    
    def reset(self) -> None:
        """Reset tous les profils"""
        self._profiles.clear()


# === Singleton accessor ===
_profiler: Optional[MemoryProfiler] = None


def get_profiler() -> MemoryProfiler:
    """Retourne l'instance singleton du MemoryProfiler"""
    global _profiler
    if _profiler is None:
        _profiler = MemoryProfiler()
    return _profiler


def init_profiler(enabled: bool = True) -> MemoryProfiler:
    """
    Initialise le profiler.
    
    Args:
        enabled: Activer le profiling
        
    Returns:
        Instance du MemoryProfiler
    """
    global _profiler
    _profiler = MemoryProfiler(enabled=enabled)
    return _profiler


# === Décorateur principal ===

def log_feature_mem(feature_name: str) -> Callable[[F], F]:
    """
    Décorateur pour mesurer la RAM/CPU d'une fonction d'initialisation.
    
    Fonctionne avec les fonctions sync et async.
    
    Usage:
        @log_feature_mem("translator")
        def init_translator():
            from langdetect import detect
            ...
        
        @log_feature_mem("llm_handler")
        async def init_llm():
            await setup_openai()
            ...
    
    Logs générés:
        [MEM] Feature translator: +53.2 MB (total: 89.4 MB)
        [CPU] Feature translator: 12.3% (init: 0.34s)
    
    Args:
        feature_name: Nom de la feature pour les logs
        
    Returns:
        Décorateur applicable à une fonction
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            profiler = get_profiler()
            context = profiler.start_profile(feature_name)
            
            try:
                result = func(*args, **kwargs)
                profiler.end_profile(context, success=True)
                return result
            except Exception as e:
                profiler.end_profile(context, success=False, error=str(e))
                raise
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            profiler = get_profiler()
            context = profiler.start_profile(feature_name)
            
            try:
                result = await func(*args, **kwargs)
                profiler.end_profile(context, success=True)
                return result
            except Exception as e:
                profiler.end_profile(context, success=False, error=str(e))
                raise
        
        # Retourner le bon wrapper selon le type de fonction
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore
    
    return decorator


def profile_block(feature_name: str):
    """
    Context manager pour profiler un bloc de code.
    
    Usage:
        with profile_block("custom_init"):
            heavy_operation()
            more_code()
    
    Args:
        feature_name: Nom pour identifier le bloc
    """
    class ProfileContext:
        def __init__(self, name: str):
            self.name = name
            self.profiler = get_profiler()
            self.context: Optional[Dict[str, Any]] = None
        
        def __enter__(self):
            self.context = self.profiler.start_profile(self.name)
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            success = exc_type is None
            error = str(exc_val) if exc_val else None
            self.profiler.end_profile(self.context, success=success, error=error)
            return False  # Ne pas supprimer l'exception
    
    return ProfileContext(feature_name)


# === Async context manager ===

class AsyncProfileBlock:
    """
    Async context manager pour profiler un bloc async.
    
    Usage:
        async with async_profile_block("async_init"):
            await heavy_async_operation()
    """
    def __init__(self, feature_name: str):
        self.name = feature_name
        self.profiler = get_profiler()
        self.context: Optional[Dict[str, Any]] = None
    
    async def __aenter__(self):
        self.context = self.profiler.start_profile(self.name)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        success = exc_type is None
        error = str(exc_val) if exc_val else None
        self.profiler.end_profile(self.context, success=success, error=error)
        return False


def async_profile_block(feature_name: str) -> AsyncProfileBlock:
    """
    Retourne un async context manager pour profiler un bloc.
    
    Args:
        feature_name: Nom pour identifier le bloc
    """
    return AsyncProfileBlock(feature_name)
