"""
Commande !trad - Traduction manuelle.

Handler pour la commande !trad avec plusieurs modes:
- !trad <message>           → Traduit vers le français
- !trad <lang>:<message>    → Traduit vers la langue spécifiée (es, en, pt...)
- !trad auto:@user <msg>    → Traduit vers la dernière langue connue de @user

Rate limiting (sauf pour les whitelistés).
"""
import logging
import re
import time
from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from core.message_handler import MessageHandler
    from core.message_types import ChatMessage

LOGGER = logging.getLogger(__name__)

# Regex pour parser la syntaxe !trad <lang>: <message>
# Supporte: es:, en:, pt:, auto:, zh-cn:, etc.
# Espace optionnel après ":" pour permettre l'autocomplétion Twitch avec Tab
LANG_PREFIX_PATTERN = re.compile(r'^(auto|[a-z]{2}(?:-[a-z]{2})?):\s*(.+)$', re.IGNORECASE)
# Regex pour extraire @mention
MENTION_PATTERN = re.compile(r'@(\w+)')


def parse_trad_args(args: str) -> Tuple[Optional[str], Optional[str], str]:
    """
    Parse les arguments de !trad
    
    Returns:
        (target_lang, mention_user, message)
        - target_lang: code langue si spécifié (es, en, auto), None sinon
        - mention_user: username mentionné si mode auto:, None sinon
        - message: le message à traduire
    """
    args = args.strip()
    
    # Check si format <lang>:<message>
    match = LANG_PREFIX_PATTERN.match(args)
    if match:
        lang_code = match.group(1).lower()
        message = match.group(2).strip()
        
        # Mode spécial "auto:" - chercher @mention
        if lang_code == 'auto':
            mention_match = MENTION_PATTERN.search(message)
            if mention_match:
                mention_user = mention_match.group(1).lower()
                # Retirer le @mention du message pour la traduction
                clean_message = MENTION_PATTERN.sub('', message).strip()
                return ('auto', mention_user, clean_message if clean_message else message)
            # auto: sans @mention = erreur
            return ('auto', None, message)
        
        return (lang_code, None, message)
    
    # Pas de préfixe = traduction vers français (comportement par défaut)
    return (None, None, args)


async def handle_trad(handler: "MessageHandler", msg: "ChatMessage", args: str) -> None:
    """
    !trad - Traduction manuelle avec plusieurs modes
    
    Syntaxes:
    - !trad <message>           → Traduit vers le français
    - !trad es:<message>        → Traduit vers l'espagnol
    - !trad auto:@user <msg>    → Traduit vers la langue de @user
    
    Args:
        handler: Instance MessageHandler
        msg: Message chat entrant
        args: Arguments de la commande
    """
    from core.message_types import OutboundMessage
    
    if not args:
        usage = (
            f"@{msg.user_login} Usage: !trad <message> | "
            f"!trad <lang>:<message> | !trad auto:@user <message>"
        )
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=usage,
            prefer="irc"
        ))
        return
    
    # Rate limiting: 30s cooldown SAUF pour whitelistés
    is_whitelisted = handler.dev_whitelist.is_dev(msg.user_login)
    
    if not is_whitelisted:
        current_time = time.time()
        last_time = handler._trad_last_time.get(msg.user_id, 0)
        
        if current_time - last_time < handler._trad_cooldown:
            cooldown_remaining = int(handler._trad_cooldown - (current_time - last_time))
            response_text = f"@{msg.user_login} ⏰ Cooldown: {cooldown_remaining}s restants"
            await handler.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            return
        
        # Update cooldown
        handler._trad_last_time[msg.user_id] = current_time
    
    # Parser les arguments
    target_lang, mention_user, message = parse_trad_args(args)
    
    # Mode auto: - récupérer la langue de l'utilisateur mentionné
    if target_lang == 'auto':
        if not mention_user:
            response_text = f"@{msg.user_login} ❌ Usage: !trad auto:@username <message>"
            await handler.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            return
        
        # Chercher la langue mémorisée
        user_lang = handler.translator.get_user_language(msg.channel, mention_user)
        if not user_lang:
            response_text = (
                f"@{msg.user_login} ❌ Langue de @{mention_user} inconnue. "
                f"Attends qu'il parle dans le chat!"
            )
            await handler.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            return
        
        target_lang = user_lang
        LOGGER.info(f"🎯 Auto-detected target language for @{mention_user}: {target_lang}")
    
    # Valider la langue cible si spécifiée
    if target_lang and target_lang != 'fr':
        if not handler.translator.is_supported_language(target_lang):
            langs = handler.translator.list_supported_languages()
            response_text = f"@{msg.user_login} ❌ Langue '{target_lang}' non supportée. Dispo: {langs}"
            await handler.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            return
    
    # Langue par défaut = français
    if not target_lang:
        target_lang = 'fr'
    
    # Traduire
    result = await handler.translator.translate(message, target_lang=target_lang)
    
    if not result:
        response_text = f"@{msg.user_login} ❌ Translation failed"
    else:
        source_lang, translation = result
        target_name = handler.translator.get_language_name(target_lang)
        
        if source_lang == target_lang:
            response_text = f"@{msg.user_login} ✅ Déjà en {target_name}!"
        else:
            # Format différent selon le mode
            if mention_user:
                # Mode auto: - réponse dirigée vers l'utilisateur mentionné
                response_text = f"🌍 @{mention_user} {translation}"
            else:
                # Mode normal
                source_name = handler.translator.get_language_name(source_lang)
                response_text = f"🌍 [{source_name}→{target_name}] {translation}"
    
    await handler.bus.publish("chat.outbound", OutboundMessage(
        channel=msg.channel,
        channel_id=msg.channel_id,
        text=response_text,
        prefer="irc"
    ))
    
    LOGGER.info(f"✅ [trad] {msg.user_login}: {source_lang}→{target_lang}")
