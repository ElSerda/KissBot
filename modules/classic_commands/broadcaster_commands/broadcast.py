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
    
    # 7. Broadcaster - MONO-PROCESS vs MULTI-PROCESS
    try:
        # Détecter le mode: si irc_client a broadcast_message(), on l'utilise directement (mono-process)
        # Sinon, on écrit dans le fichier pour le Supervisor (multi-process)
        
        if irc_client and hasattr(irc_client, 'broadcast_message'):
            # ═══════════════════════════════════════════════════════════════
            # MODE MONO-PROCESS: Broadcast direct via IRCClient
            # ═══════════════════════════════════════════════════════════════
            LOGGER.info("📢 Mode MONO-PROCESS détecté → broadcast direct via IRCClient")
            
            success, total = await irc_client.broadcast_message(
                message=broadcast_msg,
                source_channel=msg.channel,
                exclude_channel=msg.channel  # Ne pas renvoyer sur le channel source
            )
            
            # 8. Update cooldown
            _last_broadcast_time = now
            
            if success == total:
                return (
                    f"@{msg.user_login} 📢 Broadcast réussi ! "
                    f"Message envoyé sur {success}/{total} channels 🎉"
                )
            elif success > 0:
                return (
                    f"@{msg.user_login} ⚠️ Broadcast partiel: "
                    f"{success}/{total} channels ont reçu le message"
                )
            else:
                return f"@{msg.user_login} ❌ Broadcast échoué sur tous les channels"
        else:
            # ═══════════════════════════════════════════════════════════════
            # MODE MULTI-PROCESS: Écrire pour le Supervisor
            # ═══════════════════════════════════════════════════════════════
            LOGGER.info("📢 Mode MULTI-PROCESS détecté → fichier IPC pour Supervisor")
            
            broadcast_file = "pids/supervisor.broadcast"
            
            # Format: timestamp|source_channel|message
            broadcast_data = f"{int(now.timestamp())}|{msg.channel}|{broadcast_msg}\n"
            
            os.makedirs("pids", exist_ok=True)
            with open(broadcast_file, "w") as f:
                f.write(broadcast_data)
            
            # 8. Update cooldown
            _last_broadcast_time = now
            
            LOGGER.info(
                f"✅ BROADCAST REQUEST SENT TO SUPERVISOR | "
                f"source={msg.channel} | message={broadcast_msg[:50]}..."
            )
            
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

async def cmd_kbupdate(msg: ChatMessage, args: list[str], bus: MessageBus, irc_client, twitch_client=None) -> Optional[str]:
    """
    !kbupdate <message> - Notifier tous les channels d'une mise à jour du bot
    
    Envoie une ANNONCE OFFICIELLE Twitch (via /announcements API) 
    au lieu d'un message chat classique.
    
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
        irc_client: Instance IRCClient (legacy, pas utilisé pour announces)
        twitch_client: Instance Twitch API (pour /announcements)
        
    Returns:
        Message de confirmation avec nombre de channels notifiés
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
    
    # 4. Validation: max 300 chars (Twitch /announcements limit 500, on en garde pour marge)
    if len(update_msg) > 300:
        return (
            f"@{msg.user_login} ❌ Message trop long ! "
            f"Max 300 caractères (actuellement: {len(update_msg)})"
        )
    
    # 5. Format du message announce (sans préfixe, l'API ajoute visuellement)
    announce_msg = f"🤖 KissBot Update: {update_msg}"
    
    # 6. Log
    LOGGER.info(
        f"📢 ANNOUNCE REQUEST | "
        f"user={msg.user_login} | "
        f"message={update_msg[:100]}..."
    )
    
    # 7. Si pas de Twitch client, fallback à broadcast classique
    if not twitch_client:
        LOGGER.warning("⚠️ Pas de Twitch client fourni, fallback à broadcast IRC")
        
        if irc_client and hasattr(irc_client, 'broadcast_message'):
            # Fallback: Broadcast direct via IRCClient
            broadcast_msg = f"🤖 [KissBot Update] {update_msg}"
            success, total = await irc_client.broadcast_message(
                message=broadcast_msg,
                source_channel=msg.channel,
                exclude_channel=None
            )
            
            if success > 0:
                return (
                    f"@{msg.user_login} 🔧 Notification (IRC fallback) envoyée sur {success}/{total} channels"
                )
            else:
                return f"@{msg.user_login} ❌ Erreur: notification non envoyée"
        else:
            # Multi-process fallback
            now = datetime.now()
            broadcast_file = "pids/supervisor.broadcast"
            broadcast_msg = f"🤖 [KissBot Update] {update_msg}"
            broadcast_data = f"{int(now.timestamp())}|{msg.channel}|{broadcast_msg}\n"
            
            os.makedirs("pids", exist_ok=True)
            with open(broadcast_file, "w") as f:
                f.write(broadcast_data)
            
            return (
                f"@{msg.user_login} 🔧 Notification (supervisor fallback) envoyée sur tous les channels"
            )
    
    # 8. Utiliser Twitch API /announcements
    try:
        # Récupérer les channels configurés depuis le config
        # Pour l'instant, on envoie sur le channel source
        # Dans une implémentation complète, itérer sur tous les channels configured
        
        LOGGER.info(f"📢 Envoi announce via API Helix pour channel: {msg.channel_id}")
        
        # Appel à l'API Helix: send_chat_announcement
        # Signature: send_chat_announcement(broadcaster_id, moderator_id, message, color=None)
        # - broadcaster_id: ID du channel
        # - moderator_id: ID du modérateur qui envoie (le bot = moderator)
        # - message: Le message à annoncer
        # - color: Couleur de l'annonce (BLUE, GREEN, ORANGE, PURPLE)
        
        await twitch_client.send_chat_announcement(
            broadcaster_id=msg.channel_id,
            moderator_id=msg.user_id,  # Owner sending as moderator
            message=announce_msg,
            color="PURPLE"  # 👑 KissBot color
        )
        
        LOGGER.info(
            f"✅ ANNOUNCE SENT | "
            f"channel_id={msg.channel_id} | "
            f"message={announce_msg[:50]}..."
        )
        
        return (
            f"@{msg.user_login} 📢 Annonce officielle envoyée au channel {msg.channel} ! "
            f"(via /announcements API)"
        )
            
    except Exception as e:
        LOGGER.error(f"❌ Erreur announce: {e}", exc_info=True)
        
        # Log l'erreur détaillée mais reste graceful
        error_msg = str(e)
        if "403" in error_msg or "Forbidden" in error_msg:
            return (
                f"@{msg.user_login} ❌ Erreur 403: Pas les permissions /announcements sur ce channel. "
                f"Scope: channel:manage:announcements"
            )
        elif "401" in error_msg or "Unauthorized" in error_msg:
            return (
                f"@{msg.user_login} ❌ Erreur 401: Token invalide ou expiré"
            )
        else:
            return f"@{msg.user_login} ❌ Erreur technique: {error_msg[:60]}..."


# Export de la commande pour le registry
COMMANDS = {
    "kisscharity": cmd_kisscharity,
    "kbupdate": cmd_kbupdate
}
