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

async def cmd_kbupdate(msg: ChatMessage, args: list[str], bus: MessageBus, twitch_client) -> Optional[str]:
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
        twitch_client: Instance Twitch API (requis pour /announcements)
        
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
    
    # 7. Validation: Twitch client requis (pas de fallback IRC)
    if not twitch_client:
        LOGGER.error("❌ Twitch client manquant pour !kbupdate")
        return f"@{msg.user_login} ❌ Erreur système: Twitch API non disponible"
    
    # 8. Utiliser Twitch API /announcements sur TOUS les channels configurés
    try:
        # Récupérer tous les channels configurés depuis config.yaml
        import yaml
        from pathlib import Path
        
        # Trouver le répertoire racine du projet (où se trouve config/)
        current_file = Path(__file__).resolve()
        project_root = current_file
        while project_root.parent != project_root:  # Remonter jusqu'à trouver config/
            if (project_root / "config" / "config.yaml").exists():
                break
            project_root = project_root.parent
        
        config_path = project_root / "config" / "config.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"config.yaml not found at {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        all_channels = config.get('twitch', {}).get('channels', [])
        
        if not all_channels:
            LOGGER.warning("⚠️ Aucun channel configuré dans config.yaml")
            return f"@{msg.user_login} ❌ Aucun channel configuré"
        
        success_count = 0
        failed_channels = []
        
        LOGGER.info(f"📢 Broadcasting announce to {len(all_channels)} channels via API Helix")
        
        # Itérer sur tous les channels configurés (liste de strings)
        for channel_login in all_channels:
            # Normaliser le nom (enlever # si présent, lowercase)
            channel_login = channel_login.strip().lstrip('#').lower()
            
            # Récupérer l'ID du channel via l'API (nécessaire pour send_chat_announcement)
            try:
                async for user in twitch_client.get_users(logins=[channel_login]):
                    channel_id = user.id
                    
                    # Appel à l'API Helix: send_chat_announcement
                    await twitch_client.send_chat_announcement(
                        broadcaster_id=channel_id,
                        moderator_id="1209350837",  # Bot ID (serda_bot)
                        message=announce_msg,
                        color="purple"  # 👑 KissBot color
                    )
                    
                    success_count += 1
                    LOGGER.info(f"✅ Announce sent to #{channel_login} (ID: {channel_id})")
                    break  # get_users retourne async generator, on prend le premier
                    
            except Exception as channel_error:
                failed_channels.append(channel_login)
                LOGGER.error(f"❌ Failed to send announce to #{channel_login}: {channel_error}")
        
        # Résultat final
        total = len(all_channels)
        if success_count == total:
            return (
                f"@{msg.user_login} 📢 Annonce officielle envoyée sur {success_count}/{total} channels ! "
                f"(via /announcements API)"
            )
        elif success_count > 0:
            failed_str = ", ".join(failed_channels[:3])
            return (
                f"@{msg.user_login} ⚠️ Broadcast partiel: {success_count}/{total} channels. "
                f"Échecs: {failed_str}{'...' if len(failed_channels) > 3 else ''}"
            )
        else:
            return f"@{msg.user_login} ❌ Aucune annonce envoyée (erreur sur tous les channels)"
            
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
