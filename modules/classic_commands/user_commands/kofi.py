"""Commande pour afficher le lien Ko-fi de soutien."""
import logging
from twitchAPI.chat import ChatCommand

LOGGER = logging.getLogger(__name__)


async def handle_kbkofi(bot, cmd: ChatCommand):
    """
    !kbkofi
    Affiche le lien Ko-fi pour soutenir le développement de KissBot.
    """
    try:
        response = "☕ Soutenez KissBot ! → https://ko-fi.com/el_serda 💜"
        await bot.send_message(cmd.room.name, response)
        
    except Exception as e:
        LOGGER.error(f"❌ Erreur handle_kbkofi: {e}")
        await bot.send_message(cmd.room.name, f"❌ Erreur: {e}")
