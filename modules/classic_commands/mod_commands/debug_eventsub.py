#!/usr/bin/env python3
"""
Debug Commands pour EventSub - Permet aux mods/admins d'inspekter l'état de la connexion.

Commandes:
  !debug_eventsub - Affiche la session EventSub actuelle
  !debug_send <message> - Envoie un message et affiche les détails d'envoi
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.message_handler import MessageHandler
    from core.message_types import ChatMessage

LOGGER = logging.getLogger(__name__)


async def handle_debug_eventsub(handler: "MessageHandler", msg: "ChatMessage", args: str = "") -> None:
    """
    !debug_eventsub - Affiche les infos de session EventSub pour les mods/admins.
    
    Affiche:
    - Session ID
    - Status
    - Uptime
    - Keepalive timeout
    - Derniers drops
    - Reconnections
    """
    from core.message_types import OutboundMessage
    from web.core.eventsub_metrics import get_eventsub_metrics
    
    # Restrict to mods only
    if not msg.user_mod and not msg.user_broadcaster:
        response = f"@{msg.user_login} ❌ Commande réservée aux mods"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response,
        ))
        return
    
    try:
        metrics = get_eventsub_metrics()
        session = metrics.get_session()
        send_metrics = metrics.get_send_metrics()
        channel_metrics = metrics.get_channel_metrics(msg.channel)
        
        if not channel_metrics:
            response = f"@{msg.user_login} ⚠️ Pas de données pour #{msg.channel}"
            await handler.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response,
            ))
            return
        
        # Construire la réponse
        session_id = session["session_id"][:12] if session["session_id"] else "❌"
        status = "✅" if session["status"] == "connected" else "⚠️"
        uptime_secs = int(session["uptime_seconds"])
        success_rate = send_metrics["success_rate"]
        
        response = (
            f"@{msg.user_login} | "
            f"EventSub: {status} {session_id}... | "
            f"Uptime: {uptime_secs}s | "
            f"Rate: {success_rate:.1f}% ✅{channel_metrics['messages_sent']} "
            f"❌{channel_metrics['messages_failed']}"
        )
        
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response,
        ))
        
        LOGGER.info(f"📊 Debug EventSub: {response}")
        
    except Exception as e:
        LOGGER.error(f"Error in debug_eventsub: {e}", exc_info=True)
        response = f"@{msg.user_login} ❌ Erreur: {str(e)[:50]}"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response,
        ))


async def handle_debug_send(handler: "MessageHandler", msg: "ChatMessage", message_text: str = "") -> None:
    """
    !debug_send <texte> - Envoie un message de test et affiche les détails d'envoi.
    
    Utile pour tester:
    - L'envoi via EventSub
    - Les problèmes AutoMod
    - La latence
    """
    from core.message_types import OutboundMessage
    import time
    
    # Restrict to mods only
    if not msg.user_mod and not msg.user_broadcaster:
        response = f"@{msg.user_login} ❌ Commande réservée aux mods"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response,
        ))
        return
    
    if not message_text or len(message_text.strip()) < 3:
        response = f"@{msg.user_login} Usage: !debug_send <message>"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response,
        ))
        return
    
    try:
        # Envoyer le message
        timestamp = int(time.time())
        debug_msg = f"🧪 DEBUG: {message_text} [#{timestamp}]"
        
        LOGGER.info(f"📤 Debug send: {debug_msg}")
        
        start_time = time.time()
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=debug_msg,
            prefer="eventsub"
        ))
        
        # Afficher le status
        response = f"@{msg.user_login} 📤 Test message envoyé ({debug_msg[:30]}...). Check logs pour détails."
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response,
        ))
        
    except Exception as e:
        LOGGER.error(f"Error in debug_send: {e}", exc_info=True)
        response = f"@{msg.user_login} ❌ Erreur envoi: {str(e)[:50]}"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response,
        ))
