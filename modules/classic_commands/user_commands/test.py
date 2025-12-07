#!/usr/bin/env python3
"""
Commande !test - Envoie un message de test pour vérifier _log_send_result()

Cela teste que:
1. Les commandes peuvent envoyer via EventSubChatClient 
2. _log_send_result() capture bien les drop_reason d'AutoMod
"""

import logging
from typing import TYPE_CHECKING
import time
import random

if TYPE_CHECKING:
    from core.message_handler import MessageHandler
    from core.message_types import ChatMessage

LOGGER = logging.getLogger(__name__)


async def handle_test(handler: "MessageHandler", msg: "ChatMessage", query: str = "") -> None:
    """
    !test - Envoie un message de test via EventSub
    
    Args:
        handler: Instance MessageHandler
        msg: Message chat entrant
        query: Inutilisé
    """
    from core.message_types import OutboundMessage
    
    # Générer un message unique pour éviter les erreurs "message identique"
    msg_id = random.randint(1000, 9999)
    timestamp = int(time.time())
    
    # Envoyer via le MessageBus qui sera routé par EventSubChatClient
    response_text = f"🧪 KissBot test message [#{msg_id}@{timestamp}]"
    
    LOGGER.info(f"📤 Test command: sending via chat.outbound: {response_text}")
    
    await handler.bus.publish("chat.outbound", OutboundMessage(
        channel=msg.channel,
        channel_id=msg.channel_id,
        text=response_text,
        prefer="eventsub"  # Force EventSub (pas IRC)
    ))
    
    LOGGER.info("✅ Test message published to chat.outbound")
