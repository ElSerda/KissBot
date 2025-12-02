"""
Performance Commands Module - !perf, !perftrace
================================================
Commandes de performance et monitoring (Mods only).

Pattern: handler(MessageHandler, ChatMessage, args: str) -> None
"""

import time
import logging
from twitchAPI.chat import ChatMessage

LOGGER = logging.getLogger("kissbot.commands.performance")


async def handle_perf(handler, msg: ChatMessage, args: str = "") -> None:
    """
    !perf - Statistiques du cache de jeux (Mods only)
    
    Affiche:
    - Hit rate du cache
    - Nombre d'entrées
    - Jeu le plus populaire
    """
    from core.message_types import OutboundMessage
    
    # Mod only
    if not (msg.is_mod or msg.is_broadcaster):
        return  # Silently ignore for non-mods
    
    if not handler.game_lookup or not handler.game_lookup.db:
        response_text = f"@{msg.user_login} ❌ Database not available"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        return
    
    try:
        # Get cache stats
        stats = handler.game_lookup.db.get_cache_stats()
        
        # Debug: log stats structure
        LOGGER.debug(f"📊 Cache stats returned: {stats}")
        
        # Format response
        response_text = (
            f"@{msg.user_login} 📊 Cache: {stats['hit_rate']:.1f}% hit rate | "
            f"{stats['count']} entries | "
            f"Top: {stats['top_game']} ({stats['top_hits']} hits)"
        )
        
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        
        LOGGER.info(f"📊 Cache stats sent to {msg.user_login}")
        
    except Exception as e:
        LOGGER.error(f"❌ Error getting cache stats: {e}", exc_info=True)
        response_text = f"@{msg.user_login} ❌ Error getting cache stats"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))


async def handle_perftrace(handler, msg: ChatMessage, args: str = "") -> None:
    """
    !perftrace <game> - Trace performance détaillée (Mods only)
    
    Effectue une recherche complète et sauvegarde un rapport microseconde
    détaillé dans logs/perftrace_<timestamp>.txt
    """
    from core.message_types import OutboundMessage
    import os
    
    # Mod only
    if not (msg.is_mod or msg.is_broadcaster):
        return  # Silently ignore for non-mods
    
    if not handler.game_lookup:
        response_text = f"@{msg.user_login} ❌ Game lookup not available"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        return
    
    if not args.strip():
        response_text = f"@{msg.user_login} Usage: !perftrace <game name>"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        return
    
    try:
        game_name = args.strip()
        
        # Clear previous traces
        handler.game_lookup.perf.clear()
        
        # Perform search with full tracing
        LOGGER.info(f"🔬 Performance trace started for: {game_name}")
        game = await handler.game_lookup.search_game(game_name)
        
        # Get detailed report
        report = handler.game_lookup.perf.get_report()
        
        # Save to file
        os.makedirs("logs", exist_ok=True)
        
        timestamp = int(time.time())
        filename = f"logs/perftrace_{timestamp}.txt"
        
        with open(filename, 'w') as f:
            f.write(f"Performance Trace - {game_name}\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"Result: {game.name if game else 'NOT FOUND'}\n")
            f.write("=" * 60 + "\n\n")
            f.write(report)
            f.write("\n\n")
            
            # Add summary
            summary = handler.game_lookup.perf.get_summary()
            f.write("SUMMARY:\n")
            f.write(f"  Total duration: {summary['total_us']:.1f}µs\n")
            f.write(f"  Operations: {summary['operation_count']}\n")
            f.write(f"  Avg per operation: {summary['avg_us_per_operation']:.1f}µs\n")
        
        # Format summary for chat (just the key stats)
        summary = handler.game_lookup.perf.get_summary()
        total_ms = summary['total_us'] / 1000
        response_text = (
            f"@{msg.user_login} 📊 Trace: {game.name if game else 'NOT FOUND'} | "
            f"⏱️ {total_ms:.1f}ms total | "
            f"{summary['operation_count']} ops | "
            f"Saved to logs/"
        )
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        
        LOGGER.info(f"🔬 Performance trace saved: {filename}")
        
    except Exception as e:
        LOGGER.error(f"❌ Error tracing performance: {e}", exc_info=True)
        response_text = f"@{msg.user_login} ❌ Error tracing performance"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
