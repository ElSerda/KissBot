"""
🎯 KissBot Game Commands - TwitchIO 3.x Component Version
Conversion de Cog vers Component pour TwitchIO 3.x
"""

from twitchio.ext import commands

from backends.game_lookup import GameLookup


class GameCommands(commands.Component):
    """🎮 Commandes de jeux - Version TwitchIO 3.x Component"""

    def __init__(self):
        # TwitchIO 3.x : Pas besoin de bot dans __init__
        pass

    @commands.command(name="gameinfo", aliases=["gi"])
    async def game_command(self, ctx: commands.Context, *, game_name: str | None = None):
        """🎮 Recherche d'informations sur un jeu"""
        if not game_name:
            await ctx.send("🎮 Usage: !gameinfo <nom du jeu>")
            return

        try:
            bot = ctx.bot
            # Utiliser la config du bot (GameLookup gère son propre cache)
            if hasattr(bot, 'config'):
                lookup = GameLookup(bot.config)
                result = await lookup.search_game(game_name)
                
                if result:
                    # Utiliser le formatage intégré de GameLookup pour Twitch
                    response = lookup.format_result(result)
                    await ctx.send(response)
                else:
                    await ctx.send(f"❌ Jeu '{game_name}' non trouvé")
            else:
                await ctx.send("❌ Service de jeux non disponible")
                
        except Exception as e:
            await ctx.send(f"❌ Erreur: {e}")

    @commands.command(name="gamecache", aliases=["gc"])
    async def game_cache_command(self, ctx: commands.Context, *, game_name: str | None = None):
        """🗂️ Recherche dans le cache de jeux uniquement"""
        if not game_name:
            await ctx.send("🗂️ Usage: !gamecache <nom du jeu>")
            return

        try:
            bot = ctx.bot
            if hasattr(bot, 'game_cache'):
                result = bot.game_cache.get(game_name)
                if result:
                    response = f"🗂️ Cache: {result['name']} ({result.get('released', 'N/A')})"
                    await ctx.send(response)
                else:
                    await ctx.send(f"❌ '{game_name}' non trouvé dans le cache")
            else:
                await ctx.send("❌ Cache non disponible")
                
        except Exception as e:
            await ctx.send(f"❌ Erreur cache: {e}")
