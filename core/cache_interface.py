"""Common cache interface for GameCache and QuantumGameCache. See: docs/api/cache_interface.md"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheEntry:
    """Entrée de cache standardisée."""

    key: str
    value: dict[str, Any]
    timestamp: float
    ttl_seconds: float | None = None
    confirmed: bool = False
    confidence: float = 1.0
    observer_count: int = 0
    source: str = "api"


@dataclass
class CacheStats:
    """Statistiques de cache standardisées."""

    total_keys: int
    confirmed_keys: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    hit_rate: float = 0.0
    total_size_mb: float = 0.0
    avg_confidence: float = 0.0
    quantum_enabled: bool = False


class BaseCacheInterface(ABC):
    """Interface abstraite pour tous les caches KissBot."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def get(self, key: str) -> dict[str, Any] | None:
        """
        Récupère une valeur du cache.

        Args:
            key: Clé de recherche

        Returns:
            Dict avec les données ou None si non trouvé
        """
        pass

    @abstractmethod
    def set(self, key: str, value: dict[str, Any], **kwargs) -> bool:
        """
        Stocke une valeur dans le cache.

        Args:
            key: Clé de stockage
            value: Données à stocker
            **kwargs: Options spécifiques (ttl, confirmed, etc.)

        Returns:
            True si stockage réussi
        """
        pass

    @abstractmethod
    async def search(self, query: str, **kwargs) -> dict[str, Any] | None:
        """
        Recherche intelligente dans le cache.

        Args:
            query: Terme de recherche
            **kwargs: Options spécifiques (observer, mode, etc.)

        Returns:
            Résultat de recherche ou None
        """
        pass

    @abstractmethod
    def get_stats(self) -> CacheStats:
        """
        Retourne les statistiques du cache.

        Returns:
            CacheStats avec métriques actuelles
        """
        pass

    @abstractmethod
    def clear(self) -> bool:
        """
        Vide le cache.

        Returns:
            True si vidage réussi
        """
        pass

    @abstractmethod
    def cleanup_expired(self) -> int:
        """
        Nettoie les entrées expirées.

        Returns:
            Nombre d'entrées supprimées
        """
        pass

    # Méthodes optionnelles avec implémentation par défaut
    def has_key(self, key: str) -> bool:
        """Vérifie si une clé existe."""
        return self.get(key) is not None

    def size(self) -> int:
        """Retourne le nombre d'entrées."""
        stats = self.get_stats()
        return stats.total_keys

    def is_quantum_enabled(self) -> bool:
        """Indique si ce cache supporte les fonctionnalités quantiques."""
        return hasattr(self, "quantum_cache") or "quantum" in self.__class__.__name__.lower()


