"""
Cache Manager - Cache générique avec TTL
"""

import logging
import time
from typing import Any


class CacheManager:
    """Gestionnaire de cache avec TTL."""

    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(__name__)

        cache_config = config.get("cache", {})
        self.ttl = cache_config.get("ttl_seconds", 3600)
        self.max_size = cache_config.get("max_size", 1000)

        self.data: dict[str, tuple[Any, float]] = {}  # {key: (value, timestamp)}

    def get(self, key: str) -> Any | None:
        """Récupère une valeur du cache."""
        if key not in self.data:
            return None

        value, timestamp = self.data[key]

        # Vérifier TTL
        if time.time() - timestamp > self.ttl:
            del self.data[key]
            return None

        return value

    def set(self, key: str, value: Any):
        """Stocke une valeur dans le cache."""
        # Nettoyage si trop plein
        if len(self.data) >= self.max_size:
            self._cleanup()

        self.data[key] = (value, time.time())

    def _cleanup(self):
        """Nettoie les entrées expirées."""
        current_time = time.time()
        expired_keys = [
            key for key, (_, timestamp) in self.data.items() if current_time - timestamp > self.ttl
        ]

        for key in expired_keys:
            del self.data[key]

        # Si encore trop plein, supprimer les plus anciens
        if len(self.data) >= self.max_size:
            sorted_items = sorted(self.data.items(), key=lambda x: x[1][1])  # Trier par timestamp

            # Garder seulement les 80% plus récents
            keep_count = int(self.max_size * 0.8)
            self.data = dict(sorted_items[-keep_count:])
