"""
🎮 Game Cache Classique - KissBot V1

Cache système optimisé pour les données de jeux.
Archi parallèle au QuantumGameCache pour compatibilité.

FONCTIONNALITÉS :
├── Cache simple et efficace
├── Gestion TTL automatique
├── Nettoyage expired intelligent
├── Compatibilité config standard
└── Fallback pour système quantique
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any

from core.cache_interface import BaseCacheInterface, CacheStats


class GameCache(BaseCacheInterface):
    """
    Cache Classique pour les jeux - Architecture parallèle au QuantumCache

    WORKFLOW CLASSIQUE :
    - Recherche directe par clé
    - TTL fixe configurable
    - Pas d'apprentissage adaptatif
    - Cache simple mais robuste
    """

    def __init__(self, config: dict[str, Any], cache_file: str = "cache/games.json"):
        super().__init__(config)
        self.cache_file = cache_file

        # Configuration cache depuis config
        cache_config = config.get("cache", {})
        self.cache_duration = timedelta(hours=cache_config.get("duration_hours", 24))

        # Initialisation
        self.cache: dict[str, Any] = {}
        self.logger = logging.getLogger(__name__)

        self._ensure_cache_dir()
        self._load_cache()

    def _ensure_cache_dir(self):
        """Créer le dossier cache si nécessaire."""
        cache_dir = os.path.dirname(self.cache_file)
        if cache_dir and not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

    def _load_cache(self):
        """Charger le cache depuis le fichier."""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, encoding="utf-8") as f:
                    data = json.load(f)

                # Nettoyer les entrées expirées
                now = datetime.now()
                valid_cache = {}

                for key, entry in data.items():
                    cached_time = datetime.fromisoformat(entry["cached_at"])
                    if now - cached_time < self.cache_duration:
                        valid_cache[key] = entry

                self.cache = valid_cache
                self.logger.info(f"🗂️ Cache chargé: {len(self.cache)} entrées valides")
            else:
                self.logger.info("🗂️ Nouveau cache créé")

        except Exception as e:
            self.logger.error(f"Erreur chargement cache: {e}")
            self.cache = {}

    def _save_cache(self):
        """Sauvegarder le cache."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Erreur sauvegarde cache: {e}")

    def get(self, game_query: str) -> dict[Any, Any] | None:
        """Récupérer un jeu du cache."""
        cache_key = game_query.lower().strip()

        if cache_key in self.cache:
            entry = self.cache[cache_key]
            cached_time = datetime.fromisoformat(entry["cached_at"])

            # Vérifier si pas expiré
            if datetime.now() - cached_time < self.cache_duration:
                self.logger.info(f"🎯 Cache HIT: {game_query}")
                return entry["data"]
            else:
                # Supprimer entrée expirée
                del self.cache[cache_key]
                self.logger.info(f"⏰ Cache EXPIRED: {game_query}")

        self.logger.info(f"❌ Cache MISS: {game_query}")
        return None

    def set(self, game_query: str, game_data: dict[Any, Any], **kwargs) -> bool:
        """Mettre en cache un jeu - Interface BaseCacheInterface."""
        try:
            cache_key = game_query.lower().strip()

            entry = {
                "data": game_data,
                "cached_at": datetime.now().isoformat(),
                "query": game_query,
            }

            self.cache[cache_key] = entry
            self._save_cache()
            self.logger.info(f"💾 Cache SAVE: {game_query}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Erreur cache save: {e}")
            return False

    def clear_expired(self):
        """Nettoyer les entrées expirées."""
        now = datetime.now()
        expired_keys = []

        for key, entry in self.cache.items():
            cached_time = datetime.fromisoformat(entry["cached_at"])
            if now - cached_time >= self.cache_duration:
                expired_keys.append(key)

        for key in expired_keys:
            del self.cache[key]

        if expired_keys:
            self._save_cache()
            self.logger.info(f"🧹 Cache nettoyé: {len(expired_keys)} entrées expirées")

    def get_stats(self) -> CacheStats:
        """Stats du cache compatible interface."""
        total_keys = len(self.cache)
        return CacheStats(
            total_keys=total_keys,
            confirmed_keys=total_keys,  # Tout est confirmé en cache classique
            cache_hits=0,  # Pas de compteur simple dans cette version
            cache_misses=0,
            hit_rate=0.0,
            total_size_mb=0.0,
            avg_confidence=1.0,  # Confiance maximale en cache classique
            quantum_enabled=False,
        )

    async def search(self, query: str, **kwargs) -> dict[str, Any] | None:
        """Recherche compatible interface (délégue vers get)."""
        return self.get(query)

    def clear(self) -> bool:
        """Vide le cache compatible interface."""
        try:
            self.clear_all()
            return True
        except Exception:
            return False

    def cleanup_expired(self) -> int:
        """Nettoie les entrées expirées."""
        len(self.cache)
        now = datetime.now()

        expired_keys = []
        for key, entry in self.cache.items():
            cached_time = datetime.fromisoformat(entry["cached_at"])
            if now - cached_time >= self.cache_duration:
                expired_keys.append(key)

        for key in expired_keys:
            del self.cache[key]

        if expired_keys:
            self._save_cache()
            self.logger.info(f"🧹 {len(expired_keys)} entrées expirées supprimées")

        return len(expired_keys)

    def clear_game(self, game_query: str) -> bool:
        """Supprimer un jeu spécifique du cache."""
        cache_key = game_query.lower().replace(" ", "_")

        if cache_key in self.cache:
            del self.cache[cache_key]
            self._save_cache()
            self.logger.info(f"🗑️ Cache supprimé: {game_query}")
            return True

        self.logger.warning(f"🤷 Jeu non trouvé dans cache: {game_query}")
        return False

    def clear_all(self):
        """Vider complètement le cache."""
        cache_size = len(self.cache)
        self.cache = {}
        self._save_cache()
        self.logger.info(f"🗑️ Cache vidé complètement: {cache_size} entrées supprimées")


# Instance globale - À initialiser avec config au runtime
# game_cache = GameCache(config)
