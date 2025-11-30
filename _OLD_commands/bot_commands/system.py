"""Commandes système du bot (ping, uptime, debug)."""
import logging
import time
from twitchAPI.chat import ChatCommand

LOGGER = logging.getLogger(__name__)


async def handle_ping(bot, cmd: ChatCommand):
    """
    !ping
    Vérifie que le bot est actif.
    """
    try:
        await bot.send_message(cmd.room.name, f"@{cmd.user.name} 🏓 Pong! Je suis en ligne!")
    except Exception as e:
        LOGGER.error(f"❌ Erreur handle_ping: {e}")


async def handle_uptime(bot, cmd: ChatCommand):
    """
    !uptime
    Affiche depuis combien de temps le bot est en ligne.
    """
    try:
        if not hasattr(bot, 'start_time'):
            await bot.send_message(cmd.room.name, f"@{cmd.user.name} ⏱️ Uptime non disponible")
            return
        
        uptime_seconds = time.time() - bot.start_time
        hours = int(uptime_seconds // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        seconds = int(uptime_seconds % 60)
        
        await bot.send_message(cmd.room.name, f"@{cmd.user.name} ⏱️ Uptime: {hours}h {minutes}m {seconds}s")
    except Exception as e:
        LOGGER.error(f"❌ Erreur handle_uptime: {e}")
        await bot.send_message(cmd.room.name, f"@{cmd.user.name} ❌ Erreur uptime")
