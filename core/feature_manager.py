#!/usr/bin/env python3
"""
Feature Manager - Gestion centralisée des feature flags

Permet d'activer/désactiver des features du bot sans consommer de mémoire
pour les features désactivées. Compatible avec une future migration Rust (PyO3).

Usage:
    from core.feature_manager import FeatureManager, Feature
    
    features = FeatureManager(config)
    
    if features.is_enabled(Feature.TRANSLATOR):
        init_translator()

Architecture:
    - Enum Feature : Liste exhaustive des features disponibles
    - FeatureManager : Singleton qui gère l'état des features
    - Intégration config.yaml : Section `features:` pour activer/désactiver
"""

import logging
from enum import Enum, auto
from typing import Dict, Optional, Any

LOGGER = logging.getLogger(__name__)


class Feature(Enum):
    """
    Enum des features disponibles dans KissBot.
    
    Chaque feature a un nom technique et peut être activée/désactivée
    via config.yaml. Documenter ici pour référence centralisée.
    
    Note: Compatible PyO3 - les enums Rust peuvent mapper sur ces valeurs.
    """
    
    # === Core Features ===
    COMMANDS = auto()
    """Système de commandes chat (!ping, !help, etc.)"""
    
    ANALYTICS = auto()
    """Collecte et agrégation des métriques d'usage"""
    
    CHAT_LOGGER = auto()
    """Logging des messages chat dans fichiers dédiés"""
    
    SYSTEM_MONITOR = auto()
    """Monitoring CPU/RAM/Threads avec alertes"""
    
    # === Integrations ===
    TRANSLATOR = auto()
    """Traduction automatique (!trad) - Charge langdetect ~57MB"""
    
    LLM = auto()
    """LLM Handler pour !ask et mentions - Requiert API key"""
    
    GAME_ENGINE = auto()
    """Rust Game Engine pour !gi, !gs - Ultra léger"""
    
    MUSIC_CACHE = auto()
    """Cache musique quantique (POC)"""
    
    WIKIPEDIA = auto()
    """Handler Wikipedia pour !wiki"""
    
    # === Stream Monitoring ===
    STREAM_MONITOR = auto()
    """Monitoring stream (polling Helix)"""
    
    EVENTSUB = auto()
    """EventSub WebSocket pour events real-time"""
    
    STREAM_ANNOUNCER = auto()
    """Annonces automatiques stream online/offline"""
    
    # === Advanced Features ===
    DEVTOOLS = auto()
    """Outils développeur (!decoherence, debug commands)"""
    
    AUTO_PERSONA = auto()
    """Personnalité automatique basée sur contexte"""
    
    AUTO_TRANSLATE_STREAMERS = auto()
    """Traduction auto pour streamers (mode premium)"""
    
    BROADCAST = auto()
    """Système de broadcast inter-channels (!kisscharity)"""
    
    MEMORY_PROFILER = auto()
    """Profiling mémoire/CPU des features (ce système!)"""
    
    @classmethod
    def from_string(cls, name: str) -> Optional['Feature']:
        """
        Convertit un string en Feature enum.
        
        Args:
            name: Nom de la feature (case-insensitive)
            
        Returns:
            Feature enum ou None si non trouvée
        """
        name_upper = name.upper().replace('-', '_')
        try:
            return cls[name_upper]
        except KeyError:
            return None
    
    @property
    def config_key(self) -> str:
        """Retourne la clé pour config.yaml (lowercase, underscores)"""
        return self.name.lower()


