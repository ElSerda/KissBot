"""
🧠 Intelligence Commands - TwitchIO 3.x Component Version
Commandes !ask et gestion des mentions pour LLM
"""

from twitchio.ext import commands

from intelligence.neural_pathway_manager import NeuralPathwayManager
from intelligence.core import process_llm_request


class IntelligenceCommands(commands.Component):
    """🧠 Commandes Intelligence LLM - Version TwitchIO 3.x Component"""

    def __init__(self):
        # TwitchIO 3.x : Pas besoin de bot dans __init__
        self.llm_handler = None

    def _ensure_llm_handler(self, bot):
        """Initialise LLMHandler si nécessaire (lazy loading)"""
        if self.llm_handler is None:
            self.config = bot.config
            self.llm_handler = NeuralPathwayManager(bot.config)
            # Note: LLMHandler n'a pas de update_bot_name dans cette version

    @commands.command(name="ask")
    async def ask_command(self, ctx: commands.Context, *, question: str | None = None):
        """🧠 Pose une question à l'IA"""

        # Initialiser LLMHandler
        bot = ctx.bot
        self._ensure_llm_handler(bot)

        # Vérifier la question
        if not question:
            await ctx.send("🧠 Usage: !ask <question>")
            return

        try:
            # ⏱️ Rate limit check
            if hasattr(bot, 'rate_limiter') and not bot.rate_limiter.is_allowed(ctx.author.name, cooldown=10.0):
                remaining = bot.rate_limiter.get_remaining_cooldown(ctx.author.name, cooldown=10.0)
                await ctx.send(f"@{ctx.author.name} ⏱️ Cooldown! Attends {remaining:.1f}s")
                return

            # 🎮 Utiliser le game_cache du bot si disponible
            game_cache = getattr(bot, "game_cache", None)

            # 🧠 Traitement LLM
            response = await process_llm_request(
                llm_handler=self.llm_handler,
                prompt=question,
                context="ask",
                user_name=ctx.author.name or "unknown",
                game_cache=game_cache,
            )

            # 💬 Réponse Twitch
            if not response:
                await ctx.send(f"@{ctx.author.name} ❌ Erreur IA, réessaye plus tard")
            else:
                await ctx.send(f"@{ctx.author.name} {response}")

        except Exception as e:
            await ctx.send(f"@{ctx.author.name} ❌ Erreur: {e}")

    @commands.command(name="chill")
    async def chill_command(self, ctx: commands.Context, *, message: str | None = None):
        """🧠 Commande legacy !chill (alias de !ask)"""
        if not message:
            await ctx.send("🧠 Usage: !chill <message> (utilise plutôt !ask ou @bot)")
            return

        # Rediriger vers ask_command
        await self.ask_command(ctx, question=message)


# Fonction pour les mentions (@bot)
async def handle_mention_v3(bot, message):
    """
    🧠 Traite les mentions @bot dans TwitchIO 3.x

    Args:
        bot: Instance du bot TwitchIO 3.x
        message: Message TwitchIO EventSub

    Returns:
        str: Réponse générée ou None
    """
    from intelligence.core import extract_mention_message, process_llm_request

    # 🧠 Créer handler une fois
    if not hasattr(bot, "_intelligence_handler"):
        bot._intelligence_handler = NeuralPathwayManager(bot.config)
        # Note: pas de update_bot_name dans cette version

    # 📦 Extraction message - utiliser le nom de bot récupéré dynamiquement
    bot_name = getattr(bot, 'bot_login_name', bot.config.get("bot", {}).get("name", "serda_bot"))
    user_message = extract_mention_message(message.text, bot_name)
    if not user_message:
        return None

    # ⏱️ Rate limit check
    if hasattr(bot, 'rate_limiter') and not bot.rate_limiter.is_allowed(message.chatter.name, cooldown=15.0):
        return None  # Ignorer silencieusement

    # 🎮 Game cache
    game_cache = getattr(bot, "game_cache", None)

    # 🧠 Traitement LLM
    try:
        response = await process_llm_request(
            llm_handler=bot._intelligence_handler,
            prompt=user_message,
            context="mention",
            user_name=message.chatter.name or "unknown",
            game_cache=game_cache,
        )

        return f"@{message.chatter.name} {response}" if response else None

    except Exception as e:
        print(f"❌ Erreur mention LLM: {e}")
        return None
