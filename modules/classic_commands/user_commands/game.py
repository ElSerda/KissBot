"""
Game Commands Module - !gi, !gs, !gc
=====================================
Commandes de recherche de jeux vidéo.

Pattern: handler(MessageHandler, ChatMessage, args: str) -> None
"""

import time
import logging
from twitchAPI.chat import ChatMessage

LOGGER = logging.getLogger("kissbot.commands.game")


async def handle_gi(handler, msg: ChatMessage, args: str = "") -> None:
    """
    !gi <game> - Information complète sur un jeu
    
    Args:
        handler: Instance de MessageHandler (accès à game_lookup, bus)
        msg: Message Twitch
        args: Nom du jeu à rechercher
    """
    from core.message_types import OutboundMessage
    
    if not handler.game_lookup:
        response_text = f"@{msg.user_login} ❌ Game lookup not available"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        return
    
    game_name = args.strip()
    if not game_name:
        response_text = f"@{msg.user_login} Usage: !gi <game name>"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        return
    
    try:
        start_total = time.perf_counter()
        LOGGER.info(f"🎮 Searching game: {game_name}")
        
        # Direct API search (SQLite cache handled inside search_game)
        start_lookup = time.perf_counter()
        game = await handler.game_lookup.search_game(game_name)
        elapsed_lookup_ms = (time.perf_counter() - start_lookup) * 1000
        
        if game:
            LOGGER.info(f"✅ Game found: {game.name} | ⏱️ {elapsed_lookup_ms:.1f}ms")
        else:
            LOGGER.info(f"⏭️ Game not found | ⏱️ {elapsed_lookup_ms:.1f}ms")
        
        if not game:
            elapsed_total_ms = (time.perf_counter() - start_total) * 1000
            response_text = f"@{msg.user_login} ❌ Game not found: {game_name}"
            LOGGER.info(f"❌ Game not found: {game_name} | ⏱️ Total: {elapsed_total_ms:.1f}ms")
        else:
            start_format = time.perf_counter()
            # Utiliser format_result() en mode complet (pas compact)
            game_info = handler.game_lookup.format_result(game, compact=False)
            response_text = f"@{msg.user_login} {game_info}"
            
            elapsed_format_us = (time.perf_counter() - start_format) * 1_000_000
            elapsed_total_ms = (time.perf_counter() - start_total) * 1000
            LOGGER.info(
                f"✅ Game info sent: {game.name} | "
                f"⏱️ Format: {elapsed_format_us:.1f}µs | Total: {elapsed_total_ms:.1f}ms"
            )
        
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        
    except Exception as e:
        LOGGER.error(f"❌ Error searching game: {e}", exc_info=True)
        response_text = f"@{msg.user_login} ❌ Error searching game"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))


async def handle_gs(handler, msg: ChatMessage, args: str = "") -> None:
    """
    !gs <game> - Résumé court d'un jeu (nom + description uniquement)
    
    Args:
        handler: Instance de MessageHandler
        msg: Message Twitch
        args: Nom du jeu à rechercher
    """
    from core.message_types import OutboundMessage
    
    if not handler.game_lookup:
        response_text = f"@{msg.user_login} ❌ Game lookup not available"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        return
    
    game_name = args.strip()
    if not game_name:
        response_text = f"@{msg.user_login} Usage: !gs <game name>"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        return
    
    try:
        start_total = time.perf_counter()
        LOGGER.info(f"🎮 Searching game summary: {game_name}")
        
        # Rechercher le jeu
        game = await handler.game_lookup.search_game(game_name)
        elapsed_lookup_ms = (time.perf_counter() - start_total) * 1000
        
        if not game:
            response_text = f"@{msg.user_login} ❌ Game not found: {game_name}"
            LOGGER.info(f"❌ Game not found: {game_name} | ⏱️ {elapsed_lookup_ms:.1f}ms")
        else:
            # Format minimaliste : Nom (année): Description
            output = f"🎮 {game.name}"
            
            if game.year != "?":
                output += f" ({game.year})"
            
            if game.summary:
                # Limiter à 200 caractères pour Twitch
                summary_short = game.summary[:200].strip()
                if len(game.summary) > 200:
                    summary_short += "..."
                output += f": {summary_short}"
            else:
                output += " (Aucune description disponible)"
            
            response_text = f"@{msg.user_login} {output}"
            LOGGER.info(f"✅ Game summary sent: {game.name} | ⏱️ {elapsed_lookup_ms:.1f}ms")
        
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        
    except Exception as e:
        LOGGER.error(f"❌ Error searching game summary: {e}", exc_info=True)
        response_text = f"@{msg.user_login} ❌ Error searching game"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))


