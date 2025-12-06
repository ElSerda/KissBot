#!/usr/bin/env python3
"""
EventSub Chat Client - Transport Chat Twitch via EventSub WebSocket
====================================================================

Remplace IRC pour une stabilité 24/7 maximale.

Architecture:
    - RÉCEPTION: EventSub WebSocket (keepalive ~10s, détection ~20s)
    - ENVOI: Helix API send_chat_message (badge chatbot officiel)

Avantages vs IRC:
    - Keepalive: 10s vs 5min → détection déconnexion 30x plus rapide
    - Reconnexion: automatique par pyTwitchAPI
    - Format: objets structurés (badges, color, etc.) vs parsing PRIVMSG
    - Badge: obtention du badge "chatbot" officiel Twitch

Référence Twitch:
    "The preferred method of viewing and sending chats on Twitch is through 
    EventSub and Twitch API" - https://dev.twitch.tv/docs/chat/

Usage:
    client = EventSubChatClient(twitch, bus, bot_user_id, bot_login, channels, broadcaster_ids)
    await client.start()

Scopes requis:
    - user:read:chat (recevoir messages)
    - user:write:chat (envoyer messages)
    - user:bot (apparaître comme bot dans chatters list)
"""

import asyncio
import logging
import time
from typing import Optional, Dict, List

from twitchAPI.twitch import Twitch
from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.object.eventsub import ChannelChatMessageEvent

from core.message_bus import MessageBus
from core.message_types import ChatMessage, OutboundMessage

LOGGER = logging.getLogger(__name__)


