"""
Decoherence Command Module - !decoherence
==========================================
Cleanup manuel des états quantiques (cache).

Pattern: handler(MessageHandler, ChatMessage, args: str) -> None
"""

import logging
from twitchAPI.chat import ChatMessage

LOGGER = logging.getLogger("kissbot.commands.decoherence")


async def handle_decoherence(handler, msg: ChatMessage, args: str = "") -> None:
    """
    !decoherence [name] - Cleanup manuel états quantiques (Mods/Admins only)
    
    Usage:
    - !decoherence           → Cleanup ALL expired states (automatic decoherence)
    - !decoherence hades     → Force delete 'hades' state (even if not expired)
    - !decoherence hades,doom → Force delete multiple states
    """
    from core.message_types import OutboundMessage
    
    # Permission check: Mods/Admins only
    if not (msg.is_mod or msg.is_broadcaster):
        response_text = f"@{msg.user_login} ⚠️ !decoherence réservé aux mods/admins"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        return
    
    try:
        # Check if specific name provided
        if args and len(args.strip()) > 0:
            # Force delete specific states
            await _decoherence_specific(handler, msg, args.strip())
        else:
            # Global cleanup (expired only)
            await _decoherence_global(handler, msg)
        
    except Exception as e:
        LOGGER.error(f"❌ Error processing !decoherence: {e}", exc_info=True)
        response_text = f"@{msg.user_login} ❌ Erreur décohérence"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))


async def _decoherence_global(handler, msg: ChatMessage) -> None:
    """Global cleanup: Remove ALL expired states across all domains."""
    from core.message_types import OutboundMessage
    
    LOGGER.info(f"💨 Global decoherence triggered by {msg.user_login}")
    
    cleanup_parts = [f"@{msg.user_login} 💨 Décohérence globale"]
    
    # Cleanup music cache only (game cache is now SQLite-only, no expiry)
    if handler.music_cache:
        music_evaporated = handler.music_cache.cleanup_expired()
        cleanup_parts.append(f"MUSIC: {music_evaporated} évaporés")
    
    response_text = " | ".join(cleanup_parts)
    
    await handler.bus.publish("chat.outbound", OutboundMessage(
        channel=msg.channel,
        channel_id=msg.channel_id,
        text=response_text,
        prefer="irc"
    ))
    LOGGER.info(f"✅ Global decoherence completed by {msg.user_login}")


async def _decoherence_specific(handler, msg: ChatMessage, names: str) -> None:
    """Specific cleanup: Force delete named states (even if not expired)."""
    from core.message_types import OutboundMessage
    
    # Parse comma-separated names
    name_list = [name.strip() for name in names.split(",") if name.strip()]
    
    if not name_list:
        response_text = f"@{msg.user_login} ❌ Usage: !decoherence <name> ou !decoherence <name1>,<name2>"
        await handler.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        return
    
    LOGGER.info(f"💨 Specific decoherence by {msg.user_login}: {name_list}")
    
    deleted_count = 0
    failed_names = []
    
    # Delete from BOTH caches (SQLite + Quantum)
    for name in name_list:
        name_lower = name.lower().strip()
        deleted_any = False
        
        # 1. Delete from SQLite cache (via Rust engine or Python fallback)
        if hasattr(handler, 'game_lookup') and handler.game_lookup:
            try:
                # Try Rust engine cleanup first
                if hasattr(handler.game_lookup, '_engine'):
                    # Note: Rust engine doesn't have delete by name yet
                    # Fallback to Python DatabaseManager
                    pass
                
                # Use Python fallback's DatabaseManager
                if hasattr(handler.game_lookup, '_python_lookup') and handler.game_lookup._python_lookup:
                    db = handler.game_lookup._python_lookup.db
                    if db:
                        # Check if exists first
                        cached = db.get_cached_game(name_lower)
                        if cached:
                            # Delete from SQLite using proper connection context
                            with db._get_connection() as conn:
                                conn.execute(
                                    "DELETE FROM game_cache WHERE query = ?",
                                    (name_lower,)
                                )
                            deleted_any = True
                            LOGGER.info(f"💨 Deleted from SQLite: {name_lower}")
            except Exception as e:
                LOGGER.error(f"❌ Error deleting from SQLite: {e}")
        
        if deleted_any:
            deleted_count += 1
        else:
            failed_names.append(name)
    
    # Build response
    if deleted_count > 0:
        deleted_str = ", ".join([n for n in name_list if n not in failed_names])
        response_text = f"@{msg.user_login} 💨 États supprimés: {deleted_str} ({deleted_count} total)"
        
        if failed_names:
            response_text += f" | Non trouvés: {', '.join(failed_names)}"
    else:
        response_text = f"@{msg.user_login} ❌ Aucun état trouvé: {', '.join(failed_names)}"
    
    await handler.bus.publish("chat.outbound", OutboundMessage(
        channel=msg.channel,
        channel_id=msg.channel_id,
        text=response_text,
        prefer="irc"
    ))
    LOGGER.info(f"✅ Specific decoherence completed: {deleted_count} deleted")
