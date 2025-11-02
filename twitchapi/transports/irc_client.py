#!/usr/bin/env python3
"""
IRC Client - Phase 2.6 (avec timeout handling)
Client IRC Twitch complet:
- Écoute chat IRC → Publie sur chat.inbound
- Écoute chat.outbound → Envoie via IRC
- Gestion timeout pour éviter blocages LLM
"""

import asyncio
import logging
from typing import Optional

from twitchAPI.twitch import Twitch
from twitchAPI.chat import Chat, ChatMessage as TwitchChatMessage, EventData
from twitchAPI.type import ChatEvent, AuthScope

from core.message_bus import MessageBus
from core.message_types import ChatMessage, OutboundMessage

LOGGER = logging.getLogger(__name__)


class IRCClient:
    """
    Client IRC Twitch (Phase 2.4 - Bidirectionnel)
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
        
        # Phase 3.5: Track bot's permissions per channel (RAM cache)
        self._channel_permissions = {}   # channel -> {is_mod, is_vip, rate_limit, safe_delay}
        self._vip_status_cache = {}      # Glue code: Cache VIP status (pyTwitchAPI only caches mod/sub)
        
        # Phase 2.4: Subscribe aux messages sortants
        self.bus.subscribe("chat.outbound", self._handle_outbound_message)
        
        LOGGER.info(f"IRCClient init pour {bot_login} sur {len(channels)} channels (timeout={irc_send_timeout}s)")
    
    async def start(self) -> None:
        """Démarre le client IRC"""
        if self._running:
            LOGGER.warning("IRC Client déjà en cours")
            return
        
        LOGGER.info("🚀 Démarrage IRC Client...")
        
        try:
            # Créer instance Chat avec le user token
            self.chat = await Chat(self.twitch)
            
            # Phase 3.5: Monkey-patch pyTwitchAPI pour cacher VIP depuis USERSTATE
            # pyTwitchAPI cache mod/sub mais ignore vip dans _handle_user_state
            # → On wrappe le handler original pour extraire vip AVANT qu'il ne l'ignore
            original_handle_user_state = self.chat._handle_user_state
            
            async def _patched_handle_user_state(parsed: dict):
                # Extraire VIP depuis USERSTATE badges (envoyé par Twitch au JOIN)
                channel = parsed['command']['channel'][1:]  # Remove '#'
                
                # VIP est dans badges dict, pas dans tags directs !
                badges = parsed['tags'].get('badges', {})
                is_vip = badges.get('vip') is not None  # Si badge 'vip' existe → VIP=True
                
                # Cache VIP status (pyTwitchAPI ne le fait pas !)
                old_vip = self._vip_status_cache.get(channel.lower(), False)
                if is_vip != old_vip:
                    self._vip_status_cache[channel.lower()] = is_vip
                    LOGGER.info(f"✅ VIP detected via USERSTATE: #{channel} → VIP={is_vip}")
                    
                    # Re-calcul rate limit avec nouveau VIP status
                    await self._update_channel_permissions(channel, log_change=True)
                
                # Appeler le handler original de pyTwitchAPI (cache mod/sub)
                await original_handle_user_state(parsed)
            
            # Remplacer le handler USERSTATE
            self.chat._handle_user_state = _patched_handle_user_state
            LOGGER.info("✅ Monkey-patch USERSTATE installé pour détection VIP")
            
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
            
            LOGGER.info("✅ IRC Client démarré")
            
        except Exception as e:
            LOGGER.error(f"❌ Erreur démarrage IRC: {e}", exc_info=True)
            raise
    
    async def stop(self) -> None:
        """Arrête le client IRC proprement"""
        if not self._running:
            return
        
        LOGGER.info("🛑 Arrêt IRC Client...")
        
        if self.chat:
            self.chat.stop()
            self.chat = None
        
        self._running = False
        LOGGER.info("✅ IRC Client arrêté")
    
    async def _on_ready(self, ready_event: EventData) -> None:
        """
        Callback quand IRC est ready
        → Rejoint tous les channels
        """
        LOGGER.debug("📡 IRC Ready, connexion aux channels...")
        
        for channel in self.channels:
            try:
                await self.chat.join_room(channel)
                LOGGER.debug(f"✅ Rejoint #{channel}")
            except Exception as e:
                LOGGER.error(f"❌ Erreur join #{channel}: {e}")
    
    async def _on_join(self, join_event: EventData) -> None:
        """Callback quand on rejoint un channel - Détecte les permissions"""
        channel = join_event.room.name
        
        # Log seulement la première fois qu'on rejoint ce channel
        if channel not in self._joined_channels:
            self._joined_channels.add(channel)
            
            # Phase 3.5: Détecter et cacher les permissions
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
        Phase 3.5: Callback quand l'état du room change
        Détecte les changements de permissions (mod/unmod, vip/unvip)
        """
        channel = room_event.room.name
        
        # Re-check permissions
        await self._update_channel_permissions(channel, log_change=True)
    
    async def _on_notice(self, notice_event: EventData) -> None:
        """
        Phase 3.5: Callback pour les NOTICE IRC
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
        Phase 3.5: Détecte et met à jour les permissions du bot sur un channel
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
        
        # Phase 3.5: VIP detection via glue code (pyTwitchAPI doesn't cache VIP)
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
        Phase 2.6: Envoie un message via IRC avec timeout
        
        Args:
            msg: Message à envoyer
        """
        if not self.chat or not self._running:
            LOGGER.warning(f"⚠️ IRC non prêt, message ignoré: {msg.text[:50]}")
            return
        
        try:
            # Log avant envoi
            LOGGER.info(f"📤 Tentative envoi IRC à #{msg.channel}: {msg.text}")
            
            # Phase 2.6: Envoyer avec timeout pour éviter blocages
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
    
    async def get_permissions(self, channel: str) -> dict:
        """
        Phase 3.5: Récupère les permissions du bot sur un channel
        
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
        Phase 3.5: Retourne les permissions pour tous les channels
        
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
        Phase 3.5: Broadcast un message sur tous les channels connectés
        
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
