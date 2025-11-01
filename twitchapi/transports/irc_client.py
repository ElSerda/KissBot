#!/usr/bin/env python3
"""
IRC Client - Phase 2.6 (avec timeout handling)
Client IRC Twitch complet:
- Écoute chat IRC → Publie sur chat.inbound
- Écoute chat.outbound → Envoie via IRC
- Gestion timeout pour éviter blocages LLM
"""

import asyncio
import logging
from typing import Optional

from twitchAPI.twitch import Twitch
from twitchAPI.chat import Chat, ChatMessage as TwitchChatMessage, EventData
from twitchAPI.type import ChatEvent, AuthScope

from core.message_bus import MessageBus
from core.message_types import ChatMessage, OutboundMessage

LOGGER = logging.getLogger(__name__)


class IRCClient:
    """
    Client IRC Twitch (Phase 2.4 - Bidirectionnel)
    - Rejoint les channels
    - Écoute les messages → chat.inbound
    - Envoie les messages ← chat.outbound
    """
    
    def __init__(
        self,
        twitch: Twitch,
        bus: MessageBus,
        bot_user_id: str,
        bot_login: str,
        channels: list[str],
        irc_send_timeout: float = 5.0
    ):
        """
        Args:
            twitch: Instance Twitch avec user token
            bus: MessageBus pour publier
            bot_user_id: ID du bot (pour ignorer ses propres messages)
            bot_login: Login du bot
            channels: Liste des channels à rejoindre (ex: ["el_serda"])
            irc_send_timeout: Timeout envoi IRC en secondes (Phase 2.6)
        """
        self.twitch = twitch
        self.bus = bus
        self.bot_user_id = bot_user_id
        self.bot_login = bot_login.lower()
        self.channels = channels
        self.irc_send_timeout = irc_send_timeout
        
        self.chat: Optional[Chat] = None
        self._running = False
        self._joined_channels = set()  # Track channels we've already joined
        
        # Phase 2.4: Subscribe aux messages sortants
        self.bus.subscribe("chat.outbound", self._handle_outbound_message)
        
        LOGGER.info(f"IRCClient init pour {bot_login} sur {len(channels)} channels (timeout={irc_send_timeout}s)")
    
    async def start(self) -> None:
        """Démarre le client IRC"""
        if self._running:
            LOGGER.warning("IRC Client déjà en cours")
            return
        
        LOGGER.info("🚀 Démarrage IRC Client...")
        
        try:
            # Créer instance Chat avec le user token
            self.chat = await Chat(self.twitch)
            
            # Register event handlers
            self.chat.register_event(ChatEvent.READY, self._on_ready)
            self.chat.register_event(ChatEvent.MESSAGE, self._on_message)
            self.chat.register_event(ChatEvent.JOIN, self._on_join)
            self.chat.register_event(ChatEvent.LEFT, self._on_left)
            
            # Démarrer le chat
            self.chat.start()
            self._running = True
            
            LOGGER.info("✅ IRC Client démarré")
            
        except Exception as e:
            LOGGER.error(f"❌ Erreur démarrage IRC: {e}", exc_info=True)
            raise
    
    async def stop(self) -> None:
        """Arrête le client IRC proprement"""
        if not self._running:
            return
        
        LOGGER.info("🛑 Arrêt IRC Client...")
        
        if self.chat:
            self.chat.stop()
            self.chat = None
        
        self._running = False
        LOGGER.info("✅ IRC Client arrêté")
    
    async def _on_ready(self, ready_event: EventData) -> None:
        """
        Callback quand IRC est ready
        → Rejoint tous les channels
        """
        LOGGER.debug("📡 IRC Ready, connexion aux channels...")
        
        for channel in self.channels:
            try:
                await self.chat.join_room(channel)
                LOGGER.debug(f"✅ Rejoint #{channel}")
            except Exception as e:
                LOGGER.error(f"❌ Erreur join #{channel}: {e}")
    
    async def _on_join(self, join_event: EventData) -> None:
        """Callback quand on rejoint un channel"""
        channel = join_event.room.name
        # Log seulement la première fois qu'on rejoint ce channel
        if channel not in self._joined_channels:
            self._joined_channels.add(channel)
            LOGGER.debug(f"✅ Connecté à #{channel}")
    
    async def _on_left(self, left_event: EventData) -> None:
        """Callback quand on quitte un channel"""
        channel = left_event.room.name
        LOGGER.warning(f"📤 Left #{channel}")
    
    async def _on_message(self, msg: TwitchChatMessage) -> None:
        """
        Callback quand un message IRC arrive
        → Publie sur MessageBus (topic: chat.inbound)
        
        Args:
            msg: Message Twitch IRC
        """
        # Ignorer nos propres messages
        if msg.user.name.lower() == self.bot_login:
            return
        
        # Créer ChatMessage pour MessageBus
        chat_msg = ChatMessage(
            channel=msg.room.name,
            channel_id=msg.room.room_id,
            user_login=msg.user.name,
            user_id=msg.user.id,
            text=msg.text,
            is_mod=msg.user.mod,
            is_broadcaster=(msg.room.room_id == msg.user.id),
            is_vip=msg.user.vip,
            transport="irc",
            badges=msg.user.badges if msg.user.badges else {}
        )
        
        # Publier sur MessageBus
        try:
            await self.bus.publish("chat.inbound", chat_msg)
        except Exception as e:
            LOGGER.error(f"❌ Erreur publish chat.inbound: {e}")
    
    async def _handle_outbound_message(self, msg: OutboundMessage) -> None:
        """
        Phase 2.6: Envoie un message via IRC avec timeout
        
        Args:
            msg: Message à envoyer
        """
        if not self.chat or not self._running:
            LOGGER.warning(f"⚠️ IRC non prêt, message ignoré: {msg.text[:50]}")
            return
        
        try:
            # Log avant envoi
            LOGGER.info(f"📤 Tentative envoi IRC à #{msg.channel}: {msg.text}")
            
            # Phase 2.6: Envoyer avec timeout pour éviter blocages
            await asyncio.wait_for(
                self.chat.send_message(msg.channel, msg.text),
                timeout=self.irc_send_timeout
            )
            
            # Log succès
            LOGGER.info(f"✅ Sent to #{msg.channel}: {msg.text[:50]}...")
            
        except asyncio.TimeoutError:
            LOGGER.error(f"⏱️ Timeout envoi IRC à #{msg.channel} après {self.irc_send_timeout}s: {msg.text[:50]}")
        except Exception as e:
            LOGGER.error(f"❌ Erreur envoi IRC à #{msg.channel}: {e}", exc_info=True)
    
    def is_running(self) -> bool:
        """Retourne True si le client tourne"""
        return self._running
    
    def get_channels(self) -> list[str]:
        """Retourne la liste des channels"""
        return self.channels.copy()
