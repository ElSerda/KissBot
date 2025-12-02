"""
Commande !wiki - Recherche Wikipedia sans LLM.

Handler pour la commande !wiki qui recherche sur Wikipedia
et retourne un résumé de l'article trouvé.
"""
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.message_handler import MessageHandler
    from core.message_types import ChatMessage

LOGGER = logging.getLogger(__name__)


async def handle_wiki(handler: "MessageHandler", msg: "ChatMessage", query: str) -> None:
    """
    !wiki <sujet> - Recherche Wikipedia
    
    Args:
        handler: Instance MessageHandler
        msg: Message chat entrant
        query: Sujet à rechercher
    """
    from core.message_types import OutboundMessage
    
    if not query or len(query.strip()) == 0:
        response_text = f"@{msg.user_login} 📚 Usage: !wiki <sujet>"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        return
    
    try:
        from modules.integrations.wikipedia.wikipedia_handler import search_wikipedia
        
        # Basic validation
        if len(query.strip()) < 2:
            response_text = f"@{msg.user_login} ❌ Requête trop courte"
            await handler.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            LOGGER.debug(f"❌ Invalid wiki query from {msg.user_login}: {query}")
            return
        
        LOGGER.info(f"📚 Wikipedia request from {msg.user_login}: {query[:50]}...")
        
        # Récupérer la langue depuis config
        wiki_lang = handler.config.get("wikipedia", {}).get("lang", "en") if hasattr(handler, 'config') else "en"
        
        # Rechercher sur Wikipedia (retourne dict ou None)
        result = await search_wikipedia(query, lang=wiki_lang, max_length=350)
        
        # Formater la réponse
        if result:
            summary = result['summary']
            if len(summary) > 350:
                summary = summary[:347] + "..."
            response_text = f"@{msg.user_login} 📚 {result['title']}: {summary} {result['url']}"
        else:
            response_text = f"@{msg.user_login} ❌ Aucune page Wikipedia trouvée pour '{query}'"
        
        # Tronquer si trop long (limite Twitch 500 chars)
        if len(response_text) > 500:
            response_text = response_text[:497] + "..."
        
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        LOGGER.info(f"✅ Wikipedia response sent to {msg.user_login}")
            
    except Exception as e:
        LOGGER.error(f"❌ Error processing !wiki: {e}", exc_info=True)
        response_text = f"@{msg.user_login} ❌ Erreur lors de la recherche Wikipedia"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
