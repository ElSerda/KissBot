"""
🎯 KissBot Utils Commands - TwitchIO 3.x Component Version
Conversion de Cog vers Component pour TwitchIO 3.x
"""
import time

from twitchio.ext import commands

from core.handlers import HandlersFactory


class UtilsCommands(commands.Component):
    """🛠️ Commandes utilitaires - Version TwitchIO 3.x Component"""

    def __init__(self):
        # TwitchIO 3.x : Pas besoin de bot dans __init__
        # Le bot sera auto-injecté dans les méthodes
        self.handlers = HandlersFactory()

    @commands.command(name="ping")
    async def ping_command(self, ctx: commands.Context):
        """🏓 Test de latence et uptime du bot"""
        print("🔍 DEBUG: COMMANDE PING APPELÉE !")
        
        # Version simple qui marche
        bot = ctx.bot
        start_time = getattr(bot, "start_time", None)
        
        if start_time:
            uptime = time.time() - start_time
            uptime_str = f"{uptime:.1f}s"
        else:
            uptime_str = "N/A"
            
        response = f"🏓 Pong! Uptime: {uptime_str} | TwitchIO 3.x EventSub ✅"
        print(f"🔍 DEBUG: Réponse ping: {response}")
        await ctx.send(response)
        print("🔍 DEBUG: PING ENVOYÉ !")

    @commands.command(name="stats")
    async def stats_command(self, ctx: commands.Context):
        """📊 Statistiques du bot et du cache"""
        bot = ctx.bot
        start_time = getattr(bot, "start_time", None)
        
        # Uptime
        if start_time:
            uptime = time.time() - start_time
            uptime_str = f"{uptime:.1f}s"
        else:
            uptime_str = "N/A"

        # Cache stats
        cache_info = "N/A"
        if hasattr(bot, "game_cache"):
            try:
                cache_stats = bot.game_cache.get_stats()
                total = cache_stats.get('total_entries', 0)
                hit_rate = cache_stats.get('hit_rate', 0)
                cache_info = f"{total} jeux, {hit_rate:.1%} hit rate"
            except Exception:
                cache_info = "Erreur"

        response = f"📊 Stats: Uptime {uptime_str} | Cache: {cache_info} | TwitchIO 3.x ✅"
        await ctx.send(response)

    @commands.command(name="help")
    async def help_command(self, ctx: commands.Context):
        """❓ Liste des commandes disponibles"""
        help_text = (
            "🤖 KissBot TwitchIO 3.x - Commandes: "
            "!ping !stats !help !game [nom] !gc [nom] !ask [question]"
        )
        await ctx.send(help_text)

    @commands.command(name="cache")
    async def cache_command(self, ctx: commands.Context):
        """🗂️ Informations sur le cache"""
        bot = ctx.bot
        if hasattr(bot, "game_cache"):
            try:
                stats = bot.game_cache.get_stats()
                cache_info = (
                    f"🗂️ Cache: {stats.get('total_entries', 0)} jeux, "
                    f"{stats.get('hit_rate', 0):.1%} hit rate"
                )
                await ctx.send(cache_info)
            except Exception as e:
                await ctx.send(f"❌ Erreur cache: {e}")
        else:
            await ctx.send("❌ Cache non disponible")
