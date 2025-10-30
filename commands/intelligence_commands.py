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

    def _ensure_llm_handler(self, bot) -> bool:
        """
        Initialise LLMHandler si nécessaire (lazy loading)
        
        Returns:
            bool: True si handler disponible, False sinon
        """
        if self.llm_handler is not None:
            return True
            
        try:
            if not hasattr(bot, 'config') or bot.config is None:
                return False
                
            self.config = bot.config
            self.llm_handler = NeuralPathwayManager(bot.config)
            return True
            
        except Exception as e:
            return False

    @commands.command(name="ask")
    async def ask_command(self, ctx: commands.Context, *, question: str | None = None):
        """🧠 Pose une question à l'IA"""

        # Initialiser LLMHandler
        bot = ctx.bot
        if not self._ensure_llm_handler(bot):
            await ctx.send(f"@{ctx.author.name} ❌ Le système d'IA n'est pas disponible")
            return

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

    @commands.command(name="joke")
    async def joke_command(self, ctx: commands.Context):
        """
        🎭 Commande !joke - Le bot raconte une blague courte.
        Pattern optimisé Mistral AI validé .
        """
        try:
            # Initialiser LLM handler
            bot = ctx.bot
            if not self._ensure_llm_handler(bot):
                await ctx.send(f"@{ctx.author.name} ❌ Le système d'IA n'est pas disponible")
                return

            # Rate limiting (10s cooldown comme !ask)
            if hasattr(bot, 'rate_limiter') and not bot.rate_limiter.is_allowed(ctx.author.name, cooldown=10.0):
                remaining = bot.rate_limiter.get_remaining_cooldown(ctx.author.name, cooldown=10.0)
                await ctx.send(f"@{ctx.author.name} ⏱️ Cooldown! Attends {remaining:.1f}s")
                return

            # Prompt POC validé : pattern Mistral AI (0.54s, ~19 tokens, 100% succès)
            # pre_optimized=True → bypass wrapping automatique
            prompt_optimized = "Réponds EN 1 PHRASE MAX EN FRANÇAIS, SANS TE PRÉSENTER, style humoristique : raconte une blague courte"
            
            response = await process_llm_request(
                llm_handler=self.llm_handler,
                prompt=prompt_optimized,
                context="ask",
                user_name=ctx.author.name or "unknown",
                game_cache=None,
                pre_optimized=True,  # ← Prompt déjà au format optimal
                stimulus_class="gen_short"  # ← Force classification courte
            )

            # Réponse Twitch
            if not response:
                await ctx.send(f"@{ctx.author.name} ❌ Erreur IA, réessaye plus tard")
            else:
                await ctx.send(f"@{ctx.author.name} {response}")

        except Exception as e:
            await ctx.send(f"@{ctx.author.name} ❌ Erreur: {e}")


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

    # 🧠 Initialiser handler avec gestion d'erreur
    if not hasattr(bot, "_intelligence_handler"):
        try:
            if not hasattr(bot, 'config') or bot.config is None:
                return None
            bot._intelligence_handler = NeuralPathwayManager(bot.config)
        except Exception:
            return None

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
