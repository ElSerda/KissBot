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

    @commands.command(name="gamecategory", aliases=["gc"])
    async def game_category_command(self, ctx: commands.Context):
        """🎮 Auto-détecte le jeu du stream actuel et recherche ses infos"""
        try:
            bot = ctx.bot
            
            # Récupérer les infos du stream via Twitch API
            broadcaster_name = ctx.channel.name if ctx.channel else None
            if not broadcaster_name:
                await ctx.send("❌ Impossible de déterminer le channel")
                return
            
            # Utiliser l'API Helix pour récupérer le stream
            users = await bot.fetch_users(names=[broadcaster_name])
            if not users:
                await ctx.send(f"❌ Utilisateur '{broadcaster_name}' non trouvé")
                return
            
            user = users[0]
            streams = await bot.fetch_streams(user_ids=[user.id])
            
            if not streams:
                await ctx.send(f"🎮 @{broadcaster_name} n'est pas sur un jeu Nullos !")
                return
            
            stream = streams[0]
            game_name = stream.game_name
            
            if not game_name:
                await ctx.send(f"🎮 @{broadcaster_name} n'est pas sur un jeu Nullos !")
                return
            
            # Rechercher les infos du jeu via enrich_game_from_igdb_name
            # (nom IGDB = source fiable, pas besoin de fuzzy search)
            if hasattr(bot, 'config'):
                lookup = GameLookup(bot.config)
                result = await lookup.enrich_game_from_igdb_name(game_name)
                
                if result:
                    response = lookup.format_result(result)
                    await ctx.send(response)
                else:
                    await ctx.send(f"❌ Jeu '{game_name}' non trouvé dans les bases de données")
            else:
                await ctx.send("❌ Service de jeux non disponible")
                
        except Exception as e:
            await ctx.send(f"❌ Erreur: {e}")
