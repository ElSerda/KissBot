#!/usr/bin/env python3
"""
Message Handler - Phase 2.3 (SIMPLIFIED)
Traite les commandes chat basiques et publie les réponses sur MessageBus

Phase 2.3: Commandes simples (!ping, !uptime, !help)
Phase 2.4: Envoi des réponses via IRC
Phase 3+: Commandes avancées (!gc, !gi, !ask)
"""
import logging
import time
from typing import Any, Dict, Optional

from core.message_bus import MessageBus
from core.message_types import ChatMessage, OutboundMessage
from core.registry import Registry
from backends.game_lookup import GameLookup
from backends.game_cache import GameCache
from backends.music_cache import MusicCache
from backends.llm_handler import LLMHandler
from intelligence.core import extract_mention_message

# Phase 3.1: Import conditionnel pour éviter dépendance circulaire
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from twitchapi.transports.helix_readonly import HelixReadOnlyClient
    from core.system_monitor import SystemMonitor

LOGGER = logging.getLogger(__name__)


class MessageHandler:
    """
    Handler pour les commandes chat (Phase 3.4 - Quantum Commands Added)
    
    Traite les commandes:
    - !ping: Test du bot
    - !uptime: Temps de fonctionnement
    - !stats: Statistiques système (CPU/RAM/Threads) (Phase 3.3)
    - !help: Liste des commandes
    - !gi <game>: Info sur un jeu (Phase 3.1)
    - !gc: Jeu en cours du streamer (Phase 3.1)
    - !ask <question>: Question au LLM (Phase 3.2)
    - !qgame <name>: Recherche quantique de jeux (Phase 3.4)
    - !collapse <name> <number>: Ancrer jeu vérité terrain (Phase 3.4)
    - !quantum: Stats système quantique multi-domain (Phase 3.4)
    - !decoherence: Cleanup manuel états quantiques (Phase 3.4)
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
        
        # Phase 2.6: Deduplication pour éviter double traitement
        self._processed_messages = set()  # Cache des message IDs déjà traités
        self._cache_max_size = 100  # Limiter la taille du cache
        
        # Phase 3.2: Rate limiting pour mentions (15s cooldown)
        self._mention_last_time: Dict[str, float] = {}  # user_id -> timestamp
        self._mention_cooldown = config.get("commands", {}).get("cooldowns", {}).get("mention", 15.0)
        
        # Phase 3.1: Helix client (pour !gc)
        self.helix: Optional['HelixReadOnlyClient'] = None
        
        # Phase 3.3: System Monitor (pour !stats)
        self.system_monitor: Optional['SystemMonitor'] = None
        
        # Phase 3.1: Game Lookup
        self.game_lookup: Optional[GameLookup] = None
        if config and config.get("apis", {}).get("rawg_key"):
            try:
                self.game_lookup = GameLookup(config)
                LOGGER.info("✅ GameLookup initialisé")
            except Exception as e:
                LOGGER.error(f"❌ GameLookup init failed: {e}")
        
        # Phase 3.4: Quantum Game Cache
        self.game_cache: Optional[GameCache] = None
        try:
            self.game_cache = GameCache(config)
            LOGGER.info("🔬 QuantumGameCache initialisé")
        except Exception as e:
            LOGGER.error(f"❌ QuantumGameCache init failed: {e}")
        
        # Phase 3.4: Quantum Music Cache (POC)
        self.music_cache: Optional[MusicCache] = None
        try:
            self.music_cache = MusicCache(config)
            LOGGER.info("🎵 QuantumMusicCache initialisé (POC)")
        except Exception as e:
            LOGGER.error(f"❌ QuantumMusicCache init failed: {e}")
        
        # Phase 3.2: LLM Handler
        self.llm_handler: Optional[LLMHandler] = None
        if config and config.get("apis", {}).get("openai_key"):
            try:
                self.llm_handler = LLMHandler(config)
                LOGGER.info("✅ LLMHandler initialisé")
            except Exception as e:
                LOGGER.error(f"❌ LLMHandler init failed: {e}")
        
        # Subscribe aux messages entrants
        self.bus.subscribe("chat.inbound", self._handle_chat_message)
        
        LOGGER.info("MessageHandler initialisé (Phase 3.2 - LLM Added)")
    
    def set_helix(self, helix: 'HelixReadOnlyClient') -> None:
        """
        Phase 3.1: Injecte le client Helix après initialisation
        (car Helix est créé après MessageHandler dans main.py)
        """
        self.helix = helix
        LOGGER.debug("✅ Helix client injecté dans MessageHandler")
    
    def set_system_monitor(self, system_monitor: 'SystemMonitor') -> None:
        """
        Phase 3.3: Injecte le SystemMonitor après initialisation
        (pour accéder aux métriques système via !stats)
        """
        self.system_monitor = system_monitor
        LOGGER.debug("✅ SystemMonitor injecté dans MessageHandler")
    
    async def _handle_chat_message(self, msg: ChatMessage) -> None:
        """
        Traite un message chat entrant
        Détecte les commandes et publie les réponses
        
        Args:
            msg: Message chat reçu
        """
        # Phase 2.6: Deduplication - Créer ID unique basé sur user + text + timestamp approx
        msg_id = f"{msg.user_id}:{msg.text}"
        
        if msg_id in self._processed_messages:
            LOGGER.debug(f"⏭️ Message déjà traité, skip: {msg.text[:30]}")
            return
        
        # Ajouter au cache (avec limite de taille)
        self._processed_messages.add(msg_id)
        if len(self._processed_messages) > self._cache_max_size:
            # Vider la moitié du cache (FIFO approximatif)
            self._processed_messages = set(list(self._processed_messages)[50:])
        
        # Phase 3.2: Détection des mentions (@bot_name ou bot_name)
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
            # Phase 3.3: System Stats
            await self._cmd_stats(msg)
        elif command in ["!commands", "!help"]:
            await self._cmd_help(msg)
        elif command == "!gi":
            # Phase 3.1: Game Info
            await self._cmd_game_info(msg, args)
        elif command == "!gc":
            # Phase 3.1: Game Current
            await self._cmd_game_current(msg)
        elif command == "!ask":
            # Phase 3.2: LLM Ask
            await self._cmd_ask(msg, args)
        elif command == "!qgame":
            # Phase 3.4: Quantum Game Search
            await self._cmd_qgame(msg, args)
        elif command == "!collapse":
            # Phase 3.4: Quantum Collapse
            await self._cmd_collapse(msg, args)
        elif command == "!quantum":
            # Phase 3.4: Quantum Stats
            await self._cmd_quantum(msg)
        elif command == "!decoherence":
            # Phase 3.4: Quantum Cleanup
            await self._cmd_decoherence(msg, args)
        else:
            # Commande inconnue, pas de réponse
            LOGGER.debug(f"Unknown command: {command}")
    
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
        Commande !stats - Statistiques système (CPU/RAM/Threads) (Phase 3.3)
        
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
        
        # Phase 3.1: Ajouter game commands si disponibles
        if self.game_lookup:
            commands_list += " !gi <game> !gc"
        
        # Phase 3.2: Ajouter LLM command si disponible
        if self.llm_handler and self.llm_handler.is_available():
            commands_list += " !ask <question> | Mention @bot_name <message>"
        
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
        Phase 3.1: Commande !gi <game> - Info sur un jeu
        
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
            LOGGER.info(f"🎮 Searching game: {game_name}")
            
            # Phase 2.6: Timeout handling (config timeout déjà dans GameLookup)
            game = await self.game_lookup.search_game(game_name)
            
            if not game:
                response_text = f"@{msg.user_login} ❌ Game not found: {game_name}"
            else:
                # Format compact pour Twitch chat
                rating_str = f"{game.rating_rawg:.1f}" if game.rating_rawg > 0 else "N/A"
                year_str = game.year if game.year != "?" else "?"
                
                # Platforms (max 3)
                platforms = game.platforms[:3] if game.platforms else []
                platforms_str = ", ".join(platforms) if platforms else "Unknown"
                
                response_text = (
                    f"@{msg.user_login} 🎮 {game.name} ({year_str}) "
                    f"⭐ {rating_str}/5 | {platforms_str}"
                )
                
                # Ajouter metacritic si disponible
                if game.metacritic and game.metacritic > 0:
                    response_text += f" | MC: {game.metacritic}"
            
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            LOGGER.info(f"✅ Game info sent for: {game_name}")
            
        except Exception as e:
            LOGGER.error(f"❌ Error searching game: {e}", exc_info=True)
            response_text = f"@{msg.user_login} ❌ Error searching game"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
    
    async def _cmd_game_current(self, msg: ChatMessage) -> None:
        """
        Phase 3.1: Commande !gc - Jeu en cours du streamer (enrichi)
        
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
                viewer_count = stream_info.get("viewer_count", 0)
                
                # Enrichissement du jeu (IGDB name = source fiable)
                if self.game_lookup:
                    LOGGER.info(f"🎮 Enriching game from stream: {game_name}")
                    game = await self.game_lookup.enrich_game_from_igdb_name(game_name)
                    
                    if game:
                        # Format COMPACT (sans confidence/sources pour gagner de l'espace)
                        game_info = self.game_lookup.format_result(game, compact=True)
                        
                        # Ajouter la description si disponible
                        if game.summary:
                            # Calculer l'espace disponible (limite Twitch ~500 chars)
                            prefix = f"@{msg.user_login} 🎮 {msg.channel} joue actuellement à {game_info} | "
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
                                f"@{msg.user_login} 🎮 {msg.channel} joue actuellement à "
                                f"{game_info} ({viewer_count} viewers)"
                            )
                    else:
                        # Fallback si enrichissement échoue
                        response_text = (
                            f"@{msg.user_login} 🎮 {msg.channel} joue actuellement à "
                            f"**{game_name}** ({viewer_count} viewers)"
                        )
                else:
                    # Pas de GameLookup configuré
                    response_text = (
                        f"@{msg.user_login} 🎮 {msg.channel} joue actuellement à "
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
        Phase 3.2: Commande !ask - Question au LLM
        
        Args:
            msg: Message entrant
            question: Question de l'utilisateur (args après !ask)
        """
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
            
            # Appeler le LLM
            llm_response = await self.llm_handler.ask(
                question=question,
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
    
    async def _handle_mention(self, msg: ChatMessage, mention_text: str) -> None:
        """
        Phase 3.2: Traite une mention du bot (@bot_name ou bot_name)
        
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
            from intelligence.core import process_llm_request
            
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
    
    # ============================================================
    # Phase 3.4: QUANTUM COMMANDS
    # ============================================================
    
    async def _cmd_qgame(self, msg: ChatMessage, game_name: str) -> None:
        """
        Commande !qgame <name> - Recherche quantique de jeux avec superposition
        
        Affiche multiple résultats numérotés (1-2-3) avec confiance quantique.
        Users/Mods peuvent ensuite !collapse <name> <number> pour ancrer la vérité.
        
        Args:
            msg: Message original
            game_name: Nom du jeu à rechercher
        """
        if not self.game_cache:
            response_text = f"@{msg.user_login} ❌ Quantum game cache not available"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            return
        
        if not game_name or len(game_name.strip()) == 0:
            response_text = f"@{msg.user_login} 🔬 Usage: !qgame <game name>"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            return
        
        try:
            LOGGER.info(f"🔬 Quantum game search from {msg.user_login}: {game_name}")
            
            # Recherche quantique (retourne liste de superpositions)
            superpositions = await self.game_cache.search_quantum_game(
                query=game_name,
                observer=msg.user_login
            )
            
            if not superpositions:
                response_text = f"@{msg.user_login} ❌ Aucun jeu trouvé pour: {game_name}"
                await self.bus.publish("chat.outbound", OutboundMessage(
                    channel=msg.channel,
                    channel_id=msg.channel_id,
                    text=response_text,
                    prefer="irc"
                ))
                return
            
            # Format response avec superpositions numérotées
            if len(superpositions) == 1 and superpositions[0].get("collapsed"):
                # État collapsed = vérité terrain confirmée
                game = superpositions[0]["game"]
                confirmations = superpositions[0].get("confirmations", 0)
                
                response_text = (
                    f"@{msg.user_login} 🔒 {game['name']} ({game.get('year', '?')}) - "
                    f"CONFIRMÉ ✅ ({confirmations} confirmations)"
                )
            else:
                # Superposition active = multiple suggestions
                response_parts = [f"@{msg.user_login} 🔬 Superposition pour '{game_name}':"]
                
                for sup in superpositions[:3]:  # Max 3 superpositions
                    idx = sup["index"]
                    game = sup["game"]
                    conf = sup["confidence"]
                    verified = sup["verified"]
                    
                    # Format game line
                    game_line = f"{idx}. ⚛️ {game['name']}"
                    if game.get("year"):
                        game_line += f" ({game['year']})"
                    
                    # Add rating if available
                    if game.get("metacritic"):
                        game_line += f" - 🏆 {game['metacritic']}/100"
                    elif game.get("rating_rawg"):
                        game_line += f" - ⭐ {game['rating_rawg']:.1f}/5"
                    
                    game_line += f" (conf: {conf:.1f})"
                    
                    if verified:
                        game_line += " ✅"
                    
                    response_parts.append(game_line)
                
                # Add collapse instruction
                response_parts.append(f"→ !collapse {game_name} <number> pour confirmer")
                
                response_text = " | ".join(response_parts)
            
            # Truncate if too long
            if len(response_text) > 500:
                response_text = response_text[:497] + "..."
            
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            LOGGER.info(f"✅ Quantum game response sent to {msg.user_login}")
            
        except Exception as e:
            LOGGER.error(f"❌ Error processing !qgame: {e}", exc_info=True)
            response_text = f"@{msg.user_login} ❌ Erreur recherche quantique"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
    
    async def _cmd_collapse(self, msg: ChatMessage, args: str) -> None:
        """
        Commande !collapse <name> <number> - Ancrer vérité terrain (Mods/Admins only)
        
        Collapse la fonction d'onde quantique vers un état fixé.
        Mods/Admins confirment quel jeu est le vrai parmi les superpositions.
        
        Args:
            msg: Message original
            args: "<game_name> <number>" (ex: "hades 1")
        """
        # Permission check: Mods/Admins only
        if not (msg.is_mod or msg.is_broadcaster):
            response_text = f"@{msg.user_login} ⚠️ !collapse réservé aux mods/admins"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            return
        
        if not self.game_cache:
            response_text = f"@{msg.user_login} ❌ Quantum game cache not available"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            return
        
        if not args or len(args.strip()) == 0:
            response_text = f"@{msg.user_login} 🔬 Usage: !collapse <game> <number>"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            return
        
        try:
            # Parse args: "game name 1" → game_name="game name", number=1
            parts = args.strip().rsplit(maxsplit=1)
            
            if len(parts) != 2:
                response_text = f"@{msg.user_login} ❌ Format: !collapse <game> <number>"
                await self.bus.publish("chat.outbound", OutboundMessage(
                    channel=msg.channel,
                    channel_id=msg.channel_id,
                    text=response_text,
                    prefer="irc"
                ))
                return
            
            game_name, number_str = parts
            
            try:
                number = int(number_str)
            except ValueError:
                response_text = f"@{msg.user_login} ❌ Le nombre doit être 1, 2 ou 3"
                await self.bus.publish("chat.outbound", OutboundMessage(
                    channel=msg.channel,
                    channel_id=msg.channel_id,
                    text=response_text,
                    prefer="irc"
                ))
                return
            
            LOGGER.info(f"💥 Quantum collapse from {msg.user_login}: {game_name} → {number}")
            
            # Collapse quantum state
            collapsed_game = self.game_cache.collapse_game(
                query=game_name,
                observer=msg.user_login,
                state_index=number
            )
            
            if collapsed_game:
                response_text = (
                    f"💥 @{msg.user_login} a fait collapse '{game_name}' → "
                    f"{collapsed_game['name']} ({collapsed_game.get('year', '?')}) ✅ État figé !"
                )
            else:
                response_text = (
                    f"@{msg.user_login} ❌ Impossible de collapse '{game_name}' "
                    f"(état inexistant ou index invalide)"
                )
            
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            LOGGER.info(f"✅ Collapse response sent to {msg.user_login}")
            
        except Exception as e:
            LOGGER.error(f"❌ Error processing !collapse: {e}", exc_info=True)
            response_text = f"@{msg.user_login} ❌ Erreur collapse quantique"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
    
    async def _cmd_quantum(self, msg: ChatMessage) -> None:
        """
        Commande !quantum - Stats système quantique multi-domain
        
        Aggregate stats de TOUS les domaines quantiques:
        - GAME: Jeux en cache quantum
        - MUSIC: Tracks en cache quantum (POC)
        
        Future: CLIPS, VODS, etc.
        """
        try:
            LOGGER.info(f"🔬 Quantum stats request from {msg.user_login}")
            
            stats_parts = [f"@{msg.user_login} 🔬 Système Quantique"]
            
            # Game stats
            if self.game_cache:
                game_stats = self.game_cache.get_quantum_stats()
                game_part = (
                    f"GAME: {game_stats['total_games']} jeux | "
                    f"{game_stats['superpositions_active']} superpositions | "
                    f"{game_stats['verified_percentage']:.0f}% verified"
                )
                stats_parts.append(game_part)
            
            # Music stats (POC)
            if self.music_cache:
                music_stats = self.music_cache.get_quantum_stats()
                music_part = (
                    f"MUSIC: {music_stats['total_tracks']} tracks | "
                    f"{music_stats['superpositions_active']} superpositions | "
                    f"{music_stats['verified_percentage']:.0f}% verified"
                )
                stats_parts.append(music_part)
            
            response_text = " | ".join(stats_parts)
            
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
            LOGGER.info(f"✅ Quantum stats sent to {msg.user_login}")
            
        except Exception as e:
            LOGGER.error(f"❌ Error processing !quantum: {e}", exc_info=True)
            response_text = f"@{msg.user_login} ❌ Erreur stats quantiques"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="irc"
            ))
    
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
        
        # Cleanup game cache
        if self.game_cache:
            game_evaporated = self.game_cache.cleanup_expired()
            cleanup_parts.append(f"GAME: {game_evaporated} évaporés")
        
        # Cleanup music cache
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
        
        # Try to delete from game cache
        if self.game_cache:
            for name in name_list:
                cache_key = f"game:{name.lower().strip()}"
                if cache_key in self.game_cache.quantum_states:
                    del self.game_cache.quantum_states[cache_key]
                    deleted_count += 1
                    LOGGER.info(f"💨 Deleted quantum state: {cache_key}")
                else:
                    failed_names.append(name)
            
            # Save cache after deletions
            if deleted_count > 0:
                self.game_cache._save_cache()
        
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
    
    def get_stats(self) -> dict:
        """Retourne les stats du handler"""
        return {
            "commands_processed": self.command_count,
            "uptime_seconds": int(time.time() - self.start_time)
        }
