#!/usr/bin/env python3
"""
🚀 KissBot V3 - Architecture Modulaire

Architecture événementielle avec séparation IRC / Helix / EventSub
- MessageBus: Pub/sub pour communication décuplée
- Registry: État centralisé (channels, badges, scopes)
- RateLimiter: Protection anti-ban (par channel)
- Transports: IRC (listener), Helix (sender avec badge), EventSub (analytics)
- MessageHandler: Logique métier (commandes)
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

import yaml
from twitchAPI.twitch import Twitch
from twitchAPI.type import AuthScope

# Core architecture
from core.message_bus import MessageBus
from core.registry import Registry
from core.rate_limiter import RateLimiter
from core.message_handler import MessageHandler

# Transports
from transports.irc_client import IRCClient
from transports.helix_client import HelixClient
from transports.eventsub_client import EventSubClient

# Configuration logging
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
    """Charge la configuration depuis config.yaml"""
    config_file = Path("config/config.yaml")
    if not config_file.exists():
        LOGGER.error("❌ config/config.yaml introuvable")
        sys.exit(1)

    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    LOGGER.info("✅ Configuration chargée")
    return config


async def setup_twitch_api(config: dict) -> Twitch:
    """
    Initialise l'API Twitch avec le token du BOT
    
    Returns:
        Instance Twitch authentifiée avec le bot
    """
    twitch_config = config.get("twitch", {})
    
    app_id = twitch_config.get("client_id")
    app_secret = twitch_config.get("client_secret")
    bot_id = twitch_config.get("bot_id")
    
    if not app_id or not app_secret:
        LOGGER.error("❌ client_id ou client_secret manquant")
        sys.exit(1)
    
    tokens = twitch_config.get("tokens", {})
    
    # === INSTANCE BOT (IRC + Helix + EventSub) ===
    LOGGER.info("🔧 Initialisation Twitch API...")
    twitch = await Twitch(app_id, app_secret)
    
    bot_token = None
    bot_refresh = None
    for account_name, token_info in tokens.items():
        if str(token_info.get("user_id")) == str(bot_id):
            bot_token = token_info.get("access_token")
            bot_refresh = token_info.get("refresh_token")
            LOGGER.info(f"🔑 Token trouvé pour {account_name}")
            break
    
    if not bot_token:
        LOGGER.error("❌ Token BOT introuvable")
        await twitch.close()
        sys.exit(1)
    
    # Tous les scopes nécessaires
    bot_scopes = [
        AuthScope.CHAT_READ,
        AuthScope.CHAT_EDIT,
        AuthScope.USER_READ_CHAT,  # EventSub
        AuthScope.USER_BOT,        # Badge
        AuthScope.USER_WRITE_CHAT  # Helix send + Badge
    ]
    
    LOGGER.info("🔐 Authentification...")
    try:
        await twitch.set_user_authentication(bot_token, bot_scopes, bot_refresh)
        LOGGER.info("✅ Authentification réussie!")
        return twitch
    except Exception as e:
        LOGGER.error(f"❌ Erreur auth: {e}")
        await twitch.close()
        sys.exit(1)


async def setup_broadcaster_twitch_api(config: dict, broadcaster_id: str) -> Optional[Twitch]:
    """
    Initialise une 2ème instance Twitch avec le token du BROADCASTER
    Nécessaire pour EventSub subscriptions.
    
    Returns:
        Instance Twitch authentifiée avec le broadcaster, ou None si pas de token
    """
    twitch_config = config.get("twitch", {})
    
    app_id = twitch_config.get("client_id")
    app_secret = twitch_config.get("client_secret")
    tokens = twitch_config.get("tokens", {})
    
    # Trouver le token du broadcaster
    broadcaster_token = None
    broadcaster_refresh = None
    for account_name, token_info in tokens.items():
        if str(token_info.get("user_id")) == str(broadcaster_id):
            broadcaster_token = token_info.get("access_token")
            broadcaster_refresh = token_info.get("refresh_token")
            LOGGER.info(f"🔑 Token broadcaster trouvé pour {account_name}")
            break
    
    if not broadcaster_token:
        LOGGER.warning("⚠️  Token broadcaster introuvable - EventSub non disponible")
        return None
    
    # Créer instance broadcaster
    LOGGER.info("🔧 Initialisation Twitch API (broadcaster)...")
    twitch_broadcaster = await Twitch(app_id, app_secret)
    
    broadcaster_scopes = [
        AuthScope.USER_READ_CHAT,  # EventSub
        AuthScope.MODERATOR_READ_FOLLOWERS
    ]
    
    try:
        await twitch_broadcaster.set_user_authentication(
            broadcaster_token, 
            broadcaster_scopes, 
            broadcaster_refresh
        )
        LOGGER.info("✅ Authentification broadcaster réussie!")
        return twitch_broadcaster
    except Exception as e:
        LOGGER.error(f"❌ Erreur auth broadcaster: {e}")
        await twitch_broadcaster.close()
        return None


async def main():
    """Point d'entrée principal - Architecture modulaire V3"""
    print("=" * 70)
    print("🚀 KissBot V3 - Architecture Modulaire")
    print("   IRC (listener) + Helix (badge sender) + EventSub (analytics)")
    print("=" * 70)
    
    # Charger config
    config = load_config()
    twitch_config = config.get("twitch", {})
    channels = twitch_config.get("channels", [])
    bot_login = twitch_config.get("bot_login", "kissbot")
    
    if not channels:
        LOGGER.error("❌ Aucun channel configuré")
        sys.exit(1)
    
    # Initialiser l'instance Twitch (bot)
    twitch = await setup_twitch_api(config)
    
    # Initialiser l'instance Twitch (broadcaster) pour EventSub
    broadcaster_id = twitch_config.get("broadcaster_id")
    twitch_broadcaster = await setup_broadcaster_twitch_api(config, broadcaster_id) if broadcaster_id else None
    
    # ========================================================================
    # DEBUG: Lister tous les tokens disponibles
    # ========================================================================
    
    LOGGER.info("📋 Tokens disponibles dans la config:")
    tokens = twitch_config.get("tokens", {})
    for account_name, token_info in tokens.items():
        user_id = token_info.get("user_id", "N/A")
        access_token_preview = token_info.get("access_token", "")[:10] + "..." if token_info.get("access_token") else "N/A"
        LOGGER.info(f"  - {account_name} (ID: {user_id}) → Token: {access_token_preview}")
    
    bot_id = twitch_config.get("bot_id")
    broadcaster_id = twitch_config.get("broadcaster_id")
    LOGGER.info(f"🎯 Config: bot_id={bot_id}, broadcaster_id={broadcaster_id}")
    
    # ========================================================================
    # ARCHITECTURE MODULAIRE
    # ========================================================================
    
    LOGGER.info("🏗️  Initialisation architecture...")
    
    # 1. Core Infrastructure
    bus = MessageBus()
    registry = Registry()
    rate_limiter = RateLimiter(
        per30_non_verified=18,
        per30_verified=90,
        per30_mod=100
    )
    
    # 2. Récupérer et stocker les scopes via l'API Twitch
    LOGGER.info("🔍 Récupération des scopes...")
    try:
        import requests
        tokens = twitch_config.get("tokens", {})
        bot_id = twitch_config.get("bot_id")
        
        # Trouver le token du bot
        user_token = None
        for account_name, token_info in tokens.items():
            if str(token_info.get("user_id")) == str(bot_id):
                user_token = token_info.get("access_token")
                break
        
        if user_token:
            # Valider le token via l'API Twitch
            response = requests.get(
                "https://id.twitch.tv/oauth2/validate",
                headers={"Authorization": f"OAuth {user_token}"},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                scopes = set(data.get("scopes", []))
                registry.set_bot_scopes(scopes)
                LOGGER.info(f"✅ Scopes récupérés: {len(scopes)} scopes")
            else:
                LOGGER.warning(f"⚠️  Validation token failed: {response.status_code}")
        else:
            LOGGER.warning("⚠️  Token bot introuvable")
    except Exception as e:
        LOGGER.warning(f"⚠️  Erreur récupération scopes: {e}")
    
    # Vérifier les scopes critiques
    has_user_write = registry.has_scope("user:write:chat")
    has_user_bot = registry.has_scope("user:bot")
    
    if has_user_write:
        LOGGER.info("✅ Scope user:write:chat disponible (Helix send)")
    else:
        LOGGER.warning("⚠️  Scope user:write:chat manquant (pas de Helix)")
    
    if has_user_bot:
        LOGGER.info("✅ Scope user:bot disponible (Badge)")
        # 🎖️ Si on a user:bot ET channel:bot, on peut activer le badge pour tous les channels
        has_channel_bot = registry.has_scope("channel:bot")
        if has_channel_bot:
            LOGGER.info("✅ Scope channel:bot disponible - Badge activé pour tous les channels!")
            # Activer le badge pour tous les channels configurés
            for channel in channels:
                # On n'a pas encore les IDs, mais EventSub/IRC les ajoutera plus tard
                # On va juste marquer qu'on PEUT utiliser le badge
                pass
        else:
            LOGGER.warning("⚠️  Scope channel:bot manquant - Badge limité")
    else:
        LOGGER.warning("⚠️  Scope user:bot manquant (pas de badge)")
    
    # 3. Message Handler (Cerveau)
    LOGGER.info("🧠 Initialisation MessageHandler...")
    handler = MessageHandler(bus, registry, config, twitch)
    
    # 4. Transports
    LOGGER.info("📡 Initialisation transports...")
    
    bot_id = twitch_config.get("bot_id")  # Récupérer le bot_id depuis la config
    
    irc_client = IRCClient(
        twitch=twitch,
        bus=bus,
        registry=registry,
        channels=channels,
        bot_login=bot_login
    )
    
    helix_client = HelixClient(
        twitch=twitch,
        bus=bus,
        registry=registry,
        rate_limiter=rate_limiter,
        bot_login=bot_login,
        bot_id=str(bot_id) if bot_id else None  # Passer le bot_id explicitement
    )
    
    eventsub_client = EventSubClient(
        twitch=twitch_broadcaster if twitch_broadcaster else twitch,  # Utiliser broadcaster si dispo!
        bus=bus,
        registry=registry,
        channels=channels,
        bot_login=bot_login,
        broadcaster_id=str(broadcaster_id) if broadcaster_id and twitch_broadcaster else None
    )
    
    LOGGER.info("✅ Architecture initialisée!")
    
    # ========================================================================
    # DÉMARRAGE
    # ========================================================================
    
    LOGGER.info("🚀 Démarrage des transports...")
    
    # Créer et démarrer les tasks en arrière-plan
    irc_task = asyncio.create_task(irc_client.run())
    helix_task = asyncio.create_task(helix_client.run())
    eventsub_task = asyncio.create_task(eventsub_client.run())
    
    # Attendre que les transports soient VRAIMENT prêts (pas juste started)
    # IRC prend ~3s, donc on attend max 5s
    max_wait = 5.0
    waited = 0.0
    while waited < max_wait:
        await asyncio.sleep(0.5)
        waited += 0.5
        # Check si au moins IRC est connecté (essentiel)
        if irc_client._running and irc_client.chat:
            break
    
    # Maintenant on peut afficher le prompt SANS bloquer pendant le démarrage
    print('\n✅ Bot actif ! Appuyez sur ENTRÉE pour arrêter...\n')
    
    # Pattern pytwitchAPI: input() bloquant dans un executor
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, 
            input  # Juste input(), pas lambda
        )
    except (KeyboardInterrupt, EOFError):
        LOGGER.info("⚡ Interruption détectée")
    finally:
        # Arrêt propre
        LOGGER.info("🛑 Arrêt du bot...")
        
        # Annuler les tasks
        irc_task.cancel()
        helix_task.cancel()
        eventsub_task.cancel()
        
        # Attendre l'annulation
        await asyncio.gather(irc_task, helix_task, eventsub_task, return_exceptions=True)
        
        # Fermer les instances Twitch
        await twitch.close()
        if twitch_broadcaster:
            await twitch_broadcaster.close()
        
        LOGGER.info("👋 Bot arrêté proprement")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Au revoir !")
    except Exception as e:
        LOGGER.error(f"❌ Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

async def _wait_for_shutdown():
    """Attend le signal d'arrêt"""
    await SHUTDOWN_EVENT.wait()
    LOGGER.info(" Shutdown demandé")

