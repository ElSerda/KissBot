"""
Personality Commands Module - !kbpersona, !kbnsfw
=================================================
Gestion de la personnalité du bot par channel.

Pattern: handler(MessageHandler, ChatMessage, args: str) -> None
"""

import logging
from twitchAPI.chat import ChatMessage

LOGGER = logging.getLogger("kissbot.commands.personality")


async def handle_kbpersona(handler, msg: ChatMessage, args: str = "") -> None:
    """
    !kbpersona [preset|list] - Change le ton du bot pour ce channel
    
    Broadcaster only.
    - !kbpersona : Affiche le preset actuel
    - !kbpersona list : Liste les presets disponibles
    - !kbpersona <preset> : Change le preset (soft, normal, spicy, unhinged, gamer, uwu)
    """
    from core.message_types import OutboundMessage
    from modules.personality import (
        get_personality_store, 
        format_preset_list, 
        PERSONALITY_PRESETS,
        NSFW_PRESETS
    )
    
    # Check broadcaster only
    is_broadcaster = str(msg.user_id) == str(msg.channel_id)
    if not is_broadcaster:
        response_text = f"@{msg.user_login} ❌ Commande réservée au broadcaster"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        return
    
    store = get_personality_store()
    personality = store.get(msg.channel_id, msg.channel)
    
    args = args.strip().lower() if args else ""
    
    # Pas d'argument : afficher le preset actuel
    if not args:
        response_text = f"🎭 Personnalité actuelle: {personality.emoji} {personality.preset} | Tape !kbpersona list pour voir les options"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        return
    
    # Lister les presets
    if args == "list":
        preset_list = format_preset_list(include_nsfw=personality.nsfw_allowed)
        response_text = f"🎭 Presets dispo: {preset_list}"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        return
    
    # Changer le preset
    preset_name = args
    if preset_name not in PERSONALITY_PRESETS:
        response_text = f"@{msg.user_login} ❌ Preset inconnu: {preset_name} | Tape !kbpersona list"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        return
    
    # Check NSFW
    if preset_name in NSFW_PRESETS and not personality.nsfw_allowed:
        response_text = f"@{msg.user_login} ⚠️ Le preset '{preset_name}' nécessite !kbnsfw on d'abord"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        return
    
    # Appliquer le changement
    success = store.set_preset(msg.channel_id, msg.channel, preset_name)
    if success:
        preset_info = PERSONALITY_PRESETS[preset_name]
        response_text = f"✅ Personnalité changée: {preset_info['emoji']} {preset_name} - {preset_info['description']}"
    else:
        response_text = f"@{msg.user_login} ❌ Erreur lors du changement de preset"
    
    await handler.bus.publish("chat.outbound", OutboundMessage(
        channel=msg.channel,
        channel_id=msg.channel_id,
        text=response_text,
        prefer="irc"
    ))


async def handle_kbnsfw(handler, msg: ChatMessage, args: str = "") -> None:
    """
    !kbnsfw [on|off] - Active/désactive le mode 18+ pour ce channel
    
    Broadcaster only.
    Permet d'utiliser les presets NSFW comme 'unhinged'.
    """
    from core.message_types import OutboundMessage
    from modules.personality import get_personality_store
    
    # Check broadcaster only
    is_broadcaster = str(msg.user_id) == str(msg.channel_id)
    if not is_broadcaster:
        response_text = f"@{msg.user_login} ❌ Commande réservée au broadcaster"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        return
    
    store = get_personality_store()
    personality = store.get(msg.channel_id, msg.channel)
    
    args = args.strip().lower() if args else ""
    
    # Pas d'argument : afficher l'état actuel
    if not args:
        status = "🔞 activé" if personality.nsfw_allowed else "🔒 désactivé"
        response_text = f"Mode NSFW: {status} | Tape !kbnsfw on ou !kbnsfw off"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        return
    
    # Changer l'état
    if args == "on":
        success = store.set_nsfw(msg.channel_id, msg.channel, True)
        if success:
            response_text = "🔞 Mode NSFW activé ! Tu peux maintenant utiliser !kbpersona unhinged"
        else:
            response_text = f"@{msg.user_login} ❌ Erreur lors de l'activation"
    elif args == "off":
        success = store.set_nsfw(msg.channel_id, msg.channel, False)
        if success:
            # Reset to normal if currently on nsfw preset
            if personality.preset in ["unhinged"]:
                store.set_preset(msg.channel_id, msg.channel, "normal")
                response_text = "🔒 Mode NSFW désactivé ! Preset reset à 'normal'"
            else:
                response_text = "🔒 Mode NSFW désactivé !"
        else:
            response_text = f"@{msg.user_login} ❌ Erreur lors de la désactivation"
    else:
        response_text = f"@{msg.user_login} ❌ Usage: !kbnsfw on ou !kbnsfw off"
    
    await handler.bus.publish("chat.outbound", OutboundMessage(
        channel=msg.channel,
        channel_id=msg.channel_id,
        text=response_text,
        prefer="irc"
    ))
