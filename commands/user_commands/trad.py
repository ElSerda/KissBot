#!/usr/bin/env python3
"""
Commande !trad - Traduction manuelle
Usage: !trad <message>
"""

import logging
from twitchAPI.chat import ChatCommand
from backends.translator import get_translator

LOGGER = logging.getLogger(__name__)


async def handle_trad(bot, cmd: ChatCommand):
    """
    !trad <message> - Traduit un message en français
    
    Exemples:
        !trad Hello world
        !trad ¿Cómo estás?
        !trad Guten Tag
    """
    if not cmd.parameter:
        await cmd.reply("Usage: !trad <message>")
        return
    
    translator = get_translator()
    
    # Traduire vers français
    result = await translator.translate(cmd.parameter, target_lang='fr')
    
    if not result:
        await cmd.reply(f"@{cmd.user.name} ❌ Translation failed")
        return
    
    source_lang, translation = result
    lang_name = translator.get_language_name(source_lang)
    
    # Si déjà en français
    if source_lang == 'fr':
        await cmd.reply(f"@{cmd.user.name} 🇫🇷 Already in French!")
        return
    
    # Réponse avec traduction
    await cmd.reply(
        f"@{cmd.user.name} 🌍 [{lang_name.upper()}] → 🇫🇷 {translation}"
    )
    
    LOGGER.info(f"📝 Translated for {cmd.user.name}: {source_lang} → fr")
