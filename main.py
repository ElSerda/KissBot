#!/usr/bin/env python3
"""
🚀 KissBot Production - TwitchIO 3.x

Bot KissBot en production avec TwitchIO 3.x EventSub
et architecture Neural V2.0 complète !
"""

import asyncio
import logging
import sys
from pathlib import Path

# Configuration logging - SERA REMPLACÉE PAR TwitchIO
# (On laisse TwitchIO gérer le logging pour éviter les doublons)
#logging.basicConfig(
#    level=logging.INFO,
#    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
#    handlers=[
#        logging.FileHandler("kissbot_production.log"),
#        logging.StreamHandler()
#    ]
#)

def install_twitchio3():
    """Install TwitchIO 3.x si pas déjà fait"""
    import subprocess

    print("📦 Installation TwitchIO 3.x...")
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install", "twitchio==3.1.0"
        ], capture_output=True, text=True, check=True)
        print("✅ TwitchIO 3.1.0 installé !")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur installation: {e}")
        print(f"Stderr: {e.stderr}")
        return False

def load_config():
    """Charge la configuration"""
    import yaml

    config_file = Path("config/config.yaml")
    if not config_file.exists():
        print("❌ config/config.yaml non trouvé")
        sys.exit(1)

    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)

    print("✅ Configuration chargée")
    return config

async def main():
    """Main TwitchIO 3.x test"""
    print("🚀 KissBot Production - TwitchIO 3.x")
    print("=" * 50)

    # Install TwitchIO 3.x
    if not install_twitchio3():
        print("❌ Impossible d'installer TwitchIO 3.x")
        return

    # Config (pour validation mais pas utilisé par bot3_working)
    config = load_config()
    print(f"✅ Config validée: {len(config)} sections")

    # Import après installation - VERSION PRODUCTION!
    try:
        from bot import KissBotV3Working as KissBot
        print("✅ KissBot Production importé (TwitchIO 3.x EventSub!)")
    except ImportError as e:
        print(f"❌ Erreur import KissBot: {e}")
        return

    # 🎯 Setup TwitchIO 3.x logging AVANT de créer le bot
    import twitchio
    twitchio.utils.setup_logging(level=logging.INFO)

    print("🚀 Démarrage KissBot Production...")

    # Créer et lancer bot
    bot = None
    try:
        print("🤖 Création KissBot Production...")
        # KissBot n'a pas besoin de config en paramètre
        bot = KissBot()

        # Run en production (sans timeout)
        await bot.start()

    except KeyboardInterrupt:
        print("⚡ Arrêt manuel")
        if bot:
            await bot.close()

    except Exception as e:
        print(f"❌ Erreur bot: {e}")
        import traceback
        traceback.print_exc()
        if bot:
            try:
                await bot.close()
            except Exception:
                pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot arrêté")
    except Exception as e:
        print(f"❌ Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
