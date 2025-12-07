#!/usr/bin/env python3
"""
Test d'envoi via MessageBus pour vérifier _log_send_result() avec AutoMod.

Démonstration:
- Utilise le MessageBus au lieu d'appeler direct l'API
- Teste que _log_send_result() capture bien drop_reason
"""

import asyncio
import logging
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Setup path
sys.path.insert(0, str(Path(__file__).parent))

from core.message_bus import MessageBus
from core.message_types import OutboundMessage


async def main():
    """Crée un messagebus et envoie un message via chat.outbound."""
    
    bus = MessageBus()
    
    # Message de test
    msg = OutboundMessage(
        channel="el_serda",
        text="🧪 TEST via MessageBus [#" + str(int(__import__('time').time())) + "]",
        reply_to=None
    )
    
    print(f"📤 Publishing message via chat.outbound: {msg.text}")
    
    # Publier le message
    await bus.publish("chat.outbound", msg)
    
    print("✅ Message publié, attendre que EventSub l'envoie...")
    await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
