#!/usr/bin/env python3
"""
KissBot V4 - Twitch Bot with IRC, Helix API, and Stream Monitoring

════════════════════════════════════════════════════════════════════════════
Copyright (c) 2024-2025 ElSerda

Licence propriétaire "Source-Disponible" - Voir LICENSE et EULA_FR.md

✅ Gratuit pour usage personnel, éducatif et recherche
⚠️ Usage commercial nécessite une licence KissBot Pro

Ce bot inclut l'algorithme de filtrage sémantique Δₛ³.
════════════════════════════════════════════════════════════════════════════
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import pathlib

import yaml
from twitchAPI.twitch import Twitch
from twitchAPI.type import AuthScope

from core.message_bus import MessageBus
from core.registry import Registry


def convert_scope_strings_to_enums(scope_strings: list[str]) -> list[AuthScope]:
    """
    Convertit une liste de scope strings (ex: "chat:edit") en AuthScope enum.
    
    Args:
        scope_strings: Liste des scopes en format string
        
    Returns:
        Liste des AuthScope enum correspondants
    """
    scope_map = {
        'chat:edit': AuthScope.CHAT_EDIT,
        'chat:read': AuthScope.CHAT_READ,
        'user:bot': AuthScope.USER_BOT,
        'user:read:chat': AuthScope.USER_READ_CHAT,
        'user:read:moderated_channels': AuthScope.USER_READ_MODERATED_CHANNELS,
        'user:write:chat': AuthScope.USER_WRITE_CHAT,
        'moderator:manage:announcements': AuthScope.MODERATOR_MANAGE_ANNOUNCEMENTS,
        'moderator:read:chatters': AuthScope.MODERATOR_READ_CHATTERS,
        'channel:bot': AuthScope.CHANNEL_BOT,
        'channel:moderate': AuthScope.CHANNEL_MODERATE,
    }
    
    result = []
    for scope_str in scope_strings:
        if scope_str in scope_map:
            result.append(scope_map[scope_str])
        else:
            LOGGER.warning(f"⚠️ Unknown scope string: {scope_str}")
    
    return result
from core.rate_limiter import RateLimiter
from core.analytics_handler import AnalyticsHandler
from core.chat_logger import ChatLogger
from core.message_handler import MessageHandler
from core.outbound_logger import OutboundLogger
from core.stream_announcer import StreamAnnouncer
from database.manager import DatabaseManager
from twitchapi.auth_manager import AuthManager
from twitchapi.monitors.stream_monitor import StreamMonitor
from twitchapi.transports.eventsub_client import EventSubClient
from twitchapi.transports.hub_eventsub_client import HubEventSubClient
from twitchapi.transports.helix_readonly import HelixReadOnlyClient
from twitchapi.transports.irc_client import IRCClient
from core.system_monitor import SystemMonitor

# Logger will be configured in parse_args()
LOGGER = logging.getLogger(__name__)


def parse_args():
    """Parse command-line arguments for single-channel mode"""
    parser = argparse.ArgumentParser(description="KissBot V4 - Twitch Bot")
    parser.add_argument(
        '--channel',
        type=str,
        help='Run bot for a single channel (for multi-process mode)'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config/config.yaml',
        help='Path to config file (default: config/config.yaml)'
    )
    parser.add_argument(
        '--use-db',
        action='store_true',
        help='Use database for tokens instead of config.yaml'
    )
    parser.add_argument(
        '--db',
        type=str,
        default='kissbot.db',
        help='Path to database file (default: kissbot.db)'
    )
    parser.add_argument(
        '--eventsub',
        type=str,
        choices=['direct', 'hub', 'disabled'],
        default='direct',
        help='EventSub mode: direct (own WebSocket), hub (connect to Hub via IPC), disabled (polling only)'
    )
    parser.add_argument(
        '--hub-socket',
        type=str,
        default='/tmp/kissbot_hub.sock',
        help='Path to EventSub Hub IPC socket (default: /tmp/kissbot_hub.sock)'
    )
    return parser.parse_args()


def setup_logging(channel=None):
    """
    Setup hierarchical logging structure per channel
    
    Structure:
        logs/broadcast/{channel}/
        ├── instance.log     (main bot logs, startup, errors)
        ├── chat.log         (all chat messages in/out)
        ├── commands.log     (command executions)
        └── system.log       (CPU, RAM, performance metrics)
    """
    # Base logs directory
    logs_base = pathlib.Path("logs")
    
    if channel:
        # Hierarchical structure per channel
        channel_dir = logs_base / "broadcast" / channel
        channel_dir.mkdir(parents=True, exist_ok=True)
        
        # Main log file for this instance
        log_file = channel_dir / "instance.log"
        
        # Store paths for specialized loggers (used by components)
        log_paths = {
            'instance': channel_dir / "instance.log",
            'chat': channel_dir / "chat.log",
            'commands': channel_dir / "commands.log",
            'system': channel_dir / "system.log"
        }
    else:
        # Legacy: single file for non-channel mode
        logs_base.mkdir(exist_ok=True)
        log_file = logs_base / "kissbot_production.log"
        log_paths = {'instance': log_file}
    
    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ],
        force=True  # Override any existing config
    )
    
    return log_file, log_paths


def write_pid_file(channel=None):
    """Write PID file for process tracking"""
    # Create pids directory if needed
    pids_dir = pathlib.Path("pids")
    pids_dir.mkdir(exist_ok=True)
    
    # Determine PID file
    if channel:
        pid_file = pids_dir / f"{channel}.pid"
    else:
        pid_file = pids_dir / "kissbot.pid"
    
    # Write current PID
    pid = os.getpid()
    with open(pid_file, 'w') as f:
        f.write(str(pid))
    
    LOGGER.info(f"📝 PID {pid} written to {pid_file}")
    return pid_file


def remove_pid_file(pid_file):
    """Remove PID file on shutdown"""
    try:
        if pid_file.exists():
            pid_file.unlink()
            LOGGER.info(f"🗑️ PID file {pid_file} removed")
    except Exception as e:
        LOGGER.warning(f"⚠️ Could not remove PID file {pid_file}: {e}")


def load_config(config_path='config/config.yaml'):
    """Charge config.yaml"""
    config_file = pathlib.Path(config_path)
    if not config_file.exists():
        LOGGER.error(f"Config file {config_path} not found")
        sys.exit(1)
    with open(config_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_token_from_db(db_manager, twitch_login, token_type='bot'):
    """
    Load OAuth token from database.
    
    Args:
        db_manager: Instance of DatabaseManager
        twitch_login: Twitch login (e.g., 'serda_bot', 'el_serda')
        token_type: Type of token ('bot' or 'broadcaster')
    
    Returns:
        Dict with 'access_token', 'refresh_token', 'user_id' or None if not found
    """
    try:
        # Get user from DB
        user = db_manager.get_user_by_login(twitch_login)
        if not user:
            LOGGER.error(f"❌ User {twitch_login} not found in database")
            return None
        
        # Get decrypted tokens by type
        tokens = db_manager.get_tokens(user['id'], token_type=token_type)
        if not tokens:
            LOGGER.error(f"❌ No {token_type} tokens found for user {twitch_login}")
            return None
        
        # Check if tokens need reauth
        if tokens.get('needs_reauth'):
            LOGGER.error(f"❌ Tokens for {twitch_login} (type={token_type}) need reauthorization (refresh failed 3x)")
            return None
        
        # Check status
        status = tokens.get('status', 'valid')
        if status == 'revoked':
            LOGGER.error(f"❌ Tokens for {twitch_login} (type={token_type}) have been revoked")
            return None
        
        LOGGER.info(f"✅ Loaded {token_type} tokens for {twitch_login} from database (expires: {tokens['expires_at']}, status: {status})")
        
        # Parse scopes from JSON if available
        scopes = []
        if tokens.get('scopes'):
            try:
                scope_strings = json.loads(tokens['scopes'])
                scopes = convert_scope_strings_to_enums(scope_strings)
            except (json.JSONDecodeError, TypeError):
                pass
        
        return {
            'access_token': tokens['access_token'],
            'refresh_token': tokens['refresh_token'],
            'user_id': user['twitch_user_id'],
            'scopes': scopes
        }
    
    except Exception as e:
        LOGGER.error(f"❌ Failed to load token from DB for {twitch_login}: {e}")
        return None


async def main():
    """Main entry point: Initialize app token, Helix API, IRC client, and stream monitoring"""
    # Parse args first
    args = parse_args()
    
    # Setup logging (per-channel if --channel specified)
    log_file, log_paths = setup_logging(args.channel)
    
    # Write PID file for process tracking
    pid_file = write_pid_file(args.channel)
    
    # Signal: Process started (for restart-channel script)
    if args.channel:
        starting_flag = pathlib.Path(f"pids/{args.channel}.starting")
        starting_flag.touch()
        LOGGER.info(f"🚦 Starting flag created: {starting_flag}")
    
    print("=" * 70)
    print("KissBot V4 - Twitch Bot with IRC + Helix + Stream Monitoring")
    if args.channel:
        print(f"Mode: SINGLE-CHANNEL ({args.channel})")
    else:
        print("Mode: MULTI-CHANNEL")
    if args.use_db:
        print(f"Token Source: DATABASE ({args.db})")
    else:
        print("Token Source: YAML (config.yaml)")
    print("=" * 70)
    
    config = load_config(args.config)
    
    # Inject log paths into config for components
    config['_log_paths'] = log_paths
    
    twitch_config = config.get("twitch", {})
    bot_config = config.get("bot", {})
    
    # Initialize DatabaseManager if --use-db
    db_manager = None
    if args.use_db:
        try:
            db_manager = DatabaseManager(db_path=args.db)
            LOGGER.info(f"📦 Connected to database: {args.db}")
        except Exception as e:
            LOGGER.error(f"❌ Failed to connect to database: {e}")
            sys.exit(1)
    
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
    
    # Override channels if --channel specified (single-channel mode)
    if args.channel:
        irc_channels = [args.channel]
        LOGGER.info(f"🎯 Single-channel mode: {args.channel}")
    
    if not app_id or not app_secret:
        LOGGER.error("client_id ou client_secret manquant")
        sys.exit(1)
    
    # Initialisation silencieuse
    twitch_app = await Twitch(app_id, app_secret)
    
    # Load bot token (User Token for IRC)
    # Mode DB: load from database (token_type='bot')
    # Mode YAML: load from .tio.tokens.json via AuthManager
    if args.use_db:
        LOGGER.info(f"🔐 Loading bot token from database: {bot_name}")
        bot_token_data = load_token_from_db(db_manager, bot_name, token_type='bot')
        
        if not bot_token_data:
            LOGGER.error(f"❌ Bot token '{bot_name}' introuvable dans la DB !")
            await twitch_app.close()
            sys.exit(1)
        
        # Create a simple object to hold token data
        class TokenData:
            def __init__(self, access_token, refresh_token, user_login, scopes=None):
                self.access_token = access_token
                self.refresh_token = refresh_token
                self.user_login = user_login
                self.scopes = scopes or []
        
        bot_token = TokenData(
            access_token=bot_token_data['access_token'],
            refresh_token=bot_token_data['refresh_token'],
            user_login=bot_name,
            scopes=bot_token_data.get('scopes', [])
        )
        bot_user_id = bot_token_data['user_id']
        
    else:
        LOGGER.info(f"🔐 Loading bot token from YAML: {bot_name}")
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
            if args.use_db:
                # Save to database with token_type
                user = db_manager.get_user_by_login(bot_name)
                if user:
                    # Store refreshed tokens with 4 hours expiry (will be updated on next validate)
                    db_manager.store_tokens(
                        user_id=user['id'],
                        access_token=token,
                        refresh_token=refresh_token,
                        expires_in=14400,  # 4 hours
                        scopes=bot_token.scopes,  # Keep existing scopes
                        token_type='bot',  # This is the bot token
                        status='valid'
                    )
                    LOGGER.info(f"✅ Bot token auto-refreshed and saved to DB for {bot_name}")
            else:
                # Save to .tio.tokens.json (legacy mode)
                token_file = pathlib.Path(".tio.tokens.json")
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
    try:
        if args.use_db and not bot_token.scopes:
            # Mode DB sans scopes : utiliser les scopes standards pour un bot Twitch
            # Convertir les strings en AuthScope enum
            default_scopes = [
                AuthScope.CHAT_EDIT,
                AuthScope.CHAT_READ,
                AuthScope.USER_BOT,
                AuthScope.USER_READ_CHAT,
                AuthScope.USER_READ_MODERATED_CHANNELS,
                AuthScope.USER_WRITE_CHAT
            ]
            LOGGER.info(f"🔍 Using default bot scopes: {[s.value for s in default_scopes]}")
            
            await twitch_bot.set_user_authentication(
                token=bot_token.access_token,
                scope=default_scopes,
                refresh_token=bot_token.refresh_token,
                validate=True  # Active validation + auto-refresh si expiré
            )
            LOGGER.info(f"✅ User authentication set (DB mode, {len(default_scopes)} scopes)")
        else:
            # Mode YAML ou DB avec scopes
            LOGGER.info(f"🔍 Bot scopes loaded from DB: {bot_token.scopes}")
            LOGGER.info(f"🔍 Scopes type: {type(bot_token.scopes)}, first scope type: {type(bot_token.scopes[0]) if bot_token.scopes else 'empty'}")
            LOGGER.info(f"🔍 Scopes values: {[s.value if hasattr(s, 'value') else s for s in bot_token.scopes]}")
            
            await twitch_bot.set_user_authentication(
                token=bot_token.access_token,
                scope=bot_token.scopes,
                refresh_token=bot_token.refresh_token,
                validate=True  # Active validation + auto-refresh si expiré
            )
            LOGGER.info(f"✅ User authentication set (scopes: {len(bot_token.scopes)})")
    except Exception as e:
        LOGGER.error(f"❌ Failed to set user authentication: {e}", exc_info=True)
        await twitch_app.close()
        await twitch_bot.close()
        sys.exit(1)
    except Exception as e:
        LOGGER.error(f"❌ Failed to set user authentication: {e}", exc_info=True)
        await twitch_app.close()
        await twitch_bot.close()
        sys.exit(1)
    
    # Debug: vérifier l'état de l'authentification
    LOGGER.info(f"🔍 Debug: twitch_bot._user_auth_token = {twitch_bot._user_auth_token is not None}")
    LOGGER.info(f"🔍 Debug: twitch_bot._user_auth_refresh_token = {twitch_bot._user_auth_refresh_token is not None}")


    
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
    chat_logger = ChatLogger(bus, config)
    
    # Command Logger (log command executions)
    from core.command_logger import CommandLogger
    command_logger = CommandLogger(bus, config)
    
    # Message Handler (with config for GameLookup, LLM, etc.)
    message_handler = MessageHandler(bus, config)
    
    # Configure MessageBus pour game_lookup_rust (métriques)
    from modules.integrations.game_engine.rust_wrapper import set_message_bus
    set_message_bus(bus)
    
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
        # NEW: Support pour --eventsub=hub mode
        eventsub_mode = args.eventsub if hasattr(args, 'eventsub') else 'direct'
        
        if eventsub_mode == 'disabled':
            # Force polling only
            LOGGER.info("🎯 EventSub disabled via --eventsub=disabled, using polling")
            stream_monitor = StreamMonitor(
                helix=helix,
                bus=bus,
                channels=irc_channels,
                interval=polling_interval
            )
        
        elif eventsub_mode == 'hub':
            # Connect to EventSub Hub via IPC
            LOGGER.info("🎯 EventSub mode: hub (connecting to centralized Hub via IPC)")
            try:
                hub_socket = args.hub_socket if hasattr(args, 'hub_socket') else '/tmp/kissbot_hub.sock'
                eventsub_client = HubEventSubClient(
                    bus=bus,
                    channels=irc_channels,
                    broadcaster_ids=broadcaster_ids,
                    hub_socket_path=hub_socket
                )
                LOGGER.info(f"✅ Hub client created (socket: {hub_socket})")
            except Exception as e:
                LOGGER.error(f"❌ Failed to create Hub client: {e}")
                LOGGER.warning("⚠️  Falling back to polling")
                eventsub_client = None
                stream_monitor = StreamMonitor(
                    helix=helix,
                    bus=bus,
                    channels=irc_channels,
                    interval=polling_interval
                )
        
        elif monitoring_method == "auto":
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
    
    # Signal: IRC connected
    if args.channel:
        irc_flag = pathlib.Path(f"pids/{args.channel}.irc")
        irc_flag.touch()
        LOGGER.info(f"🚦 IRC flag created: {irc_flag}")
    
    # Start Stream Monitoring (EventSub or Polling)
    if eventsub_client:
        print('\n🔌 Démarrage EventSub WebSocket...')
        print('=' * 70)
        try:
            await eventsub_client.start()
            LOGGER.info(f"✅ EventSub started for {len(irc_channels)} channels")
            
            # Signal: EventSub connected
            if args.channel:
                eventsub_flag = pathlib.Path(f"pids/{args.channel}.eventsub")
                eventsub_flag.touch()
                LOGGER.info(f"🚦 EventSub flag created: {eventsub_flag}")
            
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
        config=config,
        interval=60,  # Log toutes les 60s
        cpu_threshold=50.0,  # Alerte si CPU > 50%
        ram_threshold_mb=500  # Alerte si RAM > 500MB
    )
    asyncio.create_task(system_monitor.start())
    LOGGER.info("📊 System monitoring started (dedicated system.log)")
    
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
    
    # Signal readiness to supervisor (for restart-channel script)
    if args.channel:
        ready_file = pathlib.Path(f"pids/{args.channel}.ready")
        ready_file.touch()
        LOGGER.info(f"✅ Ready flag created: {ready_file}")
    
    # Broadcast listener task
    async def broadcast_listener():
        """Listen for broadcast requests from Supervisor"""
        broadcast_file = pathlib.Path(f"pids/{args.channel}.broadcast_in")
        
        while True:
            try:
                if broadcast_file.exists():
                    # Read broadcast request
                    broadcast_data = broadcast_file.read_text().strip()
                    
                    # Delete file immediately
                    broadcast_file.unlink()
                    
                    # Parse: source_channel|message
                    parts = broadcast_data.split("|", 1)
                    if len(parts) != 2:
                        LOGGER.error(f"❌ Invalid broadcast format: {broadcast_data}")
                        await asyncio.sleep(0.1)
                        continue
                    
                    source_channel, message = parts
                    
                    # Format message with source
                    formatted_msg = f"[📢 {source_channel}] {message}"
                    
                    LOGGER.info(
                        f"📢 BROADCAST RECEIVED | source={source_channel} | "
                        f"sending to #{args.channel}"
                    )
                    
                    # Send message via IRC chat instance
                    try:
                        await irc_client.chat.send_message(args.channel, formatted_msg)
                        LOGGER.info(f"✅ Broadcast sent to #{args.channel}")
                    except Exception as e:
                        LOGGER.error(f"❌ Failed to send broadcast: {e}")
            
            except Exception as e:
                LOGGER.error(f"❌ Broadcast listener error: {e}")
            
            await asyncio.sleep(0.1)  # Check every 100ms
    
    # Start broadcast listener
    if args.channel:
        asyncio.create_task(broadcast_listener())
        LOGGER.info("📡 Broadcast listener started")
    
    try:
        # Boucle infinie qui répond bien à KeyboardInterrupt
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        LOGGER.info("CTRL+C détecté, arrêt en cours...")
    finally:
        LOGGER.info("Arret...")
        
        # Remove all status flags (signal shutdown)
        if args.channel:
            for flag_name in ["ready", "eventsub", "irc", "starting"]:
                flag_file = pathlib.Path(f"pids/{args.channel}.{flag_name}")
                if flag_file.exists():
                    flag_file.unlink()
                    LOGGER.debug(f"🧹 Flag removed: {flag_file}")
        
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
        
        # Remove PID file
        remove_pid_file(pid_file)
        
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
