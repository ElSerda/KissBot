#!/usr/bin/env python3
"""
Test de détection des permissions du bot (mod/VIP status)
- Validation avant implémentation !kisscharity
"""

import asyncio
import logging
from pathlib import Path

import yaml
from twitchAPI.twitch import Twitch

from twitchapi.auth_manager import AuthManager
from twitchapi.transports.irc_client import IRCClient
from core.message_bus import MessageBus

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(name)-20s | %(message)s',
    datefmt='%H:%M:%S'
)

LOGGER = logging.getLogger(__name__)


async def main():
    """Test la détection des permissions du bot"""
    
    # 1. Load config
    config_path = Path("config/config.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    channels = config["twitch"]["channels"]
    bot_login = "serda_bot"  # Hardcodé pour l'instant
    
    LOGGER.info(f"🧪 Test permissions bot sur {len(channels)} channels")
    
    # 2. Auth
    auth = AuthManager(config_path)
    await auth.initialize()
    
    twitch = await auth.get_twitch_client()
    bot_user_id = config["twitch"].get("bot_id", "unknown")
    
    # 3. MessageBus
    bus = MessageBus()
    
    # 4. IRC Client
    irc = IRCClient(
        twitch=twitch,
        bus=bus,
        bot_user_id=str(bot_user_id),
        bot_login=bot_login,
        channels=channels
    )
    
    # 5. Start IRC
    await irc.start()
    
    # 6. Attendre que tous les channels soient rejoints (max 10s)
    LOGGER.info("⏳ Attente connexion aux channels...")
    for _ in range(100):  # 10 secondes max
        await asyncio.sleep(0.1)
        if len(irc._joined_channels) == len(channels):
            break
    
    # 7. Afficher les permissions détectées
    print("\n" + "=" * 80)
    print("🔍 DÉTECTION PERMISSIONS DU BOT")
    print("=" * 80)
    
    for channel in channels:
        perms = irc.get_bot_permissions(channel)
        
        status_emoji = "🛡️ MOD" if perms["is_mod"] else "👤 USER"
        rate_limit = perms["rate_limit_bucket"]
        safe_delay = perms["safe_delay"]
        
        print(f"\n📺 #{channel}")
        print(f"   Status: {status_emoji}")
        print(f"   Rate limit: {rate_limit} msg/30s")
        print(f"   Safe delay (Kiss Mode): {safe_delay:.2f}s entre messages")
        
        if not perms["is_mod"]:
            print(f"   ⚠️  ATTENTION: Bot pas mod → Messages risquent d'être invisibles!")
            print(f"   💡 Solution: /mod {bot_login} sur #{channel}")
    
    print("\n" + "=" * 80)
    print("📊 RÉSUMÉ")
    print("=" * 80)
    
    mod_count = sum(1 for ch in channels if irc.is_bot_mod(ch))
    regular_count = len(channels) - mod_count
    
    print(f"  Channels avec MOD: {mod_count}/{len(channels)}")
    print(f"  Channels sans MOD: {regular_count}/{len(channels)}")
    
    if regular_count > 0:
        print("\n⚠️  WARNING: Le bot n'est pas mod partout!")
        print("   → Broadcast !kisscharity sera LENT sur ces channels (2.5s delay)")
        print("   → Rate limit 20 msg/30s au lieu de 100 msg/30s")
        print("   → Messages peuvent être invisibles sur Twitch!")
        print("\n💡 Recommandation: Donner /mod sur TOUS les channels pour perf optimale")
    else:
        print("\n✅ PARFAIT: Bot est mod partout!")
        print("   → Broadcast !kisscharity sera RAPIDE (~0.43s delay)")
        print("   → Rate limit 100 msg/30s")
    
    print("=" * 80)
    
    # 8. Stop
    await asyncio.sleep(1)
    await irc.stop()
    await auth.close()
    
    LOGGER.info("✅ Test terminé")


if __name__ == "__main__":
    asyncio.run(main())
