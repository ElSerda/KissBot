"""Commandes de jeu (game category, game info)."""
import logging
from twitchAPI.chat import ChatCommand

LOGGER = logging.getLogger(__name__)


async def handle_gc(bot, cmd: ChatCommand):
    """
    !gc / !gamecategory
    Auto-détecte le jeu du stream actuel et affiche ses infos.
    """
    try:
        broadcaster_name = cmd.room.name if cmd.room else None
        if not broadcaster_name:
            await bot.send_message(cmd.room.name, "❌ Impossible de déterminer le channel")
            return

        # Récupérer le stream actuel
        users_gen = bot.twitch.get_users(logins=[broadcaster_name])
        user = None
        async for u in users_gen:
            user = u
            break

        if not user:
            await bot.send_message(cmd.room.name, f"❌ Utilisateur '{broadcaster_name}' non trouvé")
            return

        # Récupérer les infos du stream
        streams_gen = bot.twitch.get_streams(user_id=[user.id])
        stream = None
        async for s in streams_gen:
            stream = s
            break

        if not stream:
            await bot.send_message(cmd.room.name, f"🎮 @{broadcaster_name} n'est pas sur un jeu Nullos !")
            return

        game_name = stream.game_name
        if not game_name:
            await bot.send_message(cmd.room.name, f"🎮 @{broadcaster_name} n'est pas sur un jeu Nullos !")
            return

        # Rechercher les infos du jeu
        result = await bot.game_lookup.enrich_game_from_igdb_name(game_name)

        if result:
            response = bot.game_lookup.format_result(result)
            await bot.send_message(cmd.room.name, response)
        else:
            await bot.send_message(cmd.room.name, f"❌ Jeu '{game_name}' non trouvé dans les bases de données")

    except Exception as e:
        LOGGER.error(f"❌ Erreur handle_gc: {e}")
        await bot.send_message(cmd.room.name, f"❌ Erreur: {e}")


async def handle_gi(bot, cmd: ChatCommand):
    """
    !gi / !gameinfo <nom du jeu>
    Recherche des infos sur un jeu spécifique.
    """
    game_name = cmd.parameter.strip() if cmd.parameter else None
    
    if not game_name:
        await bot.send_message(cmd.room.name, "🎮 Usage: !gameinfo <nom du jeu>")
        return

    try:
        result = await bot.game_lookup.search_game(game_name)

        if result:
            response = bot.game_lookup.format_result(result)
            await bot.send_message(cmd.room.name, response)
        else:
            await bot.send_message(cmd.room.name, f"❌ Jeu '{game_name}' non trouvé")

    except Exception as e:
        LOGGER.error(f"❌ Erreur handle_gi: {e}")
        await bot.send_message(cmd.room.name, f"❌ Erreur: {e}")
