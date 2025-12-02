"""
🔧 User Commands - System
Commandes système de base pour tous les utilisateurs.

Commands:
- !ping : Test de latence
- !uptime : Uptime du bot  
- !help : Liste des commandes
- !stats : Stats système (CPU/RAM)
"""
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.message_handler import MessageHandler
    from twitchAPI.chat import ChatMessage

from core.message_types import OutboundMessage

LOGGER = logging.getLogger(__name__)


async def handle_ping(handler: "MessageHandler", msg: "ChatMessage", args: str = "") -> None:
    """
    !ping - Test de réponse du bot
    
    Répond "Pong! 🏓" pour vérifier que le bot est actif.
    """
    response = OutboundMessage(
        channel=msg.channel,
        channel_id=msg.channel_id,
        text=f"@{msg.user_login} Pong! 🏓",
        prefer="irc"
    )
    
    await handler.bus.publish("chat.outbound", response)
    LOGGER.info(f"✅ [ping] Response to {msg.user_login}")


async def handle_uptime(handler: "MessageHandler", msg: "ChatMessage", args: str = "") -> None:
    """
    !uptime - Temps depuis le démarrage du bot
    
    Affiche le temps d'exécution et le nombre de commandes traitées.
    """
    uptime_seconds = int(time.time() - handler.start_time)
    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60
    seconds = uptime_seconds % 60
    
    uptime_str = f"{hours}h {minutes}m {seconds}s"
    
    response = OutboundMessage(
        channel=msg.channel,
        channel_id=msg.channel_id,
        text=f"@{msg.user_login} Bot uptime: {uptime_str} ⏱️ | Commands: {handler.command_count}",
        prefer="irc"
    )
    
    await handler.bus.publish("chat.outbound", response)
    LOGGER.info(f"✅ [uptime] Response to {msg.user_login}: {uptime_str}")


async def handle_stats(handler: "MessageHandler", msg: "ChatMessage", args: str = "") -> None:
    """
    !stats - Statistiques système (CPU/RAM/Threads)
    
    Affiche les métriques système en temps réel:
    - CPU%: Utilisation CPU du process bot
    - RAM: Mémoire utilisée en MB
    - Threads: Nombre de threads actifs
    - Alerts: ⚠️ si seuils dépassés (CPU > 50%, RAM > 500MB)
    """
    if not handler.system_monitor:
        response = OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=f"@{msg.user_login} ❌ System monitoring not available",
            prefer="irc"
        )
        await handler.bus.publish("chat.outbound", response)
        LOGGER.warning("⚠️ [stats] SystemMonitor not injected")
        return
    
    # Récupérer et formater les stats
    stats_text = handler.system_monitor.format_stats_message()
    
    response = OutboundMessage(
        channel=msg.channel,
        channel_id=msg.channel_id,
        text=f"@{msg.user_login} {stats_text}",
        prefer="irc"
    )
    
    await handler.bus.publish("chat.outbound", response)
    LOGGER.info(f"✅ [stats] Response to {msg.user_login}")


async def handle_help(handler: "MessageHandler", msg: "ChatMessage", args: str = "") -> None:
    """
    !help - Liste des commandes disponibles
    
    Affiche les commandes disponibles selon les features activées.
    """
    commands_list = "!ping !uptime !stats !help"
    
    # Ajouter game commands si disponibles
    if handler.game_lookup:
        commands_list += " !gi <game> !gs <game> !gc"
    
    # Ajouter LLM command si disponible
    if handler.llm_handler and handler.llm_handler.is_available():
        commands_list += " !ask <question> | Mention @bot_name <message>"
    
    # Ajouter broadcast command (broadcaster only)
    if msg.is_broadcaster:
        commands_list += " !kisscharity <message> (broadcaster)"
    
    response = OutboundMessage(
        channel=msg.channel,
        channel_id=msg.channel_id,
        text=f"@{msg.user_login} Commands: {commands_list}",
        prefer="irc"
    )
    
    await handler.bus.publish("chat.outbound", response)
    LOGGER.info(f"✅ [help] Response to {msg.user_login}")
