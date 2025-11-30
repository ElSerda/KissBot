"""
🎉 !kissanniv Command - Birthday celebration command

Simple birthday wish command for community celebrations.
"""

import random
from core.message_types import ChatMessage, OutboundMessage
from core.message_bus import MessageBus


async def cmd_kissanniv(bus: MessageBus, msg: ChatMessage, args: str) -> None:
    """
    Commande !kissanniv [name] - Souhaiter un joyeux anniversaire
    
    Args:
        bus: Message bus pour publier la réponse
        msg: Message original
        args: Nom de la personne (optionnel)
    """
    # Messages d'anniversaire variés
    messages = [
        "🎉🎂 Joyeux anniversaire {name} ! 🎊🎈",
        "🎂✨ Happy Birthday {name}! 🎉🎁",
        "🎊🎈 Bon anniversaire {name} ! 🎂🎉",
        "🥳🎂 Joyeux anniv' {name} ! 🎊✨",
        "🎉🎁 Happy B-Day {name}! 🎂🎈",
        "🎂🎊 Bonne fête {name} ! 🥳🎉",
    ]
    
    # Parse le nom
    if args and args.strip():
        name = args.strip()
        # Ajouter @ si pas déjà présent
        if not name.startswith("@"):
            name = f"@{name}"
    else:
        # Si pas de nom, utiliser l'auteur de la commande
        name = f"@{msg.user_login}"
    
    # Choisir un message aléatoire
    birthday_msg = random.choice(messages).format(name=name)
    
    # Envoyer le message
    await bus.publish("chat.outbound", OutboundMessage(
        channel=msg.channel,
        channel_id=msg.channel_id,
        text=birthday_msg,
        prefer="irc"
    ))
