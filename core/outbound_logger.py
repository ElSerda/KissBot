#!/usr/bin/env python3
"""
Outbound Logger - Phase 2.3
Affiche les messages que le bot VOUDRAIT envoyer (mais ne les envoie pas encore)
Phase 2.4 : Les messages seront réellement envoyés via IRC
"""

import logging

from core.message_bus import MessageBus
from core.message_types import OutboundMessage

LOGGER = logging.getLogger(__name__)


class OutboundLogger:
    """
    Logger pour les messages sortants (Phase 2.3)
    Affiche ce que le bot voudrait dire, sans l'envoyer
    """
    
    def __init__(self, bus: MessageBus):
        """
        Args:
            bus: MessageBus pour subscribe
        """
        self.bus = bus
        self.message_count = 0
        
        # Subscribe à chat.outbound
        self.bus.subscribe("chat.outbound", self._handle_outbound_message)
        LOGGER.info("OutboundLogger initialisé - écoute chat.outbound")
    
    async def _handle_outbound_message(self, msg: OutboundMessage) -> None:
        """
        Handler pour les messages sortants
        
        Args:
            msg: Message à envoyer
        """
        self.message_count += 1
        
        # Affichage coloré pour différencier des messages entrants
        print("\n" + "═" * 60)
        print(f"📤 OUTBOUND → #{msg.channel}")
        print("═" * 60)
        print(f"🤖 serda_bot: {msg.text}")
        print(f"   (prefer: {msg.prefer}, NOT SENT YET - Phase 2.4)")
        print("═" * 60)
        
        LOGGER.debug(
            f"Outbound message #{self.message_count}: "
            f"channel={msg.channel} "
            f"prefer={msg.prefer} "
            f"text={msg.text[:50]}..."
        )
    
    def get_message_count(self) -> int:
        """Retourne le nombre de messages sortants"""
        return self.message_count
