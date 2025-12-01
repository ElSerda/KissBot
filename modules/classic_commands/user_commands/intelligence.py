"""Commandes d'intelligence artificielle (ask, joke)."""
import logging
from twitchAPI.chat import ChatCommand

LOGGER = logging.getLogger(__name__)


async def handle_ask(bot, cmd: ChatCommand):
    """
    !ask <question>
    Pose une question à l'IA (LLM).
    """
    question = cmd.parameter.strip() if cmd.parameter else None
    
    if not question:
        await bot.send_message(cmd.room.name, "🧠 Usage: !ask <question>")
        return

    try:
        # Lazy init LLM handler
        if not bot._ensure_llm_handler():
            await bot.send_message(cmd.room.name, f"@{cmd.user.name} ❌ Le système d'IA n'est pas disponible")
            return

        # Rate limit check
        if not bot._check_rate_limit(cmd.user.name, bot.cooldown_ask):
            remaining = bot._get_remaining_cooldown(cmd.user.name, bot.cooldown_ask)
            await bot.send_message(cmd.room.name, f"@{cmd.user.name} ⏱️ Cooldown! Attends {remaining:.1f}s")
            return

        # Traitement LLM
        from modules.intelligence.core import process_llm_request
        
        response = await process_llm_request(
            llm_handler=bot.llm_handler,
            prompt=question,
            context="ask",
            user_name=cmd.user.name or "unknown",
            game_cache=bot.game_cache,
        )

        # Réponse
        if not response:
            await bot.send_message(cmd.room.name, f"@{cmd.user.name} ❌ Erreur IA, réessaye plus tard")
        else:
            await bot.send_message(cmd.room.name, f"@{cmd.user.name} {response}")

    except Exception as e:
        LOGGER.error(f"❌ Erreur handle_ask: {e}")
        await bot.send_message(cmd.room.name, f"@{cmd.user.name} ❌ Erreur: {e}")


async def handle_joke(bot, cmd: ChatCommand):
    """
    !joke
    Le bot raconte une blague.
    """
    try:
        # Lazy init LLM handler
        if not bot._ensure_llm_handler():
            await bot.send_message(cmd.room.name, f"@{cmd.user.name} ❌ Le système d'IA n'est pas disponible")
            return

        # Rate limit check
        if not bot._check_rate_limit(cmd.user.name, bot.cooldown_joke):
            remaining = bot._get_remaining_cooldown(cmd.user.name, bot.cooldown_joke)
            await bot.send_message(cmd.room.name, f"@{cmd.user.name} ⏱️ Cooldown! Attends {remaining:.1f}s")
            return

        # Prompt dynamique
        from modules.intelligence.joke_cache import get_dynamic_prompt
        
        base_prompt = "Réponds EN 1 PHRASE MAX EN FRANÇAIS, SANS TE PRÉSENTER, style humoristique : raconte une blague courte"
        dynamic_prompt = get_dynamic_prompt(base_prompt)

        # Cache key
        user_id = cmd.user.name or "unknown"
        cache_key = bot.joke_cache.get_key(user_id, dynamic_prompt)

        # Check cache
        cached_joke = bot.joke_cache.get(cache_key)
        if cached_joke:
            await bot.send_message(cmd.room.name, f"@{cmd.user.name} {cached_joke}")
            return

        # Appel LLM
        from modules.intelligence.core import process_llm_request
        
        response = await process_llm_request(
            llm_handler=bot.llm_handler,
            prompt=dynamic_prompt,
            context="joke",
            user_name=user_id,
            game_cache=bot.game_cache,
        )

        # Cache + réponse
        if response:
            bot.joke_cache.set(cache_key, response)
            await bot.send_message(cmd.room.name, f"@{cmd.user.name} {response}")
        else:
            await bot.send_message(cmd.room.name, f"@{cmd.user.name} ❌ Erreur IA, réessaye plus tard")

    except Exception as e:
        LOGGER.error(f"❌ Erreur handle_joke: {e}")
        await bot.send_message(cmd.room.name, f"@{cmd.user.name} ❌ Erreur: {e}")
