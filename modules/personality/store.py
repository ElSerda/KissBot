"""
🎭 PersonalityStore - Gestion des personnalités par channel

CRUD pour la table channel_personality.
Cache en mémoire pour éviter les requêtes DB répétées.
"""

import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from .presets import DEFAULT_PRESET, get_preset, PERSONALITY_PRESETS

LOGGER = logging.getLogger(__name__)


@dataclass
class ChannelPersonality:
    """Personnalité d'un channel"""
    channel_id: str
    channel_login: str
    preset: str
    nsfw_allowed: bool
    custom_rules: Optional[str] = None
    
    @property
    def preset_info(self) -> dict:
        """Retourne les infos du preset"""
        return get_preset(self.preset)
    
    @property
    def emoji(self) -> str:
        """Emoji du preset"""
        return self.preset_info["emoji"]
    
    @property
    def display_name(self) -> str:
        """Nom affiché du preset"""
        return self.preset_info["name"]


class PersonalityStore:
    """
    Store pour les personnalités de channels.
    
    Utilise SQLite avec cache en mémoire.
    Thread-safe via WAL mode de SQLite.
    """
    
    def __init__(self, db_path: str = "kissbot.db"):
        self.db_path = Path(db_path)
        self._cache: Dict[str, ChannelPersonality] = {}
        self._cache_ttl = 300  # 5 minutes
        self._cache_timestamps: Dict[str, float] = {}
        
        # Initialiser la table si elle n'existe pas
        self._ensure_table()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Crée une connexion SQLite"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _ensure_table(self):
        """Crée la table si elle n'existe pas"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS channel_personality (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT NOT NULL UNIQUE,
                    channel_login TEXT NOT NULL,
                    preset TEXT NOT NULL DEFAULT 'normal',
                    custom_rules TEXT,
                    nsfw_allowed BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_personality_channel 
                ON channel_personality(channel_id)
            """)
            conn.commit()
            conn.close()
            LOGGER.info("✅ PersonalityStore: Table initialisée")
        except Exception as e:
            LOGGER.error(f"❌ PersonalityStore: Erreur init table: {e}")
    
    def _is_cache_valid(self, channel_id: str) -> bool:
        """Vérifie si le cache est encore valide"""
        if channel_id not in self._cache:
            return False
        timestamp = self._cache_timestamps.get(channel_id, 0)
        return (time.time() - timestamp) < self._cache_ttl
    
    def _update_cache(self, personality: ChannelPersonality):
        """Met à jour le cache"""
        self._cache[personality.channel_id] = personality
        self._cache_timestamps[personality.channel_id] = time.time()
    
    def _invalidate_cache(self, channel_id: str):
        """Invalide le cache pour un channel"""
        self._cache.pop(channel_id, None)
        self._cache_timestamps.pop(channel_id, None)
    
    def get(self, channel_id: str, channel_login: str = "") -> ChannelPersonality:
        """
        Récupère la personnalité d'un channel.
        
        Retourne le preset par défaut si le channel n'est pas configuré.
        """
        # Check cache
        if self._is_cache_valid(channel_id):
            return self._cache[channel_id]
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM channel_personality WHERE channel_id = ?",
                (channel_id,)
            )
            row = cursor.fetchone()
            conn.close()
            
            if row:
                personality = ChannelPersonality(
                    channel_id=row["channel_id"],
                    channel_login=row["channel_login"],
                    preset=row["preset"],
                    nsfw_allowed=bool(row["nsfw_allowed"]),
                    custom_rules=row["custom_rules"]
                )
            else:
                # Retourne le preset par défaut (pas en DB)
                personality = ChannelPersonality(
                    channel_id=channel_id,
                    channel_login=channel_login or "unknown",
                    preset=DEFAULT_PRESET,
                    nsfw_allowed=False
                )
            
            self._update_cache(personality)
            return personality
            
        except Exception as e:
            LOGGER.error(f"❌ PersonalityStore.get error: {e}")
            # Fallback sur défaut
            return ChannelPersonality(
                channel_id=channel_id,
                channel_login=channel_login or "unknown",
                preset=DEFAULT_PRESET,
                nsfw_allowed=False
            )
    
    def set_preset(self, channel_id: str, channel_login: str, preset: str) -> bool:
        """
        Change le preset d'un channel.
        
        Returns:
            True si succès, False sinon
        """
        # Valider le preset
        if preset not in PERSONALITY_PRESETS:
            LOGGER.warning(f"⚠️ Preset inconnu: {preset}")
            return False
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Upsert
            cursor.execute("""
                INSERT INTO channel_personality (channel_id, channel_login, preset, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(channel_id) DO UPDATE SET
                    preset = excluded.preset,
                    channel_login = excluded.channel_login,
                    updated_at = CURRENT_TIMESTAMP
            """, (channel_id, channel_login, preset))
            
            conn.commit()
            conn.close()
            
            # Invalider le cache
            self._invalidate_cache(channel_id)
            
            LOGGER.info(f"✅ Preset changé pour #{channel_login}: {preset}")
            return True
            
        except Exception as e:
            LOGGER.error(f"❌ PersonalityStore.set_preset error: {e}")
            return False
    
    def set_nsfw(self, channel_id: str, channel_login: str, allowed: bool) -> bool:
        """
        Active/désactive le mode NSFW pour un channel.
        
        Returns:
            True si succès, False sinon
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Upsert
            cursor.execute("""
                INSERT INTO channel_personality (channel_id, channel_login, nsfw_allowed, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(channel_id) DO UPDATE SET
                    nsfw_allowed = excluded.nsfw_allowed,
                    channel_login = excluded.channel_login,
                    updated_at = CURRENT_TIMESTAMP
            """, (channel_id, channel_login, int(allowed)))
            
            conn.commit()
            conn.close()
            
            # Invalider le cache
            self._invalidate_cache(channel_id)
            
            status = "activé" if allowed else "désactivé"
            LOGGER.info(f"✅ NSFW {status} pour #{channel_login}")
            return True
            
        except Exception as e:
            LOGGER.error(f"❌ PersonalityStore.set_nsfw error: {e}")
            return False
    
    def get_stats(self) -> Dict[str, int]:
        """Retourne les stats d'utilisation des presets"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT preset, COUNT(*) as count 
                FROM channel_personality 
                GROUP BY preset
            """)
            rows = cursor.fetchall()
            conn.close()
            
            return {row["preset"]: row["count"] for row in rows}
            
        except Exception as e:
            LOGGER.error(f"❌ PersonalityStore.get_stats error: {e}")
            return {}


# Singleton global
_store_instance: Optional[PersonalityStore] = None


def get_personality_store(db_path: str = "kissbot.db") -> PersonalityStore:
    """Retourne l'instance singleton du store"""
    global _store_instance
    if _store_instance is None:
        _store_instance = PersonalityStore(db_path)
    return _store_instance
