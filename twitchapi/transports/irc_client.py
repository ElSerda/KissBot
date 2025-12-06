#!/usr/bin/env python3
"""
IRC Client - (avec timeout handling)
Client IRC Twitch complet:
- Écoute chat IRC → Publie sur chat.inbound
- Écoute chat.outbound → Envoie via IRC
- Gestion timeout pour éviter blocages LLM
"""

import asyncio
import logging
import time
from typing import Optional

from twitchAPI.twitch import Twitch
from twitchAPI.chat import Chat, ChatMessage as TwitchChatMessage, EventData
from twitchAPI.type import ChatEvent, AuthScope

from core.message_bus import MessageBus
from core.message_types import ChatMessage, OutboundMessage

LOGGER = logging.getLogger(__name__)


class IRCClient:
    """
    Client IRC Twitch (- Bidirectionnel)
    - Rejoint les channels
    - Écoute les messages → chat.inbound
    - Envoie les messages ← chat.outbound
    """
    
    def __init__(
        self,
        twitch: Twitch,
        bus: MessageBus,
        bot_user_id: str,
        bot_login: str,
        channels: list[str],
        irc_send_timeout: float = 5.0
    ):
        """
        Args:
            twitch: Instance Twitch avec user token
            bus: MessageBus pour publier
            bot_user_id: ID du bot (pour ignorer ses propres messages)
            bot_login: Login du bot
            channels: Liste des channels à rejoindre (ex: ["el_serda"])
            irc_send_timeout: Timeout envoi IRC en secondes (Phase 2.6)
        """
        self.twitch = twitch
        self.bus = bus
        self.bot_user_id = bot_user_id
        self.bot_login = bot_login.lower()
        self.channels = channels
        self.irc_send_timeout = irc_send_timeout
        
        self.chat: Optional[Chat] = None
        self._running = False
        self._joined_channels = set()  # Track channels we've already joined
        
        # Track bot's permissions per channel (RAM cache)
        self._channel_permissions = {}   # channel -> {is_mod, is_vip, rate_limit, safe_delay}
        self._vip_status_cache = {}      # Glue code: Cache VIP status (pyTwitchAPI only caches mod/sub)
        
        # Keepalive task (prevent silent IRC disconnects)
        self._keepalive_task: Optional[asyncio.Task] = None
        
        # Proactive PING tracking
        self._ping_interval = 120  # Health check toutes les 2 minutes
        self._last_twitch_ping_time: Optional[float] = None  # Dernier PING reçu de Twitch
        
        # Reconnection failure tracking
        self._consecutive_disconnects = 0
        self._max_disconnects_before_restart = 2  # Force Chat restart après 2 échecs (4 min max)
        self._last_message_time: Optional[float] = None  # Track last received message
        
        # Subscribe aux messages sortants
        self.bus.subscribe("chat.outbound", self._handle_outbound_message)
        
        LOGGER.info(f"IRCClient init pour {bot_login} sur {len(channels)} channels (timeout={irc_send_timeout}s)")
    
    async def start(self) -> None:
        """Démarre le client IRC"""
        if self._running:
            LOGGER.warning("IRC Client déjà en cours")
            return
        
        LOGGER.info("🚀 Démarrage IRC Client...")
        
        try:
            # Créer instance Chat avec le user token ET les channels initiaux
            # CRITICAL: Passer initial_channel pour que pyTwitchAPI rejoigne
            # automatiquement les channels après une reconnexion automatique.
            # Sans ça, après reconnect, _join_target est vide et les channels
            # ne sont jamais rejoints → le bot ne reçoit plus de messages !
            # 
            # no_message_reset_time=7 : Réduit le timeout de 10 min à 7 min.
            # Twitch envoie PING toutes les ~5 min, notre health check est à 6 min.
            # Donc 7 min laisse pyTwitchAPI réagir juste après nous si on échoue.
            self.chat = await Chat(
                self.twitch, 
                initial_channel=self.channels,
                no_message_reset_time=7  # 7 min au lieu de 10 min par défaut
            )
            
            # Appliquer les monkey-patches (VIP detection, PING logging, reconnect verification)
            await self._apply_monkey_patches()
            LOGGER.info("✅ Tous les monkey-patches installés")
            
            # Register event handlers
            self.chat.register_event(ChatEvent.READY, self._on_ready)
            self.chat.register_event(ChatEvent.MESSAGE, self._on_message)
            self.chat.register_event(ChatEvent.JOIN, self._on_join)
            self.chat.register_event(ChatEvent.LEFT, self._on_left)
            self.chat.register_event(ChatEvent.ROOM_STATE_CHANGE, self._on_room_state_change)
            self.chat.register_event(ChatEvent.NOTICE, self._on_notice)
            
            # Démarrer le chat
            self.chat.start()
            self._running = True
            
            # Démarrer le keepalive
            self._keepalive_task = asyncio.create_task(self._keepalive_loop())
            
            LOGGER.info("✅ IRC Client démarré")
            
        except Exception as e:
            LOGGER.error(f"❌ Erreur démarrage IRC: {e}", exc_info=True)
            raise
    
    async def stop(self) -> None:
        """Arrête le client IRC proprement"""
        if not self._running:
            return
        
        LOGGER.info("🛑 Arrêt IRC Client...")
        
        # Arrêter le keepalive
        if self._keepalive_task:
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass
            self._keepalive_task = None
        
        if self.chat:
            self.chat.stop()
            self.chat = None
        
        self._running = False
        LOGGER.info("✅ IRC Client arrêté")
    
    async def _on_ready(self, ready_event: EventData) -> None:
        """
        Callback quand IRC est ready (premier démarrage uniquement)
        
        Note: Les channels sont automatiquement rejoints via initial_channel
        passé à Chat(). Ce callback sert juste à logger le status.
        Après une reconnexion automatique, ce callback n'est PAS rappelé
        (was_ready=True dans pyTwitchAPI), mais les channels sont rejoints
        automatiquement grâce à _join_target.
        """
        LOGGER.info("📡 IRC Ready - Channels seront rejoints automatiquement via initial_channel")
    
    async def _on_join(self, join_event: EventData) -> None:
        """Callback quand on rejoint un channel - Détecte les permissions"""
        channel = join_event.room.name
        
        # Log seulement la première fois qu'on rejoint ce channel
        if channel not in self._joined_channels:
            self._joined_channels.add(channel)
            
            # Détecter et cacher les permissions
            # Note: VIP sera détecté via USERSTATE (monkey-patched handler)
            await self._update_channel_permissions(channel)
    
    async def _on_left(self, left_event: EventData) -> None:
        """Callback quand on quitte un channel"""
        channel = left_event.room.name
        LOGGER.warning(f"📤 Left #{channel}")
        
        # Cleanup permissions cache
        if channel in self._channel_permissions:
            del self._channel_permissions[channel]
    
    async def _on_room_state_change(self, room_event: EventData) -> None:
        """
        Callback quand l'état du room change
        Détecte les changements de permissions (mod/unmod, vip/unvip)
        """
        channel = room_event.room.name
        
        # Re-check permissions
        await self._update_channel_permissions(channel, log_change=True)
    
    async def _on_notice(self, notice_event: EventData) -> None:
        """
        Callback pour les NOTICE IRC
        Détecte les mod/unmod/vip/unvip du bot
        """
        # NOTICE contient les messages système Twitch
        # Ex: "You have added serda_bot as a moderator"
        #     "You have removed serda_bot as a moderator"
        
        channel = notice_event.room.name
        message = notice_event.text if hasattr(notice_event, 'text') else ""
        
        # Détecter si c'est un changement de permission pour notre bot
        bot_mentioned = self.bot_login.lower() in message.lower()
        
        if bot_mentioned:
            # Mots-clés pour mod/unmod
            if "moderator" in message.lower() or "mod" in message.lower():
                LOGGER.info(f"🔔 #{channel}: NOTICE détecté → {message}")
                # Re-check permissions
                await self._update_channel_permissions(channel, log_change=True)
            
            # Mots-clés pour vip/unvip
            elif "vip" in message.lower():
                LOGGER.info(f"🔔 #{channel}: VIP NOTICE détecté → {message}")
                await self._update_channel_permissions(channel, log_change=True)
    
    async def _update_channel_permissions(self, channel: str, log_change: bool = False) -> None:
        """
        Détecte et met à jour les permissions du bot sur un channel
        Utilise Helix API get_moderated_channels() pour détection fiable.
        
        Args:
            channel: Nom du channel
            log_change: Si True, log les changements de permissions
        """
        # ⭐ Utiliser Helix API pour détecter mod (100% fiable)
        # Scope requis: user:read:moderated_channels
        try:
            moderated_channels = []
            async for ch in self.twitch.get_moderated_channels(user_id=self.bot_user_id):
                moderated_channels.append(ch.broadcaster_login.lower())
            
            is_mod = channel.lower() in moderated_channels
        except Exception as e:
            # Fallback sur IRC is_mod() si Helix fail
            LOGGER.warning(f"⚠️  Helix API get_moderated_channels() failed, fallback IRC: {e}")
            is_mod = self.chat.is_mod(channel)
        
        # VIP detection via glue code (pyTwitchAPI doesn't cache VIP)
        # Notre cache VIP est alimenté par les messages sortants du bot (_on_message)
        is_vip = self._vip_status_cache.get(channel.lower(), False)
        
        # Calculer rate limit et safe delay
        # Twitch IRC rate limits:
        # - Bot mod/VIP: 100 messages / 30 secondes
        # - Bot regular: 20 messages / 30 secondes (non-verified)
        # - Bot verified: 7500 messages / 30 secondes (si Twitch l'approuve)
        
        if is_mod or is_vip:
            rate_limit = 100
            safe_delay = 30.0 / (100 * 0.7)  # Kiss Mode: 30% safety margin = 0.43s
        else:
            rate_limit = 20
            safe_delay = 30.0 / (20 * 0.7)   # Kiss Mode: 30% safety margin = 2.14s (~2.5s)
        
        # Check si permissions ont changé
        old_perms = self._channel_permissions.get(channel, {})
        old_is_mod = old_perms.get("is_mod", False)
        
        # Mettre à jour le cache
        self._channel_permissions[channel] = {
            "is_mod": is_mod,
            "is_vip": is_vip,
            "rate_limit": rate_limit,
            "safe_delay": safe_delay,
            "can_send": True  # On assume qu'on peut toujours envoyer (sera vérifié par Twitch)
        }
        
        # Logs
        if not old_perms:
            # Premier join - Log complet
            if is_mod and is_vip:
                status = "MOD + VIP 🛡️👑"
            elif is_mod:
                status = "MOD 🛡️"
            elif is_vip:
                status = "VIP 👑"
            else:
                status = "User 👤"
            
            LOGGER.info(f"✅ Connecté à #{channel} → {status} | Rate: {rate_limit} msg/30s | Delay: {safe_delay:.2f}s")
            
            if not is_mod and not is_vip:
                LOGGER.warning(f"⚠️  #{channel}: Bot pas mod/VIP → Messages peuvent être invisibles! Faire: /mod {self.bot_login}")
        
        elif log_change and old_is_mod != is_mod:
            # Permission a changé !
            old_status = "MOD 🛡️" if old_is_mod else "User 👤"
            new_status = "MOD 🛡️" if is_mod else "User 👤"
            LOGGER.warning(f"🔄 #{channel}: Permissions changed → {old_status} → {new_status}")
            LOGGER.info(f"📊 #{channel}: New rate limit = {rate_limit} msg/30s | Delay = {safe_delay:.2f}s")
    
    async def _on_message(self, msg: TwitchChatMessage) -> None:
        """
        Callback quand un message IRC arrive
        → Publie sur MessageBus (topic: chat.inbound)
        
        Args:
            msg: Message Twitch IRC
        """
        # Ignorer nos propres messages
        if msg.user.name.lower() == self.bot_login:
            return
        
        # 🔍 DEBUG: Log TOUS les messages reçus
        LOGGER.info(f"📥 IRC RAW | {msg.user.name} dans #{msg.room.name}: {repr(msg.text[:100])}")
        
        # 🔍 DEBUG: Log des badges pour validation A+B
        badges_str = ""
        if msg.user.mod:
            badges_str += "MOD🛡️ "
        if msg.user.vip:
            badges_str += "VIP👑 "
        if msg.user.subscriber:
            badges_str += "SUB⭐ "
        if badges_str:
            LOGGER.info(f"🔍 DEBUG BADGES | {msg.user.name} dans #{msg.room.name}: {badges_str.strip()} | badges_raw={msg.user.badges}")
        
        # Créer ChatMessage pour MessageBus
        
        # Créer ChatMessage pour MessageBus
        chat_msg = ChatMessage(
            channel=msg.room.name,
            channel_id=msg.room.room_id,
            user_login=msg.user.name,
            user_id=msg.user.id,
            text=msg.text,
            is_mod=msg.user.mod,
            is_broadcaster=(msg.room.room_id == msg.user.id),
            is_vip=msg.user.vip,
            transport="irc",
            badges=msg.user.badges if msg.user.badges else {}
        )
        
        # Publier sur MessageBus
        try:
            await self.bus.publish("chat.inbound", chat_msg)
        except Exception as e:
            LOGGER.error(f"❌ Erreur publish chat.inbound: {e}")
    
    async def _handle_outbound_message(self, msg: OutboundMessage) -> None:
        """
        Envoie un message via IRC avec timeout
        
        Args:
            msg: Message à envoyer
        """
        if not self.chat or not self._running:
            LOGGER.warning(f"⚠️ IRC non prêt, message ignoré: {msg.text[:50]}")
            return
        
        try:
            # Log avant envoi
            LOGGER.info(f"📤 Tentative envoi IRC à #{msg.channel}: {msg.text}")
            
            # Envoyer avec timeout pour éviter blocages
            await asyncio.wait_for(
                self.chat.send_message(msg.channel, msg.text),
                timeout=self.irc_send_timeout
            )
            
            # Log succès
            LOGGER.info(f"✅ Sent to #{msg.channel}: {msg.text[:50]}...")
            
        except asyncio.TimeoutError:
            LOGGER.error(f"⏱️ Timeout envoi IRC à #{msg.channel} après {self.irc_send_timeout}s: {msg.text[:50]}")
        except Exception as e:
            LOGGER.error(f"❌ Erreur envoi IRC à #{msg.channel}: {e}", exc_info=True)
    
    def is_running(self) -> bool:
        """Retourne True si le client tourne"""
        return self._running
    
    def get_channels(self) -> list[str]:
        """Retourne la liste des channels"""
        return self.channels.copy()
    
    def is_in_channel(self, channel: str) -> bool:
        """
        Vérifie si le bot est actuellement dans un channel.
        Utilise is_in_room() de pyTwitchAPI pour une vérification réelle.
        
        Args:
            channel: Nom du channel (avec ou sans #)
            
        Returns:
            True si le bot est dans le channel, False sinon
        """
        normalized = channel.lower().lstrip('#')
        # Utiliser pyTwitchAPI au lieu de notre cache interne
        if self.chat and self.chat.is_connected():
            return self.chat.is_in_room(normalized)
        return False
    
    async def verify_all_channels(self) -> tuple[list[str], list[str]]:
        """
        Vérifie que le bot est dans tous les channels attendus.
        Utilise is_connected() et is_in_room() de pyTwitchAPI pour une vérification réelle.
        Tente de rejoindre les channels manquants.
        
        Returns:
            Tuple (channels_ok, channels_missing)
        """
        expected = {c.lower().lstrip('#') for c in self.channels}
        
        # ⚠️ VÉRIFICATION RÉELLE : utiliser pyTwitchAPI, pas notre cache interne
        if not self.chat:
            LOGGER.error("❌ verify_all_channels: chat non initialisé")
            return ([], sorted(list(expected)))
        
        # Vérifier d'abord si la connexion WebSocket est vivante
        if not self.chat.is_connected():
            LOGGER.error("❌ verify_all_channels: connexion IRC fermée!")
            # Invalider notre cache interne
            self._joined_channels.clear()
            return ([], sorted(list(expected)))
        
        # Vérifier chaque channel avec is_in_room() de pyTwitchAPI
        ok = set()
        missing = set()
        for channel in expected:
            if self.chat.is_in_room(channel):
                ok.add(channel)
            else:
                missing.add(channel)
        
        # Synchroniser notre cache interne avec la réalité
        self._joined_channels = ok.copy()
        
        if missing:
            LOGGER.warning(f"🚨 Channels manquants (vérification pyTwitchAPI): {sorted(list(missing))}")
            
            # Tenter de rejoindre les channels manquants
            if self._running:
                for channel in missing:
                    try:
                        LOGGER.info(f"🔄 Tentative de rejoin #{channel}...")
                        await self.chat.join_room(channel)
                        await asyncio.sleep(0.5)  # Rate limit join
                        # Revérifier après join
                        if self.chat.is_in_room(channel):
                            ok.add(channel)
                            missing.discard(channel)
                            self._joined_channels.add(channel)
                            LOGGER.info(f"✅ Rejoin #{channel} confirmé")
                        else:
                            LOGGER.warning(f"⚠️ Rejoin #{channel} envoyé mais pas confirmé")
                    except Exception as e:
                        LOGGER.error(f"❌ Échec rejoin #{channel}: {e}")
        else:
            LOGGER.info(f"✅ Tous les channels OK (vérification pyTwitchAPI): {sorted(list(ok))}")
        
        return (sorted(list(ok)), sorted(list(missing)))
    
    async def add_channel(self, channel: str) -> bool:
        """
        Ajoute dynamiquement un channel à la liste et rejoint le chat.
        
        Args:
            channel: Nom du channel (avec ou sans #)
            
        Returns:
            True si le join a réussi, False sinon
        """
        normalized = channel.lower().lstrip('#')
        
        # Vérifier si déjà dans la liste
        if normalized in {c.lower() for c in self.channels}:
            LOGGER.warning(f"⚠️ Channel #{normalized} déjà dans la liste")
            return self.is_in_channel(normalized)
        
        if not self.chat or not self._running:
            LOGGER.error(f"❌ IRC non prêt, impossible d'ajouter #{normalized}")
            return False
        
        try:
            LOGGER.info(f"➕ Ajout dynamique du channel #{normalized}...")
            
            # Ajouter à la liste interne
            self.channels.append(normalized)
            
            # Rejoindre le channel
            await self.chat.join_room(normalized)
            
            # Attendre le join event (max 5s)
            deadline = time.time() + 5.0
            while time.time() < deadline:
                if self.is_in_channel(normalized):
                    LOGGER.info(f"✅ Channel #{normalized} ajouté et rejoint")
                    return True
                await asyncio.sleep(0.3)
            
            LOGGER.warning(f"⚠️ Channel #{normalized} ajouté mais join non confirmé")
            return False
            
        except Exception as e:
            LOGGER.error(f"❌ Erreur ajout #{normalized}: {e}")
            # Rollback
            if normalized in self.channels:
                self.channels.remove(normalized)
            return False
    
    async def remove_channel(self, channel: str) -> bool:
        """
        Retire dynamiquement un channel de la liste et quitte le chat.
        
        Args:
            channel: Nom du channel (avec ou sans #)
            
        Returns:
            True si le leave a réussi, False sinon
        """
        normalized = channel.lower().lstrip('#')
        
        # Trouver le channel dans la liste (case-insensitive)
        found = None
        for c in self.channels:
            if c.lower() == normalized:
                found = c
                break
        
        if not found:
            LOGGER.warning(f"⚠️ Channel #{normalized} pas dans la liste")
            return True  # Déjà absent = succès
        
        if not self.chat or not self._running:
            LOGGER.error(f"❌ IRC non prêt, impossible de retirer #{normalized}")
            return False
        
        try:
            LOGGER.info(f"➖ Retrait dynamique du channel #{normalized}...")
            
            # Quitter le channel
            await self.chat.leave_room(normalized)
            
            # Retirer de la liste
            self.channels.remove(found)
            
            # Nettoyer les caches
            self._joined_channels.discard(normalized)
            if normalized in self._channel_permissions:
                del self._channel_permissions[normalized]
            if normalized in self._vip_status_cache:
                del self._vip_status_cache[normalized]
            
            LOGGER.info(f"✅ Channel #{normalized} retiré")
            return True
            
        except Exception as e:
            LOGGER.error(f"❌ Erreur retrait #{normalized}: {e}")
            return False
    
    async def get_permissions(self, channel: str) -> dict:
        """
        Récupère les permissions du bot sur un channel
        
        Args:
            channel: Nom du channel (sans #)
            
        Returns:
            Dict avec:
            - can_send: bool (peut envoyer des messages ?)
            - is_mod: bool (bot est modérateur ?)
            - is_vip: bool (bot est VIP ?)
            - rate_limit: int (messages par 30s)
            - safe_delay: float (délai entre messages en secondes)
        """
        # Si on n'a pas encore les permissions pour ce channel, les détecter
        if channel not in self._channel_permissions:
            await self._update_channel_permissions(channel)
        
        return self._channel_permissions.get(channel, {
            "can_send": False,
            "is_mod": False,
            "is_vip": False,
            "rate_limit": 20,
            "safe_delay": 2.5
        })
    
    def get_all_permissions(self) -> dict[str, dict]:
        """
        Retourne les permissions pour tous les channels
        
        Returns:
            Dict {channel: permissions_dict}
        """
        return self._channel_permissions.copy()
    
    async def broadcast_message(
        self, 
        message: str, 
        source_channel: Optional[str] = None,
        exclude_channel: Optional[str] = None
    ) -> tuple[int, int]:
        """
        Broadcast un message sur tous les channels connectés
        
        Args:
            message: Le message à broadcaster
            source_channel: Channel source (pour afficher [Source: xxx])
            exclude_channel: Channel à exclure (généralement le channel d'origine)
            
        Returns:
            Tuple (success_count, total_count)
            
        Usage:
            success, total = await irc.broadcast_message(
                "🎮 Event charity ce soir !", 
                source_channel="el_serda",
                exclude_channel="el_serda"
            )
        """
        if not self.chat or not self._running:
            LOGGER.warning("⚠️ IRC non prêt, broadcast impossible")
            return (0, 0)
        
        # Normaliser le channel à exclure
        if exclude_channel:
            exclude_channel = exclude_channel.lower().lstrip('#')
        
        # Liste des channels à broadcaster
        target_channels = [
            ch for ch in self.channels 
            if not exclude_channel or ch.lower() != exclude_channel
        ]
        
        if not target_channels:
            LOGGER.warning("⚠️ Aucun channel cible pour broadcast")
            return (0, 0)
        
        LOGGER.info(f"📢 Broadcast vers {len(target_channels)} channels: {message[:50]}...")
        
        # Formater le message avec source si fournie
        if source_channel:
            formatted_message = f"[Source: {source_channel}] {message}"
        else:
            formatted_message = message
        
        success_count = 0
        failed_channels = []
        
        # Broadcaster sur chaque channel
        for channel in target_channels:
            try:
                # Respecter le rate limit du channel
                perms = await self.get_permissions(channel)
                safe_delay = perms.get("safe_delay", 2.5)
                
                # Envoyer le message avec timeout
                await asyncio.wait_for(
                    self.chat.send_message(channel, formatted_message),
                    timeout=self.irc_send_timeout
                )
                
                success_count += 1
                LOGGER.debug(f"✅ Broadcast sent to #{channel}")
                
                # Attendre le safe delay avant le prochain
                if channel != target_channels[-1]:  # Pas de delay après le dernier
                    await asyncio.sleep(safe_delay)
                    
            except asyncio.TimeoutError:
                LOGGER.error(f"⏱️ Timeout broadcast à #{channel}")
                failed_channels.append(channel)
            except Exception as e:
                LOGGER.error(f"❌ Erreur broadcast à #{channel}: {e}")
                failed_channels.append(channel)
        
        # Log final
        if failed_channels:
            LOGGER.warning(f"⚠️ Broadcast échoué sur {len(failed_channels)} channels: {failed_channels}")
        
        LOGGER.info(f"📊 Broadcast terminé: {success_count}/{len(target_channels)} envoyés")
        
        return (success_count, len(target_channels))
    
    async def _keepalive_loop(self):
        """
        Keepalive IRC basé sur l'observation des PING Twitch.
        
        Stratégie:
        1. Twitch envoie PING toutes les ~5 min → on track le dernier reçu
        2. Si pas de PING depuis > 6 min → connexion probablement morte
        3. Health check toutes les 2 min (rapide)
        4. Si problème détecté → tente rejoin immédiat
        5. Si échec persistant → force restart Chat (dernier recours)
        
        Temps de détection max: ~2 minutes (intervalle de check)
        """
        LOGGER.info(f"💓 IRC Keepalive démarré (health check toutes les {self._ping_interval}s)")
        
        while self._running:
            try:
                await asyncio.sleep(self._ping_interval)
                
                if not self.chat or not self._running:
                    continue
                
                # ═══════════════════════════════════════════════════════════
                # Health check complet
                # ═══════════════════════════════════════════════════════════
                is_healthy = await self._check_connection_health()
                
                if is_healthy:
                    # Connexion OK
                    self._consecutive_disconnects = 0
                    LOGGER.debug("💓 Health check OK - connexion saine")
                else:
                    # Problème détecté
                    self._consecutive_disconnects += 1
                    LOGGER.warning(f"⚠️ Health check FAILED ({self._consecutive_disconnects}/{self._max_disconnects_before_restart})")
                    
                    # ═══════════════════════════════════════════════════════════
                    # STRATÉGIE DE RECONNEXION PROGRESSIVE
                    # ═══════════════════════════════════════════════════════════
                    # 1er échec: Appeler _handle_base_reconnect() de pyTwitchAPI
                    #            C'est la VRAIE reconnexion native, pas un hack
                    # 2+ échecs: Force restart (dernier recours)
                    # ═══════════════════════════════════════════════════════════
                    
                    if self._consecutive_disconnects == 1:
                        # Première tentative: utiliser la reconnexion NATIVE de pyTwitchAPI
                        LOGGER.info("🔄 Appel de _handle_base_reconnect() (reconnexion native pyTwitchAPI)...")
                        try:
                            await self.chat._handle_base_reconnect()
                            LOGGER.info("✅ Reconnexion native réussie!")
                            # Vérifier qu'on est bien dans les channels
                            await asyncio.sleep(2)  # Laisser le temps au rejoin
                            ok, missing = await self.verify_all_channels()
                            if not missing:
                                LOGGER.info(f"✅ Channels OK après reconnexion: {ok}")
                                self._consecutive_disconnects = 0
                            else:
                                LOGGER.warning(f"⚠️ Channels manquants après reconnexion: {missing}")
                        except Exception as e:
                            LOGGER.error(f"❌ Échec reconnexion native: {e}")
                    
                    # Force restart si échecs persistants
                    elif self._consecutive_disconnects >= self._max_disconnects_before_restart:
                        LOGGER.error("🚨 Health checks échoués - FORCE RESTART Chat (dernier recours)")
                        await self._force_restart_chat()
                        self._consecutive_disconnects = 0
                        
            except asyncio.CancelledError:
                LOGGER.info("🛑 IRC Keepalive arrêté")
                break
            except Exception as e:
                LOGGER.error(f"❌ Erreur keepalive loop: {e}")
                await asyncio.sleep(30)  # Retry rapide si erreur
    
    async def _check_connection_health(self) -> bool:
        """
        Vérifie la santé de la connexion IRC.
        
        Utilise plusieurs indicateurs:
        1. is_connected() de pyTwitchAPI
        2. Dernier PING reçu de Twitch (doit être < 6 min)
        3. Channels effectivement rejoints
        
        Returns:
            True si connexion saine, False sinon
        """
        if not self.chat:
            return False
        
        # 1. Vérifier is_connected()
        is_connected = True
        if hasattr(self.chat, 'is_connected') and callable(self.chat.is_connected):
            is_connected = self.chat.is_connected()
        
        if not is_connected:
            LOGGER.warning("⚠️ is_connected() = False")
            return False
        
        # 2. Vérifier le dernier PING Twitch (doit être < 6 min = 360s)
        # Twitch envoie PING toutes les ~5 min
        if self._last_twitch_ping_time is not None:
            time_since_ping = time.time() - self._last_twitch_ping_time
            if time_since_ping > 360:  # > 6 min sans PING = problème
                LOGGER.warning(f"⚠️ Pas de PING Twitch depuis {time_since_ping:.0f}s (> 6 min)")
                return False
            else:
                LOGGER.debug(f"✅ Dernier PING Twitch il y a {time_since_ping:.0f}s")
        
        # 2b. Vérifier dernier message reçu (indicateur supplémentaire)
        # Si pas de message depuis 10 min ET pas de PING récent → suspicieux
        if self._last_message_time is not None:
            time_since_msg = time.time() - self._last_message_time
            if time_since_msg > 600 and (self._last_twitch_ping_time is None or time_since_ping > 300):
                LOGGER.warning(f"⚠️ Pas de message depuis {time_since_msg:.0f}s ET PING absent/ancien")
                # Ne pas retourner False ici, juste un warning (canal peut être silencieux)
        
        # 3. Vérifier qu'on est dans les channels attendus (via pyTwitchAPI)
        expected = {c.lower().lstrip('#') for c in self.channels}
        actually_joined = set()
        for channel in expected:
            if self.chat.is_in_room(channel):
                actually_joined.add(channel)
        
        if not expected.issubset(actually_joined):
            missing = expected - actually_joined
            LOGGER.warning(f"⚠️ Channels manquants (pyTwitchAPI check): {missing}")
            # Synchroniser notre cache avec la réalité
            self._joined_channels = actually_joined
            return False
        
        # Log health OK en INFO pour visibilité
        LOGGER.info(f"💓 Health check OK - connected, PING OK, {len(actually_joined)} channels")
        return True
    
    async def _force_restart_chat(self) -> None:
        """
        Force la destruction et recréation de l'instance Chat.
        À utiliser quand pyTwitchAPI a abandonné les reconnexions.
        """
        LOGGER.warning("🔄 Force restart Chat - destruction de l'instance...")
        
        try:
            # Sauvegarder les références
            old_chat = self.chat
            
            # Stopper l'ancien chat
            if old_chat:
                try:
                    old_chat.stop()
                except Exception as e:
                    LOGGER.warning(f"⚠️ Erreur lors du stop de l'ancien Chat: {e}")
            
            # Reset state
            self._joined_channels.clear()
            self._channel_permissions.clear()
            self.chat = None
            
            # Attendre un peu avant de recréer
            await asyncio.sleep(2)
            
            # Recréer le Chat avec les mêmes paramètres
            LOGGER.info("🚀 Création d'une nouvelle instance Chat...")
            self.chat = await Chat(
                self.twitch, 
                initial_channel=self.channels,
                no_message_reset_time=7  # 7 min au lieu de 10 min par défaut
            )
            
            # Réappliquer les monkey-patches (copier depuis start())
            await self._apply_monkey_patches()
            
            # Re-register event handlers
            self.chat.register_event(ChatEvent.READY, self._on_ready)
            self.chat.register_event(ChatEvent.MESSAGE, self._on_message)
            self.chat.register_event(ChatEvent.JOIN, self._on_join)
            self.chat.register_event(ChatEvent.LEFT, self._on_left)
            self.chat.register_event(ChatEvent.ROOM_STATE_CHANGE, self._on_room_state_change)
            self.chat.register_event(ChatEvent.NOTICE, self._on_notice)
            
            # Démarrer le nouveau chat
            self.chat.start()
            
            LOGGER.info("✅ Force restart Chat terminé - en attente des joins...")
            
            # Attendre et vérifier les joins
            await asyncio.sleep(10)
            ok, missing = await self.verify_all_channels()
            
            if not missing:
                LOGGER.info("✅ Force restart réussi - tous les channels rejoints")
            else:
                LOGGER.error(f"⚠️ Force restart: channels encore manquants: {missing}")
                
        except Exception as e:
            LOGGER.error(f"❌ Erreur durant force restart Chat: {e}", exc_info=True)
    
    async def _apply_monkey_patches(self) -> None:
        """Applique les monkey-patches sur l'instance Chat."""
        if not self.chat:
            return
        
        # Patch USERSTATE pour VIP
        original_handle_user_state = self.chat._handle_user_state
        
        async def _patched_handle_user_state(parsed: dict):
            channel = parsed['command']['channel'][1:]
            badges = parsed['tags'].get('badges') or {}
            is_vip = badges.get('vip') is not None
            
            old_vip = self._vip_status_cache.get(channel.lower(), False)
            if is_vip != old_vip:
                self._vip_status_cache[channel.lower()] = is_vip
                LOGGER.info(f"✅ VIP detected via USERSTATE: #{channel} → VIP={is_vip}")
                await self._update_channel_permissions(channel, log_change=True)
            
            await original_handle_user_state(parsed)
        
        self.chat._handle_user_state = _patched_handle_user_state
        
        # Patch PING (Twitch → nous) - Track le timestamp pour health check
        original_handle_ping = self.chat._handle_ping
        
        async def _patched_handle_ping(parsed: dict):
            # Tracker le dernier PING reçu de Twitch
            self._last_twitch_ping_time = time.time()
            LOGGER.info(f"🏓 PING reçu de Twitch → PONG envoyé")
            await original_handle_ping(parsed)
        
        self.chat._handle_ping = _patched_handle_ping
        
        # Patch reconnect verifier
        try:
            original_base_reconnect = getattr(self.chat, '_handle_base_reconnect', None)
            
            if original_base_reconnect is not None:
                async def _patched_base_reconnect(*args, **kwargs):
                    LOGGER.warning('🔁 pyTwitchAPI base reconnect detected - verifying channel joins')
                    await original_base_reconnect(*args, **kwargs)
                    
                    deadline = time.time() + 12.0
                    expected = set([c.lower().lstrip('#') for c in self.channels])
                    while time.time() < deadline:
                        current = set([c.lower() for c in self._joined_channels])
                        if expected.issubset(current):
                            LOGGER.info('✅ Rejoin confirmed after reconnect (joined=%s)', sorted(list(current)))
                            return
                        await asyncio.sleep(0.5)
                    
                    LOGGER.error('🚨 Reconnect completed but channels not rejoined within timeout.')
                
                self.chat._handle_base_reconnect = _patched_base_reconnect
        except Exception as e:
            LOGGER.error(f'❌ Failed to install reconnect verifier: {e}')
