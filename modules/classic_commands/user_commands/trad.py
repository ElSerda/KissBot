"""
Commande !trad - Traduction manuelle.

Handler pour la commande !trad qui traduit un message
vers le français avec rate limiting (sauf pour les whitelistés).
"""
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.message_handler import MessageHandler
    from core.message_types import ChatMessage

LOGGER = logging.getLogger(__name__)


async def handle_trad(handler: "MessageHandler", msg: "ChatMessage", args: str) -> None:
    """
    !trad <message> - Traduction manuelle vers le français
    
    Args:
        handler: Instance MessageHandler
        msg: Message chat entrant
        args: Message à traduire
    """
    from core.message_types import OutboundMessage
    
    if not args:
        response_text = f"@{msg.user_login} Usage: !trad <message>"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        return
    
    # Rate limiting: 30s cooldown SAUF pour whitelistés
    is_whitelisted = handler.dev_whitelist.is_dev(msg.user_login)
    
    if not is_whitelisted:
        current_time = time.time()
        last_time = handler._trad_last_time.get(msg.user_id, 0)
        
        if current_time - last_time < handler._trad_cooldown:
            cooldown_remaining = int(handler._trad_cooldown - (current_time - last_time))
            response_text = f"@{msg.user_login} ⏰ Cooldown: {cooldown_remaining}s restants"
            await handler.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            LOGGER.debug(f"🔇 !trad de {msg.user_login} en cooldown ({cooldown_remaining}s restants)")
            return
        
        # Update cooldown
        handler._trad_last_time[msg.user_id] = current_time
    
    result = await handler.translator.translate(args, target_lang='fr')
    
    if not result:
        response_text = f"@{msg.user_login} ❌ Translation failed"
    else:
        source_lang, translation = result
        
        if source_lang == 'fr':
            response_text = f"@{msg.user_login} 🇫🇷 Already in French!"
        else:
            response_text = f"[TRAD] {msg.user_login} a dit: {translation}"
    
    await handler.bus.publish("chat.outbound", OutboundMessage(
        channel=msg.channel,
        channel_id=msg.channel_id,
        text=response_text,
        prefer="irc"
    ))