# === Feature Metadata ===
FEATURE_METADATA: Dict[Feature, Dict[str, Any]] = {
    Feature.COMMANDS: {
        "description": "Système de commandes chat",
        "memory_estimate_mb": 2,
        "requires": [],
        "default": True,
    },
    Feature.ANALYTICS: {
        "description": "Collecte métriques d'usage",
        "memory_estimate_mb": 1,
        "requires": [],
        "default": True,
    },
    Feature.CHAT_LOGGER: {
        "description": "Logging messages chat",
        "memory_estimate_mb": 1,
        "requires": [],
        "default": True,
    },
    Feature.SYSTEM_MONITOR: {
        "description": "Monitoring CPU/RAM",
        "memory_estimate_mb": 1,
        "requires": [],
        "default": True,
    },
    Feature.TRANSLATOR: {
        "description": "Traduction (!trad) - langdetect charge ~57MB",
        "memory_estimate_mb": 60,
        "requires": [],
        "default": True,
        "heavy": True,  # Marqueur pour features gourmandes
    },
    Feature.LLM: {
        "description": "LLM Handler (!ask, mentions)",
        "memory_estimate_mb": 5,
        "requires": ["apis.openai_key"],
        "default": True,
    },
    Feature.GAME_ENGINE: {
        "description": "Rust Game Engine (!gi, !gs)",
        "memory_estimate_mb": 0.1,
        "requires": [],
        "default": True,
    },
    Feature.MUSIC_CACHE: {
        "description": "Cache musique quantique (POC)",
        "memory_estimate_mb": 2,
        "requires": [],
        "default": False,
    },
    Feature.WIKIPEDIA: {
        "description": "Handler Wikipedia (!wiki)",
        "memory_estimate_mb": 1,
        "requires": [],
        "default": True,
    },
    Feature.STREAM_MONITOR: {
        "description": "Polling Helix pour stream status",
        "memory_estimate_mb": 1,
        "requires": [],
        "default": True,
    },
    Feature.EVENTSUB: {
        "description": "EventSub WebSocket real-time",
        "memory_estimate_mb": 3,
        "requires": [],
        "default": True,
    },
    Feature.STREAM_ANNOUNCER: {
        "description": "Annonces stream online/offline",
        "memory_estimate_mb": 1,
        "requires": [Feature.STREAM_MONITOR],
        "default": True,
    },
    Feature.DEVTOOLS: {
        "description": "Outils développeur",
        "memory_estimate_mb": 0.5,
        "requires": [],
        "default": False,
    },
    Feature.AUTO_PERSONA: {
        "description": "Personnalité auto contextuelle",
        "memory_estimate_mb": 2,
        "requires": [Feature.LLM],
        "default": False,
    },
    Feature.AUTO_TRANSLATE_STREAMERS: {
        "description": "Traduction auto streamers",
        "memory_estimate_mb": 0.5,
        "requires": [Feature.TRANSLATOR],
        "default": False,
    },
    Feature.BROADCAST: {
        "description": "Broadcast inter-channels",
        "memory_estimate_mb": 0.5,
        "requires": [],
        "default": True,
    },
    Feature.MEMORY_PROFILER: {
        "description": "Profiling mémoire/CPU features",
        "memory_estimate_mb": 1,
        "requires": [],
        "default": False,
    },
}


