#!/usr/bin/env python3
"""
📢 Stream Announcer - Auto-announce stream online/offline in chat

Subscribes to system.event (stream.online/offline) from MessageBus.
Publishes auto-announce messages to chat via MessageBus.

Configurable messages and enable/disable per event type.
"""
import logging
from typing import Dict, Optional

from core.message_bus import MessageBus
from core.message_types import SystemEvent, OutboundMessage

LOGGER = logging.getLogger(__name__)


class StreamAnnouncer:
    """
    Announces stream status changes in chat.
    
    Subscribes to system.event messages and publishes chat.outbound messages
    when streams go online/offline.
    """
    
    def __init__(self, bus: MessageBus, config: Optional[Dict] = None):
        """
        Args:
            bus: MessageBus for pub/sub
            config: Configuration dict with announcements settings
        """
        self.bus = bus
        self.config = config or {}
        
        # Get announcements config
        announcements_config = self.config.get("announcements", {})
        
        # Online announce settings
        self.announce_online = announcements_config.get("stream_online", {}).get("enabled", True)
        self.online_message = announcements_config.get("stream_online", {}).get(
            "message",
            "🔴 @{channel} est maintenant en live ! 🎮 {title}"
        )
        
        # Offline announce settings (usually disabled by default)
        self.announce_offline = announcements_config.get("stream_offline", {}).get("enabled", False)
        self.offline_message = announcements_config.get("stream_offline", {}).get(
            "message",
            "💤 @{channel} est maintenant hors ligne. À bientôt !"
        )
        
        # Subscribe to system events
        self.bus.subscribe("system.event", self._handle_system_event)
        
        LOGGER.info(
            f"📢 StreamAnnouncer initialized - "
            f"online={self.announce_online}, offline={self.announce_offline}"
        )
    
    async def _handle_system_event(self, event: SystemEvent):
        """
        Handle system events from MessageBus
        
        Args:
            event: SystemEvent with kind and payload
        """
        if event.kind == "stream.online":
            await self._handle_stream_online(event)
        elif event.kind == "stream.offline":
            await self._handle_stream_offline(event)
    
    async def _handle_stream_online(self, event: SystemEvent):
        """
        Handle stream.online event
        
        Args:
            event: SystemEvent with stream.online payload
        """
        if not self.announce_online:
            LOGGER.debug("🔇 Stream online announce disabled, skipping")
            return
        
        # Extract payload
        channel = event.payload.get("channel")
        channel_id = event.payload.get("channel_id")
        title = event.payload.get("title", "")
        game_name = event.payload.get("game_name", "")
        viewer_count = event.payload.get("viewer_count", 0)
        source = event.payload.get("source", "unknown")
        
        if not channel or not channel_id:
            LOGGER.warning(f"⚠️ Missing channel/channel_id in stream.online event: {event.payload}")
            return
        
        # Format message
        try:
            message_text = self.online_message.format(
                channel=channel,
                title=title or "Sans titre",
                game_name=game_name or "Catégorie inconnue",
                viewer_count=viewer_count
            )
        except KeyError as e:
            LOGGER.error(f"❌ Error formatting online message: {e}")
            message_text = f"🔴 @{channel} est maintenant en live !"
        
        # Truncate if too long (Twitch limit 500 chars)
        if len(message_text) > 500:
            message_text = message_text[:497] + "..."
        
        # Publish to chat
        await self.bus.publish("chat.outbound", OutboundMessage(
            channel=channel,
            channel_id=channel_id,
            text=message_text,
            prefer="irc"  # Use IRC by default for announcements
        ))
        
        LOGGER.info(f"📢 Stream online announced: {channel} (source={source})")
    
    async def _handle_stream_offline(self, event: SystemEvent):
        """
        Handle stream.offline event
        
        Args:
            event: SystemEvent with stream.offline payload
        """
        if not self.announce_offline:
            LOGGER.debug("🔇 Stream offline announce disabled, skipping")
            return
        
        # Extract payload
        channel = event.payload.get("channel")
        channel_id = event.payload.get("channel_id")
        source = event.payload.get("source", "unknown")
        
        if not channel or not channel_id:
            LOGGER.warning(f"⚠️ Missing channel/channel_id in stream.offline event: {event.payload}")
            return
        
        # Format message
        try:
            message_text = self.offline_message.format(channel=channel)
        except KeyError as e:
            LOGGER.error(f"❌ Error formatting offline message: {e}")
            message_text = f"💤 @{channel} est maintenant hors ligne."
        
        # Publish to chat
        await self.bus.publish("chat.outbound", OutboundMessage(
            channel=channel,
            channel_id=channel_id,
            text=message_text,
            prefer="irc"
        ))
        
        LOGGER.info(f"📢 Stream offline announced: {channel} (source={source})")
