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
        """📊 Statistiques du bot, cache et LLM"""
        bot = ctx.bot
        start_time = getattr(bot, "start_time", None)

        # Uptime
        if start_time:
            uptime = time.time() - start_time
            uptime_str = f"{uptime:.1f}s"
        else:
            uptime_str = "N/A"

        # Game Cache stats
        cache_info = "N/A"
        if hasattr(bot, "game_cache"):
            try:
                cache_stats = bot.game_cache.get_stats()
                total = cache_stats.get('total_entries', 0)
                hit_rate = cache_stats.get('hit_rate', 0)
                cache_info = f"{total} jeux ({hit_rate:.1%} hit)"
            except Exception:
                cache_info = "Erreur"

        # LLM Stats (Neural Pathway + JokeCache)
        llm_info = "N/A"
        joke_cache_info = "N/A"
        
        if hasattr(bot, '_intelligence_handler'):
            try:
                # Neural metrics (synapse, circuit breaker, latency)
                metrics = bot._intelligence_handler.get_neural_metrics()
                synapse_state = metrics.get('circuit_state', 'N/A')
                success_rate = metrics.get('ema_success_rate', 0)
                avg_latency = metrics.get('ema_latency', 0)
                
                llm_info = f"Circuit:{synapse_state} | Success:{success_rate*100:.0f}% | Lat:{avg_latency:.1f}s"
            except Exception:
                llm_info = "Erreur"
        
        # JokeCache stats (accéder via IntelligenceCommands)
        if hasattr(bot, '_components'):
            for component in bot._components:
                if hasattr(component, 'joke_cache'):
                    try:
                        joke_stats = component.joke_cache.get_stats()
                        joke_entries = joke_stats.get('total_entries', 0)
                        joke_hit_rate = joke_stats.get('hit_rate', 0)
                        joke_cache_info = f"{joke_entries} blagues ({joke_hit_rate:.0f}% hit)"
                    except Exception:
                        joke_cache_info = "Erreur"
                    break

        response = (
            f"📊 Stats: Uptime {uptime_str} | "
            f"GameCache: {cache_info} | "
            f"JokeCache: {joke_cache_info} | "
            f"LLM: {llm_info}"
        )
        await ctx.send(response)

    @commands.command(name="help")
    async def help_command(self, ctx: commands.Context):
        """❓ Liste des commandes disponibles"""
        help_text = (
            "🤖 KissBot TwitchIO 3.x - Commandes: "
            "!ping !stats !help !game [nom] !gc [nom] !ask [question] !joke"
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