async def handle_gc(handler, msg: ChatMessage, args: str = "") -> None:
    """
    !gc - Jeu en cours du streamer (enrichi)
    
    Utilise Helix get_stream() pour récupérer game_name,
    puis enrichit avec GameLookup pour infos complètes.
    Si offline, message automatique.
    
    Args:
        handler: Instance de MessageHandler (accès à helix, game_lookup, bus)
        msg: Message Twitch
        args: Non utilisé pour cette commande
    """
    from core.message_types import OutboundMessage
    
    if not handler.helix:
        response_text = f"@{msg.user_login} ❌ Helix client not available"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        LOGGER.error("❌ !gc called but Helix not injected")
        return
    
    try:
        # Récupérer les infos du stream
        stream_info = await handler.helix.get_stream(msg.channel)
        
        if stream_info and stream_info.get("game_name"):
            # Stream LIVE → Enrichir avec GameLookup
            game_name = stream_info["game_name"]
            game_id = stream_info.get("game_id")  # Twitch category ID
            viewer_count = stream_info.get("viewer_count", 0)
            
            # Enrichissement du jeu via recherche par nom (fuzzy match)
            game = None
            if handler.game_lookup:
                LOGGER.info(f"🎮 Enriching game by name: {game_name}")
                game = await handler.game_lookup.search_game(game_name)
                
            if game:
                # Format COMPACT (sans confidence/sources pour gagner de l'espace)
                game_info = handler.game_lookup.format_result(game, compact=True)
                
                # Ajouter la description si disponible
                if game.summary:
                    # Calculer l'espace disponible (limite Twitch ~500 chars)
                    prefix = f"@{msg.user_login} {msg.channel} joue actuellement à {game_info} | "
                    max_summary_len = 450 - len(prefix)  # Marge de sécurité
                    
                    # Tronquer intelligemment (phrase complète si possible)
                    summary = game.summary[:max_summary_len]
                    if len(game.summary) > max_summary_len:
                        # Chercher dernier point ou espace pour couper proprement
                        last_dot = summary.rfind('. ')
                        last_space = summary.rfind(' ')
                        if last_dot > max_summary_len * 0.7:  # Si point à 70%+, couper là
                            summary = summary[:last_dot + 1]
                        elif last_space > max_summary_len * 0.8:  # Sinon dernier espace
                            summary = summary[:last_space] + "..."
                        else:
                            summary += "..."
                    
                    response_text = f"{prefix}{summary}"
                else:
                    # Pas de description, format compact suffit
                    response_text = (
                        f"@{msg.user_login} {msg.channel} joue actuellement à "
                        f"{game_info}"
                    )
            else:
                # Pas de GameLookup ou recherche échouée → fallback simple
                response_text = (
                    f"@{msg.user_login} {msg.channel} joue actuellement à "
                    f"**{game_name}** ({viewer_count} viewers)"
                )
        else:
            # Stream OFFLINE → Message auto
            response_text = (
                f"@{msg.user_login} 💤 {msg.channel} est offline actuellement"
            )
        
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        LOGGER.info(f"✅ Game current sent to {msg.user_login} (channel: {msg.channel})")
        
    except Exception as e:
        LOGGER.error(f"❌ Error getting current game: {e}", exc_info=True)
        response_text = f"@{msg.user_login} ❌ Error getting current game"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