class CacheManager:
    """
    Gestionnaire unifié pour tous les types de cache.

    Permet de switcher entre GameCache/QuantumGameCache de façon transparente.
    """

    def __init__(self, config: dict[str, Any], prefer_quantum: bool = True):
        self.config = config
        self.prefer_quantum = prefer_quantum
        self.logger = logging.getLogger(__name__)

        # Initialiser le cache principal
        self.primary_cache = self._create_primary_cache()

        # Cache de fallback optionnel
        self.fallback_cache = self._create_fallback_cache()

        self.logger.info(
            f"🗂️ CacheManager initialisé - "
            f"Principal: {self.primary_cache.__class__.__name__}, "
            f"Fallback: {self.fallback_cache.__class__.__name__ if self.fallback_cache else 'None'}"
        )

    def _create_primary_cache(self) -> BaseCacheInterface:
        """Crée le cache principal selon la configuration."""
        if self.prefer_quantum:
            try:
                from backends.quantum_game_cache import QuantumGameCache

                self.logger.info("🔬 Cache quantique sélectionné comme principal")
                return QuantumGameCache(self.config)
            except ImportError:
                self.logger.warning("⚠️ Cache quantique non disponible, fallback classique")

        from backends.game_cache import GameCache

        self.logger.info("💾 Cache classique sélectionné comme principal")
        return GameCache(self.config)

    def _create_fallback_cache(self) -> BaseCacheInterface | None:
        """Crée le cache de fallback."""
        if isinstance(self.primary_cache, BaseCacheInterface) and hasattr(
            self.primary_cache, "quantum_cache"
        ):
            # Si primary est quantique, fallback classique
            try:
                from backends.game_cache import GameCache

                self.logger.info("💾 Cache classique configuré comme fallback")
                return GameCache(self.config)
            except ImportError:
                pass

        return None

    # Interface unifiée - délègue au cache principal
    def get(self, key: str) -> dict[str, Any] | None:
        """Récupération avec fallback automatique."""
        try:
            result = self.primary_cache.get(key)
            if result is not None:
                return result
        except Exception as e:
            self.logger.warning(f"Erreur cache principal: {e}")

        # Fallback
        if self.fallback_cache:
            try:
                return self.fallback_cache.get(key)
            except Exception as e:
                self.logger.error(f"Erreur cache fallback: {e}")

        return None

    def set(self, key: str, value: dict[str, Any], **kwargs) -> bool:
        """Stockage avec synchronisation optionnelle."""
        success = False

        # Stocker dans le cache principal
        try:
            success = self.primary_cache.set(key, value, **kwargs)
        except Exception as e:
            self.logger.error(f"Erreur stockage principal: {e}")

        # Optionnel : synchroniser avec fallback pour cohérence
        if self.fallback_cache and success:
            try:
                # Stockage simplifié dans fallback (sans options quantiques)
                fallback_kwargs = {k: v for k, v in kwargs.items() if k in ["ttl_seconds"]}
                self.fallback_cache.set(key, value, **fallback_kwargs)
            except Exception as e:
                self.logger.warning(f"Sync fallback échouée: {e}")

        return success

    async def search(self, query: str, **kwargs) -> dict[str, Any] | None:
        """Recherche avec fallback automatique."""
        try:
            result = await self.primary_cache.search(query, **kwargs)
            if result is not None:
                return result
        except Exception as e:
            self.logger.warning(f"Erreur recherche principale: {e}")

        # Fallback
        if self.fallback_cache:
            try:
                # Recherche simplifiée dans fallback
                simple_result = self.fallback_cache.get(query.lower())
                if simple_result:
                    return simple_result
            except Exception as e:
                self.logger.error(f"Erreur recherche fallback: {e}")

        return None

    def get_stats(self) -> dict[str, CacheStats]:
        """Statistiques combinées des caches."""
        stats = {}

        try:
            stats["primary"] = self.primary_cache.get_stats()
        except Exception as e:
            self.logger.error(f"Erreur stats principal: {e}")
            stats["primary"] = CacheStats(total_keys=0)

        if self.fallback_cache:
            try:
                stats["fallback"] = self.fallback_cache.get_stats()
            except Exception as e:
                self.logger.warning(f"Erreur stats fallback: {e}")
                stats["fallback"] = CacheStats(total_keys=0)

        return stats

    def get_unified_stats(self) -> CacheStats:
        """Statistiques unifiées pour compatibilité."""
        all_stats = self.get_stats()
        primary_stats = all_stats.get("primary", CacheStats(total_keys=0))

        # Utiliser les stats du cache principal
        primary_stats.quantum_enabled = self.primary_cache.is_quantum_enabled()
        return primary_stats

    def clear(self) -> bool:
        """Vide tous les caches."""
        success = True

        try:
            success &= self.primary_cache.clear()
        except Exception as e:
            self.logger.error(f"Erreur vidage principal: {e}")
            success = False

        if self.fallback_cache:
            try:
                success &= self.fallback_cache.clear()
            except Exception as e:
                self.logger.warning(f"Erreur vidage fallback: {e}")

        return success

    def cleanup_expired(self) -> int:
        """Nettoie tous les caches."""
        total_cleaned = 0

        try:
            total_cleaned += self.primary_cache.cleanup_expired()
        except Exception as e:
            self.logger.error(f"Erreur cleanup principal: {e}")

        if self.fallback_cache:
            try:
                total_cleaned += self.fallback_cache.cleanup_expired()
            except Exception as e:
                self.logger.warning(f"Erreur cleanup fallback: {e}")

        return total_cleaned


# Types utilitaires
CacheType = BaseCacheInterface | CacheManager
GameCacheType = BaseCacheInterface | CacheManager  # Simplifié pour éviter les imports circulaires
