"""
🏆 Helix Transport - Client API Helix pour envoi avec badge

Responsabilités:
- Consomme chat.outbound → Envoie via send_chat_message() si badge dispo
- Cache les broadcaster_id pour éviter les appels API répétés
- Gère les erreurs (rate limits, permissions, etc.)
"""
import asyncio
import logging
from typing import Optional

from twitchAPI.twitch import Twitch
from twitchAPI.helper import first

from core.message_bus import MessageBus
from core.message_types import OutboundMessage, SystemEvent
from core.registry import Registry
from core.rate_limiter import RateLimiter

LOGGER = logging.getLogger(__name__)


class HelixClient:
    """Client Helix pour envoi avec badge officiel"""
    
    def __init__(
        self,
        twitch: Twitch,
        bus: MessageBus,
        registry: Registry,
        rate_limiter: RateLimiter,
        bot_login: str,
        bot_id: Optional[str] = None
    ):
        """
        Args:
            twitch: Instance Twitch API
            bus: MessageBus pour pub/sub
            registry: Registry pour état
            rate_limiter: RateLimiter pour éviter les bans
            bot_login: Login du bot
            bot_id: ID du bot (optionnel, sera récupéré si non fourni)
        """
        self.twitch = twitch
        self.bus = bus
        self.registry = registry
        self.rate_limiter = rate_limiter
        self.bot_login = bot_login
        
        self._bot_id: Optional[str] = bot_id  # Utiliser l'ID fourni si disponible
        self._running = False
        
    async def start(self):
        """Démarre le client Helix"""
        LOGGER.info("🏆 Démarrage Helix Client...")
        
        # Récupérer le bot user_id si pas déjà fourni
        if not self._bot_id:
            try:
                bot_user = await first(self.twitch.get_users(logins=[self.bot_login]))
                if bot_user:
                    self._bot_id = bot_user.id
                    LOGGER.info(f"✅ Bot ID récupéré: {self._bot_id}")
                else:
                    LOGGER.error("❌ Bot user non trouvé!")
                    return
            except Exception as e:
                LOGGER.error(f"❌ Erreur récupération bot ID: {e}")
                return
        else:
            LOGGER.info(f"✅ Bot ID fourni: {self._bot_id}")
            
        # S'abonner au bus pour les messages sortants
        self.bus.subscribe("chat.outbound", self._on_outbound)
        
        self._running = True
        LOGGER.info("✅ Helix Client démarré")
        
    async def stop(self):
        """Arrête le client Helix"""
        LOGGER.info("🛑 Arrêt Helix Client...")
        self._running = False
        LOGGER.info("✅ Helix Client arrêté")
        
    async def run(self):
        """Boucle principale (keep alive)"""
        await self.start()
        
        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            LOGGER.info("⚠️ Helix Client cancelled")
        finally:
            await self.stop()
            
    # ========================================================================
    # ENVOI HELIX
    # ========================================================================
    
    async def _on_outbound(self, msg: OutboundMessage):
        """
        Consomme les messages sortants du bus.
        Envoie si prefer='helix' ET badge dispo.
        """
        LOGGER.info(f"🏆 HelixClient._on_outbound: channel={msg.channel}, prefer={msg.prefer}, text={msg.text[:50]}")
        
        # Si prefer='irc', laisser IRC gérer
        if msg.prefer == "irc":
            LOGGER.info(f"   ↳ Skip (prefer='irc')")
            return
            
        # Vérifier si on peut utiliser Helix
        should_use_helix = False
        
        if msg.prefer == "helix":
            # Forcé Helix
            should_use_helix = True
            LOGGER.info(f"   ↳ Helix forcé")
        elif msg.prefer == "auto":
            # Auto: utiliser Helix si badge dispo
            should_use_helix = self.registry.should_use_helix(msg.channel_id)
            LOGGER.info(f"   ↳ Auto mode: should_use_helix={should_use_helix}")
            
        if not should_use_helix:
            LOGGER.info(f"   ↳ Skip (should_use_helix=False)")
            return
            
        # Vérifier rate limit
        if not self.rate_limiter.can_send(msg.channel_id, cost=1, is_mod=False, is_verified=False):
            LOGGER.warning(f"⏱️ Rate limit atteint pour {msg.channel}: message droppé")
            return
            
        # Envoyer via Helix
        await self._send_helix(msg)
        
    async def _send_helix(self, msg: OutboundMessage):
        """Envoie un message via API Helix"""
        if not self._bot_id:
            LOGGER.error("❌ Bot ID non disponible")
            return
            
        try:
            # Récupérer broadcaster_id (avec cache)
            broadcaster_id = await self._get_broadcaster_id(msg.channel)
            if not broadcaster_id:
                LOGGER.error(f"❌ Broadcaster ID non trouvé pour {msg.channel}")
                return
                
            # Envoyer via API Helix
            result = await self.twitch.send_chat_message(
                broadcaster_id=broadcaster_id,
                sender_id=self._bot_id,
                message=msg.text,
                reply_parent_message_id=msg.reply_to
            )
            
            LOGGER.info(f"🏆 Helix sent [{msg.channel}]: {msg.text[:50]}...")
            
            # Publier événement succès
            await self.bus.publish("system.event", SystemEvent(
                kind="helix.send.success",
                payload={
                    "channel": msg.channel,
                    "message_id": result.message_id if hasattr(result, 'message_id') else None,
                    "text_length": len(msg.text)
                }
            ))
            
        except Exception as e:
            LOGGER.error(f"❌ Erreur envoi Helix [{msg.channel}]: {e}")
            
            # Publier événement erreur
            await self.bus.publish("system.event", SystemEvent(
                kind="helix.send.error",
                payload={
                    "channel": msg.channel,
                    "error": str(e),
                    "prefer": msg.prefer
                }
            ))
            
            # Si prefer='auto', IRC peut prendre le relais (déjà publié sur bus)
            
    # ========================================================================
    # UTILS
    # ========================================================================
    
    async def _get_broadcaster_id(self, channel_name: str) -> Optional[str]:
        """
        Récupère le broadcaster_id avec cache.
        
        Args:
            channel_name: Nom du channel (sans #)
            
        Returns:
            broadcaster_id ou None
        """
        # Check cache
        cached_id = self.registry.get_broadcaster_id(channel_name)
        if cached_id:
            return cached_id
            
        # Fetch from API
        try:
            user = await first(self.twitch.get_users(logins=[channel_name]))
            if user:
                self.registry.cache_broadcaster_id(channel_name, user.id)
                return user.id
        except Exception as e:
            LOGGER.error(f"❌ Erreur récupération broadcaster ID pour {channel_name}: {e}")
            
        return None
