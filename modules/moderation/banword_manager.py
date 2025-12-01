#!/usr/bin/env python3
"""
BanWord Manager - Gestion des mots bannis par channel (SQLite)

Stocke les banwords par channel dans la BDD kissbot.db.
Quand un message contient un banword → BAN instantané.

Table: banwords
- id: INTEGER PRIMARY KEY
- channel: TEXT (nom du channel sans #)
- word: TEXT (mot banni, lowercase)
- added_by: TEXT (qui a ajouté)
- added_at: TIMESTAMP
- UNIQUE(channel, word)

Usage:
    manager = get_banword_manager()
    manager.add_banword("el_serda", "streamboo", "moderator")
    
    # Dans message handler:
    if manager.check_message("el_serda", message):
        # BAN l'utilisateur
"""

import sqlite3
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict
from contextlib import contextmanager

LOGGER = logging.getLogger(__name__)

# Singleton instance
_instance: Optional["BanWordManager"] = None

# Default DB path
DEFAULT_DB_PATH = "kissbot.db"


def get_banword_manager(db_path: str = DEFAULT_DB_PATH) -> "BanWordManager":
    """Get singleton instance of BanWordManager."""
    global _instance
    if _instance is None:
        _instance = BanWordManager(db_path)
    return _instance


class BanWordManager:
    """
    Gestionnaire de mots bannis par channel (SQLite).
    
    Chaque channel a sa propre liste de banwords.
    Les mots sont stockés en lowercase pour matching case-insensitive.
    """
    
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self._cache: Dict[str, set] = {}  # Cache en mémoire par channel
        self._init_table()
        self._load_cache()
    
    @contextmanager
    def _get_connection(self):
        """Context manager pour connexion SQLite."""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_table(self) -> None:
        """Crée la table banwords si elle n'existe pas."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS banwords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT NOT NULL,
                    word TEXT NOT NULL,
                    added_by TEXT DEFAULT 'system',
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(channel, word)
                )
            """)
            # Index pour recherche rapide par channel
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_banwords_channel 
                ON banwords(channel)
            """)
        LOGGER.info("📝 BanWord table initialized")
    
    def _load_cache(self) -> None:
        """Charge tous les banwords en cache mémoire."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT channel, word FROM banwords"
            )
            
            self._cache = {}
            for row in cursor:
                channel = row['channel']
                if channel not in self._cache:
                    self._cache[channel] = set()
                self._cache[channel].add(row['word'])
            
            total = sum(len(words) for words in self._cache.values())
            LOGGER.info(f"📝 Loaded {total} banwords for {len(self._cache)} channels")
    
    def add_banword(self, channel: str, word: str, added_by: str = "mod") -> bool:
        """
        Ajoute un mot banni pour un channel.
        
        Args:
            channel: Nom du channel (sans #)
            word: Mot à bannir (sera lowercase)
            added_by: Username de celui qui ajoute
        
        Returns:
            True si ajouté, False si déjà présent
        """
        channel = channel.lower().lstrip('#')
        word = word.lower().strip()
        
        if not word or len(word) < 2:
            return False
        
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO banwords (channel, word, added_by) 
                    VALUES (?, ?, ?)
                    """,
                    (channel, word, added_by)
                )
            
            # Update cache
            if channel not in self._cache:
                self._cache[channel] = set()
            self._cache[channel].add(word)
            
            LOGGER.info(f"🚫 Banword added: '{word}' for #{channel} by {added_by}")
            return True
            
        except sqlite3.IntegrityError:
            # Already exists (UNIQUE constraint)
            return False
    
    def remove_banword(self, channel: str, word: str) -> bool:
        """
        Retire un mot banni pour un channel.
        
        Args:
            channel: Nom du channel (sans #)
            word: Mot à retirer
        
        Returns:
            True si retiré, False si non trouvé
        """
        channel = channel.lower().lstrip('#')
        word = word.lower().strip()
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM banwords WHERE channel = ? AND word = ?",
                (channel, word)
            )
            
            if cursor.rowcount > 0:
                # Update cache
                if channel in self._cache:
                    self._cache[channel].discard(word)
                
                LOGGER.info(f"✅ Banword removed: '{word}' for #{channel}")
                return True
        
        return False
    
    def list_banwords(self, channel: str) -> List[str]:
        """
        Liste les mots bannis pour un channel.
        
        Args:
            channel: Nom du channel (sans #)
        
        Returns:
            Liste des mots bannis (triée)
        """
        channel = channel.lower().lstrip('#')
        
        # Use cache for fast lookup
        if channel in self._cache:
            return sorted(list(self._cache[channel]))
        
        return []
    
    def check_message(self, channel: str, message: str) -> Optional[str]:
        """
        Vérifie si un message contient un banword.
        
        Args:
            channel: Nom du channel (sans #)
            message: Message à vérifier
        
        Returns:
            Le banword trouvé, ou None si aucun
        """
        channel = channel.lower().lstrip('#')
        
        if channel not in self._cache or not self._cache[channel]:
            return None
        
        message_lower = message.lower()
        
        for word in self._cache[channel]:
            # Word boundary match pour éviter faux positifs
            # Ex: "stream" ne matche pas dans "downstream"
            pattern = r'\b' + re.escape(word) + r'\b'
            if re.search(pattern, message_lower):
                return word
        
        return None
    
    def check_message_contains(self, channel: str, message: str) -> Optional[str]:
        """
        Vérifie si un message contient un banword (substring match).
        Plus agressif - matche même au milieu d'un mot.
        
        Args:
            channel: Nom du channel (sans #)
            message: Message à vérifier
        
        Returns:
            Le banword trouvé, ou None si aucun
        """
        channel = channel.lower().lstrip('#')
        
        if channel not in self._cache or not self._cache[channel]:
            return None
        
        message_lower = message.lower()
        
        for word in self._cache[channel]:
            if word in message_lower:
                return word
        
        return None
    
    def get_ban_reason(self, channel: str, word: str) -> str:
        """
        Génère la raison du ban pour un banword.
        
        Args:
            channel: Nom du channel
            word: Le banword détecté
        
        Returns:
            Message de raison pour le /ban
        """
        return f"Auto-ban: banword detected"
    
    def get_banword_info(self, channel: str, word: str) -> Optional[Dict]:
        """
        Récupère les infos d'un banword (qui l'a ajouté, quand).
        
        Args:
            channel: Nom du channel
            word: Le mot à chercher
        
        Returns:
            Dict avec added_by, added_at ou None
        """
        channel = channel.lower().lstrip('#')
        word = word.lower().strip()
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT added_by, added_at 
                FROM banwords 
                WHERE channel = ? AND word = ?
                """,
                (channel, word)
            )
            row = cursor.fetchone()
            
            if row:
                return {
                    "word": word,
                    "added_by": row['added_by'],
                    "added_at": row['added_at']
                }
        
        return None
    
    def get_stats(self) -> Dict:
        """Retourne des stats sur les banwords."""
        return {
            "channels": len(self._cache),
            "total_words": sum(len(words) for words in self._cache.values()),
            "per_channel": {
                channel: len(words) 
                for channel, words in self._cache.items()
            }
        }
    
    def clear_channel(self, channel: str) -> int:
        """
        Supprime tous les banwords d'un channel.
        
        Args:
            channel: Nom du channel
        
        Returns:
            Nombre de mots supprimés
        """
        channel = channel.lower().lstrip('#')
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM banwords WHERE channel = ?",
                (channel,)
            )
            count = cursor.rowcount
        
        # Clear cache
        if channel in self._cache:
            del self._cache[channel]
        
        LOGGER.info(f"🗑️ Cleared {count} banwords for #{channel}")
        return count
