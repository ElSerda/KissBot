"""
🗂️ Registry - État centralisé du bot

Gère les channels, badges, scopes, permissions.
Permet le routing intelligent des messages.
"""
import logging
from typing import Dict, Set, Optional

LOGGER = logging.getLogger(__name__)


class Registry:
    """État global du bot (channels, badges, scopes)"""
    
    def __init__(self):
        # Channels actifs
        self._channels: Dict[str, Dict] = {}  # channel_name -> {id, broadcaster_id, ...}
        
        # Badges bot (USER_BOT + CHANNEL_BOT activé)
        self._channel_has_badge: Dict[str, bool] = {}  # channel_id -> True si badge dispo
        
        # Scopes disponibles
        self._bot_scopes: Set[str] = set()
        
        # Cache IDs
        self._user_id_cache: Dict[str, str] = {}  # login -> user_id
        self._broadcaster_id_cache: Dict[str, str] = {}  # channel_name -> broadcaster_id
        
    # ========================================================================
    # CHANNELS
    # ========================================================================
    
    def add_channel(self, name: str, channel_id: str, **kwargs):
        """Ajoute un channel au registry"""
        self._channels[name] = {
            "id": channel_id,
            "broadcaster_id": channel_id,
            **kwargs
        }
        LOGGER.info(f"✅ Channel ajouté: {name} (ID: {channel_id})")
        
    def get_channel(self, name: str) -> Optional[Dict]:
        """Récupère les infos d'un channel"""
        return self._channels.get(name)
        
    def get_channels(self) -> Dict[str, Dict]:
        """Retourne tous les channels"""
        return self._channels.copy()
        
    # ========================================================================
    # BADGES
    # ========================================================================
    
    def set_channel_badge(self, channel_id: str, has_badge: bool):
        """
        Indique si le bot a le badge sur ce channel.
        Badge = USER_BOT activé + broadcaster a autorisé CHANNEL_BOT.
        """
        self._channel_has_badge[channel_id] = has_badge
        status = "✅ BADGE" if has_badge else "⚠️ NO BADGE"
        LOGGER.info(f"{status} pour channel {channel_id}")
        
    def has_channel_badge(self, channel_id: str) -> bool:
        """Vérifie si le bot a le badge sur ce channel"""
        return self._channel_has_badge.get(channel_id, False)
        
    # ========================================================================
    # SCOPES
    # ========================================================================
    
    def set_bot_scopes(self, scopes: Set[str]):
        """Définit les scopes du bot"""
        self._bot_scopes = scopes
        LOGGER.info(f"🔑 Bot scopes: {', '.join(scopes)}")
        
    def has_scope(self, scope: str) -> bool:
        """Vérifie si le bot a un scope"""
        return scope in self._bot_scopes
        
    def can_use_helix_send(self) -> bool:
        """Vérifie si le bot peut envoyer via Helix"""
        return self.has_scope("user:write:chat") and self.has_scope("user:bot")
        
    # ========================================================================
    # CACHE IDS
    # ========================================================================
    
    def cache_user_id(self, login: str, user_id: str):
        """Cache un user_id"""
        self._user_id_cache[login.lower()] = user_id
        
    def get_user_id(self, login: str) -> Optional[str]:
        """Récupère un user_id depuis le cache"""
        return self._user_id_cache.get(login.lower())
        
    def cache_broadcaster_id(self, channel_name: str, broadcaster_id: str):
        """Cache un broadcaster_id"""
        self._broadcaster_id_cache[channel_name.lower()] = broadcaster_id
        
    def get_broadcaster_id(self, channel_name: str) -> Optional[str]:
        """Récupère un broadcaster_id depuis le cache"""
        return self._broadcaster_id_cache.get(channel_name.lower())
        
    # ========================================================================
    # ROUTING
    # ========================================================================
    
    def should_use_helix(self, channel_id: str) -> bool:
        """
        Détermine si on doit utiliser Helix pour envoyer.
        
        Helix si:
        1. On a les scopes nécessaires (user:write:chat + user:bot)
        2. ET soit:
           - On a channel:bot (badge global)
           - OU le channel a explicitement le badge
        """
        # Vérifier les scopes de base
        can_helix = self.can_use_helix_send()
        has_channel_bot = self.has_scope("channel:bot")
        has_badge = self.has_channel_badge(channel_id) if channel_id else False
        
        LOGGER.info(
            f"🔍 should_use_helix({channel_id}): "
            f"can_helix={can_helix}, channel:bot={has_channel_bot}, badge={has_badge}"
        )
        
        if not can_helix:
            return False
            
        # Si on a channel:bot, on peut utiliser Helix partout
        if has_channel_bot:
            LOGGER.info(f"   ↳ TRUE (channel:bot scope disponible)")
            return True
            
        # Sinon, vérifier si ce channel spécifique a le badge
        result = has_badge
        LOGGER.info(f"   ↳ {result} (badge check pour ce channel)")
        return result
        
    # ========================================================================
    # STATS
    # ========================================================================
    
    def get_stats(self) -> Dict:
        """Retourne les stats du registry"""
        return {
            "channels": len(self._channels),
            "badges": sum(1 for v in self._channel_has_badge.values() if v),
            "scopes": len(self._bot_scopes),
            "cached_users": len(self._user_id_cache),
            "cached_broadcasters": len(self._broadcaster_id_cache)
        }
