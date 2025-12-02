"""
📢 User Commands - Promo
Commandes promotionnelles et liens utiles.

Commands:
- !kbkofi : Lien Ko-fi pour soutenir le développement
- !kisscharity : Broadcaster un message charity (broadcaster only)
"""
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.message_handler import MessageHandler
    from twitchAPI.chat import ChatMessage

from core.message_types import OutboundMessage

LOGGER = logging.getLogger(__name__)


async def handle_kbkofi(handler: "MessageHandler", msg: "ChatMessage", args: str = "") -> None:
    """
    !kbkofi - Affiche le lien Ko-fi pour soutenir le développement de KissBot
    """
    response_text = "☕ Soutenez KissBot ! → https://ko-fi.com/el_serda 💜"
    
    await handler.bus.publish("chat.outbound", OutboundMessage(
        channel=msg.channel,
        channel_id=msg.channel_id,
        text=response_text,
        prefer="irc"
    ))
    LOGGER.info(f"✅ [kbkofi] Response to {msg.user_login}")


async def handle_kisscharity(handler: "MessageHandler", msg: "ChatMessage", args: str = "") -> None:
    """
    !kisscharity <message> - Broadcaster un message sur tous les channels
    
    Commande KILLER FEATURE pour annonces multi-channels:
    - Events charity
    - Raids communautaires
    - Collaborations multi-streamers
    
    Restrictions:
    - Broadcaster only
    - Cooldown 5 minutes global
    - Max 500 caractères
    """
    from modules.classic_commands.bot_commands.broadcast import cmd_kisscharity
    
    # Check si IRC client est disponible
    if not handler.irc_client:
        response_text = f"@{msg.user_login} ❌ Erreur système : IRC client non disponible"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        return
    
    # Parser les arguments
    args_list = args.split() if args else []
    
    # Appeler le handler de broadcast
    response_text = await cmd_kisscharity(
        msg=msg,
        args=args_list,
        bus=handler.bus,
        irc_client=handler.irc_client
    )
    
    # Envoyer la réponse
    if response_text:
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
    LOGGER.info(f"✅ [kisscharity] Broadcast initiated by {msg.user_login}")
