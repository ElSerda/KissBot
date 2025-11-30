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
    Recherche des infos sur un jeu spécifique avec réponses intelligentes.
    
    Réponses:
    1. Aucun résultat dans les APIs → "❌ Aucun jeu trouvé pour '{query}' dans les bases de données"
    2. Match unique trouvé → "🎮 {game_info}"
    3. Plusieurs résultats proches → "🔍 Plusieurs jeux trouvés : 1. {game1} 2. {game2} ... (typo ?)"
    """
    game_name = cmd.parameter.strip() if cmd.parameter else None
    
    if not game_name:
        await bot.send_message(cmd.room.name, "🎮 Usage: !gameinfo <nom du jeu>")
        return

    try:
        # Import SearchResultType
        from backends.game_lookup import SearchResultType
        
        # Utiliser la nouvelle API v2
        if hasattr(bot.game_lookup, 'search_game_v2'):
            response = await bot.game_lookup.search_game_v2(game_name)
        else:
            # Fallback vers l'ancienne API
            result = await bot.game_lookup.search_game(game_name)
            if result:
                formatted = bot.game_lookup.format_result(result)
                await bot.send_message(cmd.room.name, formatted)
            else:
                await bot.send_message(cmd.room.name, f"❌ Jeu '{game_name}' non trouvé")
            return
        
        if not response:
            await bot.send_message(cmd.room.name, f"❌ Erreur de recherche pour '{game_name}'")
            return
        
        # Cas 1: Aucun résultat dans les APIs
        if response.result_type == SearchResultType.NO_API_RESULTS:
            await bot.send_message(
                cmd.room.name,
                f"❌ Aucun jeu trouvé pour '{game_name}' dans les bases de données (Steam, RAWG, IGDB)"
            )
            return
        
        # Cas 2: Match unique trouvé
        if response.result_type == SearchResultType.SUCCESS and response.best_match:
            formatted = bot.game_lookup.format_result(response.best_match)
            await bot.send_message(cmd.room.name, formatted)
            return
        
        # Cas 3: Plusieurs résultats proches (possible typo)
        if response.result_type == SearchResultType.MULTIPLE_RESULTS and response.best_match:
            # Format: "🔍 Plusieurs jeux trouvés : 1. Game A (2020) | 2. Game B (2019) ... (typo ?)"
            results_text = f"1. {response.best_match.name}"
            if response.best_match.year != "?":
                results_text += f" ({response.best_match.year})"
            
            for i, alt in enumerate(response.alternatives[:2], 2):  # Max 2 alternatives
                results_text += f" | {i}. {alt.name}"
                if alt.year != "?":
                    results_text += f" ({alt.year})"
            
            await bot.send_message(
                cmd.room.name,
                f"🔍 Plusieurs jeux trouvés pour '{game_name}': {results_text} ... (typo ?)"
            )
            return
        
        # Cas 4: Pas de match après ranking (APIs ont retourné des résultats mais aucun bon match)
        if response.result_type == SearchResultType.NO_MATCH:
            await bot.send_message(
                cmd.room.name,
                f"❌ Aucun jeu correspondant à '{game_name}' trouvé ({response.total_candidates} candidats analysés)"
            )
            return
        
        # Fallback
        await bot.send_message(cmd.room.name, f"❌ Jeu '{game_name}' non trouvé")

    except Exception as e:
        LOGGER.error(f"❌ Erreur handle_gi: {e}")
        await bot.send_message(cmd.room.name, f"❌ Erreur: {e}")


async def handle_gs(bot, cmd: ChatCommand):
    """
    !gs / !gamesummary <nom du jeu>
    Affiche uniquement le nom et la description d'un jeu (format minimaliste).
    
    Format: 🎮 Nom du Jeu (année): Description courte...
    """
    game_name = cmd.parameter.strip() if cmd.parameter else None
    
    if not game_name:
        await bot.send_message(cmd.room.name, "🎮 Usage: !gamesummary <nom du jeu>")
        return

    try:
        # Rechercher le jeu
        result = await bot.game_lookup.search_game(game_name)
        
        if not result:
            await bot.send_message(cmd.room.name, f"❌ Jeu '{game_name}' non trouvé")
            return
        
        # Format minimaliste : Nom (année): Description
        output = f"🎮 {result.name}"
        
        if result.year != "?":
            output += f" ({result.year})"
        
        if result.summary:
            # Limiter à 200 caractères pour Twitch
            summary_short = result.summary[:200].strip()
            if len(result.summary) > 200:
                summary_short += "..."
            output += f": {summary_short}"
        else:
            output += " (Aucune description disponible)"
        
        await bot.send_message(cmd.room.name, output)

    except Exception as e:
        LOGGER.error(f"❌ Erreur handle_gs: {e}")
        await bot.send_message(cmd.room.name, f"❌ Erreur: {e}")
