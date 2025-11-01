#!/usr/bin/env python3
"""
Chat Logger - Phase 2.2
Simple subscriber pour afficher les messages IRC reçus
"""

import logging

from core.message_bus import MessageBus
from core.message_types import ChatMessage

LOGGER = logging.getLogger(__name__)


class ChatLogger:
    """
    Subscriber simple qui log tous les messages chat.inbound
    Utilisé pour valider que l'IRC fonctionne
    """
    
    def __init__(self, bus: MessageBus):
        """
        Args:
            bus: MessageBus pour subscribe
        """
        self.bus = bus
        self.message_count = 0
        
        # Subscribe à chat.inbound
        self.bus.subscribe("chat.inbound", self._handle_chat_message)
        LOGGER.info("ChatLogger initialisé - écoute chat.inbound")
    
    async def _handle_chat_message(self, msg: ChatMessage) -> None:
        """
        Handler pour les messages IRC entrants
        
        Args:
            msg: Message chat reçu
        """
        self.message_count += 1
        
        # Badges
        badges_str = ""
        if msg.is_broadcaster:
            badges_str += "👑"
        if msg.is_mod:
            badges_str += "🛡️"
        if msg.badges.get("subscriber"):
            badges_str += "⭐"
        if msg.is_vip:
            badges_str += "💎"
        
        # Affichage structuré multi-channel
        separator = "─" * 60
        print(f"\n{separator}")
        print(f"📺 Channel: #{msg.channel}")
        print(separator)
        print(f"👤 {badges_str}{msg.user_login}: {msg.text}")
        print(separator)
    
    def get_message_count(self) -> int:
        """Retourne le nombre de messages reçus"""
        return self.message_count
