"""
📡 IRC Transport - Client IRC pour Twitch

Responsabilités:
- Écoute IRC → Publie chat.inbound
- Consomme chat.outbound → Envoie via IRC si prefer='irc' ou fallback
"""
import asyncio
import logging
from typing import Optional

from twitchAPI.twitch import Twitch
from twitchAPI.chat import Chat, ChatMessage as TwitchChatMessage, ChatCommand, EventData
from twitchAPI.type import ChatEvent

from core.message_bus import MessageBus
from core.message_types import ChatMessage, OutboundMessage
from core.registry import Registry

LOGGER = logging.getLogger(__name__)


class IRCClient:
    """Client IRC Twitch (listener + sender)"""
    
    def __init__(
        self,
        twitch: Twitch,
        bus: MessageBus,
        registry: Registry,
        channels: list[str],
        bot_login: str
    ):
        """
        Args:
            twitch: Instance Twitch API
            bus: MessageBus pour pub/sub
            registry: Registry pour état
            channels: Liste des channels à rejoindre
            bot_login: Login du bot (pour ignorer ses propres messages)
        """
        self.twitch = twitch
        self.bus = bus
        self.registry = registry
        self.channels = channels
        self.bot_login = bot_login.lower()
        
        self.chat: Optional[Chat] = None
        self._running = False
        
    async def start(self):
        """Démarre le client IRC"""
        LOGGER.info("📡 Démarrage IRC Client...")
        
        # Créer le chat
        self.chat = await Chat(self.twitch)
        
        # Enregistrer les événements
        self.chat.register_event(ChatEvent.READY, self._on_ready)
        self.chat.register_event(ChatEvent.MESSAGE, self._on_message)
        
        # S'abonner au bus pour les messages sortants
        self.bus.subscribe("chat.outbound", self._on_outbound)
        
        # Démarrer le chat
        self.chat.start()
        self._running = True
        
        LOGGER.info("✅ IRC Client démarré")
        
    async def stop(self):
        """Arrête le client IRC"""
        LOGGER.info("🛑 Arrêt IRC Client...")
        self._running = False
        
        if self.chat:
            self.chat.stop()
            await self.chat.wait_for_stopped()
            
        LOGGER.info("✅ IRC Client arrêté")
        
    async def run(self):
        """Boucle principale (keep alive)"""
        await self.start()
        
        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            LOGGER.info("⚠️ IRC Client cancelled")
        finally:
            await self.stop()
            
    # ========================================================================
    # ÉVÉNEMENTS IRC (RECEIVE)
    # ========================================================================
    
    async def _on_ready(self, ready_event: EventData):
        """Appelé quand IRC est prêt"""
        LOGGER.info("🎯 IRC prêt ! Rejoindre les channels...")
        
        # Rejoindre les channels
        await ready_event.chat.join_room(self.channels)
        LOGGER.info(f"✅ IRC channels rejoints: {', '.join(self.channels)}")
        
    async def _on_message(self, msg: TwitchChatMessage):
        """Appelé pour chaque message IRC reçu"""
        LOGGER.info(f"📨 IRC MESSAGE REÇU: [{msg.room.name}] {msg.user.name}: {msg.text}")
        
        # Ignorer ses propres messages
        if msg.user.name.lower() == self.bot_login:
            LOGGER.info(f"   ↳ Ignoré (message du bot)")
            return
            
        # Convertir en ChatMessage (DTO)
        chat_msg = ChatMessage(
            channel=msg.room.name,
            channel_id=self.registry.get_broadcaster_id(msg.room.name) or "unknown",
            user_login=msg.user.name,
            user_id=msg.user.id or "unknown",
            text=msg.text,
            is_mod=msg.user.mod,
            is_broadcaster=msg.user.name.lower() == msg.room.name.lower(),
            is_vip=msg.user.vip if hasattr(msg.user, 'vip') else False,
            transport="irc",
            badges=msg.user.badges if hasattr(msg.user, 'badges') else {},
            meta={
                "room_id": msg.room.room_id if hasattr(msg.room, 'room_id') else None,
                "sent_timestamp": msg.sent_timestamp if hasattr(msg, 'sent_timestamp') else None
            }
        )
        
        # Publier sur le bus
        LOGGER.info(f"   ↳ Publié sur chat.inbound: {chat_msg.text}")
        await self.bus.publish("chat.inbound", chat_msg)
        
    # ========================================================================
    # ENVOI IRC (SEND)
    # ========================================================================
    
    async def _on_outbound(self, msg: OutboundMessage):
        """
        Consomme les messages sortants du bus.
        Envoie si prefer='irc' OU si fallback nécessaire.
        """
        LOGGER.info(f"📡 IRCClient._on_outbound: channel={msg.channel}, prefer={msg.prefer}, text={msg.text[:50]}")
        
        # Si prefer='helix', laisser Helix gérer (sauf si Helix fail)
        if msg.prefer == "helix":
            # Helix a priorité, on skip
            LOGGER.info(f"   ↳ Skip (prefer='helix')")
            return
            
        # Si prefer='auto', vérifier si Helix dispo
        if msg.prefer == "auto":
            should_use_helix = self.registry.should_use_helix(msg.channel_id)
            LOGGER.info(f"   ↳ Auto mode: should_use_helix={should_use_helix}")
            if should_use_helix:
                # Helix dispo, il va gérer
                LOGGER.info(f"   ↳ Skip (Helix va gérer)")
                return
                
        # OK, on envoie via IRC
        LOGGER.info(f"   ↳ Envoi via IRC")
        await self._send_irc(msg)
        
    async def _send_irc(self, msg: OutboundMessage):
        """Envoie un message via IRC"""
        if not self.chat:
            LOGGER.error("❌ Chat IRC non initialisé")
            return
            
        try:
            await self.chat.send_message(msg.channel, msg.text)
            LOGGER.info(f"📤 IRC sent [{msg.channel}]: {msg.text[:50]}...")
        except Exception as e:
            LOGGER.error(f"❌ Erreur envoi IRC [{msg.channel}]: {e}")
            
    # ========================================================================
    # UTILS
    # ========================================================================
    
    async def send_direct(self, channel: str, text: str):
        """Envoie direct (bypass le bus, pour debug)"""
        if self.chat:
            await self.chat.send_message(channel, text)
