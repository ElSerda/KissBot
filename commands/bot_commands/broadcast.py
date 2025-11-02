"""
Phase 3.5: Broadcast Commands
Commandes permettant de broadcaster des messages sur tous les channels.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from core.message_types import ChatMessage
from core.message_bus import MessageBus

LOGGER = logging.getLogger(__name__)

# Cooldown global pour broadcast (5 minutes)
BROADCAST_COOLDOWN = timedelta(minutes=5)
_last_broadcast_time: Optional[datetime] = None


async def cmd_kisscharity(msg: ChatMessage, args: list[str], bus: MessageBus, irc_client) -> Optional[str]:
    """
    !kisscharity <message> - Broadcaster un message sur tous les channels
    
    Usage:
        !kisscharity 🎮 Event charity ce soir à 20h pour Sidaction !
    
    Permissions:
        - Broadcaster only (msg.is_broadcaster)
    
    Cooldown:
        - 5 minutes entre chaque broadcast
    
    Args:
        msg: Message d'origine
        args: Liste des arguments (le message à broadcaster)
        bus: MessageBus
        irc_client: Instance IRCClient pour broadcaster
        
    Returns:
        Message de réponse avec succès/total
    """
    global _last_broadcast_time
    
    # 1. Permission check: Broadcaster only
    if not msg.is_broadcaster:
        LOGGER.warning(f"⚠️ !kisscharity refusé: {msg.user_login} n'est pas broadcaster")
        return f"@{msg.user_login} ❌ Seul le broadcaster peut utiliser !kisscharity"
    
    # 2. Cooldown check
    now = datetime.now()
    if _last_broadcast_time:
        time_since_last = now - _last_broadcast_time
        if time_since_last < BROADCAST_COOLDOWN:
            remaining = BROADCAST_COOLDOWN - time_since_last
            remaining_minutes = int(remaining.total_seconds() // 60)
            remaining_seconds = int(remaining.total_seconds() % 60)
            
            LOGGER.warning(
                f"⚠️ !kisscharity cooldown: {msg.user_login} "
                f"(reste {remaining_minutes}m {remaining_seconds}s)"
            )
            
            return (
                f"@{msg.user_login} ⏱️ Cooldown actif ! "
                f"Attends encore {remaining_minutes}m {remaining_seconds}s avant le prochain broadcast"
            )
    
    # 3. Validation: message non-vide
    if not args:
        return f"@{msg.user_login} ❌ Usage: !kisscharity <message>"
    
    # 4. Construire le message à broadcaster
    broadcast_msg = " ".join(args)
    
    # 5. Validation: max 500 chars (limite Twitch)
    if len(broadcast_msg) > 500:
        return (
            f"@{msg.user_login} ❌ Message trop long ! "
            f"Max 500 caractères (actuellement: {len(broadcast_msg)})"
        )
    
    # 6. Log avant broadcast
    LOGGER.info(
        f"📢 BROADCAST REQUEST | "
        f"user={msg.user_login} | "
        f"channel={msg.channel} | "
        f"message={broadcast_msg[:100]}..."
    )
    
    # 7. Broadcaster via IRC Client
    try:
        success, total = await irc_client.broadcast_message(
            message=broadcast_msg,
            source_channel=msg.channel,  # Ajouter source pour afficher [Source: xxx]
            exclude_channel=msg.channel  # Ne pas dupliquer sur le channel d'origine
        )
        
        # 8. Update cooldown
        _last_broadcast_time = now
        
        # 9. Log résultat
        success_rate = (success / total * 100) if total > 0 else 0
        LOGGER.info(
            f"✅ BROADCAST SENT | "
            f"user={msg.user_login} | "
            f"sent={success}/{total} ({success_rate:.1f}%) | "
            f"message={broadcast_msg[:50]}..."
        )
        
        # 10. Analytics event (optionnel)
        # TODO: Ajouter analytics.track("broadcast_sent", {...}) si système d'analytics existe
        
        # 11. Response
        if success == total:
            # Tous envoyés avec succès
            return (
                f"@{msg.user_login} 📢 Message diffusé avec succès sur {success} channels ! 🎉"
            )
        elif success > 0:
            # Succès partiel
            failed = total - success
            return (
                f"@{msg.user_login} 📢 Message diffusé sur {success}/{total} channels "
                f"({failed} échecs)"
            )
        else:
            # Tous échoués
            return f"@{msg.user_login} ❌ Erreur : impossible de diffuser le message"
            
    except Exception as e:
        LOGGER.error(f"❌ Erreur broadcast: {e}", exc_info=True)
        return f"@{msg.user_login} ❌ Erreur technique lors du broadcast"


# Export de la commande pour le registry
COMMANDS = {
    "kisscharity": cmd_kisscharity
}
