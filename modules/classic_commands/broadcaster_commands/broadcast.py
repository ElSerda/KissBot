"""
Broadcast Commands
Commandes permettant de broadcaster des messages sur tous les channels.
"""

import logging
import os
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
    
    # 7. Broadcaster via Supervisor (communication inter-bots)
    try:
        # Écrire la commande de broadcast dans un fichier pour le Supervisor
        broadcast_file = "pids/supervisor.broadcast"
        
        # Format: timestamp|source_channel|message
        broadcast_data = f"{int(now.timestamp())}|{msg.channel}|{broadcast_msg}\n"
        
        # Écrire dans le fichier (append mode pour ne pas écraser)
        os.makedirs("pids", exist_ok=True)
        with open(broadcast_file, "w") as f:
            f.write(broadcast_data)
        
        # 8. Update cooldown
        _last_broadcast_time = now
        
        # 9. Log broadcast request
        LOGGER.info(
            f"✅ BROADCAST REQUEST SENT TO SUPERVISOR | "
            f"user={msg.user_login} | "
            f"source={msg.channel} | "
            f"message={broadcast_msg[:50]}..."
        )
        
        # 10. Response immédiate (le Supervisor s'occupe de la diffusion)
        return (
            f"@{msg.user_login} 📢 Broadcast en cours sur tous les channels... "
            f"(traitement par Supervisor)"
        )
            
    except Exception as e:
        LOGGER.error(f"❌ Erreur broadcast: {e}", exc_info=True)
        return f"@{msg.user_login} ❌ Erreur technique lors du broadcast"


# ============================================================================
# !kbupdate - Notification de mise à jour pour les testeurs
# ============================================================================

# Owner only (el_serda user_id)
OWNER_USER_ID = "44456636"  # el_serda

async def cmd_kbupdate(msg: ChatMessage, args: list[str], bus: MessageBus, irc_client) -> Optional[str]:
    """
    !kbupdate <message> - Notifier tous les channels d'une mise à jour du bot
    
    Usage:
        !kbupdate Nouvelle commande !wiki disponible ! 🎉
        !kbupdate Maintenance en cours, redémarrage dans 5 min ⚙️
    
    Permissions:
        - Owner only (el_serda uniquement)
    
    Cooldown:
        - Aucun (owner peut spammer s'il veut 😎)
    
    Args:
        msg: Message d'origine
        args: Liste des arguments (le message de mise à jour)
        bus: MessageBus
        irc_client: Instance IRCClient pour broadcaster
        
    Returns:
        Message de confirmation
    """
    # 1. Permission check: Owner only
    if msg.user_id != OWNER_USER_ID:
        LOGGER.warning(f"⚠️ !kbupdate refusé: {msg.user_login} (id={msg.user_id}) n'est pas owner")
        return f"@{msg.user_login} ❌ Seul el_serda peut utiliser !kbupdate"
    
    # 2. Validation: message non-vide
    if not args:
        return f"@{msg.user_login} ❌ Usage: !kbupdate <message>"
    
    # 3. Construire le message
    update_msg = " ".join(args)
    
    # 4. Validation: max 400 chars (on garde de la marge pour le préfixe)
    if len(update_msg) > 400:
        return (
            f"@{msg.user_login} ❌ Message trop long ! "
            f"Max 400 caractères (actuellement: {len(update_msg)})"
        )
    
    # 5. Format du message broadcast
    broadcast_msg = f"🤖 [KissBot Update] {update_msg}"
    
    # 6. Log
    LOGGER.info(
        f"🔧 UPDATE BROADCAST | "
        f"user={msg.user_login} | "
        f"message={update_msg[:100]}..."
    )
    
    # 7. Écrire dans le fichier broadcast pour le Supervisor
    try:
        now = datetime.now()
        broadcast_file = "pids/supervisor.broadcast"
        
        # Format: timestamp|source_channel|message
        broadcast_data = f"{int(now.timestamp())}|{msg.channel}|{broadcast_msg}\n"
        
        os.makedirs("pids", exist_ok=True)
        with open(broadcast_file, "w") as f:
            f.write(broadcast_data)
        
        LOGGER.info(
            f"✅ UPDATE BROADCAST SENT | "
            f"message={broadcast_msg[:50]}..."
        )
        
        return (
            f"@{msg.user_login} 🔧 Notification envoyée sur tous les channels ! "
            f"\"[KissBot Update] {update_msg[:50]}...\""
        )
            
    except Exception as e:
        LOGGER.error(f"❌ Erreur kbupdate: {e}", exc_info=True)
        return f"@{msg.user_login} ❌ Erreur technique lors de l'envoi"


# Export de la commande pour le registry
COMMANDS = {
    "kisscharity": cmd_kisscharity,
    "kbupdate": cmd_kbupdate
}
