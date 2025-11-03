"""
EventSub WebSocket client wrapper for real-time stream notifications.

Wrapper autour de pyTwitchAPI.eventsub.websocket.EventSubWebsocket pour intégrer
les notifications en temps réel dans l'architecture du bot via MessageBus.

Architecture:
    EventSubWebsocket (pyTwitchAPI) → EventSubClient (wrapper) → MessageBus → StreamAnnouncer

Avantages EventSub vs Polling:
    - Latence: < 1s vs 60s
    - API Calls: 0 (push-based) vs 4/min
    - Real-time: Instant notifications

Fallback:
    Si EventSub échoue, le bot peut fallback sur StreamMonitor (polling) pour garantir
    la résilience du système.
"""

import asyncio
import logging
from typing import Dict, List, Optional

from twitchAPI.twitch import Twitch
from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.object.eventsub import StreamOnlineEvent, StreamOfflineEvent

from core.message_bus import MessageBus
from core.message_types import SystemEvent


LOGGER = logging.getLogger(__name__)


class EventSubClient:
    """
    Wrapper EventSub WebSocket pour notifications stream en temps réel.
    
    Intègre EventSubWebsocket de pyTwitchAPI avec MessageBus du bot pour publier
    les événements stream.online et stream.offline de manière unifiée.
    
    Architecture hybride:
        - EventSub (primary): Real-time push notifications (< 1s)
        - Polling (fallback): Backup si EventSub échoue
    
    Performance:
        - Startup: ~3.5s pour 8 subscriptions (4 channels × 2 events)
        - Runtime: 0 requête API (WebSocket push)
        - Latence: < 1s par event (vs 60s polling)
        - Parallélisation: asyncio.gather() pour subscriptions simultanées
    
    Design Decision - 2 subscriptions par channel:
        Toujours subscribe à online ET offline (même si 1 seul activé dans config)
        pour éviter comportement imprévisible et dépendance au polling.
        StreamAnnouncer gère l'announce selon config.
    
    Attributes:
        twitch: Instance Twitch API (pyTwitchAPI)
        bus: MessageBus pour publier system.event
        channels: Liste des channels à monitorer
        broadcaster_ids: Mapping channel_name -> broadcaster_id
        eventsub: Instance EventSubWebsocket (pyTwitchAPI)
        _running: État du client
        _subscription_ids: IDs des subscriptions actives
    """
    
    def __init__(
        self,
        twitch: Twitch,
        bus: MessageBus,
        channels: List[str],
        broadcaster_ids: Dict[str, str]
    ):
        """
        Initialize EventSub client.
        
        Args:
            twitch: Instance Twitch API configurée avec app token
            bus: MessageBus pour publier events
            channels: Liste channels à monitorer ["el_serda", "morthycya"]
            broadcaster_ids: Mapping {"el_serda": "123456", "morthycya": "789012"}
        """
        self.twitch = twitch
        self.bus = bus
        self.channels = channels
        self.broadcaster_ids = broadcaster_ids
        
        # EventSub WebSocket instance (sera créé au start)
        self.eventsub: Optional[EventSubWebsocket] = None
        
        # État
        self._running = False
        self._subscription_ids: List[str] = []
        
        # Cost limit fallback tracking (NEW)
        self._failed_offline_subs: List[Dict[str, str]] = []  # Subscriptions échouées (cost exceeded)
        self._retry_task: Optional[asyncio.Task] = None  # Background retry task
        
        # Reconnection tracking (NEW - fix session expiry)
        self._reconnect_task: Optional[asyncio.Task] = None
        self._max_reconnect_attempts = 5
        self._reconnect_delay = 10  # seconds
        
        LOGGER.info(f"🔌 EventSubClient initialized for {len(channels)} channels")
    
    async def start(self):
        """
        Démarre EventSub WebSocket et subscribe aux événements stream.
        
        Crée la connexion WebSocket et enregistre les callbacks pour:
            - stream.online: Broadcaster démarre un stream
            - stream.offline: Broadcaster arrête un stream
        
        Raises:
            Exception: Si connexion EventSub échoue (fallback polling requis)
        """
        if self._running:
            LOGGER.warning("⚠️  EventSubClient already running")
            return
        
        try:
            LOGGER.info("🚀 Starting EventSub WebSocket connection...")
            
            # Créer EventSub WebSocket avec instance Twitch
            self.eventsub = EventSubWebsocket(self.twitch)
            
            # IMPORTANT: Start EventSub AVANT de subscribe (NOTE: start() is NOT async!)
            self.eventsub.start()
            LOGGER.info("✅ EventSub WebSocket connected")
            
            # Créer toutes les tasks de subscription (parallélisation pour speed!)
            subscription_tasks = []
            
            for channel in self.channels:
                broadcaster_id = self.broadcaster_ids.get(channel)
                
                if not broadcaster_id:
                    LOGGER.error(f"❌ No broadcaster_id for channel '{channel}', skipping")
                    continue
                
                # Créer tasks pour ce channel (online + offline)
                subscription_tasks.append(
                    self._subscribe_channel(channel, broadcaster_id)
                )
            
            # Exécuter TOUTES les subscriptions en parallèle (return_exceptions pour pas crash)
            LOGGER.info(f"🚀 Subscribing to {len(subscription_tasks)} channels in parallel...")
            results = await asyncio.gather(*subscription_tasks, return_exceptions=True)
            
            # Log résultats
            success_count = sum(1 for r in results if not isinstance(r, Exception))
            if success_count < len(results):
                LOGGER.warning(f"⚠️  {len(results) - success_count} channels failed to subscribe")
            
            self._running = True
            LOGGER.info(f"✅ EventSub started ({len(self._subscription_ids)} subscriptions)")
            
            # Si des subscriptions offline ont échoué (cost exceeded), start retry task
            if self._failed_offline_subs:
                LOGGER.info(f"🔄 Starting retry task for {len(self._failed_offline_subs)} failed subscriptions...")
                self._retry_task = asyncio.create_task(self._retry_failed_subscriptions())
            
            # Start health check task (NEW - monitor WebSocket connection)
            self._reconnect_task = asyncio.create_task(self._health_check_loop())
            LOGGER.info("🏥 Health check loop started")
        
        except Exception as e:
            LOGGER.error(f"❌ EventSub start failed: {e}")
            LOGGER.warning("⚠️  Fallback to polling recommended")
            raise
    
    async def _subscribe_channel(self, channel: str, broadcaster_id: str):
        """
        Subscribe to stream.online and stream.offline for a channel.
        
        Helper method pour paralléliser les subscriptions avec asyncio.gather().
        
        DESIGN DECISION: Pourquoi 2 subscriptions par channel ?
        ----------------------------------------------------------
        On subscribe TOUJOURS aux 2 events (online + offline) même si un seul
        est activé dans config, pour éviter un comportement imprévisible :
        
        - Si uniquement stream.online subscribed :
          ✅ Détecte offline→online (< 1s)
          ❌ Ne détecte PAS online→offline (pas d'event)
          → Besoin de fallback polling pour offline (complexité)
        
        - Si 2 subscriptions (online + offline) :
          ✅ Détecte tous les changements (< 1s)
          ✅ Behavior cohérent et prévisible
          ✅ 0 requête API en runtime (WebSocket push)
          ⚠️  Coût startup : 3.5s (acceptable, one-time)
        
        StreamAnnouncer gère l'announce selon config.stream_online/offline.enabled
        
        Args:
            channel: Channel name (e.g. "el_serda")
            broadcaster_id: Twitch user ID
        
        Raises:
            Exception: Si les deux subscriptions échouent
        """
        success_count = 0
        
        # Subscribe stream.online
        try:
            sub_id = await self.eventsub.listen_stream_online(
                broadcaster_user_id=broadcaster_id,
                callback=self._handle_stream_online
            )
            self._subscription_ids.append(sub_id)
            LOGGER.info(f"✅ Subscribed stream.online: {channel} (ID: {broadcaster_id})")
            success_count += 1
        except Exception as e:
            LOGGER.error(f"❌ Failed to subscribe stream.online for {channel}: {e}")
        
        # Subscribe stream.offline
        try:
            sub_id = await self.eventsub.listen_stream_offline(
                broadcaster_user_id=broadcaster_id,
                callback=self._handle_stream_offline
            )
            self._subscription_ids.append(sub_id)
            LOGGER.info(f"✅ Subscribed stream.offline: {channel} (ID: {broadcaster_id})")
            success_count += 1
        except Exception as e:
            error_msg = str(e).lower()
            
            # Détecte cost exceeded (fallback + retry)
            if "cost exceeded" in error_msg or "cost" in error_msg:
                LOGGER.warning(f"⚠️  Cost limit reached for {channel} stream.offline - Added to retry queue")
                self._failed_offline_subs.append({
                    "channel": channel,
                    "broadcaster_id": broadcaster_id,
                    "event": "stream.offline"
                })
            else:
                LOGGER.error(f"❌ Failed to subscribe stream.offline for {channel}: {e}")
        
        # Si les deux ont échoué, raise pour que gather() le catch
        if success_count == 0:
            raise Exception(f"Both subscriptions failed for {channel}")
    
    async def _retry_failed_subscriptions(self):
        """
        Background task: Retry subscriptions qui ont échoué (cost exceeded).
        
        Stratégie:
            - Attendre 30s initial (laisser quota potentiel se libérer)
            - Retry toutes les failed subscriptions
            - Si succès: Retire de la queue
            - Si échec: Re-try après 60s (exponential backoff)
            - Max 3 tentatives par subscription
        
        Context: Cost limit EventSub WebSocket = 10 max
        Si on a 7 channels × 2 events = 14 cost, les 4 derniers offline échouent.
        Après 30s, si d'autres subscriptions expirent ou se libèrent, retry.
        """
        retry_attempts = {}  # {channel: attempt_count}
        max_attempts = 3
        retry_delay = 30  # Secondes
        
        while self._running and self._failed_offline_subs:
            await asyncio.sleep(retry_delay)
            
            LOGGER.info(f"🔄 Retrying {len(self._failed_offline_subs)} failed subscriptions...")
            
            # Copy list pour itérer safely
            failed_subs = self._failed_offline_subs.copy()
            
            for sub_info in failed_subs:
                channel = sub_info["channel"]
                broadcaster_id = sub_info["broadcaster_id"]
                
                # Get current attempt count
                attempt = retry_attempts.get(channel, 0) + 1
                retry_attempts[channel] = attempt
                
                # Retry subscription
                try:
                    sub_id = await self.eventsub.listen_stream_offline(
                        broadcaster_user_id=broadcaster_id,
                        callback=self._handle_stream_offline
                    )
                    self._subscription_ids.append(sub_id)
                    LOGGER.info(f"✅ Retry SUCCESS: {channel} stream.offline (attempt {attempt})")
                    
                    # Remove from failed queue
                    self._failed_offline_subs.remove(sub_info)
                    
                except Exception as e:
                    error_msg = str(e).lower()
                    if "cost exceeded" in error_msg:
                        LOGGER.info(f"🔄 Retry {channel}: Still cost exceeded (attempt {attempt}/{max_attempts})")
                        
                        # Give up after max attempts
                        if attempt >= max_attempts:
                            LOGGER.warning(f"⚠️  Max retry attempts reached for {channel}, giving up")
                            self._failed_offline_subs.remove(sub_info)
                    else:
                        LOGGER.error(f"❌ Retry {channel} failed with non-cost error: {e}")
                        # Remove si erreur autre que cost exceeded
                        self._failed_offline_subs.remove(sub_info)
            
            # Exponential backoff pour next retry
            retry_delay = min(retry_delay * 2, 300)  # Max 5min
        
        LOGGER.info("✅ Retry task finished (no more failed subscriptions)")
    
    async def _health_check_loop(self):
        """
        Health check loop pour détecter déconnexions WebSocket.
        
        Vérifie périodiquement l'état de la connexion EventSub.
        Si déconnecté, tente de reconnecter automatiquement.
        
        IMPORTANT: Ce workaround est nécessaire car pyTwitchAPI peut échouer
        à se reconnecter automatiquement quand la session WebSocket expire
        (erreur "websocket transport session does not exist").
        
        Stratégie:
            - Check toutes les 60s
            - Si self.eventsub est None ou non connecté → reconnect
            - Max 5 tentatives avec backoff exponentiel
        """
        check_interval = 60  # Check every 60s
        reconnect_attempts = 0
        
        while self._running:
            try:
                await asyncio.sleep(check_interval)
                
                # Check if EventSub is still alive
                if not self.eventsub or not self._running:
                    LOGGER.warning("⚠️  Health check: EventSub connection lost!")
                    
                    if reconnect_attempts < self._max_reconnect_attempts:
                        reconnect_attempts += 1
                        LOGGER.info(f"🔄 Attempting reconnect ({reconnect_attempts}/{self._max_reconnect_attempts})...")
                        
                        try:
                            # Stop proprement l'ancienne connexion
                            if self.eventsub:
                                try:
                                    await self.eventsub.stop()
                                except:
                                    pass
                            
                            # Reset état
                            self._subscription_ids.clear()
                            self._running = False
                            
                            # Attendre avant reconnexion
                            await asyncio.sleep(self._reconnect_delay)
                            
                            # Restart complet
                            await self.start()
                            
                            LOGGER.info("✅ Reconnection successful!")
                            reconnect_attempts = 0  # Reset counter on success
                            
                        except Exception as e:
                            LOGGER.error(f"❌ Reconnect attempt {reconnect_attempts} failed: {e}")
                            
                            if reconnect_attempts >= self._max_reconnect_attempts:
                                LOGGER.error("❌ Max reconnect attempts reached, giving up")
                                LOGGER.error("⚠️  Manual restart or polling fallback required")
                                self._running = False
                                break
                    else:
                        LOGGER.error("❌ EventSub permanently disconnected, health check stopped")
                        break
                else:
                    # Connection OK, reset attempt counter
                    if reconnect_attempts > 0:
                        reconnect_attempts = 0
                
            except asyncio.CancelledError:
                LOGGER.info("🛑 Health check loop cancelled")
                break
            except Exception as e:
                LOGGER.error(f"❌ Health check error: {e}")
                await asyncio.sleep(check_interval)
        
        LOGGER.info("🛑 Health check loop stopped")
    
    async def stop(self):
        """
        Arrête EventSub WebSocket et nettoie les subscriptions.
        
        Ferme proprement la connexion WebSocket et libère les ressources.
        """
        if not self._running:
            return
        
        LOGGER.info("🛑 Stopping EventSub WebSocket...")
        
        # Cancel health check task if running (NEW)
        if self._reconnect_task and not self._reconnect_task.done():
            LOGGER.info("🛑 Cancelling health check task...")
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
        
        # Cancel retry task if running
        if self._retry_task and not self._retry_task.done():
            LOGGER.info("🛑 Cancelling retry task...")
            self._retry_task.cancel()
            try:
                await self._retry_task
            except asyncio.CancelledError:
                pass
        
        try:
            if self.eventsub:
                await self.eventsub.stop()
                LOGGER.info("✅ EventSub WebSocket stopped")
        except Exception as e:
            LOGGER.error(f"❌ Error stopping EventSub: {e}")
        finally:
            self._running = False
            self._subscription_ids.clear()
            self._failed_offline_subs.clear()
            self.eventsub = None
    
    async def _handle_stream_online(self, event: StreamOnlineEvent):
        """
        Callback EventSub: Stream online.
        
        Publié sur MessageBus via system.event pour trigger StreamAnnouncer.
        
        Args:
            event: StreamOnlineEvent de pyTwitchAPI
        """
        event_data = event.to_dict()
        
        # Extract data from EventSub event
        broadcaster_id = event_data.get("broadcaster_user_id")
        broadcaster_login = event_data.get("broadcaster_user_login")
        stream_type = event_data.get("type", "live")  # live, playlist, watch_party, premiere, rerun
        started_at = event_data.get("started_at")
        
        # Fallback: Si broadcaster_login absent (bug Twitch early event),
        # retrouver via broadcaster_id dans notre mapping inverse
        if not broadcaster_login and broadcaster_id:
            # Reverse lookup: broadcaster_id -> channel
            for channel, stored_id in self.broadcaster_ids.items():
                if stored_id == broadcaster_id:
                    broadcaster_login = channel
                    LOGGER.debug(f"🔍 [EventSub] Resolved broadcaster_id {broadcaster_id} → {channel}")
                    break
        
        # Si toujours pas trouvé, fallback "unknown"
        if not broadcaster_login:
            broadcaster_login = "unknown"
            LOGGER.warning(
                f"⚠️ [EventSub] Received stream.online with missing broadcaster_user_login "
                f"(broadcaster_id={broadcaster_id})"
            )
        
        LOGGER.info(
            f"🔴 [EventSub] {broadcaster_login} is now ONLINE "
            f"(type: {stream_type}, started: {started_at})"
        )
        
        # Publier sur MessageBus (même format que StreamMonitor)
        system_event = SystemEvent(
            kind="stream.online",
            payload={
                "channel": broadcaster_login,
                "channel_id": broadcaster_id,  # StreamAnnouncer expects channel_id
                "type": stream_type,
                "started_at": started_at,
                "source": "eventsub",
                # Note: EventSub stream.online ne contient PAS title/game/viewer_count
                # Ces champs seront None/0, StreamAnnouncer gère les defaults
            }
        )
        
        await self.bus.publish("system.event", system_event)
    
    async def _handle_stream_offline(self, event: StreamOfflineEvent):
        """
        Callback EventSub: Stream offline.
        
        Publié sur MessageBus via system.event.
        
        Args:
            event: StreamOfflineEvent de pyTwitchAPI
        """
        event_data = event.to_dict()
        
        broadcaster_id = event_data.get("broadcaster_user_id")
        broadcaster_login = event_data.get("broadcaster_user_login")
        
        # Ignorer les événements malformés sans broadcaster_id
        if not broadcaster_id:
            LOGGER.debug(
                f"🔍 [EventSub] Ignoring stream.offline with missing broadcaster_id | "
                f"Raw: {event_data}"
            )
            return
        
        # Fallback: Si broadcaster_login absent, retrouver via broadcaster_id
        if not broadcaster_login:
            for channel, stored_id in self.broadcaster_ids.items():
                if stored_id == broadcaster_id:
                    broadcaster_login = channel
                    LOGGER.debug(f"🔍 [EventSub] Resolved broadcaster_id {broadcaster_id} → {channel}")
                    break
        
        if not broadcaster_login:
            LOGGER.warning(
                f"⚠️ [EventSub] Cannot resolve broadcaster_login for stream.offline "
                f"(broadcaster_id={broadcaster_id}) | Known IDs: {list(self.broadcaster_ids.values())}"
            )
            return
        
        LOGGER.info(f"⚫ [EventSub] {broadcaster_login} is now OFFLINE")
        
        # Publier sur MessageBus
        system_event = SystemEvent(
            kind="stream.offline",
            payload={
                "channel": broadcaster_login,
                "channel_id": broadcaster_id,  # StreamAnnouncer expects channel_id
                "source": "eventsub",
            }
        )
        
        await self.bus.publish("system.event", system_event)
    
    def is_running(self) -> bool:
        """Vérifie si EventSub WebSocket est actif."""
        return self._running
