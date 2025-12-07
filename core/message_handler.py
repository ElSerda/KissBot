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
from core.feature_manager import get_feature_manager, Feature
from core.memory_profiler import log_feature_mem, profile_block
from modules.moderation import get_banword_manager

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
        
        # Get feature manager (already initialized in main.py)
        self.features = get_feature_manager()
        
        # Game Lookup (Rust Engine avec fallback Python) - Conditional
        self.game_lookup = None
        if self.features and self.features.is_enabled(Feature.GAME_ENGINE):
            try:
                with profile_block("game_lookup_init"):
                    from modules.integrations.game_engine.rust_wrapper import get_game_lookup
                    db_path = config.get('db_path', 'kissbot.db')
                    self.game_lookup = get_game_lookup(db_path, config)
                LOGGER.info("🦀 GameLookup initialisé (Rust Engine + Python fallback)")
            except Exception as e:
                LOGGER.error(f"❌ GameLookup init failed: {e}")
        
        # Quantum Music Cache (POC) - Conditional
        self.music_cache = None
        if self.features and self.features.is_enabled(Feature.MUSIC_CACHE):
            try:
                with profile_block("music_cache_init"):
                    from modules.integrations.music.music_cache import MusicCache
                    self.music_cache = MusicCache(config)
                LOGGER.info("🎵 QuantumMusicCache initialisé (POC)")
            except Exception as e:
                LOGGER.error(f"❌ QuantumMusicCache init failed: {e}")
        
        # LLM Handler - Conditional (biggest memory saver if disabled)
        self.llm_handler = None
        if self.features and self.features.is_enabled(Feature.LLM):
            if config and config.get("apis", {}).get("openai_key"):
                try:
                    with profile_block("llm_handler_init"):
                        from modules.integrations.llm_provider.llm_handler import LLMHandler
                        self.llm_handler = LLMHandler(config)
                    LOGGER.info("✅ LLMHandler initialisé")
                except Exception as e:
                    LOGGER.error(f"❌ LLMHandler init failed: {e}")
        
        # Translation Service - Conditional (langdetect = ~57MB!)
        self.translator = None
        self.dev_whitelist = set()
        if self.features and self.features.is_enabled(Feature.TRANSLATOR):
            try:
                with profile_block("translator_init"):
                    from modules.integrations.translator.translator import get_translator, get_dev_whitelist
                    self.translator = get_translator()
                    self.dev_whitelist = get_dev_whitelist(db_manager=None)
                LOGGER.info("🌍 TranslationService initialisé")
            except Exception as e:
                LOGGER.error(f"❌ TranslationService init failed: {e}")
        
        # BanWord Manager (auto-ban sur mots interdits) - Always enabled
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
    
    def set_twitch(self, twitch_client) -> None:
        """
        Injecte le Twitch API Client après initialisation
        (pour appels API comme /announcements via !kbupdate)
        """
        self.twitch = twitch_client
        LOGGER.debug("✅ Twitch API Client injecté dans MessageHandler")
    
    def _sanitize_unicode_injection(self, text: str) -> str:
        """
        🛡️ SANITIZER: Supprime les caractères Unicode invisibles utilisés pour l'injection.
        
        Ranges dangereux supprimés:
        - U+E0000-U+E01FF: Tag Characters (texte caché dans emojis)
        - U+200B-U+200F: Zero-width spaces et directional marks
        - U+2028-U+202F: Line/paragraph separators et invisibles
        - U+2060-U+206F: Word joiners et invisibles
        - U+FEFF: BOM (Byte Order Mark)
        
        Exemple d'attaque bloquée:
        🥰 + U+E0148,U+E0155... = "Hey serda_bot hack" caché
        
        Args:
            text: Texte brut du message
            
        Returns:
            Texte nettoyé sans caractères invisibles dangereux
        """
        if not text:
            return text
        
        cleaned = []
        injection_detected = False
        
        for char in text:
            cp = ord(char)
            
            # Tag Characters (emoji injection) - U+E0000 à U+E01FF
            if 0xE0000 <= cp <= 0xE01FF:
                injection_detected = True
                continue
            
            # Zero-width et directional marks - U+200B à U+200F
            if 0x200B <= cp <= 0x200F:
                injection_detected = True
                continue
            
            # Line/paragraph separators invisibles - U+2028 à U+202F
            if 0x2028 <= cp <= 0x202F:
                injection_detected = True
                continue
            
            # Word joiners et format chars - U+2060 à U+206F
            if 0x2060 <= cp <= 0x206F:
                injection_detected = True
                continue
            
            # BOM
            if cp == 0xFEFF:
                injection_detected = True
                continue
            
            cleaned.append(char)
        
        result = ''.join(cleaned)
        
        if injection_detected:
            LOGGER.warning(f"🛡️ Unicode injection détectée et nettoyée: '{text[:50]}' → '{result[:50]}'")
        
        return result
    
    async def _handle_chat_message(self, msg: ChatMessage) -> None:
        """
        Traite un message chat entrant.
        Pipeline en 3 niveaux :
        - Niveau 1 : Filtres passifs (logs, analytics) - TOUJOURS exécutés
        - Niveau 2 : Filtres bloquants (banword, spam, flood) - peuvent STOP
        - Niveau 3 : Dispatch exclusif (commandes > mentions > reste)
        
        Args:
            msg: Message chat reçu
        """
        text = (msg.text or "").strip()
        
        # 🛡️ SANITIZER: Supprimer les Unicode Tag Characters (anti-injection)
        # Range U+E0000-U+E01FF : Caractères invisibles utilisés pour cacher du texte
        # Exemple: 🥰 + caractères invisibles encodant "@serda_bot hack"
        text = self._sanitize_unicode_injection(text)
        
        # ═══════════════════════════════════════════════════════════════════
        # 🔇 EARLY EXITS - Cas où on ignore silencieusement
        # ═══════════════════════════════════════════════════════════════════
        
        # Message vide
        if not text:
            return
        
        # Ignorer les messages des autres bots connus
        KNOWN_BOTS = [
            'nightbot', 'streamelements', 'streamlabs', 'moobot', 'fossabot',
            'wizebot', 'botisimo', 'cloudbot', 'deepbot', 'ankhbot',
            'phantombot', 'coebot', 'ohbot', 'revlobot', 'vivbot'
        ]
        
        if msg.user_login.lower() in KNOWN_BOTS:
            LOGGER.debug(f"🤖 Ignoring bot message from {msg.user_login}")
            return
        
        # ═══════════════════════════════════════════════════════════════════
        # 🔄 DEDUPLICATION - Éviter double traitement (AVANT tout)
        # ═══════════════════════════════════════════════════════════════════
        msg_timestamp = int(time.time())
        msg_id = f"{msg.user_id}:{text}:{msg_timestamp}"
        
        if msg_id in self._processed_messages:
            LOGGER.debug(f"⏭️ Message déjà traité, skip: {text[:30]}")
            return
        
        # Ajouter au cache (avec limite de taille)
        self._processed_messages.add(msg_id)
        if len(self._processed_messages) > self._cache_max_size:
            self._processed_messages = set(list(self._processed_messages)[50:])
        
        # ═══════════════════════════════════════════════════════════════════
        # 🚫 NIVEAU 2 : FILTRES BLOQUANTS (banword, spam, flood)
        # ═══════════════════════════════════════════════════════════════════
        
        # Banword check - s'applique à TOUS les messages (commandes incluses)
        matched_banword = self.banword_manager.check_message(msg.channel, text)
        if matched_banword:
            await self._execute_banword_ban(msg, matched_banword)
            # TODO: analytics.mark_blocked(msg, "banword")
            return
        
        # TODO: Spam detection hook (à implémenter)
        # if await self._is_spam(msg):
        #     await self._handle_spam(msg)
        #     return
        
        # TODO: Rate limit check (à injecter)
        # if self._is_rate_limited(msg.user_id):
        #     return
        
        # ═══════════════════════════════════════════════════════════════════
        # 🎯 NIVEAU 3 : DISPATCH EXCLUSIF (commandes > mentions > passif)
        # ═══════════════════════════════════════════════════════════════════
        
        # 1. COMMANDES - Priorité absolue (fixe le hack !trad & serda_bot)
        if text.startswith("!"):
            await self._handle_command(msg, text)
            return
        
        # 2. MENTIONS - Seulement pour messages NON-commandes
        bot_name = self.config.get("bot_login_name", "serda_bot")
        from modules.intelligence.core import extract_mention_message
        mention_text = extract_mention_message(text, bot_name)
        
        if mention_text:
            await self._handle_mention(msg, mention_text)
            return
        
        # 3. FEATURES PASSIVES - Messages normaux sans commande ni mention
        await self._handle_passive_features(msg, text)
    
    async def _handle_command(self, msg: ChatMessage, text: str) -> None:
        """
        Route une commande ! vers le handler approprié.
        Extrait du pipeline principal pour clarté.
        """
        parts = text.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        LOGGER.info(f"🤖 Command: {command} from {msg.user_login} in #{msg.channel}")

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
            await self._cmd_joke(msg, args)
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
        elif command == "!kbanniv":
            await self._cmd_kbanniv(msg, args)
        elif command == "!decoherence":
            await self._cmd_decoherence(msg, args)
        elif command == "!kisscharity":
            await self._cmd_kisscharity(msg, args)
        elif command == "!kbupdate":
            await self._cmd_kbupdate(msg, args)
        elif command == "!kbkofi":
            await self._cmd_kbkofi(msg)
        elif command == "!kbpersona":
            await self._cmd_kbpersona(msg, args)
        elif command == "!kbnsfw":
            await self._cmd_kbnsfw(msg, args)
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
        """Commande !ping - Déléguée à modules/"""
        from modules.classic_commands.user_commands.system import handle_ping
        await handle_ping(self, msg)
    
    async def _cmd_uptime(self, msg: ChatMessage) -> None:
        """Commande !uptime - Déléguée à modules/"""
        from modules.classic_commands.user_commands.system import handle_uptime
        await handle_uptime(self, msg)
    
    async def _cmd_stats(self, msg: ChatMessage) -> None:
        """Commande !stats - Déléguée à modules/"""
        from modules.classic_commands.user_commands.system import handle_stats
        await handle_stats(self, msg)
    
    async def _cmd_help(self, msg: ChatMessage) -> None:
        """Commande !help - Déléguée à modules/"""
        from modules.classic_commands.user_commands.system import handle_help
        await handle_help(self, msg)
    
    async def _cmd_game_info(self, msg: ChatMessage, game_name: str) -> None:
        """Commande !gi <game> - Déléguée à modules/"""
        from modules.classic_commands.user_commands.game import handle_gi
        await handle_gi(self, msg, game_name)
    
    async def _cmd_game_summary(self, msg: ChatMessage, game_name: str) -> None:
        """Commande !gs <game> - Déléguée à modules/"""
        from modules.classic_commands.user_commands.game import handle_gs
        await handle_gs(self, msg, game_name)
    
    
    async def _cmd_perf(self, msg: ChatMessage, args: str) -> None:
        """Commande !perf - Déléguée à modules/"""
        from modules.classic_commands.mod_commands.performance import handle_perf
        await handle_perf(self, msg, args)
    
    async def _cmd_perftrace(self, msg: ChatMessage, args: str) -> None:
        """Commande !perftrace - Déléguée à modules/"""
        from modules.classic_commands.mod_commands.performance import handle_perftrace
        await handle_perftrace(self, msg, args)
    
    async def _cmd_game_current(self, msg: ChatMessage) -> None:
        """Commande !gc - Déléguée à modules/"""
        from modules.classic_commands.user_commands.game import handle_gc
        await handle_gc(self, msg)
    
    async def _cmd_ask(self, msg: ChatMessage, args: str) -> None:
        """Commande !ask - Déléguée à modules/"""
        from modules.classic_commands.user_commands.intelligence import handle_ask
        await handle_ask(self, msg, args)
    
    async def _cmd_joke(self, msg: ChatMessage, args: str) -> None:
        """Commande !joke - Déléguée à modules/"""
        from modules.classic_commands.user_commands.intelligence import handle_joke
        await handle_joke(self, msg, args)
    
    async def _cmd_wiki(self, msg: ChatMessage, query: str) -> None:
        """Commande !wiki - Déléguée à modules/"""
        from modules.classic_commands.user_commands.wiki import handle_wiki
        await handle_wiki(self, msg, query)
    
    async def _cmd_kbanniv(self, msg: ChatMessage, args: str) -> None:
        """Commande !kbanniv - Déléguée à modules/"""
        from modules.classic_commands.user_commands.kbanniv import handle_kbanniv
        await handle_kbanniv(self, msg, args)
    
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
        
        # 🔴 ANTI-DOUBLON: Dedupe basé sur user + contenu (fenêtre 10s)
        mention_key = f"mention:{msg.user_id}:{msg.channel}:{mention_text[:100]}"
        current_time = time.time()
        
        if not hasattr(self, '_mention_dedupe'):
            self._mention_dedupe = {}
        
        last_mention = self._mention_dedupe.get(mention_key, 0)
        if current_time - last_mention < 10.0:  # 10s window anti-doublon
            LOGGER.warning(f"🔴 DOUBLON MENTION BLOQUÉ: {msg.user_login} (delta={current_time - last_mention:.2f}s)")
            return
        
        self._mention_dedupe[mention_key] = current_time
        
        # Cleanup vieux entries (garder 200 max)
        if len(self._mention_dedupe) > 200:
            sorted_keys = sorted(self._mention_dedupe.items(), key=lambda x: x[1])
            for k, _ in sorted_keys[:100]:
                del self._mention_dedupe[k]
        
        # Rate limiting additionnel: 15s cooldown par utilisateur (tous messages confondus)
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
                pre_optimized=False,
                channel_id=msg.channel_id  # 🎭 Personnalité par channel
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
        
        Mode dry-run en dev: ne ban pas vraiment, juste log + message
        
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
        
        # ═══════════════════════════════════════════════════════════════════
        # MODE DRY-RUN : Vérifier si on peut vraiment bannir
        # ═══════════════════════════════════════════════════════════════════
        
        # Ne jamais bannir le broadcaster (sécurité absolue)
        if msg.is_broadcaster:
            LOGGER.warning(
                f"⚠️ Banword détecté mais broadcaster protégé: {msg.user_login} in #{msg.channel}"
            )
            # Ne PAS afficher le mot banni dans le message public (sécurité)
            safe_msg = f"🚫 Mot interdit détecté mais broadcaster protégé: @{msg.user_login}"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=safe_msg,
                prefer="irc"
            ))
            return

        # Config: activer le vrai ban uniquement si explicitement configuré
        banword_config = self.config.get("moderation", {}).get("banword", {})
        dry_run = banword_config.get("dry_run", False)  # Par défaut: dry-run activé !
        
        # Vérifier si le bot est mod sur ce channel (via les meta du message)
        bot_is_mod = msg.meta.get("bot_is_mod", False)  # ← Passé depuis EventSubChatClient
        
        try:
            if dry_run:
                # MODE DRY-RUN: Juste notifier, ne pas bannir
                # Ne PAS afficher le mot banni dans le message public (sécurité)
                if bot_is_mod:
                    notify_msg = (
                        f"🚫 [DRY-RUN] Mot interdit détecté! "
                        f"Je POURRAIS ban @{msg.user_login} (je suis mod)"
                    )
                else:
                    notify_msg = (
                        f"🚫 [DRY-RUN] Mot interdit détecté! "
                        f"User: @{msg.user_login} — ⚠️ Je ne suis pas mod, ban impossible"
                    )
                
                await self.bus.publish("chat.outbound", OutboundMessage(
                    channel=msg.channel,
                    channel_id=msg.channel_id,
                    text=notify_msg,
                    prefer="irc"
                ))
                
                LOGGER.info(f"🔒 DRY-RUN: Would ban {msg.user_login} for '{matched_word}'")
                
            else:
                # MODE PRODUCTION: Vraiment bannir
                ban_command = f"/ban {msg.user_login} {ban_reason}"
                
                await self.bus.publish("chat.outbound", OutboundMessage(
                    channel=msg.channel,
                    channel_id=msg.channel_id,
                    text=ban_command,
                    prefer="irc"
                ))
                
                LOGGER.info(f"✅ Ban EXECUTED for {msg.user_login}: {ban_reason}")
            
        except Exception as e:
            LOGGER.error(f"❌ Error executing banword ban for {msg.user_login}: {e}", exc_info=True)
    
    # ============================================================
    # ADMIN COMMANDS
    # ============================================================
    
    async def _cmd_decoherence(self, msg: ChatMessage, args: str = "") -> None:
        """Commande !decoherence - Déléguée à modules/"""
        from modules.classic_commands.broadcaster_commands.decoherence import handle_decoherence
        await handle_decoherence(self, msg, args)

    async def _cmd_kisscharity(self, msg: ChatMessage, args: str) -> None:
        """!kisscharity - Délégué à modules/"""
        from modules.classic_commands.user_commands.promo import handle_kisscharity
        await handle_kisscharity(self, msg, args)
    
    async def _cmd_kbupdate(self, msg: ChatMessage, args: str) -> None:
        """
        !kbupdate <message> - Notifier tous les channels d'une MAJ du bot
        
        Owner only (el_serda) - Pas de cooldown
        Utilise l'API Helix /announcements (annonces officielles purple).
        """
        from modules.classic_commands.broadcaster_commands.broadcast import cmd_kbupdate
        
        # Check si Twitch client est disponible
        twitch_client = getattr(self, 'twitch', None)
        if not twitch_client:
            response_text = f"@{msg.user_login} ❌ Erreur système : Twitch API non disponible"
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="eventsub"
            ))
            return
        
        # Parser les arguments
        args_list = args.split() if args else []
        
        # Appeler le handler avec Twitch client
        response_text = await cmd_kbupdate(
            msg=msg,
            args=args_list,
            bus=self.bus,
            twitch_client=twitch_client
        )
        
        # Envoyer la réponse
        if response_text:
            await self.bus.publish("chat.outbound", OutboundMessage(
                channel=msg.channel,
                channel_id=msg.channel_id,
                text=response_text,
                prefer="eventsub"
            ))
    
    async def _cmd_kbkofi(self, msg: ChatMessage) -> None:
        """!kbkofi - Délégué à modules/"""
        from modules.classic_commands.user_commands.promo import handle_kbkofi
        await handle_kbkofi(self, msg)
    
    async def _cmd_kbpersona(self, msg: ChatMessage, args: str) -> None:
        """Commande !kbpersona - Déléguée à modules/"""
        from modules.classic_commands.broadcaster_commands.personality import handle_kbpersona
        await handle_kbpersona(self, msg, args)
    
    async def _cmd_kbnsfw(self, msg: ChatMessage, args: str) -> None:
        """Commande !kbnsfw - Déléguée à modules/"""
        from modules.classic_commands.broadcaster_commands.personality import handle_kbnsfw
        await handle_kbnsfw(self, msg, args)
    
    def get_uptime_seconds(self) -> int:
        """Retourne l'uptime en secondes"""
        return int(time.time() - self.start_time)
    
    async def _handle_passive_features(self, msg: ChatMessage, text: str) -> None:
        """
        Traite les features passives pour les messages normaux.
        Appelé uniquement pour les messages qui ne sont ni commandes ni mentions.
        
        Args:
            msg: Message chat reçu
            text: Texte nettoyé du message
        """
        # Auto-traduction pour devs whitelistés
        await self._handle_auto_translation(msg)
        
        # TODO: Autres features passives futures
        # - Auto-persona (réponse contextuelle)
        # - Détection de questions
        # - Réactions automatiques
    
    async def _handle_auto_translation(self, msg: ChatMessage) -> None:
        """
        Auto-traduction UNIQUEMENT pour les devs whitelistés.
        
        Activé par !adddev <user> - Désactivé par !remdev <user>
        La commande !trad reste disponible pour tous.
        """
        # 🛡️ RESTRICTION: Seulement pour les devs whitelistés
        # Évite les appels inutiles à detect_language() pour chaque message
        if not self.dev_whitelist.is_dev(msg.user_login):
            return
        
        # Détecter la langue
        detected_lang = await self.translator.detect_language(msg.text)
        
        if detected_lang and detected_lang != 'fr':
            # Mémoriser la langue de cet utilisateur (pour !trad auto:)
            self.translator.remember_user_language(msg.channel, msg.user_login, detected_lang)
        
        # Si français, rien à afficher
        if detected_lang == 'fr' or not detected_lang:
            return
        
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
        """Commande !trad - Déléguée à modules/"""
        from modules.classic_commands.user_commands.trad import handle_trad
        await handle_trad(self, msg, args)
    
    async def _cmd_adddev(self, msg: ChatMessage, args: str) -> None:
        """Commande !adddev - Déléguée à modules/"""
        from modules.classic_commands.mod_commands.devlist import handle_adddev
        await handle_adddev(self, msg, args)
    
    async def _cmd_rmdev(self, msg: ChatMessage, args: str) -> None:
        """Commande !rmdev - Déléguée à modules/"""
        from modules.classic_commands.mod_commands.devlist import handle_rmdev
        await handle_rmdev(self, msg, args)
    
    async def _cmd_listdevs(self, msg: ChatMessage) -> None:
        """Commande !listdevs - Déléguée à modules/"""
        from modules.classic_commands.mod_commands.devlist import handle_listdevs
        await handle_listdevs(self, msg)
    
    # ════════════════════════════════════════════════════════════════════════
    # 🚫 BANWORD COMMANDS (Mod/Broadcaster only)
    # ════════════════════════════════════════════════════════════════════════
    
    async def _cmd_kbbanword(self, msg: ChatMessage, args: str) -> None:
        """Commande !kbbanword - Déléguée à modules/"""
        from modules.classic_commands.mod_commands.banwords import handle_kbbanword
        await handle_kbbanword(self, msg, args)
    
    async def _cmd_kbunbanword(self, msg: ChatMessage, args: str) -> None:
        """Commande !kbunbanword - Déléguée à modules/"""
        from modules.classic_commands.mod_commands.banwords import handle_kbunbanword
        await handle_kbunbanword(self, msg, args)
    
    async def _cmd_kbbanwords(self, msg: ChatMessage) -> None:
        """Commande !kbbanwords - Déléguée à modules/"""
        from modules.classic_commands.mod_commands.banwords import handle_kbbanwords
        await handle_kbbanwords(self, msg)
