#!/usr/bin/env python3
"""Test simulation timeout - Phase 2.6"""

import asyncio
import logging
import sys
from pathlib import Path

import yaml
from twitchAPI.twitch import Twitch

from core.message_bus import MessageBus
from core.message_types import OutboundMessage
from twitchapi.auth_manager import AuthManager
from twitchapi.transports.irc_client import IRCClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
    handlers=[logging.StreamHandler()]
)

LOGGER = logging.getLogger(__name__)


def load_config():
    config_file = Path("config/config.yaml")
    with open(config_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


async def main():
    """Test timeout handling"""
    print("🧪 Test Timeout Simulation - Phase 2.6")
    print("=" * 70)
    
    config = load_config()
    twitch_config = config.get("twitch", {})
    timeouts = config.get("timeouts", {})
    
    irc_send_timeout = timeouts.get("irc_send", 5.0)
    
    print(f"⏱️  Config timeout IRC: {irc_send_timeout}s")
    
    app_id = twitch_config.get("client_id")
    app_secret = twitch_config.get("client_secret")
    bot_user_id = "1209350837"
    
    # Init Twitch
    twitch_app = await Twitch(app_id, app_secret)
    auth_manager = AuthManager(twitch_app)
    bot_token = await auth_manager.load_token_from_file(bot_user_id)
    
    if not bot_token:
        LOGGER.error("Token bot introuvable")
        await twitch_app.close()
        sys.exit(1)
    
    twitch_bot = await Twitch(app_id, app_secret)
    await twitch_bot.set_user_authentication(
        token=bot_token.access_token,
        scope=bot_token.scopes,
        refresh_token=bot_token.refresh_token,
        validate=False
    )
    
    # Init bus et IRC
    bus = MessageBus()
    irc_client = IRCClient(
        twitch=twitch_bot,
        bus=bus,
        bot_user_id=bot_user_id,
        bot_login=bot_token.user_login,
        channels=["el_serda"],
        irc_send_timeout=irc_send_timeout
    )
    
    print(f"✅ IRC Client créé avec timeout={irc_send_timeout}s")
    
    # Démarrer IRC
    await irc_client.start()
    await asyncio.sleep(3)  # Attendre connexion
    
    print("\n🎯 Test 1: Message normal (devrait passer)")
    print("-" * 70)
    
    msg1 = OutboundMessage(
        channel="el_serda",
        channel_id="44456636",  # ID el_serda
        text="🧪 Test timeout - Message normal"
    )
    await bus.publish("chat.outbound", msg1)
    await asyncio.sleep(2)
    
    print("\n🎯 Test 2: Simuler blocage avec timeout court")
    print("-" * 70)
    print("⚠️  On va modifier le timeout à 0.5s et envoyer un message...")
    
    # Réduire timeout temporairement
    irc_client.irc_send_timeout = 0.5
    
    msg2 = OutboundMessage(
        channel="el_serda",
        channel_id="44456636",
        text="🧪 Test timeout - Ce message va timeout si IRC lent"
    )
    await bus.publish("chat.outbound", msg2)
    await asyncio.sleep(2)
    
    print("\n🎯 Test 3: Remettre timeout normal")
    print("-" * 70)
    irc_client.irc_send_timeout = irc_send_timeout
    
    msg3 = OutboundMessage(
        channel="el_serda",
        channel_id="44456636",
        text="🧪 Test timeout - Retour à la normale"
    )
    await bus.publish("chat.outbound", msg3)
    await asyncio.sleep(2)
    
    print("\n✅ Tests terminés")
    print("=" * 70)
    print("📊 Résultats:")
    print("  - Message 1 devrait avoir été envoyé")
    print("  - Message 2 devrait avoir timeout (si IRC >0.5s)")
    print("  - Message 3 devrait avoir été envoyé")
    print("\nVérifie les logs ci-dessus pour confirmer ⬆️")
    
    # Cleanup
    await irc_client.stop()
    await twitch_bot.close()
    await twitch_app.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Test interrompu")
    except Exception as e:
        LOGGER.error(f"Erreur: {e}", exc_info=True)
        sys.exit(1)
