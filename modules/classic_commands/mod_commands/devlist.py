"""
Dev Whitelist Commands Module - !adddev, !rmdev, !listdevs
==========================================================
Gestion de la whitelist développeurs (auto-trad).

Pattern: handler(MessageHandler, ChatMessage, args: str) -> None
"""

import logging
from twitchAPI.chat import ChatMessage

LOGGER = logging.getLogger("kissbot.commands.devlist")


async def handle_adddev(handler, msg: ChatMessage, args: str = "") -> None:
    """
    !adddev <username> - Ajoute dev à whitelist (mod only)
    
    Les devs ont accès à la traduction automatique sans cooldown.
    """
    from core.message_types import OutboundMessage
    
    if not (msg.is_mod or msg.is_broadcaster):
        return  # Silently ignore
    
    if not args:
        response_text = f"@{msg.user_login} Usage: !adddev <username>"
    else:
        username = args.strip().lstrip('@')
        added = handler.dev_whitelist.add_dev(username)
        
        if added:
            response_text = f"@{msg.user_login} ✅ {username} added to dev whitelist (auto-trad enabled)"
            LOGGER.info(f"👥 {msg.user_login} added {username} to dev whitelist")
        else:
            response_text = f"@{msg.user_login} ℹ️ {username} already in dev whitelist"
    
    await handler.bus.publish("chat.outbound", OutboundMessage(
        channel=msg.channel,
        channel_id=msg.channel_id,
        text=response_text
    ))


async def handle_rmdev(handler, msg: ChatMessage, args: str = "") -> None:
    """
    !rmdev <username> - Retire dev de whitelist (mod only)
    """
    from core.message_types import OutboundMessage
    
    if not (msg.is_mod or msg.is_broadcaster):
        return  # Silently ignore
    
    if not args:
        response_text = f"@{msg.user_login} Usage: !rmdev <username>"
    else:
        username = args.strip().lstrip('@')
        removed = handler.dev_whitelist.remove_dev(username)
        
        if removed:
            response_text = f"@{msg.user_login} ✅ {username} removed from dev whitelist"
            LOGGER.info(f"👥 {msg.user_login} removed {username} from dev whitelist")
        else:
            response_text = f"@{msg.user_login} ℹ️ {username} not in dev whitelist"
    
    await handler.bus.publish("chat.outbound", OutboundMessage(
        channel=msg.channel,
        channel_id=msg.channel_id,
        text=response_text
    ))


async def handle_listdevs(handler, msg: ChatMessage, args: str = "") -> None:
    """
    !listdevs - Liste les devs whitelistés (mod only)
    """
    from core.message_types import OutboundMessage
    
    if not (msg.is_mod or msg.is_broadcaster):
        return  # Silently ignore
    
    devs = handler.dev_whitelist.list_devs()
    
    if not devs:
        response_text = f"@{msg.user_login} ℹ️ No devs in whitelist"
    else:
        dev_list = ", ".join(devs)
        response_text = f"@{msg.user_login} 👥 Devs (auto-trad): {dev_list}"
    
    await handler.bus.publish("chat.outbound", OutboundMessage(
        channel=msg.channel,
        channel_id=msg.channel_id,
        text=response_text
    ))