class EventSubChatClient:
    """
    Client Chat Twitch via EventSub WebSocket.
    
    Alternative à IRCClient avec détection de déconnexion 30x plus rapide.
    
    Attributes:
        twitch: Instance Twitch API (avec bot user token)
        bus: MessageBus pour publier/consommer
        bot_user_id: ID du compte bot
        bot_login: Login du compte bot
        channels: Liste des channels à écouter
        broadcaster_ids: Mapping channel_name -> broadcaster_id
    """
    
    def __init__(
        self,
        twitch: Twitch,
        bus: MessageBus,
        bot_user_id: str,
        bot_login: str,
        channels: List[str],
        broadcaster_ids: Dict[str, str],
        send_timeout: float = 5.0
    ):
        """
        Args:
            twitch: Instance Twitch avec user token (scopes: user:read:chat, user:write:chat)
            bus: MessageBus pour publier les messages entrants
            bot_user_id: ID Twitch du bot
            bot_login: Login du bot (pour ignorer ses propres messages)
            channels: Liste des channels à écouter ["el_serda", "morthycya"]
            broadcaster_ids: Mapping {"el_serda": "123456", ...}
            send_timeout: Timeout pour l'envoi de messages (Helix API)
        """
        self.twitch = twitch
        self.bus = bus
        self.bot_user_id = bot_user_id
        self.bot_login = bot_login.lower()
        self.channels = [c.lower().lstrip('#') for c in channels]
        self.broadcaster_ids = {k.lower(): v for k, v in broadcaster_ids.items()}
        self.send_timeout = send_timeout
        
        # EventSub WebSocket
        self.eventsub: Optional[EventSubWebsocket] = None
        
        # État
        self._running = False
        self._subscribed_channels: set[str] = set()
        
        # Keepalive tracking
        self._last_keepalive_time: float = 0.0
        self._keepalive_count: int = 0
        self._health_check_task: Optional[asyncio.Task] = None
        
        # Permissions cache (comme IRC client)
        self._channel_permissions: Dict[str, dict] = {}
        
        # Subscribe aux messages sortants
        self.bus.subscribe("chat.outbound", self._handle_outbound_message)
        
        LOGGER.info(f"EventSubChatClient init pour {bot_login} sur {len(channels)} channels")
    
    async def start(self) -> None:
        """Démarre le client EventSub Chat."""
        if self._running:
            LOGGER.warning("EventSub Chat Client déjà en cours")
            return
        
        LOGGER.info("🚀 Démarrage EventSub Chat Client...")
        
        try:
            # Créer EventSub WebSocket
            self.eventsub = EventSubWebsocket(self.twitch)
            
            # Hook pour tracker les keepalives (détection santé connexion)
            await self._install_keepalive_hook()
            
            # Démarrer le WebSocket
            self.eventsub.start()
            self._running = True
            self._last_keepalive_time = time.time()
            
            LOGGER.info("✅ EventSub WebSocket démarré")
            
            # S'abonner aux messages de chaque channel
            for channel in self.channels:
                await self._subscribe_channel(channel)
            
            # Démarrer le health check
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            
            LOGGER.info(f"✅ EventSub Chat Client démarré - {len(self._subscribed_channels)} channels")
            
        except Exception as e:
            LOGGER.error(f"❌ Erreur démarrage EventSub Chat: {e}", exc_info=True)
            raise
    
    async def stop(self) -> None:
        """Arrête le client proprement."""
        if not self._running:
            return
        
        LOGGER.info("🛑 Arrêt EventSub Chat Client...")
        
        # Arrêter health check
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
        
        # Arrêter EventSub
        if self.eventsub:
            await self.eventsub.stop()
            self.eventsub = None
        
        self._running = False
        self._subscribed_channels.clear()
        
        LOGGER.info("✅ EventSub Chat Client arrêté")
    
    async def _install_keepalive_hook(self) -> None:
        """Installe un hook pour tracker les keepalives EventSub."""
        if not self.eventsub:
            return
        
        # Sauvegarder le handler original
        original_handler = self.eventsub._handle_keepalive
        
        async def patched_keepalive(data: dict):
            """Hook keepalive pour tracking."""
            self._last_keepalive_time = time.time()
            self._keepalive_count += 1
            
            # Log toutes les minutes environ (6 keepalives × 10s)
            if self._keepalive_count % 6 == 0:
                LOGGER.debug(f"💓 EventSub keepalive #{self._keepalive_count}")
            
            # Appeler le handler original
            await original_handler(data)
        
        self.eventsub._handle_keepalive = patched_keepalive
        LOGGER.debug("✅ Keepalive hook installé")
    
    async def _subscribe_channel(self, channel: str) -> bool:
        """
        S'abonne aux messages d'un channel.
        
        Args:
            channel: Nom du channel (sans #)
            
        Returns:
            True si l'abonnement a réussi
        """
        channel = channel.lower().lstrip('#')
        
        if channel in self._subscribed_channels:
            LOGGER.debug(f"Déjà abonné à #{channel}")
            return True
        
        broadcaster_id = self.broadcaster_ids.get(channel)
        if not broadcaster_id:
            LOGGER.error(f"❌ Broadcaster ID non trouvé pour #{channel}")
            return False
        
        try:
            LOGGER.info(f"📡 Abonnement EventSub chat de #{channel}...")
            
            # Créer le callback pour ce channel
            async def on_message(event: ChannelChatMessageEvent):
                await self._on_chat_message(event, channel)
            
            # S'abonner
            await self.eventsub.listen_channel_chat_message(
                broadcaster_user_id=broadcaster_id,
                user_id=self.bot_user_id,
                callback=on_message
            )
            
            self._subscribed_channels.add(channel)
            
            # Détecter les permissions
            await self._update_channel_permissions(channel)
            
            LOGGER.info(f"✅ Abonné aux messages de #{channel}")
            return True
            
        except Exception as e:
            LOGGER.error(f"❌ Échec abonnement #{channel}: {e}")
            return False
    
    async def _on_chat_message(self, event: ChannelChatMessageEvent, channel: str) -> None:
        """
        Callback pour les messages chat reçus via EventSub.
        
        Args:
            event: Événement ChannelChatMessage de pyTwitchAPI
            channel: Nom du channel
        """
        # Reset keepalive timer (chaque message = connexion vivante)
        self._last_keepalive_time = time.time()
        
        evt = event.event
        
        # Ignorer nos propres messages
        if evt.chatter_user_login.lower() == self.bot_login:
            return
        
        # Extraire les badges
        badges = {}
        is_mod = False
        is_broadcaster = False
        is_vip = False
        
        if evt.badges:
            for badge in evt.badges:
                badges[badge.set_id] = badge.id
                if badge.set_id == "moderator":
                    is_mod = True
                elif badge.set_id == "broadcaster":
                    is_broadcaster = True
                elif badge.set_id == "vip":
                    is_vip = True
        
        # Log du message
        badge_str = f"[{','.join(badges.keys())}]" if badges else ""
        LOGGER.info(f"📥 EventSub {badge_str} {evt.chatter_user_name} dans #{channel}: {evt.message.text[:100]}")
        
        # Vérifier si le BOT est mod sur ce channel
        bot_is_mod = self._channel_permissions.get(channel, {}).get("is_mod", False)
        
        # Créer ChatMessage pour MessageBus
        chat_msg = ChatMessage(
            channel=channel,
            channel_id=evt.broadcaster_user_id,
            user_login=evt.chatter_user_login,
            user_id=evt.chatter_user_id,
            text=evt.message.text,
            is_mod=is_mod,
            is_broadcaster=is_broadcaster,
            is_vip=is_vip,
            transport="eventsub",  # Différencier de "irc"
            badges=badges,
            meta={
                "message_id": evt.message_id,
                "color": evt.color if hasattr(evt, 'color') else None,
                "reply": evt.reply if hasattr(evt, 'reply') else None,
                "bot_is_mod": bot_is_mod  # ← Info de bot permissions
            }
        )
        
        # Publier sur MessageBus
        try:
            await self.bus.publish("chat.inbound", chat_msg)
        except Exception as e:
            LOGGER.error(f"❌ Erreur publish chat.inbound: {e}")
    
    async def _handle_outbound_message(self, msg: OutboundMessage) -> None:
        """
        Envoie un message via Helix API send_chat_message.
        
        Avantages vs IRC:
        - Badge chatbot officiel (si scope user:bot + channel:bot)
        - Rate limit API séparé
        - Plus fiable
        
        Args:
            msg: Message à envoyer
        """
        if not self._running:
            LOGGER.warning(f"⚠️ EventSub Chat non prêt, message ignoré: {msg.text[:50]}")
            return
        
        channel = msg.channel.lower().lstrip('#')
        broadcaster_id = self.broadcaster_ids.get(channel)
        
        if not broadcaster_id:
            LOGGER.error(f"❌ Broadcaster ID non trouvé pour #{channel}")
            return
        
        try:
            LOGGER.info(f"📤 Envoi Helix API à #{channel}: {msg.text[:50]}...")
            
            # Envoyer via Helix API avec timeout
            await asyncio.wait_for(
                self.twitch.send_chat_message(
                    broadcaster_id=broadcaster_id,
                    sender_id=self.bot_user_id,
                    message=msg.text,
                    reply_parent_message_id=msg.reply_to
                ),
                timeout=self.send_timeout
            )
            
            LOGGER.info(f"✅ Sent to #{channel}: {msg.text[:50]}...")
            
        except asyncio.TimeoutError:
            LOGGER.error(f"⏱️ Timeout envoi à #{channel} après {self.send_timeout}s")
        except Exception as e:
            LOGGER.error(f"❌ Erreur envoi à #{channel}: {e}", exc_info=True)
    
    async def _health_check_loop(self) -> None:
        """
        Health check basé sur les keepalives EventSub.
        
        Twitch envoie un keepalive toutes les ~10 secondes.
        Si rien reçu pendant 30s, la connexion est considérée morte.
        pyTwitchAPI gère la reconnexion automatiquement.
        """
        LOGGER.info("💓 Health check EventSub démarré (interval: 15s, timeout: 30s)")
        
        while self._running:
            try:
                await asyncio.sleep(15)  # Check toutes les 15 secondes
                
                if not self._running:
                    break
                
                elapsed = time.time() - self._last_keepalive_time
                
                if elapsed < 20:
                    # Connexion OK
                    LOGGER.debug(f"💓 EventSub OK - dernier keepalive il y a {elapsed:.1f}s")
                elif elapsed < 30:
                    # Warning
                    LOGGER.warning(f"⚠️ EventSub: pas de keepalive depuis {elapsed:.1f}s")
                else:
                    # Connexion probablement morte - pyTwitchAPI devrait reconnecter
                    LOGGER.error(f"🚨 EventSub: connexion morte? Pas de signal depuis {elapsed:.1f}s")
                    # pyTwitchAPI gère la reconnexion automatiquement
                    # On reset juste le timer pour éviter les logs répétés
                    self._last_keepalive_time = time.time()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                LOGGER.error(f"❌ Erreur health check: {e}")
    
    async def _update_channel_permissions(self, channel: str) -> None:
        """
        Détecte les permissions du bot sur un channel.
        
        Args:
            channel: Nom du channel
        """
        try:
            # Vérifier si mod via Helix API
            moderated_channels = []
            async for ch in self.twitch.get_moderated_channels(user_id=self.bot_user_id):
                moderated_channels.append(ch.broadcaster_login.lower())
            
            is_mod = channel.lower() in moderated_channels
            
            # Rate limits
            if is_mod:
                rate_limit = 100
            else:
                rate_limit = 20
            
            self._channel_permissions[channel] = {
                "is_mod": is_mod,
                "rate_limit": rate_limit
            }
            
            status = "MOD 🛡️" if is_mod else "User 👤"
            LOGGER.info(f"✅ #{channel}: {status} | Rate: {rate_limit} msg/30s")
            
        except Exception as e:
            LOGGER.warning(f"⚠️ Impossible de vérifier permissions #{channel}: {e}")
    
    # ========== API publique ==========
    
    def is_running(self) -> bool:
        """Retourne True si le client tourne."""
        return self._running
    
    def get_channels(self) -> List[str]:
        """Retourne la liste des channels."""
        return list(self._subscribed_channels)
    
    def is_in_channel(self, channel: str) -> bool:
        """Vérifie si on écoute un channel."""
        return channel.lower().lstrip('#') in self._subscribed_channels
    
    async def add_channel(self, channel: str) -> bool:
        """
        Ajoute dynamiquement un channel.
        
        Args:
            channel: Nom du channel
            
        Returns:
            True si l'ajout a réussi
        """
        channel = channel.lower().lstrip('#')
        
        if channel in self._subscribed_channels:
            LOGGER.debug(f"Déjà dans #{channel}")
            return True
        
        if channel not in self.broadcaster_ids:
            LOGGER.error(f"❌ Broadcaster ID manquant pour #{channel}")
            return False
        
        self.channels.append(channel)
        return await self._subscribe_channel(channel)
    
    async def verify_all_channels(self) -> tuple[List[str], List[str]]:
        """
        Vérifie que tous les channels sont abonnés.
        
        Returns:
            Tuple (channels_ok, channels_missing)
        """
        expected = set(self.channels)
        ok = self._subscribed_channels.copy()
        missing = expected - ok
        
        if missing:
            LOGGER.warning(f"🚨 Channels manquants: {sorted(missing)}")
            for channel in missing:
                if await self._subscribe_channel(channel):
                    ok.add(channel)
                    missing.discard(channel)
        else:
            LOGGER.info(f"✅ Tous les channels OK: {sorted(ok)}")
        
        return (sorted(ok), sorted(missing))
    
    def get_health_status(self) -> dict:
        """
        Retourne le status de santé du client.
        
        Returns:
            Dict avec les infos de santé
        """
        elapsed = time.time() - self._last_keepalive_time if self._last_keepalive_time else float('inf')
        
        return {
            "running": self._running,
            "connected": elapsed < 30,
            "last_keepalive_ago": elapsed,
            "keepalive_count": self._keepalive_count,
            "channels_subscribed": len(self._subscribed_channels),
            "channels_expected": len(self.channels)
        }
