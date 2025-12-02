"""
Banword Commands Module - !kbbanword, !kbunbanword, !kbbanwords
===============================================================
Gestion des mots interdits (auto-ban).

Pattern: handler(MessageHandler, ChatMessage, args: str) -> None
"""

import logging
from twitchAPI.chat import ChatMessage

LOGGER = logging.getLogger("kissbot.commands.banwords")


async def handle_kbbanword(handler, msg: ChatMessage, args: str = "") -> None:
    """
    !kbbanword <mot> - Ajoute un banword (mod/broadcaster only)
    
    Tout message contenant ce mot = BAN instantané
    """
    from core.message_types import OutboundMessage
    
    if not (msg.is_mod or msg.is_broadcaster):
        return  # Silently ignore
    
    if not args:
        response_text = (
            f"@{msg.user_login} Usage: !kbbanword <mot> — "
            f"Ajoute un mot qui déclenche un BAN instantané"
        )
    else:
        word = args.strip().lower()
        
        # Validation
        if len(word) < 3:
            response_text = f"@{msg.user_login} ⚠️ Le mot doit faire au moins 3 caractères"
        elif len(word) > 50:
            response_text = f"@{msg.user_login} ⚠️ Le mot est trop long (max 50 caractères)"
        else:
            added = handler.banword_manager.add_banword(msg.channel, word, msg.user_login)
            
            if added:
                response_text = (
                    f"@{msg.user_login} 🚫 Banword ajouté: \"{word}\" — "
                    f"Tout message contenant ce mot = BAN instantané"
                )
                LOGGER.info(f"🚫 BANWORD | #{msg.channel} | {msg.user_login} added: '{word}'")
            else:
                response_text = f"@{msg.user_login} ℹ️ \"{word}\" est déjà dans la liste"
    
    await handler.bus.publish("chat.outbound", OutboundMessage(
        channel=msg.channel,
        channel_id=msg.channel_id,
        text=response_text
    ))


async def handle_kbunbanword(handler, msg: ChatMessage, args: str = "") -> None:
    """
    !kbunbanword <mot> - Retire un banword (mod/broadcaster only)
    """
    from core.message_types import OutboundMessage
    
    if not (msg.is_mod or msg.is_broadcaster):
        return  # Silently ignore
    
    if not args:
        response_text = f"@{msg.user_login} Usage: !kbunbanword <mot>"
    else:
        word = args.strip().lower()
        removed = handler.banword_manager.remove_banword(msg.channel, word)
        
        if removed:
            response_text = f"@{msg.user_login} ✅ Banword retiré: \"{word}\""
            LOGGER.info(f"✅ BANWORD | #{msg.channel} | {msg.user_login} removed: '{word}'")
        else:
            response_text = f"@{msg.user_login} ℹ️ \"{word}\" n'est pas dans la liste"
    
    await handler.bus.publish("chat.outbound", OutboundMessage(
        channel=msg.channel,
        channel_id=msg.channel_id,
        text=response_text
    ))


async def handle_kbbanwords(handler, msg: ChatMessage, args: str = "") -> None:
    """
    !kbbanwords - Liste les banwords du channel (mod/broadcaster only)
    """
    from core.message_types import OutboundMessage
    
    if not (msg.is_mod or msg.is_broadcaster):
        return  # Silently ignore
    
    words = handler.banword_manager.list_banwords(msg.channel)
    
    if not words:
        response_text = (
            f"@{msg.user_login} ℹ️ Aucun banword configuré. "
            f"Utilisez !kbbanword <mot> pour en ajouter"
        )
    else:
        # Limiter l'affichage si trop de mots
        if len(words) > 10:
            display = ", ".join(words[:10]) + f" ... (+{len(words) - 10})"
        else:
            display = ", ".join(words)
        
        response_text = f"@{msg.user_login} 🚫 Banwords ({len(words)}): {display}"
    
    await handler.bus.publish("chat.outbound", OutboundMessage(
        channel=msg.channel,
        channel_id=msg.channel_id,
        text=response_text
    ))
