#!/usr/bin/env python3
"""KissBot V4 - Twitch Bot with IRC, Helix API, and Stream Monitoring"""

import asyncio
import json
import logging
import sys
from pathlib import Path

import yaml
from twitchAPI.twitch import Twitch

from core.message_bus import MessageBus
from core.registry import Registry
from core.rate_limiter import RateLimiter
from core.analytics_handler import AnalyticsHandler
from core.chat_logger import ChatLogger
from core.message_handler import MessageHandler
from core.outbound_logger import OutboundLogger
from core.stream_announcer import StreamAnnouncer
from twitchapi.auth_manager import AuthManager
from twitchapi.monitors.stream_monitor import StreamMonitor
from twitchapi.transports.eventsub_client import EventSubClient
from twitchapi.transports.helix_readonly import HelixReadOnlyClient
from twitchapi.transports.irc_client import IRCClient
from core.system_monitor import SystemMonitor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
    handlers=[
        logging.FileHandler("kissbot_production.log"),
        logging.StreamHandler()
    ]
)

LOGGER = logging.getLogger(__name__)


def load_config():
    """Charge config.yaml"""
    config_file = Path("config/config.yaml")
    if not config_file.exists():
        LOGGER.error("config/config.yaml introuvable")
        sys.exit(1)
    with open(config_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


async def main():
    """Main entry point: Initialize app token, Helix API, IRC client, and stream monitoring"""
    print("=" * 70)
    print("KissBot V4 - Twitch Bot with IRC + Helix + Stream Monitoring")
    print("=" * 70)
    
    config = load_config()
    twitch_config = config.get("twitch", {})
    bot_config = config.get("bot", {})
    
    # Load timeouts from config
    timeouts = config.get("timeouts", {})
    irc_send_timeout = timeouts.get("irc_send", 5.0)
    helix_timeout = timeouts.get("helix_request", 8.0)
    
    app_id = twitch_config.get("client_id")
    app_secret = twitch_config.get("client_secret")
    bot_name = bot_config.get("name", "serda_bot")
    bot_user_id = "1209350837"  # ID de serda_bot
    
    # IRC channels to join (also monitored by StreamMonitor)
    irc_channels = twitch_config.get("channels", [])
    
    if not app_id or not app_secret:
        LOGGER.error("client_id ou client_secret manquant")
        sys.exit(1)
    
    # Initialisation silencieuse
    twitch_app = await Twitch(app_id, app_secret)
    
    # Load bot token (User Token)
    auth_manager = AuthManager(twitch_app)
    bot_token = await auth_manager.load_token_from_file(bot_user_id)
    
    if not bot_token:
        LOGGER.error(f"❌ Token bot '{bot_name}' introuvable !")
        await twitch_app.close()
        sys.exit(1)
    
    # Créer instance Twitch avec User Token pour IRC
    twitch_bot = await Twitch(app_id, app_secret)
    
    # UserAuthenticationStorageHelper natif de pyTwitchAPI
    # Gère automatiquement: load token, refresh callback, save token
    from twitchAPI.oauth import UserAuthenticationStorageHelper
    from pathlib import Path
    
    # Custom storage path pour notre format .tio.tokens.json
    # Note: UserAuthenticationStorageHelper utilise un format différent, mais on peut adapter
    # Pour l'instant, on utilise set_user_authentication classique avec callback manuel
    
    # Callback pour sauvegarder le token après refresh automatique
    async def save_refreshed_token(token: str, refresh_token: str):
        """Callback appelé automatiquement par pyTwitchAPI quand le token est refreshé"""
        try:
            token_file = Path(".tio.tokens.json")
            if token_file.exists():
                with open(token_file, 'r') as f:
                    data = json.load(f)
                
                # Update token pour ce user_id
                if bot_user_id in data:
                    data[bot_user_id]["token"] = token
                    data[bot_user_id]["refresh"] = refresh_token
                    
                    with open(token_file, 'w') as f:
                        json.dump(data, f, indent=2)
                    
                    LOGGER.info(f"✅ Token auto-refreshé et sauvegardé pour {bot_name}")
        except Exception as e:
            LOGGER.error(f"❌ Erreur sauvegarde token refreshé: {e}")
    
    # Set user authentication avec callback de refresh natif
    await twitch_bot.set_user_authentication(
        token=bot_token.access_token,
        scope=bot_token.scopes,
        refresh_token=bot_token.refresh_token,
        validate=True  # Active validation + auto-refresh si expiré
    )
    
    # Activer le callback de refresh automatique (feature native pyTwitchAPI)
    twitch_bot.user_auth_refresh_callback = save_refreshed_token
    
    # Test API App Token (silencieux)
    try:
        users = []
        async for user in twitch_app.get_users(logins=["twitch"]):
            users.append(user)
        if users:
            user = users[0]
            # Silencieux, juste pour valider que l'API fonctionne
        else:
            LOGGER.warning("Test API : User 'twitch' non trouve")
    except Exception as e:
        LOGGER.error(f"Erreur test API: {e}")
    
    # Initialize message bus architecture
    bus = MessageBus()
    registry = Registry()
    rate_limiter = RateLimiter()
    
    # Analytics Handler
    analytics = AnalyticsHandler(bus)
    
    # Chat Logger (log IRC messages)
    chat_logger = ChatLogger(bus)
    
    # Message Handler (with config for GameLookup, LLM, etc.)
    message_handler = MessageHandler(bus, config)
    
    # Outbound Logger (DISABLED - real IRC send enabled)
    # outbound_logger = OutboundLogger(bus)
    
    # Helix Read-Only (with App Token + timeout)
    helix = HelixReadOnlyClient(twitch_app, bus, helix_timeout=helix_timeout)
    
    # Inject Helix into MessageHandler (for !gc command)
    message_handler.set_helix(helix)
    
    # Stream Announcer (auto-announce stream online/offline)
    announcements_config = config.get("announcements", {})
    monitoring_enabled = announcements_config.get("monitoring", {}).get("enabled", True)
    
    stream_announcer = None
    stream_monitor = None
    eventsub_client = None
    
    if monitoring_enabled:
        # Créer StreamAnnouncer (écoute system.event sur bus)
        stream_announcer = StreamAnnouncer(bus, config)
        
        # Déterminer méthode de monitoring
        monitoring_method = announcements_config.get("monitoring", {}).get("method", "auto")
        polling_interval = announcements_config.get("monitoring", {}).get("polling_interval", 60)
        
        # Préparer broadcaster_ids (requis pour EventSub)
        broadcaster_ids = {}
        for channel in irc_channels:
            user_info = await helix.get_user(channel)
            if user_info:
                broadcaster_ids[channel] = user_info["id"]
                LOGGER.debug(f"📝 Broadcaster ID: {channel} -> {user_info['id']}")
            else:
                LOGGER.warning(f"⚠️ Cannot get broadcaster ID for {channel}")
        
        # Logique hybrid: auto, eventsub, ou polling
        if monitoring_method == "auto":
            # Auto: Try EventSub first, fallback to polling if fails
            try:
                LOGGER.info("🎯 Method=auto: Trying EventSub WebSocket first...")
                eventsub_client = EventSubClient(
                    twitch=twitch_bot,
                    bus=bus,
                    channels=irc_channels,
                    broadcaster_ids=broadcaster_ids
                )
                # Start will be called after IRC is ready
            except Exception as e:
                LOGGER.warning(f"⚠️ EventSub unavailable: {e}, will use polling")
                eventsub_client = None
            
            # Always create polling as fallback
            stream_monitor = StreamMonitor(
                helix=helix,
                bus=bus,
                channels=irc_channels,
                interval=polling_interval
            )
        
        elif monitoring_method == "eventsub":
            # Force EventSub only
            try:
                LOGGER.info("🎯 Method=eventsub: Using EventSub WebSocket only")
                eventsub_client = EventSubClient(
                    twitch=twitch_bot,
                    bus=bus,
                    channels=irc_channels,
                    broadcaster_ids=broadcaster_ids
                )
            except Exception as e:
                LOGGER.error(f"❌ EventSub failed and no fallback: {e}")
                raise
        
        elif monitoring_method == "polling":
            # Force polling only
            LOGGER.info("🎯 Method=polling: Using Helix polling only")
            stream_monitor = StreamMonitor(
                helix=helix,
                bus=bus,
                channels=irc_channels,
                interval=polling_interval
            )
        
        else:
            LOGGER.warning(f"⚠️ Unknown method '{monitoring_method}', using polling")
            stream_monitor = StreamMonitor(
                helix=helix,
                bus=bus,
                channels=irc_channels,
                interval=polling_interval
            )
    
    # IRC Client (with Bot Token + timeout)
    irc_client = IRCClient(
        twitch=twitch_bot,
        bus=bus,
        bot_user_id=bot_user_id,
        bot_login=bot_token.user_login,
        channels=irc_channels,
        irc_send_timeout=irc_send_timeout
    )
    
    # Inject IRC Client into MessageHandler (for !kisscharity broadcast)
    message_handler.set_irc_client(irc_client)
    
    LOGGER.info(f"🚀 KissBot démarré | Channels: {', '.join([f'#{c}' for c in irc_channels])} | Timeouts: IRC={irc_send_timeout}s, Helix={helix_timeout}s")
    
    # Démarrer IRC Client
    print('\n💬 Démarrage IRC Client...')
    print('=' * 70)
    await irc_client.start()
    
    # Attendre que IRC soit connecté
    await asyncio.sleep(2)
    
    # Start Stream Monitoring (EventSub or Polling)
    if eventsub_client:
        print('\n🔌 Démarrage EventSub WebSocket...')
        print('=' * 70)
        try:
            await eventsub_client.start()
            LOGGER.info(f"✅ EventSub started for {len(irc_channels)} channels")
            
            # Si EventSub démarre OK et method=auto, on n'a pas besoin de polling
            if monitoring_method == "auto":
                LOGGER.info("✅ EventSub active, polling fallback disabled")
                stream_monitor = None  # Disable polling fallback
        except Exception as e:
            LOGGER.error(f"❌ EventSub start failed: {e}")
            eventsub_client = None
            
            # Fallback to polling if auto mode
            if monitoring_method == "auto" and stream_monitor:
                LOGGER.warning("⚠️ Falling back to polling mode")
                print('\n📡 Fallback: Démarrage Stream Monitor (Polling)...')
                print('=' * 70)
                await stream_monitor.start()
                LOGGER.info(f"✅ Polling fallback started (interval={polling_interval}s)")
    
    # Démarrer polling si pas EventSub
    if stream_monitor and not eventsub_client:
        print('\n📡 Démarrage Stream Monitor (Polling)...')
        print('=' * 70)
        await stream_monitor.start()
        monitoring_info = f"method={monitoring_method}, interval={polling_interval}s"
        LOGGER.info(f"✅ Stream monitoring started: {monitoring_info}")
    
    # Tests de démonstration Helix
    print('\n🔍 Tests Helix Read-Only:')
    print('=' * 70)
    
    # Test plusieurs channels pour trouver un stream live
    test_channels = irc_channels  # Utiliser les channels de la config
    for channel in test_channels:
        print(f"\n📺 Test channel: {channel}")
        
        # Test 1: Infos utilisateur
        user_info = await helix.get_user(channel)
        if user_info:
            print(f"  ✅ User: {user_info['display_name']} (ID: {user_info['id']})")
        
        # Test 2: Infos stream
        stream_info = await helix.get_stream(channel)
        if stream_info:
            print(f"  🔴 LIVE! {stream_info['title']}")
            print(f"  👥 {stream_info['viewer_count']} viewers")
            print(f"  🎮 {stream_info['game_name']}")
            break  # Arrêter dès qu'on trouve un live
        else:
            print("  ⚪ Offline")
    
    print('=' * 70)
    
    # Attendre que toutes les tasks Analytics finissent
    await asyncio.sleep(0.1)  # Petite pause pour laisser les tasks se terminer
    
    # System Monitoring (CPU/RAM metrics)
    system_monitor = SystemMonitor(
        interval=60,  # Log toutes les 60s
        log_file="metrics.json",
        cpu_threshold=50.0,  # Alerte si CPU > 50%
        ram_threshold_mb=500  # Alerte si RAM > 500MB
    )
    asyncio.create_task(system_monitor.start())
    LOGGER.info("📊 System monitoring started (metrics.json)")
    
    # Inject SystemMonitor into MessageHandler (for !stats command)
    message_handler.set_system_monitor(system_monitor)
    
    # Stats Analytics
    stats = analytics.get_stats()
    chat_count = chat_logger.get_message_count()
    print(f"\n📊 Analytics: {stats['total_events']} événements traités")
    print(f"💬 Chat Logger: {chat_count} messages reçus")
    
    # Info monitoring
    if eventsub_client or stream_monitor:
        if eventsub_client:
            print(f"🔌 Stream Monitoring: EventSub WebSocket (REAL-TIME)")
        elif stream_monitor:
            print(f"📡 Stream Monitoring: Polling (interval={polling_interval}s)")
        
        online_enabled = announcements_config.get("stream_online", {}).get("enabled", True)
        offline_enabled = announcements_config.get("stream_offline", {}).get("enabled", False)
        print(f"   Announcements: online={'✅' if online_enabled else '❌'}, offline={'✅' if offline_enabled else '❌'}")
    else:
        print("📡 Stream Monitoring: DÉSACTIVÉ")
    
    print('\n' + '=' * 70)
    print('🚀 BOT OPERATIONAL - ALL SYSTEMS BOOTED')
    print('=' * 70)
    print(f'📺 Channels: {", ".join([f"#{c}" for c in irc_channels])}')
    print(f'💬 Commands: !ping !uptime !stats !help !gi !gc !ask @mention')
    print(f'📊 Monitoring: CPU/RAM metrics logged to metrics.json')
    print(f'🔌 Transport: IRC Client + EventSub WebSocket')
    print(f'\n💡 Ready to receive messages!')
    print(f'   Press CTRL+C to shutdown...\n')
    
    try:
        # Boucle infinie qui répond bien à KeyboardInterrupt
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        LOGGER.info("CTRL+C détecté, arrêt en cours...")
    finally:
        LOGGER.info("Arret...")
        
        # Stop monitoring (EventSub + Polling + System)
        if eventsub_client:
            await eventsub_client.stop()
        
        if stream_monitor:
            await stream_monitor.stop()
        
        if system_monitor:
            await system_monitor.stop()
        
        await irc_client.stop()
        await twitch_bot.close()
        await twitch_app.close()
        LOGGER.info("Termine")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nAu revoir !")
    except Exception as e:
        LOGGER.error(f"Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
