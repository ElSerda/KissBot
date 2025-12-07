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
    
    # 7. Utiliser Twitch API /announcements sur TOUS les channels configurés
    # ARCHITECTURE: Utilise le token BROADCASTER de chaque channel (pas le bot token)
    # - Charge token depuis DB: token_type='broadcaster'
    # - Crée Twitch instance temporaire avec ce token
    # - Appel API avec moderator_id = broadcaster_id (pas besoin de /mod)
    try:
        # Récupérer tous les channels configurés depuis config.yaml
        import yaml
        import json
        from pathlib import Path
        from twitchAPI.twitch import Twitch
        from twitchAPI.oauth import AuthScope
        from database.manager import DatabaseManager
        
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
        
        # Load DB credentials
        client_id = config['twitch']['client_id']
        client_secret = config['twitch']['client_secret']
        db_path = project_root / "kissbot.db"
        key_path = project_root / ".kissbot.key"
        
        # Initialize DB manager
        db = DatabaseManager(str(db_path), str(key_path))
        
        success_count = 0
        failed_channels = []
        
        LOGGER.info(f"📢 Broadcasting announce to {len(all_channels)} channels via BROADCASTER tokens")
        
        # Itérer sur tous les channels configurés (liste de strings)
        for channel_login in all_channels:
            # Normaliser le nom (enlever # si présent, lowercase)
            channel_login = channel_login.strip().lstrip('#').lower()
            
            try:
                # 1. Get broadcaster user from DB
                broadcaster_user = db.get_user_by_login(channel_login)
                if not broadcaster_user:
                    LOGGER.warning(f"⚠️ User {channel_login} not found in DB, skipping")
                    failed_channels.append(channel_login)
                    continue
                
                # 2. Get broadcaster token from DB
                broadcaster_token = db.get_tokens(broadcaster_user['id'], token_type='broadcaster')
                if not broadcaster_token:
                    LOGGER.warning(f"⚠️ No broadcaster token for {channel_login}, skipping")
                    failed_channels.append(channel_login)
                    continue
                
                # 3. Parse scopes (stored as JSON array string)
                scopes_str = broadcaster_token['scopes']
                if isinstance(scopes_str, str):
                    scopes_list = json.loads(scopes_str)
                else:
                    scopes_list = scopes_str
                
                # Convert to AuthScope enums
                scope_enums = []
                for scope_str in scopes_list:
                    for auth_scope in AuthScope:
                        if auth_scope.value == scope_str:
                            scope_enums.append(auth_scope)
                            break
                
                # 4. Create temporary Twitch instance with broadcaster token
                temp_twitch = Twitch(client_id, client_secret)
                await temp_twitch.set_user_authentication(
                    token=broadcaster_token['access_token'],
                    scope=scope_enums,
                    refresh_token=broadcaster_token['refresh_token'],
                    validate=True
                )
                
                # 5. Get broadcaster ID (field is 'twitch_user_id' in DB schema)
                broadcaster_id = str(broadcaster_user['twitch_user_id'])
                
                # 6. Send announcement with broadcaster token + moderator_id = broadcaster_id
                await temp_twitch.send_chat_announcement(
                    broadcaster_id=broadcaster_id,
                    moderator_id=broadcaster_id,  # CRITICAL: broadcaster acts on own channel
                    message=announce_msg,
                    color="purple"  # 👑 KissBot color
                )
                
                await temp_twitch.close()
                
                success_count += 1
                LOGGER.info(f"✅ Announce sent to #{channel_login} (ID: {broadcaster_id}) via broadcaster token")
                    
            except Exception as channel_error:
                failed_channels.append(channel_login)
                LOGGER.error(f"❌ Failed to send announce to #{channel_login}: {channel_error}")
        
        # Résultat final - Ne pas envoyer de réponse sur le channel source
        # Seulement logger le résultat (pas de spam dans le chat)
        total = len(all_channels)
        if success_count == total:
            LOGGER.info(f"✅ !kbupdate: {success_count}/{total} annonces envoyées avec succès")
            return None  # Pas de réponse dans le chat
        elif success_count > 0:
            failed_str = ", ".join(failed_channels[:3])
            LOGGER.warning(f"⚠️ !kbupdate: {success_count}/{total} envoyés. Échecs: {failed_str}")
            return None  # Pas de réponse dans le chat
        else:
            # Seulement si échec total, on informe l'owner
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
