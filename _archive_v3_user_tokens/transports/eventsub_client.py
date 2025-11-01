"""
⚡ EventSub Transport - Client EventSub WebSocket

Responsabilités:
- Écoute channel.chat.message → Publie system.event (analytics)
- Active le badge "Powered by Bot" automatiquement
- Optionnel: follows, subs, raids, etc.
"""
import asyncio
import logging
from typing import Optional

from twitchAPI.twitch import Twitch
from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.object.eventsub import ChannelChatMessageEvent
from twitchAPI.helper import first

from core.message_bus import MessageBus
from core.message_types import SystemEvent
from core.registry import Registry

LOGGER = logging.getLogger(__name__)


class EventSubClient:
    """Client EventSub WebSocket pour badge + analytics"""
    
    def __init__(
        self,
        twitch: Twitch,
        bus: MessageBus,
        registry: Registry,
        channels: list[str],
        bot_login: str,
        broadcaster_id: Optional[str] = None
    ):
        """
        Args:
            twitch: Instance Twitch API (broadcaster pour EventSub!)
            bus: MessageBus pour pub/sub
            registry: Registry pour état
            channels: Liste des channels à monitorer
            bot_login: Login du bot
            broadcaster_id: ID du broadcaster (pour EventSub user_id)
        """
        self.twitch = twitch
        self.bus = bus
        self.registry = registry
        self.channels = channels
        self.bot_login = bot_login
        self.broadcaster_id_param = broadcaster_id
        
        self.eventsub: Optional[EventSubWebsocket] = None
        self._bot_id: Optional[str] = None
        self._running = False
        
    async def start(self):
        """Démarre le client EventSub"""
        LOGGER.info("⚡ Démarrage EventSub Client...")
        
        # Récupérer le bot user_id
        try:
            bot_user = await first(self.twitch.get_users(logins=[self.bot_login]))
            if bot_user:
                self._bot_id = bot_user.id
                LOGGER.info(f"✅ Bot ID récupéré: {self._bot_id}")
            else:
                LOGGER.error("❌ Bot user non trouvé!")
                return
        except Exception as e:
            LOGGER.error(f"❌ Erreur récupération bot ID: {e}")
            return
            
        # Créer EventSub WebSocket
        self.eventsub = EventSubWebsocket(self.twitch)
        self.eventsub.start()
        
        # Attendre la connexion
        await asyncio.sleep(2)
        
        # S'abonner aux événements pour chaque channel
        for channel_name in self.channels:
            await self._subscribe_channel(channel_name)
            
        self._running = True
        LOGGER.info("✅ EventSub Client démarré")
        
    async def stop(self):
        """Arrête le client EventSub"""
        LOGGER.info("🛑 Arrêt EventSub Client...")
        self._running = False
        
        if self.eventsub:
            await self.eventsub.stop()
            
        LOGGER.info("✅ EventSub Client arrêté")
        
    async def run(self):
        """Boucle principale (keep alive)"""
        await self.start()
        
        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            LOGGER.info("⚠️ EventSub Client cancelled")
        finally:
            await self.stop()
            
    # ========================================================================
    # SUBSCRIPTIONS
    # ========================================================================
    
    async def _subscribe_channel(self, channel_name: str):
        """
        S'abonne aux événements EventSub d'un channel.
        L'abonnement à channel.chat.message active automatiquement le badge.
        """
        if not self.eventsub or not self._bot_id:
            return
            
        try:
            # Récupérer broadcaster_id
            broadcaster = await first(self.twitch.get_users(logins=[channel_name]))
            if not broadcaster:
                LOGGER.error(f"❌ Broadcaster {channel_name} non trouvé")
                return
                
            broadcaster_id = broadcaster.id
            
            # Cache l'ID
            self.registry.cache_broadcaster_id(channel_name, broadcaster_id)
            self.registry.add_channel(channel_name, broadcaster_id)
            
            # Créer un callback async pour EventSub
            async def on_message_wrapper(event):
                await self._on_chat_message(event, channel_name)
            
            # S'abonner à channel.chat.message (ACTIVE LE BADGE!)
            # user_id doit être l'ID du token utilisé (broadcaster!)
            eventsub_user_id = self.broadcaster_id_param if self.broadcaster_id_param else self._bot_id
            
            await self.eventsub.listen_channel_chat_message(
                broadcaster_user_id=broadcaster_id,
                user_id=eventsub_user_id,  # Utiliser broadcaster ID si disponible
                callback=on_message_wrapper
            )
            
            LOGGER.info(f"🏆 EventSub badge activé sur {channel_name} (user_id={eventsub_user_id})")
            
            # Marquer que le badge est dispo (si scopes OK)
            if self.registry.can_use_helix_send():
                self.registry.set_channel_badge(broadcaster_id, True)
                
        except Exception as e:
            LOGGER.error(f"❌ Erreur subscription EventSub pour {channel_name}: {e}")
            
    # ========================================================================
    # ÉVÉNEMENTS
    # ========================================================================
    
    async def _on_chat_message(self, event: ChannelChatMessageEvent, channel_name: str):
        """
        Callback EventSub pour les messages chat.
        Utilisé pour analytics, pas pour processing (IRC fait ça).
        """
        try:
            # Publier événement système (analytics)
            await self.bus.publish("system.event", SystemEvent(
                kind="eventsub.chat.message",
                payload={
                    "channel": channel_name,
                    "user_login": event.event.chatter_user_login,
                    "user_id": event.event.chatter_user_id,
                    "text": event.event.message.text,
                    "message_id": event.event.message_id,
                    "badges": [b.set_id for b in event.event.badges] if event.event.badges else [],
                    "color": event.event.color
                }
            ))
            
            LOGGER.debug(f"📡 EventSub [{channel_name}] {event.event.chatter_user_login}: {event.event.message.text[:30]}...")
            
        except Exception as e:
            LOGGER.error(f"❌ Erreur traitement EventSub message: {e}")
            
    # ========================================================================
    # SUBSCRIPTIONS OPTIONNELLES (FOLLOWS, SUBS, RAIDS)
    # ========================================================================
    
    async def subscribe_follows(self, channel_name: str):
        """S'abonne aux follows d'un channel"""
        # TODO: Implémenter si besoin
        pass
        
    async def subscribe_subs(self, channel_name: str):
        """S'abonne aux subs d'un channel"""
        # TODO: Implémenter si besoin
        pass
        
    async def subscribe_raids(self, channel_name: str):
        """S'abonne aux raids d'un channel"""
        # TODO: Implémenter si besoin
        pass
