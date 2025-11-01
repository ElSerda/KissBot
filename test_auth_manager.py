#!/usr/bin/env python3
"""Test AuthManager - Load token serda_bot"""

import asyncio
import logging
import sys
from pathlib import Path

import yaml
from twitchAPI.twitch import Twitch

from twitchapi.auth_manager import AuthManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s"
)

LOGGER = logging.getLogger(__name__)


async def main():
    """Test load token serda_bot"""
    print("=" * 70)
    print("TEST AuthManager - Load Token")
    print("=" * 70)
    
    # Load config
    config_file = Path("config/config.yaml")
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    twitch_config = config.get("twitch", {})
    app_id = twitch_config.get("client_id")
    app_secret = twitch_config.get("client_secret")
    
    # Init Twitch (App Token)
    LOGGER.info("Init Twitch API (App Token)...")
    twitch = await Twitch(app_id, app_secret)
    
    # Init AuthManager
    auth_manager = AuthManager(twitch)
    
    # Load token serda_bot (user_id: 1209350837)
    LOGGER.info("\n🔑 Chargement token serda_bot...")
    bot_token = await auth_manager.load_token_from_file("1209350837")
    
    if bot_token:
        print(f"\n✅ Token chargé !")
        print(f"   User: {bot_token.user_login}")
        print(f"   ID: {bot_token.user_id}")
        print(f"   Expire: {bot_token.expires_at}")
        print(f"   Scopes: {bot_token.scopes}")
    else:
        print("\n❌ Échec chargement token")
        sys.exit(1)
    
    # Cleanup
    await twitch.close()
    print("\n✅ Test réussi !")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrompu")
    except Exception as e:
        LOGGER.error(f"Erreur: {e}", exc_info=True)
        sys.exit(1)
