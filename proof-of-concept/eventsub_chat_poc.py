#!/usr/bin/env python3
"""
Proof of Concept: Chat via EventSub WebSocket
==============================================

Avantages par rapport à IRC:
- Keepalive toutes les ~10 secondes (vs 5 minutes pour IRC)
- Détection de déconnexion quasi-instantanée
- Reconnexion automatique native
- Même messages, même format

Usage:
    python proof-of-concept/eventsub_chat_poc.py

Nécessite:
    - config/config.yaml avec broadcaster et bot tokens
    - Scopes: user:read:chat, user:write:chat
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

# Ajouter le répertoire racine au path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticationStorageHelper
from twitchAPI.type import AuthScope
from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.object.eventsub import ChannelChatMessageEvent
from twitchAPI.helper import first

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%H:%M:%S'
)
LOGGER = logging.getLogger('EventSubChat')

# Tracker pour le keepalive
last_keepalive_time = time.time()
keepalive_count = 0


async def on_chat_message(event: ChannelChatMessageEvent):
    """Callback pour les messages chat reçus via EventSub."""
    global last_keepalive_time
    last_keepalive_time = time.time()  # Chaque message reset le timer
    
    chatter = event.event.chatter_user_name
    message = event.event.message.text
    badges = [b.set_id for b in event.event.badges] if event.event.badges else []
    
    # Afficher le message
    badge_str = f"[{','.join(badges)}]" if badges else ""
    LOGGER.info(f"💬 {badge_str} {chatter}: {message}")


async def keepalive_monitor():
    """Moniteur pour afficher les keepalives reçus."""
    global last_keepalive_time, keepalive_count
    
    LOGGER.info("📡 Keepalive monitor démarré - Twitch envoie un keepalive toutes les ~10s")
    
    while True:
        await asyncio.sleep(5)  # Check toutes les 5 secondes
        
        elapsed = time.time() - last_keepalive_time
        
        if elapsed < 15:
            LOGGER.debug(f"💓 Connexion vivante (dernier signal il y a {elapsed:.1f}s)")
        elif elapsed < 30:
            LOGGER.warning(f"⚠️ Pas de signal depuis {elapsed:.1f}s (timeout ~20s)")
        else:
            LOGGER.error(f"🚨 CONNEXION MORTE? Pas de signal depuis {elapsed:.1f}s")


async def main():
    global last_keepalive_time
    
    # Charger la config
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    if not config_path.exists():
        LOGGER.error(f"Config non trouvée: {config_path}")
        return
    
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    client_id = config['apis']['igdb_client_id']  # Même que Twitch app
    client_secret = config['apis']['igdb_client_secret']
    
    # Channel à écouter
    channels = config.get('channels', ['el_serda'])
    broadcaster_login = channels[0] if channels else 'el_serda'
    
    LOGGER.info("=" * 60)
    LOGGER.info("🚀 EventSub Chat POC - Keepalive 10s vs IRC 5min")
    LOGGER.info("=" * 60)
    LOGGER.info(f"📺 Channel: {broadcaster_login}")
    
    # Utiliser le DatabaseManager pour récupérer les tokens
    from database.manager import DatabaseManager
    db = DatabaseManager()
    
    # Récupérer l'ID du bot depuis la table users
    with db._get_connection() as conn:
        cursor = conn.execute(
            "SELECT id FROM users WHERE is_bot = 1 LIMIT 1"
        )
        row = cursor.fetchone()
        if not row:
            LOGGER.error("Pas de bot trouvé dans la DB!")
            return
        db_bot_id = row[0]
    
    bot_tokens = db.get_tokens(user_id=db_bot_id, token_type="bot")
    if not bot_tokens:
        LOGGER.error(f"Pas de tokens bot dans la DB pour user_id={db_bot_id}!")
        return
    
    bot_access_token = bot_tokens['access_token']
    bot_refresh_token = bot_tokens['refresh_token']
    LOGGER.info("✅ Tokens récupérés depuis la base de données")
    
    # Initialiser Twitch API
    twitch = await Twitch(client_id, client_secret)
    
    # Authentifier avec le bot token
    await twitch.set_user_authentication(
        bot_access_token,
        [AuthScope.USER_READ_CHAT, AuthScope.USER_WRITE_CHAT, AuthScope.CHAT_READ],
        bot_refresh_token
    )
    
    # Récupérer les IDs
    bot_user = await first(twitch.get_users())
    broadcaster = await first(twitch.get_users(logins=[broadcaster_login]))
    
    if not broadcaster:
        LOGGER.error(f"Broadcaster '{broadcaster_login}' non trouvé!")
        return
    
    bot_id = bot_user.id
    broadcaster_id = broadcaster.id
    
    LOGGER.info(f"🤖 Bot: {bot_user.display_name} (ID: {bot_id})")
    LOGGER.info(f"📺 Broadcaster: {broadcaster.display_name} (ID: {broadcaster_id})")
    
    # Créer EventSub WebSocket
    eventsub = EventSubWebsocket(twitch)
    
    # Hook pour tracker les keepalives
    original_handle_keepalive = eventsub._handle_keepalive
    async def patched_handle_keepalive(data: dict):
        global last_keepalive_time, keepalive_count
        last_keepalive_time = time.time()
        keepalive_count += 1
        if keepalive_count % 6 == 0:  # Log toutes les minutes environ
            LOGGER.info(f"💓 Keepalive #{keepalive_count} reçu (toutes les ~10s)")
        await original_handle_keepalive(data)
    eventsub._handle_keepalive = patched_handle_keepalive
    
    # Démarrer EventSub
    eventsub.start()
    LOGGER.info("✅ EventSub WebSocket démarré")
    
    # S'abonner aux messages chat
    await eventsub.listen_channel_chat_message(
        broadcaster_user_id=broadcaster_id,
        user_id=bot_id,  # Le bot lit les messages
        callback=on_chat_message
    )
    LOGGER.info(f"✅ Abonné aux messages chat de #{broadcaster_login}")
    
    # Démarrer le moniteur de keepalive
    monitor_task = asyncio.create_task(keepalive_monitor())
    
    LOGGER.info("")
    LOGGER.info("=" * 60)
    LOGGER.info("🎯 EN ATTENTE DE MESSAGES...")
    LOGGER.info("   Comparaison: IRC = PING toutes les 5 min")
    LOGGER.info("                EventSub = Keepalive toutes les 10s")
    LOGGER.info("   → Détection de déconnexion 30x plus rapide!")
    LOGGER.info("=" * 60)
    LOGGER.info("")
    
    # Attendre indéfiniment
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        LOGGER.info("🛑 Arrêt demandé...")
    finally:
        monitor_task.cancel()
        await eventsub.stop()
        await twitch.close()


if __name__ == "__main__":
    asyncio.run(main())
