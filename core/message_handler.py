#!/usr/bin/env python3
"""
Message Handler
Traite les commandes chat et publie les réponses sur MessageBus
"""
import logging
import time
import asyncio
from typing import Any, Dict, Optional

from core.message_bus import MessageBus
from core.message_types import ChatMessage, OutboundMessage
from core.registry import Registry
from modules.moderation import get_banword_manager
from modules.integrations.game_engine.rust_wrapper import get_game_lookup
from modules.integrations.music.music_cache import MusicCache
from modules.integrations.llm_provider.llm_handler import LLMHandler
from modules.integrations.translator.translator import get_translator, get_dev_whitelist
from modules.intelligence.core import extract_mention_message

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from twitchapi.transports.helix_readonly import HelixReadOnlyClient
    from core.system_monitor import SystemMonitor

LOGGER = logging.getLogger(__name__)


class MessageHandler:
    """
    Handler pour les commandes chat
    
    Traite les commandes:
    - !ping: Test du bot
    - !uptime: Temps de fonctionnement
    - !stats: Statistiques système (CPU/RAM/Threads)
    - !help: Liste des commandes
    - !gi <game>: Info sur un jeu (multi-API avec fusion intelligente)
    - !gs <game>: Summary rapide (cache-only, ultra rapide)
    - !gc: Jeu en cours du streamer
    - !ask <question>: Question au LLM
    - !decoherence: Cleanup manuel cache SQLite
    - !kisscharity <message>: Broadcaster message sur tous les channels
    """
    
    def __init__(self, bus: MessageBus, config: Optional[Dict] = None):
        """
        Args:
            bus: MessageBus pour subscribe/publish
            config: Configuration du bot (pour GameLookup, LLM)
        """
        self.bus = bus
        self.command_count = 0
        self.start_time = time.time()
        self.config = config or {}
        
        # Deduplication pour éviter double traitement
        self._processed_messages = set()  # Cache des message IDs déjà traités
        self._cache_max_size = 100  # Limiter la taille du cache
        
        # Rate limiting pour mentions (15s cooldown)
        self._mention_last_time: Dict[str, float] = {}  # user_id -> timestamp
        self._mention_cooldown = config.get("commands", {}).get("cooldowns", {}).get("mention", 15.0)
        
        # Rate limiting pour !ask (60s cooldown)
        self._ask_last_time: Dict[str, float] = {}  # user_id -> timestamp
        self._ask_cooldown = 60.0  # 1 minute
        
        # Rate limiting pour !trad (30s cooldown, sauf whitelistés)
        self._trad_last_time: Dict[str, float] = {}  # user_id -> timestamp
        self._trad_cooldown = 30.0  # 30 secondes
        
        # Helix client (pour !gc)
        self.helix: Optional['HelixReadOnlyClient'] = None
        
        # System Monitor (pour !stats)
        self.system_monitor: Optional['SystemMonitor'] = None
        
        # IRC Client (pour !kisscharity broadcast)
        self.irc_client = None
        
        # Game Lookup (Rust Engine avec fallback Python)
        self.game_lookup = None
        try:
            db_path = config.get('db_path', 'kissbot.db')
            self.game_lookup = get_game_lookup(db_path, config)
            LOGGER.info("🦀 GameLookup initialisé (Rust Engine v0.1.0 + Python fallback)")
        except Exception as e:
            LOGGER.error(f"❌ GameLookup init failed: {e}")
        
        # Quantum Music Cache (POC)
        self.music_cache: Optional[MusicCache] = None
        try:
            self.music_cache = MusicCache(config)
            LOGGER.info("🎵 QuantumMusicCache initialisé (POC)")
        except Exception as e:
            LOGGER.error(f"❌ QuantumMusicCache init failed: {e}")
        
        # LLM Handler
        self.llm_handler: Optional[LLMHandler] = None
        if config and config.get("apis", {}).get("openai_key"):
            try:
                self.llm_handler = LLMHandler(config)
                LOGGER.info("✅ LLMHandler initialisé")
            except Exception as e:
                LOGGER.error(f"❌ LLMHandler init failed: {e}")
        
        # Translation Service
        self.translator = get_translator()
        self.dev_whitelist = get_dev_whitelist(db_manager=None)  # Will set DB later
        LOGGER.info("🌍 TranslationService initialisé")
        
        # BanWord Manager (auto-ban sur mots interdits)
        self.banword_manager = get_banword_manager()
        LOGGER.info("🚫 BanWordManager initialisé")
        
        # Subscribe aux messages entrants
        self.bus.subscribe("chat.inbound", self._handle_chat_message)
        
        LOGGER.info("MessageHandler initialisé")
    
    def set_helix(self, helix: 'HelixReadOnlyClient') -> None:
        """
        Injecte le client Helix après initialisation
        (car Helix est créé après MessageHandler dans main.py)
        """
        self.helix = helix
        LOGGER.debug("✅ Helix client injecté dans MessageHandler")
    
    def set_system_monitor(self, system_monitor: 'SystemMonitor') -> None:
        """
        Injecte le SystemMonitor après initialisation
        (pour accéder aux métriques système via !stats)
        """
        self.system_monitor = system_monitor
        LOGGER.debug("✅ SystemMonitor injecté dans MessageHandler")
    
    def set_irc_client(self, irc_client) -> None:
        """
        Injecte le IRC Client après initialisation
        (pour broadcast_message via !kisscharity)
        """
        self.irc_client = irc_client
        LOGGER.debug("✅ IRC Client injecté dans MessageHandler")
    
    async def _handle_chat_message(self, msg: ChatMessage) -> None:
        """
        Traite un message chat entrant
        Détecte les commandes et publie les réponses
        
        Args:
            msg: Message chat reçu
        """
        # Ignorer les messages des autres bots
        KNOWN_BOTS = [
            'nightbot', 'streamelements', 'streamlabs', 'moobot', 'fossabot',
            'wizebot', 'botisimo', 'cloudbot', 'deepbot', 'ankhbot',
            'phantombot', 'coebot', 'ohbot', 'revlobot', 'vivbot'
        ]
        
        if msg.user_login.lower() in KNOWN_BOTS:
            LOGGER.debug(f"🤖 Ignoring bot message from {msg.user_login}")
            return
        
        # ═══════════════════════════════════════════════════════════════════
        # 🚫 BANWORD CHECK - Auto-ban si mot interdit détecté
        # ═══════════════════════════════════════════════════════════════════
        matched_banword = self.banword_manager.check_message(msg.channel, msg.text)
        if matched_banword:
            await self._execute_banword_ban(msg, matched_banword)
            return  # Ne pas traiter le message davantage
        
        # Auto-traduction pour devs whitelistés (avant deduplication)
        if not msg.text.startswith("!"):
            await self._handle_auto_translation(msg)
        
        # Deduplication - Créer ID unique basé sur user + text + timestamp (secondes)
        # Timestamp en secondes pour éviter duplicates dans la même seconde uniquement
        msg_timestamp = int(time.time())
        msg_id = f"{msg.user_id}:{msg.text}:{msg_timestamp}"
        
        if msg_id in self._processed_messages:
            LOGGER.debug(f"⏭️ Message déjà traité, skip: {msg.text[:30]}")
            return
        
        # Ajouter au cache (avec limite de taille)
        self._processed_messages.add(msg_id)
        if len(self._processed_messages) > self._cache_max_size:
            # Vider la moitié du cache (FIFO approximatif)
            self._processed_messages = set(list(self._processed_messages)[50:])
        
        # Détection des mentions (@bot_name ou bot_name)
        # Prioritaire sur les commandes pour intercepter "@bot_name !ping"
        bot_name = self.config.get("bot_login_name", "serda_bot")
        mention_text = extract_mention_message(msg.text, bot_name)
        
        if mention_text:
            # Mention détectée, router vers LLM
            await self._handle_mention(msg, mention_text)
            return  # Ne pas traiter comme commande
        
        # Ignorer les messages qui ne commencent pas par !
        if not msg.text.startswith("!"):
            return
        
        # Parser la commande
        parts = msg.text.split(maxsplit=1)
        command = parts[0].lower()  # Ex: "!ping"
        args = parts[1] if len(parts) > 1 else ""
        
        LOGGER.info(f"🤖 Command: {command} from {msg.user_login} in #{msg.channel}")
        self.command_count += 1
        
        # Router vers le handler approprié
        if command == "!ping":
            await self._cmd_ping(msg)
        elif command == "!uptime":
            await self._cmd_uptime(msg)
        elif command == "!stats":
            await self._cmd_stats(msg)
        elif command in ["!commands", "!help"]:
            await self._cmd_help(msg)
        elif command == "!gi":
            await self._cmd_game_info(msg, args)
        elif command == "!gs":
            await self._cmd_game_summary(msg, args)
        elif command == "!gc":
            await self._cmd_game_current(msg)
        elif command == "!perf":
            await self._cmd_perf(msg, args)
        elif command == "!perftrace":
            await self._cmd_perftrace(msg, args)
        elif command == "!ask":
            await self._cmd_ask(msg, args)
        elif command == "!joke":
            await self._cmd_joke(msg)
        elif command == "!wiki":
            await self._cmd_wiki(msg, args)
        elif command == "!trad":
            await self._cmd_trad(msg, args)
        elif command == "!adddev":
            await self._cmd_adddev(msg, args)
        elif command == "!rmdev":
            await self._cmd_rmdev(msg, args)
        elif command == "!listdevs":
            await self._cmd_listdevs(msg)
        elif command == "!kissanniv":
            await self._cmd_kissanniv(msg, args)
        elif command == "!decoherence":
            await self._cmd_decoherence(msg, args)
        elif command == "!kisscharity":
            await self._cmd_kisscharity(msg, args)
        # ═══════════════════════════════════════════════════════════════════
        # 🚫 BANWORD COMMANDS (Mod/Broadcaster only)
        # ═══════════════════════════════════════════════════════════════════
        elif command == "!kbbanword":
            await self._cmd_kbbanword(msg, args)
        elif command == "!kbunbanword":
            await self._cmd_kbunbanword(msg, args)
        elif command == "!kbbanwords":
            await self._cmd_kbbanwords(msg)
        else:
            # Commande inconnue, pas de réponse
            LOGGER.debug(f"Unknown command: {command}")
            return
        
        # Publish command execution event for CommandLogger
        await self.bus.publish("command.executed", {
            'command': command[1:],  # Remove ! prefix
            'user': msg.user_login,
            'channel': msg.channel,
            'args': args,
            'result': 'success'
        })
    
    async def _cmd_ping(self, msg: ChatMessage) -> None:
        """Commande !ping - Test de réponse du bot"""
        response = OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=f"@{msg.user_login} Pong! 🏓",
            prefer="irc"
        )
        
        await self.bus.publish("chat.outbound", response)
        LOGGER.info(f"✅ Response queued: Pong to {msg.user_login}")
    
    async def _cmd_uptime(self, msg: ChatMessage) -> None:
        """Commande !uptime - Temps depuis le démarrage du bot"""
        uptime_seconds = int(time.time() - self.start_time)
        hours = uptime_seconds // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60
        
        uptime_str = f"{hours}h {minutes}m {seconds}s"
        
        response = OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=f"@{msg.user_login} Bot uptime: {uptime_str} ⏱️ | Commands: {self.command_count}",
            prefer="irc"
        )
        
        await self.bus.publish("chat.outbound", response)
        LOGGER.info(f"✅ Response queued: Uptime to {msg.user_login}")
    
    async def _cmd_stats(self, msg: ChatMessage) -> None:
        """
        Commande !stats - Statistiques système (CPU/RAM/Threads)
        
        Affiche les métriques système en temps réel:
        - CPU%: Utilisation CPU du process bot
        - RAM: Mémoire utilisée en MB
        - Threads: Nombre de threads actifs
        - Uptime: Temps depuis démarrage du monitoring
        - Alerts: ⚠️ si seuils dépassés (CPU > 50%, RAM > 500MB)
        """
        if not self.system_monitor:
            # Monitoring pas disponible
            response = OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=f"@{msg.user_login} ❌ System monitoring not available",
                prefer="irc"
            )
            await self.bus.publish("chat.outbound", response)
            LOGGER.warning("⚠️ !stats called but SystemMonitor not injected")
            return
        
        # Récupérer et formater les stats
        stats_text = self.system_monitor.format_stats_message()
        
        response = OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=f"@{msg.user_login} {stats_text}",
            prefer="irc"
        )
        
        await self.bus.publish("chat.outbound", response)
        LOGGER.info(f"✅ Response queued: Stats to {msg.user_login}")
    
    async def _cmd_help(self, msg: ChatMessage) -> None:
        """Commande !help - Liste des commandes disponibles"""
        commands_list = "!ping !uptime !stats !help"
        
        # Ajouter game commands si disponibles
        if self.game_lookup:
            commands_list += " !gi <game> !gs <game> !gc"
        
        # Ajouter LLM command si disponible
        if self.llm_handler and self.llm_handler.is_available():
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
        
        await self.bus.publish("chat.outbound", response)
        LOGGER.info(f"✅ Response queued: Help to {msg.user_login}")
    
    async def _cmd_game_info(self, msg: ChatMessage, game_name: str) -> None:
        """
        Commande !gi <game> - Info sur un jeu
        
        Args:
            msg: Message chat
            game_name: Nom du jeu à rechercher
        """
        if not self.game_lookup:
            response_text = f"@{msg.user_login} ❌ Game lookup not available"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            return
        
        if not game_name.strip():
            response_text = f"@{msg.user_login} Usage: !gi <game name>"
            await self.bus.publish("chat.outbound", OutboundMessage(
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
            game = await self.game_lookup.search_game(game_name)
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
                game_info = self.game_lookup.format_result(game, compact=False)
                response_text = f"@{msg.user_login} {game_info}"
                
                elapsed_format_us = (time.perf_counter() - start_format) * 1_000_000
                elapsed_total_ms = (time.perf_counter() - start_total) * 1000
                LOGGER.info(
                    f"✅ Game info sent: {game.name} | "
                    f"⏱️ Format: {elapsed_format_us:.1f}µs | Total: {elapsed_total_ms:.1f}ms"
                )
            
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            
        except Exception as e:
            LOGGER.error(f"❌ Error searching game: {e}", exc_info=True)
            response_text = f"@{msg.user_login} ❌ Error searching game"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
    
    async def _cmd_game_summary(self, msg: ChatMessage, game_name: str) -> None:
        """
        Commande !gs <game> - Résumé court d'un jeu (nom + description uniquement)
        
        Args:
            msg: Message chat
            game_name: Nom du jeu à rechercher
        """
        if not self.game_lookup:
            response_text = f"@{msg.user_login} ❌ Game lookup not available"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            return
        
        if not game_name.strip():
            response_text = f"@{msg.user_login} Usage: !gs <game name>"
            await self.bus.publish("chat.outbound", OutboundMessage(
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
            game = await self.game_lookup.search_game(game_name)
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
            
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            
        except Exception as e:
            LOGGER.error(f"❌ Error searching game summary: {e}", exc_info=True)
            response_text = f"@{msg.user_login} ❌ Error searching game"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
    
    
    async def _cmd_perf(self, msg: ChatMessage, args: str) -> None:
        """
        Commande !perf - Statistiques du cache de jeux (Mods only)
        
        Affiche:
        - Hit rate du cache
        - Nombre d'entrées
        - Jeu le plus populaire
        """
        # Mod only
        if not (msg.is_mod or msg.is_broadcaster):
            return  # Silently ignore for non-mods
        
        if not self.game_lookup or not self.game_lookup.db:
            response_text = f"@{msg.user_login} ❌ Database not available"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            return
        
        try:
            # Get cache stats
            stats = self.game_lookup.db.get_cache_stats()
            
            # Debug: log stats structure
            LOGGER.debug(f"📊 Cache stats returned: {stats}")
            
            # Format response
            response_text = (
                f"@{msg.user_login} 📊 Cache: {stats['hit_rate']:.1f}% hit rate | "
                f"{stats['count']} entries | "
                f"Top: {stats['top_game']} ({stats['top_hits']} hits)"
            )
            
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            
            LOGGER.info(f"📊 Cache stats sent to {msg.user_login}")
            
        except Exception as e:
            LOGGER.error(f"❌ Error getting cache stats: {e}", exc_info=True)
            response_text = f"@{msg.user_login} ❌ Error getting cache stats"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
    
    async def _cmd_perftrace(self, msg: ChatMessage, args: str) -> None:
        """
        Commande !perftrace <game> - Trace performance détaillée (Mods only)
        
        Effectue une recherche complète et sauvegarde un rapport microseconde
        détaillé dans logs/perftrace_<timestamp>.txt
        """
        # Mod only
        if not (msg.is_mod or msg.is_broadcaster):
            return  # Silently ignore for non-mods
        
        if not self.game_lookup:
            response_text = f"@{msg.user_login} ❌ Game lookup not available"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            return
        
        if not args.strip():
            response_text = f"@{msg.user_login} Usage: !perftrace <game name>"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            return
        
        try:
            game_name = args.strip()
            
            # Clear previous traces
            self.game_lookup.perf.clear()
            
            # Perform search with full tracing
            LOGGER.info(f"🔬 Performance trace started for: {game_name}")
            game = await self.game_lookup.search_game(game_name)
            
            # Get detailed report
            report = self.game_lookup.perf.get_report()
            
            # Save to file
            import os
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
                summary = self.game_lookup.perf.get_summary()
                f.write("SUMMARY:\n")
                f.write(f"  Total duration: {summary['total_us']:.1f}µs\n")
                f.write(f"  Operations: {summary['operation_count']}\n")
                f.write(f"  Avg per operation: {summary['avg_us_per_operation']:.1f}µs\n")
            
            # Format summary for chat (just the key stats)
            total_ms = summary['total_us'] / 1000
            response_text = (
                f"@{msg.user_login} 📊 Trace: {game.name if game else 'NOT FOUND'} | "
                f"⏱️ {total_ms:.1f}ms total | "
                f"{summary['operation_count']} ops | "
                f"Saved to logs/"
            )
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            
            LOGGER.info(f"🔬 Performance trace saved: {filename}")
            
        except Exception as e:
            LOGGER.error(f"❌ Error tracing performance: {e}", exc_info=True)
            response_text = f"@{msg.user_login} ❌ Error tracing performance"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
    
    async def _cmd_game_current(self, msg: ChatMessage) -> None:
        """
        Commande !gc - Jeu en cours du streamer (enrichi)
        
        Utilise Helix get_stream() pour récupérer game_name,
        puis enrichit avec GameLookup pour infos complètes.
        Si offline, message automatique.
        """
        if not self.helix:
            response_text = f"@{msg.user_login} ❌ Helix client not available"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            LOGGER.error("❌ !gc called but Helix not injected")
            return
        
        try:
            # Récupérer les infos du stream
            stream_info = await self.helix.get_stream(msg.channel)
            
            if stream_info and stream_info.get("game_name"):
                # Stream LIVE → Enrichir avec GameLookup
                game_name = stream_info["game_name"]
                game_id = stream_info.get("game_id")  # IGDB ID exact
                viewer_count = stream_info.get("viewer_count", 0)
                
                # Enrichissement du jeu via IGDB ID (source de vérité)
                if self.game_lookup and game_id:
                    LOGGER.info(f"🎮 Enriching game from IGDB ID: {game_id} ({game_name})")
                    game = await self.game_lookup.enrich_game_from_igdb_id(game_id)
                    
                    if game:
                        # Format COMPACT (sans confidence/sources pour gagner de l'espace)
                        game_info = self.game_lookup.format_result(game, compact=True)
                        
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
                            # Fallback sur viewers si pas de description
                            response_text = (
                                f"@{msg.user_login} {msg.channel} joue actuellement à "
                                f"{game_info} ({viewer_count} viewers)"
                            )
                    else:
                        # Fallback si enrichissement échoue
                        response_text = (
                            f"@{msg.user_login} {msg.channel} joue actuellement à "
                            f"**{game_name}** ({viewer_count} viewers)"
                        )
                else:
                    # Pas de GameLookup configuré
                    response_text = (
                        f"@{msg.user_login} {msg.channel} joue actuellement à "
                        f"**{game_name}** ({viewer_count} viewers)"
                    )
            else:
                # Stream OFFLINE → Message auto
                response_text = (
                    f"@{msg.user_login} 💤 {msg.channel} est offline actuellement"
                )
            
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            LOGGER.info(f"✅ Game current sent to {msg.user_login} (channel: {msg.channel})")
            
        except Exception as e:
            LOGGER.error(f"❌ Error getting current game: {e}", exc_info=True)
            response_text = f"@{msg.user_login} ❌ Error getting current game"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
    
    async def _cmd_ask(self, msg: ChatMessage, question: str) -> None:
        """
        Commande !ask - Question au LLM
        
        Args:
            msg: Message entrant
            question: Question de l'utilisateur (args après !ask)
        """
        # Rate limiting: 60s cooldown par utilisateur
        current_time = time.time()
        last_time = self._ask_last_time.get(msg.user_id, 0)
        
        if current_time - last_time < self._ask_cooldown:
            cooldown_remaining = int(self._ask_cooldown - (current_time - last_time))
            response_text = f"@{msg.user_login} ⏰ Cooldown: {cooldown_remaining}s restants"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            LOGGER.debug(f"🔇 !ask de {msg.user_login} en cooldown ({cooldown_remaining}s restants)")
            return
        
        # Update cooldown
        self._ask_last_time[msg.user_id] = current_time
        
        if not self.llm_handler or not self.llm_handler.is_available():
            response_text = f"@{msg.user_login} ❌ Le système d'IA n'est pas disponible"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            LOGGER.error("❌ !ask called but LLM not initialized")
            return
        
        if not question or len(question.strip()) == 0:
            response_text = f"@{msg.user_login} 🧠 Usage: !ask <question>"
            await self.bus.publish("chat.outbound", OutboundMessage(
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
                wiki_context = await asyncio.wait_for(
                    search_wikipedia(question, lang=self.config.get("wikipedia", {}).get("lang", "fr")),
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
            llm_response = await self.llm_handler.ask(
                question=enhanced_question,
                user_name=msg.user_login,
                channel=msg.channel,
                game_cache=None  # TODO: Ajouter game_cache si besoin
            )
            
            if llm_response:
                # Formatter la réponse pour Twitch (limite 500 chars)
                response_text = f"@{msg.user_login} {llm_response}"
                
                # Tronquer si trop long
                if len(response_text) > 500:
                    response_text = response_text[:497] + "..."
                
                await self.bus.publish("chat.outbound", OutboundMessage(
                    channel=msg.channel,
                    channel_id=msg.channel_id,
                    text=response_text,
                    prefer="irc"
                ))
                LOGGER.info(f"✅ LLM response sent to {msg.user_login} ({len(llm_response)} chars)")
            else:
                response_text = f"@{msg.user_login} ❌ Je n'ai pas pu générer une réponse"
                await self.bus.publish("chat.outbound", OutboundMessage(
                    channel=msg.channel,
                    channel_id=msg.channel_id,
                    text=response_text,
                    prefer="irc"
                ))
                LOGGER.warning(f"⚠️ LLM returned None for {msg.user_login}")
                
        except Exception as e:
            LOGGER.error(f"❌ Error processing !ask: {e}", exc_info=True)
            response_text = f"@{msg.user_login} ❌ Erreur lors du traitement de ta question"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
    
    async def _cmd_joke(self, msg: ChatMessage) -> None:
        """
        Commande !joke - Génération de blague via LLM
        
        Args:
            msg: Message entrant
        """
        # Rate limiting: 60s cooldown par utilisateur
        if not hasattr(self, '_joke_last_time'):
            self._joke_last_time = {}
        if not hasattr(self, '_joke_cooldown'):
            self._joke_cooldown = 60.0
        
        current_time = time.time()
        last_time = self._joke_last_time.get(msg.user_id, 0)
        
        if current_time - last_time < self._joke_cooldown:
            cooldown_remaining = int(self._joke_cooldown - (current_time - last_time))
            response_text = f"@{msg.user_login} ⏰ Cooldown: {cooldown_remaining}s restants"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            return
        
        # Update cooldown
        self._joke_last_time[msg.user_id] = current_time
        
        if not self.llm_handler or not self.llm_handler.is_available():
            response_text = f"@{msg.user_login} ❌ Le système d'IA n'est pas disponible"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            return
        
        try:
            LOGGER.info(f"😄 Joke request from {msg.user_login}")
            
            # Demander une blague au LLM
            llm_response = await self.llm_handler.ask(
                question="Raconte-moi une blague courte et drôle",
                user_name=msg.user_login,
                channel=msg.channel
            )
            
            if llm_response:
                response_text = f"@{msg.user_login} {llm_response}"
                
                # Tronquer si trop long
                if len(response_text) > 500:
                    response_text = response_text[:497] + "..."
                
                await self.bus.publish("chat.outbound", OutboundMessage(
                    channel=msg.channel,
                    channel_id=msg.channel_id,
                    text=response_text,
                    prefer="irc"
                ))
                LOGGER.info(f"✅ Joke sent to {msg.user_login}")
            else:
                response_text = f"@{msg.user_login} ❌ Je n'ai pas pu générer une blague"
                await self.bus.publish("chat.outbound", OutboundMessage(
                    channel=msg.channel,
                    channel_id=msg.channel_id,
                    text=response_text,
                    prefer="irc"
                ))
                
        except Exception as e:
            LOGGER.error(f"❌ Error processing !joke: {e}", exc_info=True)
            response_text = f"@{msg.user_login} ❌ Erreur lors de la génération de la blague"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
    
    async def _cmd_wiki(self, msg: ChatMessage, query: str) -> None:
        """
        Commande !wiki - Recherche Wikipedia sans LLM
        
        Args:
            msg: Message entrant
            query: Requête de recherche (args après !wiki)
        """
        if not query or len(query.strip()) == 0:
            response_text = f"@{msg.user_login} 📚 Usage: !wiki <sujet>"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            return
        
        try:
            from modules.integrations.wikipedia.wikipedia_handler import search_wikipedia
            
            # Basic validation
            if not query or len(query.strip()) < 2:
                response_text = f"@{msg.user_login} ❌ Requête trop courte"
                await self.bus.publish("chat.outbound", OutboundMessage(
                    channel=msg.channel,
                    channel_id=msg.channel_id,
                    text=response_text,
                    prefer="irc"
                ))
                LOGGER.debug(f"❌ Invalid wiki query from {msg.user_login}: {query}")
                return
            
            LOGGER.info(f"📚 Wikipedia request from {msg.user_login}: {query[:50]}...")
            
            # Récupérer la langue depuis config
            wiki_lang = self.config.get("wikipedia", {}).get("lang", "en")
            
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
            
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            LOGGER.info(f"✅ Wikipedia response sent to {msg.user_login}")
                
        except Exception as e:
            LOGGER.error(f"❌ Error processing !wiki: {e}", exc_info=True)
            response_text = f"@{msg.user_login} ❌ Erreur lors de la recherche Wikipedia"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
    
    async def _cmd_kissanniv(self, msg: ChatMessage, args: str) -> None:
        """
        Commande !kissanniv [name] - Souhaiter un joyeux anniversaire
        
        Args:
            msg: Message original
            args: Nom de la personne (optionnel)
        """
        try:
            from modules.classic_commands.user_commands.kissanniv import cmd_kissanniv
            await cmd_kissanniv(self.bus, msg, args)
        except Exception as e:
            LOGGER.error(f"❌ Error processing !kissanniv: {e}", exc_info=True)
            response_text = f"@{msg.user_login} ❌ Erreur lors de l'envoi du message d'anniversaire"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
    
    async def _cmd_anniv(self, msg: ChatMessage, name: str) -> None:
        """
        Commande !anniv <name> - Souhaiter un joyeux anniversaire
        
        Args:
            msg: Message original
            name: Nom de la personne
        """
        try:
            from modules.classic_commands.user_commands.anniv import cmd_anniv
            await cmd_anniv(msg, name, self.bus, self.config)
        except Exception as e:
            LOGGER.error(f"❌ Error processing !anniv: {e}", exc_info=True)
            response_text = f"@{msg.user_login} ❌ Erreur lors de l'envoi du message d'anniversaire"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
    
    async def _handle_mention(self, msg: ChatMessage, mention_text: str) -> None:
        """
        Traite une mention du bot (@bot_name ou bot_name)
        
        Args:
            msg: Message original
            mention_text: Texte extrait après la mention
        """
        # Check si LLM disponible
        if not self.llm_handler or not self.llm_handler.is_available():
            LOGGER.debug("🔇 Mention ignorée (LLM non disponible)")
            return  # Silent ignore
        
        # Rate limiting: 15s cooldown par utilisateur
        current_time = time.time()
        last_time = self._mention_last_time.get(msg.user_id, 0)
        
        if current_time - last_time < self._mention_cooldown:
            cooldown_remaining = int(self._mention_cooldown - (current_time - last_time))
            LOGGER.debug(f"🔇 Mention de {msg.user_login} en cooldown ({cooldown_remaining}s restants)")
            return  # Silent ignore (pas de message d'erreur)
        
        # Update cooldown
        self._mention_last_time[msg.user_id] = current_time
        
        LOGGER.info(f"💬 Mention from {msg.user_login}: {mention_text[:50]}...")
        
        try:
            # Appeler le LLM avec context="mention"
            # Note: LLMHandler.ask() utilise context="ask" par défaut
            # Pour context="mention", on doit appeler process_llm_request directement
            from modules.intelligence.core import process_llm_request
            
            llm_response = await process_llm_request(
                llm_handler=self.llm_handler.neural_pathway,
                prompt=mention_text,
                context="mention",  # Différent de "ask"
                user_name=msg.user_login,
                game_cache=None,
                pre_optimized=False
            )
            
            if llm_response:
                # Formatter la réponse pour Twitch (limite 500 chars)
                response_text = f"@{msg.user_login} {llm_response}"
                
                # Tronquer si trop long
                if len(response_text) > 500:
                    response_text = response_text[:497] + "..."
                
                await self.bus.publish("chat.outbound", OutboundMessage(
                    channel=msg.channel,
                    channel_id=msg.channel_id,
                    text=response_text,
                    prefer="irc"
                ))
                LOGGER.info(f"✅ Mention response sent to {msg.user_login} ({len(llm_response)} chars)")
            else:
                LOGGER.debug(f"🔇 LLM returned None for mention (silent ignore)")
                # Silent ignore si LLM ne répond pas
                
        except Exception as e:
            LOGGER.error(f"❌ Error processing mention from {msg.user_login}: {e}", exc_info=True)
            # Silent ignore en cas d'erreur
    
    async def _execute_banword_ban(self, msg: ChatMessage, matched_word: str) -> None:
        """
        Exécute un ban automatique suite à un banword détecté
        
        Args:
            msg: Message contenant le banword
            matched_word: Le mot interdit qui a déclenché le ban
        """
        # Construire la raison du ban
        ban_reason = self.banword_manager.get_ban_reason(msg.channel, matched_word)
        
        LOGGER.warning(
            f"🚫 BANWORD TRIGGERED: '{matched_word}' by {msg.user_login} "
            f"in #{msg.channel} - Message: '{msg.text[:50]}...'"
        )
        
        try:
            # Envoyer la commande /ban via IRC
            ban_command = f"/ban {msg.user_login} {ban_reason}"
            
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=ban_command,
                prefer="irc"
            ))
            
            LOGGER.info(f"✅ Ban sent for {msg.user_login}: {ban_reason}")
            
            # Optionnel: Notifier les mods via un message
            # await self.bus.publish("chat.outbound", OutboundMessage(
            #     channel=msg.channel,
            #     channel_id=msg.channel_id,
            #     text=f"🚫 {msg.user_login} auto-banni (banword: {matched_word})",
            #     prefer="irc"
            # ))
            
        except Exception as e:
            LOGGER.error(f"❌ Error executing banword ban for {msg.user_login}: {e}", exc_info=True)
    
    # ============================================================
    # ADMIN COMMANDS
    # ============================================================
    
    async def _cmd_decoherence(self, msg: ChatMessage, args: str = "") -> None:
        """
        Commande !decoherence [name] - Cleanup manuel états quantiques (Mods/Admins only)
        
        Usage:
        - !decoherence           → Cleanup ALL expired states (automatic decoherence)
        - !decoherence hades     → Force delete 'hades' state (even if not expired)
        - !decoherence hades,doom → Force delete multiple states
        
        Mods can clean cache pollution or force remove problematic states.
        """
        # Permission check: Mods/Admins only
        if not (msg.is_mod or msg.is_broadcaster):
            response_text = f"@{msg.user_login} ⚠️ !decoherence réservé aux mods/admins"
            await self.bus.publish("chat.outbound", OutboundMessage(
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
                await self._decoherence_specific(msg, args.strip())
            else:
                # Global cleanup (expired only)
                await self._decoherence_global(msg)
            
        except Exception as e:
            LOGGER.error(f"❌ Error processing !decoherence: {e}", exc_info=True)
            response_text = f"@{msg.user_login} ❌ Erreur décohérence"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
    
    async def _decoherence_global(self, msg: ChatMessage) -> None:
        """Global cleanup: Remove ALL expired states across all domains."""
        LOGGER.info(f"💨 Global decoherence triggered by {msg.user_login}")
        
        cleanup_parts = [f"@{msg.user_login} 💨 Décohérence globale"]
        
        # Cleanup music cache only (game cache is now SQLite-only, no expiry)
        if self.music_cache:
            music_evaporated = self.music_cache.cleanup_expired()
            cleanup_parts.append(f"MUSIC: {music_evaporated} évaporés")
        
        response_text = " | ".join(cleanup_parts)
        
        await self.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        LOGGER.info(f"✅ Global decoherence completed by {msg.user_login}")
    
    async def _decoherence_specific(self, msg: ChatMessage, names: str) -> None:
        """Specific cleanup: Force delete named states (even if not expired)."""
        # Parse comma-separated names
        name_list = [name.strip() for name in names.split(",") if name.strip()]
        
        if not name_list:
            response_text = f"@{msg.user_login} ❌ Usage: !decoherence <name> ou !decoherence <name1>,<name2>"
            await self.bus.publish("chat.outbound", OutboundMessage(
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
            if hasattr(self, 'game_lookup') and self.game_lookup:
                try:
                    # Try Rust engine cleanup first
                    if hasattr(self.game_lookup, '_engine'):
                        # Note: Rust engine doesn't have delete by name yet
                        # Fallback to Python DatabaseManager
                        pass
                    
                    # Use Python fallback's DatabaseManager
                    if hasattr(self.game_lookup, '_python_lookup') and self.game_lookup._python_lookup:
                        db = self.game_lookup._python_lookup.db
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
        
        await self.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        LOGGER.info(f"✅ Specific decoherence completed: {deleted_count} deleted")
    
    async def _cmd_kisscharity(self, msg: ChatMessage, args: str) -> None:
        """
        !kisscharity <message> - Broadcaster un message sur tous les channels
        
        Commande KILLER FEATURE pour annonces multi-channels:
        - Events charity
        - Raids communautaires
        - Collaborations multi-streamers
        
        Restrictions:
        - Broadcaster only
        - Cooldown 5 minutes global
        - Max 500 caractères
        """
        from modules.classic_commands.bot_commands.broadcast import cmd_kisscharity
        
        # Check si IRC client est disponible
        if not self.irc_client:
            response_text = f"@{msg.user_login} ❌ Erreur système : IRC client non disponible"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            return
        
        # Parser les arguments
        args_list = args.split() if args else []
        
        # Appeler le handler de broadcast
        response_text = await cmd_kisscharity(
            msg=msg,
            args=args_list,
            bus=self.bus,
            irc_client=self.irc_client
        )
        
        # Envoyer la réponse
        if response_text:
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
    
    def get_stats(self) -> dict:
        """Retourne les stats du handler"""
        return {
            "commands_processed": self.command_count,
            "uptime_seconds": int(time.time() - self.start_time)
        }
    
    async def _handle_auto_translation(self, msg: ChatMessage) -> None:
        """
        Auto-traduction pour les devs whitelistés
        Détecte si le message est en français, sinon traduit
        """
        # Check whitelist
        if not self.dev_whitelist.is_dev(msg.user_login):
            return
        
        # Détect language
        is_french = await self.translator.is_french(msg.text)
        
        if is_french:
            return  # Déjà en français, rien à faire
        
        # Translate
        result = await self.translator.translate(msg.text, target_lang='fr')
        
        if not result:
            LOGGER.warning(f"⚠️ Auto-translation failed for {msg.user_login}")
            return
        
        source_lang, translation = result
        lang_name = self.translator.get_language_name(source_lang)
        
        # Reply with translation
        response_text = f"🌍 [{lang_name.upper()}] {msg.user_login}: {translation}"
        
        await self.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text,
            prefer="irc"
        ))
        
        LOGGER.info(f"✅ Auto-translated {msg.user_login}: {source_lang} → fr")
    
    async def _cmd_trad(self, msg: ChatMessage, args: str) -> None:
        """Commande !trad <message> - Traduction manuelle"""
        if not args:
            response_text = f"@{msg.user_login} Usage: !trad <message>"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text
            ))
            return
        
        # Rate limiting: 30s cooldown SAUF pour whitelistés
        is_whitelisted = self.dev_whitelist.is_dev(msg.user_login)
        
        if not is_whitelisted:
            current_time = time.time()
            last_time = self._trad_last_time.get(msg.user_id, 0)
            
            if current_time - last_time < self._trad_cooldown:
                cooldown_remaining = int(self._trad_cooldown - (current_time - last_time))
                response_text = f"@{msg.user_login} ⏰ Cooldown: {cooldown_remaining}s restants"
                await self.bus.publish("chat.outbound", OutboundMessage(
                    channel=msg.channel,
                    channel_id=msg.channel_id,
                    text=response_text
                ))
                LOGGER.debug(f"🔇 !trad de {msg.user_login} en cooldown ({cooldown_remaining}s restants)")
                return
            
            # Update cooldown
            self._trad_last_time[msg.user_id] = current_time
        
        result = await self.translator.translate(args, target_lang='fr')
        
        if not result:
            response_text = f"@{msg.user_login} ❌ Translation failed"
        else:
            source_lang, translation = result
            
            if source_lang == 'fr':
                response_text = f"@{msg.user_login} 🇫🇷 Already in French!"
            else:
                response_text = f"[TRAD] {msg.user_login} a dit: {translation}"
        
        await self.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text
        ))
    
    async def _cmd_adddev(self, msg: ChatMessage, args: str) -> None:
        """Commande !adddev <username> - Ajoute dev à whitelist (mod only)"""
        if not (msg.is_mod or msg.is_broadcaster):
            return  # Silently ignore
        
        if not args:
            response_text = f"@{msg.user_login} Usage: !adddev <username>"
        else:
            username = args.strip().lstrip('@')
            added = self.dev_whitelist.add_dev(username)
            
            if added:
                response_text = f"@{msg.user_login} ✅ {username} added to dev whitelist (auto-trad enabled)"
                LOGGER.info(f"👥 {msg.user_login} added {username} to dev whitelist")
            else:
                response_text = f"@{msg.user_login} ℹ️ {username} already in dev whitelist"
        
        await self.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text
        ))
    
    async def _cmd_rmdev(self, msg: ChatMessage, args: str) -> None:
        """Commande !rmdev <username> - Retire dev de whitelist (mod only)"""
        if not (msg.is_mod or msg.is_broadcaster):
            return  # Silently ignore
        
        if not args:
            response_text = f"@{msg.user_login} Usage: !rmdev <username>"
        else:
            username = args.strip().lstrip('@')
            removed = self.dev_whitelist.remove_dev(username)
            
            if removed:
                response_text = f"@{msg.user_login} ✅ {username} removed from dev whitelist"
                LOGGER.info(f"👥 {msg.user_login} removed {username} from dev whitelist")
            else:
                response_text = f"@{msg.user_login} ℹ️ {username} not in dev whitelist"
        
        await self.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text
        ))
    
    async def _cmd_listdevs(self, msg: ChatMessage) -> None:
        """Commande !listdevs - Liste les devs whitelistés"""
        devs = self.dev_whitelist.list_devs()
        
        if not devs:
            response_text = f"@{msg.user_login} ℹ️ No devs in whitelist"
        else:
            dev_list = ", ".join(devs)
            response_text = f"@{msg.user_login} 👥 Devs (auto-trad): {dev_list}"
        
        await self.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text
        ))
    
    # ════════════════════════════════════════════════════════════════════════
    # 🚫 BANWORD COMMANDS (Mod/Broadcaster only)
    # ════════════════════════════════════════════════════════════════════════
    
    async def _cmd_kbbanword(self, msg: ChatMessage, args: str) -> None:
        """
        Commande !kbbanword <mot> - Ajoute un banword (mod/broadcaster only)
        
        Tout message contenant ce mot = BAN instantané
        """
        if not (msg.is_mod or msg.is_broadcaster):
            return  # Silently ignore
        
        if not args:
            response_text = (
                f"@{msg.user_login} Usage: !kbbanword <mot> — "
                f"Ajoute un mot qui déclenche un BAN instantané"
            )
        else:
            word = args.strip().lower()
            
            # Validation
            if len(word) < 3:
                response_text = f"@{msg.user_login} ⚠️ Le mot doit faire au moins 3 caractères"
            elif len(word) > 50:
                response_text = f"@{msg.user_login} ⚠️ Le mot est trop long (max 50 caractères)"
            else:
                added = self.banword_manager.add_banword(msg.channel, word, msg.user_login)
                
                if added:
                    response_text = (
                        f"@{msg.user_login} 🚫 Banword ajouté: \"{word}\" — "
                        f"Tout message contenant ce mot = BAN instantané"
                    )
                    LOGGER.info(f"🚫 BANWORD | #{msg.channel} | {msg.user_login} added: '{word}'")
                else:
                    response_text = f"@{msg.user_login} ℹ️ \"{word}\" est déjà dans la liste"
        
        await self.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text
        ))
    
    async def _cmd_kbunbanword(self, msg: ChatMessage, args: str) -> None:
        """Commande !kbunbanword <mot> - Retire un banword (mod/broadcaster only)"""
        if not (msg.is_mod or msg.is_broadcaster):
            return  # Silently ignore
        
        if not args:
            response_text = f"@{msg.user_login} Usage: !kbunbanword <mot>"
        else:
            word = args.strip().lower()
            removed = self.banword_manager.remove_banword(msg.channel, word)
            
            if removed:
                response_text = f"@{msg.user_login} ✅ Banword retiré: \"{word}\""
                LOGGER.info(f"✅ BANWORD | #{msg.channel} | {msg.user_login} removed: '{word}'")
            else:
                response_text = f"@{msg.user_login} ℹ️ \"{word}\" n'est pas dans la liste"
        
        await self.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text
        ))
    
    async def _cmd_kbbanwords(self, msg: ChatMessage) -> None:
        """Commande !kbbanwords - Liste les banwords du channel (mod/broadcaster only)"""
        if not (msg.is_mod or msg.is_broadcaster):
            return  # Silently ignore
        
        words = self.banword_manager.list_banwords(msg.channel)
        
        if not words:
            response_text = (
                f"@{msg.user_login} ℹ️ Aucun banword configuré. "
                f"Utilisez !kbbanword <mot> pour en ajouter"
            )
        else:
            # Limiter l'affichage si trop de mots
            if len(words) > 10:
                display = ", ".join(words[:10]) + f" ... (+{len(words) - 10})"
            else:
                display = ", ".join(words)
            
            response_text = f"@{msg.user_login} 🚫 Banwords ({len(words)}): {display}"
        
        await self.bus.publish("chat.outbound", OutboundMessage(
            channel=msg.channel,
            channel_id=msg.channel_id,
            text=response_text
        ))
