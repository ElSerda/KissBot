#!/usr/bin/env python3
"""
📡 Stream Monitor - Polling-based stream status detection

Polls Twitch Helix API every N seconds to detect stream online/offline transitions.
Publishes system.event messages on MessageBus when state changes.

Use Case: Fallback mechanism when EventSub is not available.
"""
import asyncio
import logging
from typing import Dict, Optional, List
from datetime import datetime

from core.message_bus import MessageBus
from core.message_types import SystemEvent

# Type checking import
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from twitchapi.transports.helix_readonly import HelixReadOnlyClient

LOGGER = logging.getLogger(__name__)


class StreamMonitor:
    """
    Monitors stream status changes via Helix API polling.
    
    Detects online/offline transitions and publishes system.event messages.
    Graceful fallback when EventSub is unavailable.
    """
    
    def __init__(
        self,
        helix: 'HelixReadOnlyClient',
        bus: MessageBus,
        channels: List[str],
        interval: int = 60
    ):
        """
        Args:
            helix: Helix API client for stream queries
            bus: MessageBus for publishing events
            channels: List of channel names to monitor (e.g., ["el_serda", "pelerin_"])
            interval: Polling interval in seconds (default: 60s)
        """
        self.helix = helix
        self.bus = bus
        self.channels = channels
        self.interval = interval
        
        # State tracking: channel_name -> {"status": "online|offline", "last_check": datetime, "stream": dict}
        self._state: Dict[str, Dict] = {}
        
        # Control
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        LOGGER.info(f"📡 StreamMonitor initialized - Monitoring {len(channels)} channels, interval={interval}s")
    
    async def start(self):
        """Start the monitoring loop"""
        if self._running:
            LOGGER.warning("⚠️ StreamMonitor already running")
            return
        
        self._running = True
        
        # Initialize state for all channels
        for channel in self.channels:
            self._state[channel] = {
                "status": "unknown",  # Will be set on first check
                "last_check": None,
                "stream": None
            }
        
        # Start monitoring task
        self._task = asyncio.create_task(self._monitoring_loop())
        LOGGER.info("✅ StreamMonitor started")
    
    async def stop(self):
        """Stop the monitoring loop"""
        if not self._running:
            return
        
        LOGGER.info("🛑 Stopping StreamMonitor...")
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        LOGGER.info("✅ StreamMonitor stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop - polls Helix API at regular intervals"""
        LOGGER.info(f"🔄 StreamMonitor loop started (interval={self.interval}s)")
        
        try:
            while self._running:
                await self._check_all_channels()
                await asyncio.sleep(self.interval)
        except asyncio.CancelledError:
            LOGGER.debug("🛑 StreamMonitor loop cancelled")
        except Exception as e:
            LOGGER.error(f"❌ StreamMonitor loop error: {e}", exc_info=True)
    
    async def _check_all_channels(self):
        """Check status of all monitored channels"""
        for channel in self.channels:
            try:
                await self._check_channel(channel)
            except Exception as e:
                LOGGER.error(f"❌ Error checking channel {channel}: {e}")
    
    async def _check_channel(self, channel: str):
        """
        Check a single channel's stream status and detect transitions
        
        Args:
            channel: Channel name (login)
        """
        try:
            # Query Helix API (get_stream returns dict if online, None if offline)
            stream_data = await self.helix.get_stream(channel)
            
            # Determine current status
            current_status = "online" if stream_data else "offline"
            previous_status = self._state[channel]["status"]
            
            # Update state
            self._state[channel]["status"] = current_status
            self._state[channel]["last_check"] = datetime.now()
            self._state[channel]["stream"] = stream_data
            
            # Detect transition
            if previous_status == "unknown":
                # First check, just log
                LOGGER.info(f"📊 {channel}: Initial status = {current_status}")
            elif previous_status != current_status:
                # TRANSITION DETECTED!
                await self._handle_transition(channel, previous_status, current_status, stream_data)
            else:
                # No transition, just refresh log
                if current_status == "online":
                    # Clean log for online refresh
                    viewers = stream_data.get("viewer_count", 0) if stream_data else 0
                    LOGGER.info(f"🔄 [Refresh] {channel} - Still Live ✅ ({viewers} viewers)")
                else:
                    # Silent for offline refresh (avoid spam)
                    LOGGER.debug(f"🔄 [Refresh] {channel} - Still Offline ⚪")
            
        except Exception as e:
            LOGGER.error(f"❌ Error querying stream for {channel}: {e}")
    
    async def _handle_transition(
        self,
        channel: str,
        old_status: str,
        new_status: str,
        stream_data: Optional[Dict]
    ):
        """
        Handle stream status transition and publish event
        
        Args:
            channel: Channel name
            old_status: Previous status (online/offline)
            new_status: New status (online/offline)
            stream_data: Stream data from Helix (if online)
        """
        transition = f"{old_status} → {new_status}"
        
        if new_status == "online":
            # Stream went LIVE
            LOGGER.info(f"🔴 {channel}: STREAM ONLINE (was {old_status})")
            
            # Publish system.event
            await self.bus.publish("system.event", SystemEvent(
                kind="stream.online",
                payload={
                    "channel": channel,
                    "channel_id": stream_data.get("user_id") if stream_data else None,
                    "title": stream_data.get("title") if stream_data else None,
                    "game_name": stream_data.get("game_name") if stream_data else None,
                    "viewer_count": stream_data.get("viewer_count", 0) if stream_data else 0,
                    "started_at": stream_data.get("started_at") if stream_data else None,
                    "transition": transition,
                    "source": "stream_monitor"  # Indicate polling source
                }
            ))
            
        elif new_status == "offline":
            # Stream went OFFLINE
            LOGGER.info(f"💤 {channel}: STREAM OFFLINE (was {old_status})")
            
            # Publish system.event
            await self.bus.publish("system.event", SystemEvent(
                kind="stream.offline",
                payload={
                    "channel": channel,
                    "channel_id": self._state[channel].get("stream", {}).get("user_id") if self._state[channel].get("stream") else None,
                    "transition": transition,
                    "source": "stream_monitor"
                }
            ))
    
    def get_status(self, channel: str) -> Optional[str]:
        """
        Get current status of a channel
        
        Args:
            channel: Channel name
            
        Returns:
            "online", "offline", "unknown", or None if channel not monitored
        """
        if channel not in self._state:
            return None
        return self._state[channel]["status"]
    
    def get_state(self, channel: str) -> Optional[Dict]:
        """
        Get full state for a channel
        
        Args:
            channel: Channel name
            
        Returns:
            State dict with status, last_check, stream data
        """
        return self._state.get(channel)
    
    def get_all_states(self) -> Dict[str, Dict]:
        """Get state for all monitored channels"""
        return self._state.copy()
