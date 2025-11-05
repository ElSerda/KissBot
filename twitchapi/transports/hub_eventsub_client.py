"""
Hub EventSub Client - Connects bot to EventSub Hub via IPC.

This is a wrapper around IPCClient that provides the same interface as
EventSubClient, allowing bots to transparently use either direct WebSocket
or Hub-based EventSub.

Usage:
    # Instead of:
    # eventsub = EventSubClient(twitch, bus, channels, broadcaster_ids)
    
    # Use:
    eventsub = HubEventSubClient(
        bus=bus,
        channels=channels,
        broadcaster_ids=broadcaster_ids,
        hub_socket_path="/tmp/kissbot_hub.sock"
    )
    await eventsub.start()
"""

import asyncio
import logging
from typing import Dict, List

from core.message_bus import MessageBus
from core.message_types import SystemEvent
from core.ipc_protocol import IPCClient, EventMessage, AckMessage, ErrorMessage

LOGGER = logging.getLogger(__name__)


class HubEventSubClient:
    """
    EventSub client that connects to centralized Hub via IPC.
    
    Provides same interface as EventSubClient but uses Hub instead of
    direct WebSocket connection.
    
    Architecture:
        [Bot] ←IPC→ [Hub] ←WebSocket→ [Twitch EventSub]
    
    Attributes:
        bus: MessageBus for publishing system events
        channels: List of channel names to monitor
        broadcaster_ids: Mapping channel_name -> broadcaster_id
        hub_socket_path: Path to Hub IPC socket
        ipc_client: IPCClient instance
        _running: Client state
        _receive_task: Background task for receiving events
    """
    
    def __init__(
        self,
        bus: MessageBus,
        channels: List[str],
        broadcaster_ids: Dict[str, str],
        hub_socket_path: str = "/tmp/kissbot_hub.sock"
    ):
        self.bus = bus
        self.channels = channels
        self.broadcaster_ids = broadcaster_ids
        self.hub_socket_path = hub_socket_path
        
        self.ipc_client = IPCClient(socket_path=hub_socket_path)
        self._running = False
        self._receive_task = None
        
        LOGGER.info(f"🌐 Hub EventSub Client initialized for {len(channels)} channels")
    
    async def start(self):
        """
        Connect to Hub and subscribe to events.
        
        Raises:
            ConnectionError: If Hub is not reachable
        """
        if self._running:
            LOGGER.warning("⚠️  Hub client already running")
            return
        
        try:
            # Connect to Hub
            LOGGER.info(f"🔗 Connecting to EventSub Hub at {self.hub_socket_path}...")
            await self.ipc_client.connect(timeout=5.0)
            LOGGER.info("✅ Connected to EventSub Hub")
            
            # Send hello for each channel
            # Note: Hub expects 1 hello per bot (single channel in single-channel mode)
            # For multi-channel, we'd need to send multiple hellos or extend protocol
            
            for channel in self.channels:
                broadcaster_id = self.broadcaster_ids.get(channel)
                if not broadcaster_id:
                    LOGGER.warning(f"⚠️  No broadcaster_id for {channel}, skipping")
                    continue
                
                # Send hello with desired topics
                topics = ["stream.online", "stream.offline"]
                LOGGER.info(f"👋 Sending hello to Hub: {channel} (ID: {broadcaster_id})")
                await self.ipc_client.send_hello(
                    channel=channel,
                    channel_id=broadcaster_id,
                    topics=topics
                )
                LOGGER.info(f"✅ Hello sent for {channel}")
            
            # Start receiving events in background
            self._running = True
            self._receive_task = asyncio.create_task(self._receive_loop())
            
            LOGGER.info("✅ Hub EventSub client started")
        
        except ConnectionError as e:
            LOGGER.error(f"❌ Failed to connect to Hub: {e}")
            LOGGER.error("💡 Make sure EventSub Hub is running: python eventsub_hub.py")
            raise
        
        except Exception as e:
            LOGGER.error(f"❌ Failed to start Hub client: {e}")
            raise
    
    async def stop(self):
        """Disconnect from Hub."""
        if not self._running:
            return
        
        LOGGER.info("🛑 Stopping Hub EventSub client...")
        
        self._running = False
        
        # Cancel receive task
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        
        # Disconnect from Hub
        await self.ipc_client.disconnect()
        
        LOGGER.info("✅ Hub EventSub client stopped")
    
    async def _receive_loop(self):
        """
        Background task: Receive events from Hub and publish to MessageBus.
        
        Translates IPC EventMessages to SystemEvents for MessageBus.
        """
        LOGGER.info("📥 Started receiving events from Hub...")
        
        try:
            async for msg in self.ipc_client.receive():
                if isinstance(msg, EventMessage):
                    # Translate to SystemEvent
                    await self._handle_event(msg)
                
                elif isinstance(msg, AckMessage):
                    # Log acknowledgments
                    LOGGER.debug(f"✅ ACK: {msg.cmd} / {msg.topic} → {msg.status}")
                
                elif isinstance(msg, ErrorMessage):
                    # Log errors
                    LOGGER.error(f"❌ Hub error: {msg.cmd} / {msg.code} → {msg.detail}")
                
                else:
                    LOGGER.debug(f"📨 Hub message: {type(msg).__name__}")
        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            LOGGER.error(f"❌ Receive loop error: {e}")
            import traceback
            traceback.print_exc()
        
        LOGGER.info("📥 Stopped receiving events from Hub")
    
    async def _handle_event(self, event: EventMessage):
        """
        Handle EventMessage from Hub.
        
        Translates IPC event to SystemEvent and publishes to MessageBus.
        
        Args:
            event: EventMessage from Hub
        """
        # Find channel name from channel_id
        channel = None
        for ch, cid in self.broadcaster_ids.items():
            if cid == event.channel_id:
                channel = ch
                break
        
        if not channel:
            LOGGER.warning(f"⚠️  Unknown channel_id: {event.channel_id}")
            return
        
        # Create SystemEvent (same format as EventSubClient)
        if event.topic == "stream.online":
            system_event = SystemEvent(
                kind="stream.online",
                payload={
                    "channel": channel,
                    "channel_id": event.channel_id,
                    "type": event.payload.get("type", "live"),
                    "started_at": event.payload.get("started_at"),
                    "source": "eventsub_hub",
                }
            )
        
        elif event.topic == "stream.offline":
            system_event = SystemEvent(
                kind="stream.offline",
                payload={
                    "channel": channel,
                    "channel_id": event.channel_id,
                    "source": "eventsub_hub",
                }
            )
        
        else:
            LOGGER.warning(f"⚠️  Unknown event topic: {event.topic}")
            return
        
        # Publish to MessageBus
        LOGGER.info(f"📢 Event from Hub: {event.topic} → {channel}")
        await self.bus.publish("system.event", system_event)
    
    def is_running(self) -> bool:
        """Check if client is running."""
        return self._running
