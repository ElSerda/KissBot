"""
🎂 Commande !anniv - Souhaiter un joyeux anniversaire

Commande simple pour célébrer les anniversaires dans le chat !
"""

import random
from core.message_types import ChatMessage, OutboundMessage
from core.message_bus import MessageBus


async def cmd_anniv(msg: ChatMessage, args: str, bus: MessageBus, config: dict) -> None:
    """
    Commande !anniv <name> - Souhaiter un joyeux anniversaire
    
    Args:
        msg: Message original
        args: Nom de la personne (ex: "Serda" ou "@Serda")
        bus: Message bus pour publier
        config: Configuration bot
    """
    if not args or len(args.strip()) == 0:
        response_text = f"@{msg.user_login} 🎂 Usage: !anniv <nom>"
        await bus.publish("chat.outbound", OutboundMessage(
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
    
    await bus.publish("chat.outbound", OutboundMessage(
        channel=msg.channel,
        channel_id=msg.channel_id,
        text=response_text,
        prefer="irc"
    ))


# Export for registry
__all__ = ['cmd_anniv']