class FeatureManager:
    """
    Gestionnaire centralisé des feature flags.
    
    Lit la configuration depuis config.yaml et fournit une API simple
    pour vérifier si une feature est activée.
    
    Usage:
        features = FeatureManager(config)
        
        if features.is_enabled(Feature.TRANSLATOR):
            # Initialiser uniquement si activé
            init_translator()
    
    Config YAML attendue:
        features:
            translator: true
            llm: false
            devtools: true
    """
    
    _instance: Optional['FeatureManager'] = None
    
    def __new__(cls, config: Optional[Dict] = None):
        """Singleton pattern pour accès global"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialise le FeatureManager avec la config.
        
        Args:
            config: Configuration complète du bot (dict)
        """
        if self._initialized and config is None:
            return
            
        self._config = config or {}
        self._features_config = self._config.get("features", {})
        self._enabled_features: Dict[Feature, bool] = {}
        self._initialized = True
        
        # Charger l'état de chaque feature
        self._load_features()
        
        LOGGER.info(f"🎛️ FeatureManager initialized: {self.get_enabled_count()}/{len(Feature)} features enabled")
    
    def _load_features(self) -> None:
        """Charge l'état de chaque feature depuis la config"""
        for feature in Feature:
            # Valeur par défaut depuis metadata
            default = FEATURE_METADATA.get(feature, {}).get("default", True)
            
            # Override depuis config.yaml si présent
            config_value = self._features_config.get(feature.config_key)
            
            if config_value is not None:
                self._enabled_features[feature] = bool(config_value)
            else:
                self._enabled_features[feature] = default
    
    def is_enabled(self, feature: Feature) -> bool:
        """
        Vérifie si une feature est activée.
        
        Args:
            feature: Feature enum à vérifier
            
        Returns:
            True si activée, False sinon
        """
        return self._enabled_features.get(feature, False)
    
    def is_enabled_str(self, feature_name: str) -> bool:
        """
        Vérifie si une feature est activée (version string).
        
        Args:
            feature_name: Nom de la feature (ex: "translator")
            
        Returns:
            True si activée, False sinon
        """
        feature = Feature.from_string(feature_name)
        if feature is None:
            LOGGER.warning(f"⚠️ Unknown feature: {feature_name}")
            return False
        return self.is_enabled(feature)
    
    def enable(self, feature: Feature) -> None:
        """Active une feature dynamiquement"""
        self._enabled_features[feature] = True
        LOGGER.info(f"✅ Feature {feature.name} enabled")
    
    def disable(self, feature: Feature) -> None:
        """Désactive une feature dynamiquement"""
        self._enabled_features[feature] = False
        LOGGER.info(f"❌ Feature {feature.name} disabled")
    
    def get_enabled_count(self) -> int:
        """Retourne le nombre de features activées"""
        return sum(1 for enabled in self._enabled_features.values() if enabled)
    
    def get_enabled_features(self) -> list[Feature]:
        """Retourne la liste des features activées"""
        return [f for f, enabled in self._enabled_features.items() if enabled]
    
    def get_disabled_features(self) -> list[Feature]:
        """Retourne la liste des features désactivées"""
        return [f for f, enabled in self._enabled_features.items() if not enabled]
    
    def get_heavy_features(self) -> list[Feature]:
        """Retourne les features marquées comme 'heavy' (gourmandes en RAM)"""
        return [
            f for f in self.get_enabled_features()
            if FEATURE_METADATA.get(f, {}).get("heavy", False)
        ]
    
    def estimate_memory_usage(self) -> float:
        """
        Estime la consommation mémoire des features activées.
        
        Returns:
            Estimation en MB
        """
        total = 0.0
        for feature in self.get_enabled_features():
            meta = FEATURE_METADATA.get(feature, {})
            total += meta.get("memory_estimate_mb", 0)
        return total
    
    def get_status_report(self) -> str:
        """
        Génère un rapport d'état des features.
        
        Returns:
            String formaté avec l'état de chaque feature
        """
        lines = ["🎛️ Feature Status Report", "=" * 40]
        
        enabled = self.get_enabled_features()
        disabled = self.get_disabled_features()
        
        lines.append(f"\n✅ Enabled ({len(enabled)}):")
        for f in enabled:
            meta = FEATURE_METADATA.get(f, {})
            mem = meta.get("memory_estimate_mb", "?")
            heavy = " 🔴 HEAVY" if meta.get("heavy") else ""
            lines.append(f"   {f.config_key}: ~{mem}MB{heavy}")
        
        lines.append(f"\n❌ Disabled ({len(disabled)}):")
        for f in disabled:
            lines.append(f"   {f.config_key}")
        
        lines.append(f"\n📊 Estimated total: ~{self.estimate_memory_usage():.1f}MB")
        
        return "\n".join(lines)


# === Singleton accessor ===
_feature_manager: Optional[FeatureManager] = None


def get_feature_manager() -> Optional[FeatureManager]:
    """Retourne l'instance singleton du FeatureManager"""
    return FeatureManager._instance


def init_feature_manager(config: Dict) -> FeatureManager:
    """
    Initialise le FeatureManager avec la config.
    
    Args:
        config: Configuration complète du bot
        
    Returns:
        Instance du FeatureManager
    """
    return FeatureManager(config)
