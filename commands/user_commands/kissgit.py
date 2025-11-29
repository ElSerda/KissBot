"""Commande pour afficher le lien GitHub du bot."""
import logging
from twitchAPI.chat import ChatCommand

LOGGER = logging.getLogger(__name__)


async def handle_kissgit(bot, cmd: ChatCommand):
    """
    !kissgit
    Affiche le lien GitHub du KissBot.
    """
    try:
        response = "🔗 KissBot source: https://github.com/ElSerda/KissBot"
        await bot.send_message(cmd.room.name, response)
        
    except Exception as e:
        LOGGER.error(f"❌ Erreur handle_kissgit: {e}")
        await bot.send_message(cmd.room.name, f"❌ Erreur: {e}")
