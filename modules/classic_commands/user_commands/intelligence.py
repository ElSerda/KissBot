"""
Commandes d'intelligence artificielle (ask, joke) - Version MessageHandler.

Ces handlers sont appelés par core/message_handler.py avec le format:
    async def handler(handler_instance, msg: ChatMessage, args: str) -> None

Où:
    - handler_instance: Instance de MessageHandler
    - msg: ChatMessage avec user_login, channel, channel_id, etc.
    - args: Arguments après la commande (ex: "question" pour "!ask question")
"""
import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.message_handler import MessageHandler
    from core.message_types import ChatMessage

LOGGER = logging.getLogger(__name__)


async def handle_ask(handler: "MessageHandler", msg: "ChatMessage", question: str) -> None:
    """
    !ask <question>
    Pose une question à l'IA (LLM).
    
    Args:
        handler: Instance MessageHandler
        msg: Message chat entrant
        question: Question posée par l'utilisateur
    """
    from core.message_types import OutboundMessage
    
    # Validation
    if not question or not question.strip():
        response_text = f"@{msg.user_login} 🧠 Usage: !ask <question>"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        return
    
    question = question.strip()
    
    # Check LLM disponible
    if not handler.llm_handler:
        LOGGER.error("❌ !ask called but LLM not initialized")
        response_text = f"@{msg.user_login} ❌ Le système d'IA n'est pas disponible"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        return
    
    try:
        LOGGER.info(f"🧠 LLM request from {msg.user_login}: {question[:50]}...")
        
        # 🔥 RAG: Tentative Wikipedia pour contexte factuel (best-effort)
        wiki_context = None
        try:
            from modules.integrations.wikipedia.wikipedia_handler import search_wikipedia
            
            LOGGER.debug(f"🔍 Attempting Wikipedia lookup for RAG: {question[:30]}...")
            wiki_lang = handler.config.get("wikipedia", {}).get("lang", "fr") if hasattr(handler, 'config') else "fr"
            wiki_context = await asyncio.wait_for(
                search_wikipedia(question, lang=wiki_lang),
                timeout=2.0  # Max 2s pour ne pas bloquer
            )
            
            if wiki_context:
                LOGGER.info(f"✅ Wikipedia context retrieved: {wiki_context['title']}")
            else:
                LOGGER.debug(f"⚠️ No Wikipedia result for: {question[:30]}")
                
        except asyncio.TimeoutError:
            LOGGER.warning(f"⏰ Wikipedia timeout (>2s) for: {question[:30]}")
        except Exception as e:
            LOGGER.warning(f"⚠️ Wikipedia error: {e}")
        
        # Construire la query pour le LLM (avec ou sans contexte Wikipedia)
        if wiki_context:
            # RAG: Injecter le contexte Wikipedia dans le prompt
            enhanced_question = f"""[Contexte factuel Wikipedia: {wiki_context['summary']}]

Question utilisateur: {question}

Réponds en te basant sur ces informations factuelles."""
            LOGGER.debug(f"📚 RAG enabled: Query enhanced with Wikipedia context")
        else:
            # Pas de contexte: prompt normal
            enhanced_question = question
            LOGGER.debug(f"🤷 RAG disabled: No Wikipedia context available")
        
        # Appeler le LLM avec la query (enrichie ou non)
        llm_response = await handler.llm_handler.ask(
            question=enhanced_question,
            user_name=msg.user_login,
            channel=msg.channel,
            game_cache=None,
            channel_id=msg.channel_id  # 🎭 Personnalité par channel
        )
        
        if llm_response:
            # Tronquer le contenu LLM à 450 chars (sécurité IRC/Twitch)
            if len(llm_response) > 450:
                llm_response = llm_response[:447] + "..."
            
            # [ASK] prefix pour maximiser l'espace (vs @username qui prend plus de chars)
            response_text = f"[ASK] {llm_response}"
            
            await handler.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            LOGGER.info(f"✅ LLM response sent to {msg.user_login} ({len(llm_response)} chars)")
        else:
            response_text = f"@{msg.user_login} ❌ Je n'ai pas pu générer une réponse"
            await handler.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            LOGGER.warning(f"⚠️ LLM returned None for {msg.user_login}")
            
    except Exception as e:
        LOGGER.error(f"❌ Error processing !ask: {e}", exc_info=True)
        response_text = f"@{msg.user_login} ❌ Erreur lors du traitement de ta question"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))


async def handle_joke(handler: "MessageHandler", msg: "ChatMessage", args: str) -> None:
    """
    !joke
    Le bot raconte une blague via LLM.
    
    Args:
        handler: Instance MessageHandler
        msg: Message chat entrant
        args: Arguments (ignorés pour !joke)
    """
    from core.message_types import OutboundMessage
    
    # Check LLM disponible
    if not handler.llm_handler:
        LOGGER.error("❌ !joke called but LLM not initialized")
        response_text = f"@{msg.user_login} ❌ Le système d'IA n'est pas disponible"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        return
    
    try:
        LOGGER.info(f"😂 Processing !joke from {msg.user_login}")
        
        # Prompt pour blague
        joke_prompt = "Raconte une blague courte et drôle en français. Sois original et surprenant."
        
        # Appeler le LLM avec context="joke"
        llm_response = await handler.llm_handler.ask(
            question=joke_prompt,
            user_name=msg.user_login,
            channel=msg.channel,
            game_cache=None,
            channel_id=msg.channel_id
        )
        
        if llm_response:
            response_text = f"😂 {llm_response}"
            
            # Tronquer si trop long
            if len(response_text) > 500:
                response_text = response_text[:497] + "..."
            
            await handler.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            LOGGER.info(f"✅ Joke sent to {msg.user_login}")
        else:
            response_text = f"@{msg.user_login} ❌ Pas d'inspiration pour une blague..."
            await handler.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            
    except Exception as e:
        LOGGER.error(f"❌ Error processing !joke: {e}", exc_info=True)
        response_text = f"@{msg.user_login} ❌ Erreur lors de la génération de blague"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
