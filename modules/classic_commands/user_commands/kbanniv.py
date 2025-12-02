"""
🎂 Commande !kbanniv - Souhaiter un joyeux anniversaire

Commande simple pour célébrer les anniversaires dans le chat !
Pattern: handler(MessageHandler, ChatMessage, args: str) -> None
"""

import random
import logging
from twitchAPI.chat import ChatMessage

LOGGER = logging.getLogger("kissbot.commands.kbanniv")


async def handle_kbanniv(handler, msg: ChatMessage, args: str = "") -> None:
    """
    !kbanniv <name> - Souhaiter un joyeux anniversaire
    
    Args:
        handler: Instance de MessageHandler
        msg: Message Twitch
        args: Nom de la personne (ex: "Serda" ou "@Serda")
    """
    from core.message_types import OutboundMessage
    
    if not args or len(args.strip()) == 0:
        response_text = f"@{msg.user_login} 🎂 Usage: !kbanniv <nom>"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        return
    
    # Clean le nom (enlever @ si présent)
    name = args.strip().lstrip('@')
    
    # Messages d'anniversaire variés
    messages = [
        f"🎂🎉 Joyeux anniversaire @{name} ! 🎁✨",
        f"🎊 Happy Birthday @{name} ! Que cette année soit incroyable ! 🎂🎈",
        f"🎉🎂 Bon anniversaire @{name} ! On te souhaite plein de bonheur ! 🎁🎊",
        f"🎈 Joyeux anniv' @{name} ! Profite bien de ta journée ! 🎂🎉",
        f"🎁 Happy Birthday @{name} ! Une année de plus, une année de mieux ! 🎊🎂",
        f"🎂 Joyeux anniversaire @{name} ! Des bisous et des câlins ! 💕🎉",
        f"🎉 Bon annif @{name} ! Que tous tes vœux se réalisent ! 🎂✨",
        f"🎊🎂 Joyeux anniversaire @{name} ! Passe une superbe journée ! 🎁🎈",
    ]
    
    # Choisir un message aléatoire
    response_text = random.choice(messages)
    
    await handler.bus.publish("chat.outbound", OutboundMessage(
        channel=msg.channel,
        channel_id=msg.channel_id,
        text=response_text,
        prefer="irc"
    ))
    
    LOGGER.info(f"🎂 {msg.user_login} wished happy birthday to {name}")
