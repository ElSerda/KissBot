#!/usr/bin/env python3
"""
EventSub Hub - Centralized WebSocket manager for KissBot.

Replaces N EventSub WebSocket connections (1 per bot) with a single persistent
WebSocket that multiplexes all subscriptions and routes events to bots via IPC.

Architecture:
    [Twitch EventSub WS] ←→ [Hub] ←→ [Bot #1, Bot #2, ..., Bot #N]
                          1 WS        Unix sockets (IPC)

Features:
    - Single WebSocket connection per application (Twitch limit: 3 transports)
    - Multiplexes hundreds of subscriptions on 1 WebSocket
    - IPC server for bot connections (Unix sockets)
    - Reconciliation loop (desired vs active subscriptions)
    - Rate limiting (1-2 req/s) with jitter (150-300ms)
    - Backoff strategy for errors (exponential 2/4/8/16/60s)
    - Health monitoring and auto-reconnect
    - Database-driven (desired_subscriptions, active_subscriptions, hub_state)

Usage:
    # Start Hub
    python eventsub_hub.py --config config/config.yaml --db kissbot.db
    
    # Bots connect via IPC
    # main.py --channel el_serda --eventsub=hub

Design Principles:
    - Never reconnect WebSocket for subscription changes (HTTP API only)
    - Reconcile calmly (diff desired vs active, rate-limit creates/deletes)
    - First subscription created < 10s after WebSocket connect (avoid 4003)
    - Deduplication: UNIQUE(channel_id, topic) in both tables
    - Error handling: Backoff, no retry loops on 401 (needs_reauth)
"""

import argparse
import asyncio
import logging
import random
import signal
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

import yaml
from twitchAPI.twitch import Twitch
from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.object.eventsub import StreamOnlineEvent, StreamOfflineEvent

# Import IPC protocol
from core.ipc_protocol import (
    IPCServer,
    HelloMessage,
    SubscribeMessage,
    UnsubscribeMessage,
    PingMessage,
    AckMessage,
    ErrorMessage,
    EventMessage,
    PongMessage,
)

# Import database
from database.manager import DatabaseManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
    handlers=[
        logging.FileHandler("logs/eventsub_hub.log"),
        logging.StreamHandler()
    ]
)
LOGGER = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class HubConfig:
    """EventSub Hub configuration."""
    socket_path: str = "/tmp/kissbot_hub.sock"
    reconcile_interval: int = 60  # seconds
    req_rate_per_s: float = 2.0  # requests per second for creates/deletes
    req_jitter_ms: int = 200  # jitter between requests (ms)
    ws_backoff_base: int = 2  # backoff base (seconds)
    ws_backoff_max: int = 60  # max backoff (seconds)
    health_timeout: int = 15  # health check timeout (seconds)
    
    @classmethod
    def from_yaml(cls, yaml_config: dict, socket_path: str = None) -> "HubConfig":
        """Load configuration from YAML config dict."""
        eventsub_cfg = yaml_config.get("eventsub", {})
        hub_cfg = eventsub_cfg.get("hub", {})
        
        return cls(
            socket_path=socket_path or hub_cfg.get("socket_path", "/tmp/kissbot_hub.sock"),
            reconcile_interval=eventsub_cfg.get("reconcile_interval", 60),
            req_rate_per_s=eventsub_cfg.get("req_rate_per_s", 2.0),
            req_jitter_ms=eventsub_cfg.get("req_jitter_ms", 200),
            ws_backoff_base=eventsub_cfg.get("ws_backoff_base", 2),
            ws_backoff_max=eventsub_cfg.get("ws_backoff_max", 60),
            health_timeout=15  # Not configurable yet
        )


# ============================================================================
# EventSub Hub
# ============================================================================

class EventSubHub:
    """
    Centralized EventSub WebSocket manager.
    
    Responsibilities:
        - Maintain 1 WebSocket connection to Twitch EventSub
        - Listen for bot connections via IPC (Unix socket)
        - Reconcile desired vs active subscriptions
        - Route events to appropriate bots
        - Rate limiting and backoff for API calls
        - Health monitoring and auto-reconnect
    """
    
    def __init__(
        self,
        config: HubConfig,
        db: DatabaseManager,
        twitch: Twitch,
        default_broadcaster_id: Optional[str] = None,
    ):
        self.config = config
        self.db = db
        self.twitch = twitch
        
        # IPC Server for bot connections
        self.ipc_server = IPCServer(socket_path=config.socket_path)
        
        # EventSub WebSocket
        self.eventsub: Optional[EventSubWebsocket] = None
        self._ws_connected = False
        self._ws_session_id: Optional[str] = None
        
        # State
        self._running = False
        self._reconcile_task: Optional[asyncio.Task] = None
        self._health_task: Optional[asyncio.Task] = None
        self._ws_monitor_task: Optional[asyncio.Task] = None  # NEW: Monitor for 4003/reconnect
        
        # Track created subscriptions for re-creation after reconnect
        self._created_subscriptions: List[Dict] = []  # [{channel_id, topic, version}, ...]
        
        # Metrics
        self._total_events_routed = 0
        self._ws_reconnect_count = 0
        self._error_burst_level = 0
        
        # Channel mapping (channel_id -> channel_login) for routing
        self._channel_mapping: Dict[str, str] = {}  # "44456636" -> "el_serda"
        # Optional: broadcaster id to use for creating a first subscription
        self._default_broadcaster_id: Optional[str] = default_broadcaster_id
        
        LOGGER.info("🌐 EventSub Hub initialized")
    
    # ========================================================================
    # Lifecycle
    # ========================================================================
    
    async def start(self):
        """Start EventSub Hub."""
        if self._running:
            LOGGER.warning("⚠️  Hub already running")
            return
        
        LOGGER.info("🚀 Starting EventSub Hub...")
        
        # Update hub_state
        self._update_hub_state("ws_state", "connecting")
        
        # Start IPC server
        await self.ipc_server.start(handler=self._handle_bot_message)
        
        # Start EventSub WebSocket
        await self._connect_websocket()
        
        # Start reconciliation loop
        self._reconcile_task = asyncio.create_task(self._reconciliation_loop())
        
        # Start health check
        self._health_task = asyncio.create_task(self._health_check_loop())
        
        self._running = True
        LOGGER.info("✅ EventSub Hub started")
        
        # Log to audit
        self._audit_log("eventsub_hub_start", {
            "socket_path": self.config.socket_path,
            "pid": None,  # Will be set by main()
        }, severity="info")
    
    async def stop(self):
        """Stop EventSub Hub."""
        if not self._running:
            return
        
        LOGGER.info("🛑 Stopping EventSub Hub...")
        
        self._running = False
        
        # Cancel tasks
        if self._reconcile_task:
            self._reconcile_task.cancel()
            try:
                await self._reconcile_task
            except asyncio.CancelledError:
                pass
        
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
        
        # Cancel WebSocket monitor task
        if self._ws_monitor_task:
            self._ws_monitor_task.cancel()
            try:
                await self._ws_monitor_task
            except asyncio.CancelledError:
                pass
        
        # Stop WebSocket
        if self.eventsub:
            try:
                await self.eventsub.stop()
            except Exception as e:
                LOGGER.error(f"❌ Error stopping EventSub: {e}")
        
        # Stop IPC server
        await self.ipc_server.stop()
        
        # Update hub_state
        self._update_hub_state("ws_state", "down")
        
        LOGGER.info("✅ EventSub Hub stopped")
        
        # Log to audit
        self._audit_log("eventsub_hub_stop", {
            "reason": "manual",
        }, severity="info")
    
    # ========================================================================
    # WebSocket Management
    # ========================================================================
    
    async def _connect_websocket(self, attempt: int = 1, skip_monitor: bool = False):
        """
        Connect to Twitch EventSub WebSocket.
        
        Args:
            attempt: Reconnection attempt number
            skip_monitor: Skip starting monitor task (used when called from monitor itself)
        """
        try:
            LOGGER.info(f"🔌 Connecting to EventSub WebSocket (attempt {attempt})...")
            
            # Create EventSub WebSocket
            self.eventsub = EventSubWebsocket(self.twitch)
            
            # Register reconnect/disconnect callbacks for monitoring
            # pyTwitchAPI may use on_reconnect or similar
            if hasattr(self.eventsub, 'on_reconnect'):
                self.eventsub.on_reconnect = self._on_ws_reconnect
            if hasattr(self.eventsub, 'on_disconnect'):
                self.eventsub.on_disconnect = self._on_ws_disconnect
            
            # Register event handlers
            # Note: We'll subscribe to events dynamically, not here
            
            # Start WebSocket (synchronous!)
            self.eventsub.start()
            
            # Wait a moment for WELCOME message with real session_id
            await asyncio.sleep(0.5)
            
            # Get real session_id from EventSub WebSocket (if available)
            # pyTwitchAPI stores it after WELCOME message
            real_session_id = getattr(self.eventsub, 'session_id', None) or \
                             getattr(self.eventsub, '_session_id', None) or \
                             f"session_{int(time.time())}"
            
            self._ws_connected = True
            self._ws_session_id = real_session_id
            
            # Update Hub state with session binding
            self._update_hub_state("ws_state", "connected")
            self._update_hub_state("current_session_id", real_session_id)
            self._update_hub_state("last_ws_connect_ts", str(int(time.time())))
            
            # Increment reconnect counter
            reconnect_count = int(self._get_hub_state("ws_reconnect_count", "0"))
            self._update_hub_state("ws_reconnect_count", str(reconnect_count + 1))
            
            LOGGER.info(f"✅ EventSub WebSocket connected (session: {self._ws_session_id})")
            
            # Log to audit
            self._audit_log("eventsub_ws_connect", {
                "session_id": self._ws_session_id,
                "attempt": attempt,
            }, severity="info")
            
            # CRITICAL: Create first subscription within 10s to avoid 4003
            await self._create_first_subscription()
            
            # Start WebSocket monitor task (detects issues and forces clean reconnect)
            # Skip if called from monitor itself to avoid recursion
            if not skip_monitor:
                if self._ws_monitor_task and not self._ws_monitor_task.done():
                    self._ws_monitor_task.cancel()
                    try:
                        await self._ws_monitor_task
                    except asyncio.CancelledError:
                        pass
                self._ws_monitor_task = asyncio.create_task(self._ws_monitor_loop())
        
        except Exception as e:
            LOGGER.error(f"❌ Failed to connect WebSocket: {e}")
            self._ws_connected = False
            self._update_hub_state("ws_state", "down")
            
            # Log to audit
            self._audit_log("eventsub_ws_connect", {
                "attempt": attempt,
                "error": str(e),
            }, severity="error")
            
            # Backoff and retry (exponential with max cap)
            # Backoff sequence: 2, 4, 8, 16, 32, 60, 60, 60...
            if attempt < 10:  # Allow 10 attempts before giving up
                backoff = min(self.config.ws_backoff_base ** attempt, self.config.ws_backoff_max)
                LOGGER.info(f"🔄 Retrying in {backoff}s... (attempt {attempt + 1}/10)")
                await asyncio.sleep(backoff)
                await self._connect_websocket(attempt + 1, skip_monitor=skip_monitor)
            else:
                LOGGER.error("❌ Max reconnect attempts (10) reached, giving up")
                raise
    
    # Alias for internal use
    _connect_websocket_internal = _connect_websocket
    
    def _on_ws_reconnect(self):
        """Callback when EventSub WebSocket reconnects automatically."""
        LOGGER.info("🔄 EventSub WebSocket reconnected (pyTwitchAPI auto-reconnect)")
        self._ws_connected = True
        self._ws_reconnect_count += 1
        self._update_hub_state("ws_state", "connected")
        self._update_hub_state("ws_reconnect_count", str(self._ws_reconnect_count))
        self._audit_log("eventsub_ws_auto_reconnect", {}, severity="info")
    
    def _on_ws_disconnect(self):
        """Callback when EventSub WebSocket disconnects."""
        LOGGER.warning("⚠️  EventSub WebSocket disconnected (pyTwitchAPI callback)")
        self._ws_connected = False
        self._update_hub_state("ws_state", "disconnected")
        self._audit_log("eventsub_ws_disconnect", {}, severity="warning")
    
    async def _ws_monitor_loop(self):
        """
        Monitor pyTwitchAPI WebSocket connection and handle disconnections.
        
        pyTwitchAPI's internal auto-reconnect can fail silently, leaving us
        with a dead connection. This monitor detects that and forces a clean
        reconnect with fresh EventSubWebsocket object.
        
        We check for:
        - Connection being None or closed
        - Session being invalid (after pyTwitchAPI internal reconnect fails)
        """
        LOGGER.info("🔍 WebSocket monitor loop started")
        
        # Wait for initial connection to stabilize
        await asyncio.sleep(15)
        
        # Track stable session after initial connection
        stable_session_id = self._ws_session_id
        consecutive_failures = 0
        
        while self._running:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds
                
                if not self._running:
                    break
                
                # Check if eventsub object is gone or connection is dead
                if not self.eventsub:
                    LOGGER.warning("⚠️  Monitor: eventsub is None, waiting for reconnect...")
                    consecutive_failures += 1
                    if consecutive_failures >= 3:
                        LOGGER.error("❌ Monitor: 3 consecutive failures, triggering reconnect")
                        await self._force_reconnect_with_subscriptions()
                        consecutive_failures = 0
                        stable_session_id = self._ws_session_id
                    continue
                
                # Check internal connection state
                connection = getattr(self.eventsub, '_connection', None)
                if connection and hasattr(connection, 'closed') and connection.closed:
                    LOGGER.warning("⚠️  Monitor: WebSocket connection is closed")
                    consecutive_failures += 1
                    if consecutive_failures >= 2:
                        LOGGER.error("❌ Monitor: Connection closed, triggering reconnect")
                        await self._force_reconnect_with_subscriptions()
                        consecutive_failures = 0
                        stable_session_id = self._ws_session_id
                    continue
                
                # Check if pyTwitchAPI is stuck in reconnecting state
                is_reconnecting = getattr(self.eventsub, '_is_reconnecting', False)
                if is_reconnecting:
                    LOGGER.warning("⚠️  Monitor: pyTwitchAPI is in reconnecting state")
                    consecutive_failures += 1
                    if consecutive_failures >= 6:  # ~60 seconds of reconnecting
                        LOGGER.error("❌ Monitor: pyTwitchAPI stuck reconnecting, taking over")
                        await self._force_reconnect_with_subscriptions()
                        consecutive_failures = 0
                        stable_session_id = self._ws_session_id
                    continue
                
                # All good, reset failure counter
                if consecutive_failures > 0:
                    LOGGER.info("✅ Monitor: Connection recovered")
                consecutive_failures = 0
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                LOGGER.error(f"❌ WebSocket monitor error: {e}")
                await asyncio.sleep(10)
        
        LOGGER.info("🛑 WebSocket monitor loop stopped")
    
    async def _force_reconnect_with_subscriptions(self):
        """Force a complete reconnect and recreate all subscriptions."""
        LOGGER.info("🔄 Force reconnecting with subscription recreation...")
        
        # Save subscriptions to recreate (deduplicate by channel_id+topic)
        seen = set()
        subs_to_recreate = []
        for sub in self._created_subscriptions:
            key = (sub['channel_id'], sub['topic'])
            if key not in seen:
                seen.add(key)
                subs_to_recreate.append(sub)
        
        # Clear tracked subscriptions (will be re-added on creation)
        self._created_subscriptions.clear()
        
        # Stop old EventSub cleanly
        if self.eventsub:
            try:
                await self.eventsub.stop()
            except Exception as e:
                LOGGER.warning(f"⚠️  Error stopping old EventSub: {e}")
        
        self.eventsub = None
        self._ws_connected = False
        
        # Small delay before reconnect
        await asyncio.sleep(2)
        
        # Reconnect with fresh EventSubWebsocket (skip monitor creation - we're already in it)
        await self._connect_websocket_internal(attempt=1, skip_monitor=True)
        
        # Recreate all subscriptions
        if subs_to_recreate:
            LOGGER.info(f"🔄 Recreating {len(subs_to_recreate)} subscriptions...")
            for sub in subs_to_recreate:
                try:
                    await self._create_subscription(
                        channel_id=sub['channel_id'],
                        topic=sub['topic'],
                        version=sub.get('version', '1')
                    )
                    await asyncio.sleep(0.5)  # Rate limit
                except Exception as e:
                    LOGGER.error(f"❌ Failed to recreate subscription {sub}: {e}")
        
        LOGGER.info("✅ Force reconnect complete")
    
    async def _create_first_subscription(self):
        """
        Create first subscription < 10s after WebSocket connect.
        
        Twitch returns 4003 (websocket_connection_unused) if no subscription
        is created within 10 seconds of WebSocket connect.
        
        Strategy:
            - Check desired_subscriptions for any pending sub
            - If found, create it immediately
            - If not found, wait for first bot hello (should arrive soon)
        """
        # Check if we have any desired subscriptions
        desired = self._get_desired_subscriptions()
        
        if desired:
            # Create first one immediately
            first_sub = desired[0]
            LOGGER.info(f"🚀 Creating first subscription to avoid 4003: {first_sub['channel_id']} / {first_sub['topic']}")
            await self._create_subscription(
                channel_id=first_sub['channel_id'],
                topic=first_sub['topic'],
                version=first_sub['version']
            )
        else:
            LOGGER.warning("⚠️  No desired subscriptions yet, attempting fallback first-subscription on hub broadcaster...")

            # Try to create a safe fallback subscription on the hub's broadcaster
            # This satisfies Twitch requirement to create *a* subscription within 10s
            if self._default_broadcaster_id:
                try:
                    LOGGER.info(f"🔁 Creating fallback subscription: {self._default_broadcaster_id} / stream.online")
                    success = await self._create_subscription(
                        channel_id=self._default_broadcaster_id,
                        topic="stream.online",
                        version="1",
                    )
                    if success:
                        LOGGER.info("✅ Fallback first-subscription created successfully")
                        return
                    else:
                        LOGGER.warning("⚠️ Fallback subscription creation returned False")
                except Exception as e:
                    LOGGER.warning(f"⚠️ Fallback subscription failed: {e}")

            # If we reach here, there's nothing we can do until a bot connects
            LOGGER.warning("⚠️  No desired subscriptions and no fallback possible, waiting for bot hello...")
    
    # ========================================================================
    # IPC Message Handling (Bot → Hub)
    # ========================================================================
    
    async def _handle_bot_message(self, msg, client_id: str):
        """
        Handle incoming message from bot.
        
        Args:
            msg: Deserialized message dataclass
            client_id: Bot identifier (channel name)
        """
        if isinstance(msg, HelloMessage):
            await self._handle_hello(msg, client_id)
        
        elif isinstance(msg, SubscribeMessage):
            await self._handle_subscribe(msg, client_id)
        
        elif isinstance(msg, UnsubscribeMessage):
            await self._handle_unsubscribe(msg, client_id)
        
        elif isinstance(msg, PingMessage):
            await self._handle_ping(msg, client_id)
        
        else:
            LOGGER.warning(f"⚠️  Unknown message type from {client_id}: {type(msg)}")
    
    async def _handle_hello(self, msg: HelloMessage, client_id: str):
        """
        Handle bot hello message.
        
        Bot announces itself and declares desired subscriptions.
        """
        LOGGER.info(f"👋 Hello from {msg.channel} (ID: {msg.channel_id})")
        
        # Store channel mapping
        self._channel_mapping[msg.channel_id] = msg.channel
        
        # Add desired subscriptions to DB
        for topic in msg.topics:
            self._add_desired_subscription(
                channel_id=msg.channel_id,
                topic=topic,
                version="1",
                transport="websocket"
            )
        
        # Send ack for each topic
        for topic in msg.topics:
            ack = AckMessage(
                cmd="hello",
                channel_id=msg.channel_id,
                topic=topic,
                status="pending"
            )
            await self.ipc_server.send_to_client(client_id, ack)
        
        # Log to audit
        self._audit_log("ipc_hello_received", {
            "channel": msg.channel,
            "channel_id": msg.channel_id,
            "topics": msg.topics,
        }, severity="info")
        
        # Trigger reconciliation soon (will create subs)
        # Note: Reconciliation loop will pick this up
    
    async def _handle_subscribe(self, msg: SubscribeMessage, client_id: str):
        """Handle dynamic subscription request from bot."""
        LOGGER.info(f"➕ Subscribe request: {msg.channel_id} / {msg.topic}")
        
        # Add to desired_subscriptions
        self._add_desired_subscription(
            channel_id=msg.channel_id,
            topic=msg.topic,
            version="1",
            transport="websocket"
        )
        
        # Send ack
        ack = AckMessage(
            cmd="subscribe",
            channel_id=msg.channel_id,
            topic=msg.topic,
            status="pending"
        )
        await self.ipc_server.send_to_client(client_id, ack)
        
        # Log to audit
        self._audit_log("ipc_subscribe_request", {
            "channel": client_id,
            "channel_id": msg.channel_id,
            "topic": msg.topic,
        }, severity="info")
    
    async def _handle_unsubscribe(self, msg: UnsubscribeMessage, client_id: str):
        """Handle unsubscribe request from bot."""
        LOGGER.info(f"➖ Unsubscribe request: {msg.channel_id} / {msg.topic}")
        
        # Remove from desired_subscriptions
        self._remove_desired_subscription(
            channel_id=msg.channel_id,
            topic=msg.topic
        )
        
        # Send ack
        ack = AckMessage(
            cmd="unsubscribe",
            channel_id=msg.channel_id,
            topic=msg.topic,
            status="ok"
        )
        await self.ipc_server.send_to_client(client_id, ack)
        
        # Log to audit
        self._audit_log("ipc_unsubscribe_request", {
            "channel": client_id,
            "channel_id": msg.channel_id,
            "topic": msg.topic,
        }, severity="info")
    
    async def _handle_ping(self, msg: PingMessage, client_id: str):
        """Handle keepalive ping from bot."""
        pong = PongMessage(timestamp=msg.timestamp)
        await self.ipc_server.send_to_client(client_id, pong)
    
    # ========================================================================
    # Database Operations
    # ========================================================================
    
    def _add_desired_subscription(
        self,
        channel_id: str,
        topic: str,
        version: str,
        transport: str
    ):
        """Add subscription to desired_subscriptions table."""
        now = int(time.time())
        
        try:
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO desired_subscriptions 
                    (channel_id, topic, version, transport, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (channel_id, topic, version, transport, now, now))
                conn.commit()
        except Exception as e:
            LOGGER.error(f"❌ Failed to add desired subscription: {e}")
    
    def _remove_desired_subscription(self, channel_id: str, topic: str):
        """Remove subscription from desired_subscriptions table."""
        try:
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM desired_subscriptions 
                    WHERE channel_id = ? AND topic = ?
                """, (channel_id, topic))
                conn.commit()
        except Exception as e:
            LOGGER.error(f"❌ Failed to remove desired subscription: {e}")
    
    def _get_desired_subscriptions(self) -> List[Dict]:
        """Get all desired subscriptions."""
        try:
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT channel_id, topic, version, transport 
                    FROM desired_subscriptions
                """)
                rows = cursor.fetchall()
                return [
                    {
                        "channel_id": row[0],
                        "topic": row[1],
                        "version": row[2],
                        "transport": row[3]
                    }
                    for row in rows
                ]
        except Exception as e:
            LOGGER.error(f"❌ Failed to get desired subscriptions: {e}")
            return []
    
    def _get_active_subscriptions(self) -> List[Dict]:
        """Get all active subscriptions."""
        try:
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT twitch_sub_id, channel_id, topic, status 
                    FROM active_subscriptions
                """)
                rows = cursor.fetchall()
                return [
                    {
                        "twitch_sub_id": row[0],
                        "channel_id": row[1],
                        "topic": row[2],
                        "status": row[3]
                    }
                    for row in rows
                ]
        except Exception as e:
            LOGGER.error(f"❌ Failed to get active subscriptions: {e}")
            return []
    
    def _update_hub_state(self, key: str, value: str):
        """Update hub_state key-value."""
        try:
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO hub_state (key, value, updated_at)
                    VALUES (?, ?, ?)
                """, (key, value, int(time.time())))
                conn.commit()
        except Exception as e:
            LOGGER.error(f"❌ Failed to update hub_state: {e}")
    
    def _get_hub_state(self, key: str, default: str = None) -> Optional[str]:
        """Get hub_state value by key."""
        try:
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                row = cursor.execute(
                    "SELECT value FROM hub_state WHERE key = ?",
                    (key,)
                ).fetchone()
                return row[0] if row else default
        except Exception as e:
            LOGGER.error(f"❌ Failed to get hub_state: {e}")
            return default
    
    def _audit_log(self, event_type: str, details: Dict, severity: str = "info"):
        """Write audit log entry."""
        try:
            import json
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO audit_log (event_type, user_id, channel_id, details, severity)
                    VALUES (?, NULL, NULL, ?, ?)
                """, (event_type, json.dumps(details), severity))
                conn.commit()
        except Exception as e:
            LOGGER.error(f"❌ Failed to write audit log: {e}")
    
    # ========================================================================
    # Reconciliation Loop
    # ========================================================================
    
    async def _reconciliation_loop(self):
        """
        Periodic reconciliation of desired vs active subscriptions.
        
        Runs every reconcile_interval seconds.
        Compares desired_subscriptions with active_subscriptions and:
            - Creates missing subscriptions (rate-limited)
            - Deletes extra subscriptions (rate-limited)
        """
        LOGGER.info("🔄 Reconciliation loop started")
        
        while self._running:
            try:
                # Wait for interval with jitter
                jitter = random.uniform(0, 5)
                await asyncio.sleep(self.config.reconcile_interval + jitter)
                
                if not self._ws_connected:
                    LOGGER.debug("⏸️  Skipping reconciliation (WebSocket not connected)")
                    continue
                
                # Perform reconciliation
                await self._reconcile()
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                LOGGER.error(f"❌ Reconciliation error: {e}")
                await asyncio.sleep(10)  # Backoff on error
        
        LOGGER.info("🛑 Reconciliation loop stopped")
    
    async def _reconcile(self):
        """Perform single reconciliation pass."""
        start_time = time.time()
        
        LOGGER.info("🔍 Starting reconciliation...")
        
        # Get desired and active subscriptions
        desired = self._get_desired_subscriptions()
        active = self._get_active_subscriptions()
        
        # Create sets for comparison (channel_id, topic)
        desired_set = {(d['channel_id'], d['topic']) for d in desired}
        active_set = {(a['channel_id'], a['topic']) for a in active}
        
        # Calculate diff
        to_create = desired_set - active_set
        to_delete = active_set - desired_set
        
        LOGGER.info(f"📊 Reconciliation: desired={len(desired)}, active={len(active)}, to_create={len(to_create)}, to_delete={len(to_delete)}")
        
        # Create missing subscriptions (rate-limited)
        created_count = 0
        for channel_id, topic in to_create:
            # Find full subscription info
            sub_info = next((d for d in desired if d['channel_id'] == channel_id and d['topic'] == topic), None)
            if not sub_info:
                continue
            
            # Create subscription
            success = await self._create_subscription(
                channel_id=channel_id,
                topic=topic,
                version=sub_info['version']
            )
            
            if success:
                created_count += 1
            
            # Rate limiting with jitter
            delay = (1.0 / self.config.req_rate_per_s) + (random.randint(0, self.config.req_jitter_ms) / 1000.0)
            await asyncio.sleep(delay)
        
        # Delete extra subscriptions (rate-limited)
        deleted_count = 0
        for channel_id, topic in to_delete:
            # Find twitch_sub_id
            sub_info = next((a for a in active if a['channel_id'] == channel_id and a['topic'] == topic), None)
            if not sub_info:
                continue
            
            # Delete subscription
            success = await self._delete_subscription(
                twitch_sub_id=sub_info['twitch_sub_id']
            )
            
            if success:
                deleted_count += 1
            
            # Rate limiting with jitter
            delay = (1.0 / self.config.req_rate_per_s) + (random.randint(0, self.config.req_jitter_ms) / 1000.0)
            await asyncio.sleep(delay)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        LOGGER.info(f"✅ Reconciliation complete: created={created_count}, deleted={deleted_count}, duration={duration_ms}ms")
        
        # Update hub_state
        self._update_hub_state("last_reconcile_ts", str(int(time.time())))
        
        # Log to audit
        self._audit_log("eventsub_reconcile", {
            "desired_count": len(desired),
            "active_count": len(active),
            "to_create": len(to_create),
            "to_delete": len(to_delete),
            "created": created_count,
            "deleted": deleted_count,
            "duration_ms": duration_ms,
        }, severity="info")
    
    # ========================================================================
    # Subscription Management (via HTTP API)
    # ========================================================================
    
    async def _create_subscription(
        self,
        channel_id: str,
        topic: str,
        version: str
    ) -> bool:
        """
        Create EventSub subscription via HTTP API.
        
        IMPORTANT: Does NOT reconnect WebSocket. Uses existing connection.
        
        Returns:
            True if successful, False otherwise
        """
        # This is a placeholder - full implementation continues in Part 2
        # For now, we'll use the EventSub WebSocket's listen_* methods
        
        try:
            LOGGER.info(f"📝 Creating subscription: {channel_id} / {topic}")
            
            # Map topic to EventSub listen method
            if topic == "stream.online":
                sub_id = await self.eventsub.listen_stream_online(
                    broadcaster_user_id=channel_id,
                    callback=self._handle_stream_online_event
                )
            elif topic == "stream.offline":
                sub_id = await self.eventsub.listen_stream_offline(
                    broadcaster_user_id=channel_id,
                    callback=self._handle_stream_offline_event
                )
            else:
                LOGGER.error(f"❌ Unsupported topic: {topic}")
                return False
            
            # Add to active_subscriptions
            now = int(time.time())
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO active_subscriptions
                    (twitch_sub_id, channel_id, topic, status, cost, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (sub_id, channel_id, topic, "enabled", 1, now, now))
                conn.commit()
            
            LOGGER.info(f"✅ Subscription created: {sub_id}")
            
            # Track subscription for re-creation on reconnect
            self._created_subscriptions.append({
                "channel_id": channel_id,
                "topic": topic,
                "sub_id": sub_id
            })
            
            # Log to audit
            self._audit_log("eventsub_create", {
                "channel_id": channel_id,
                "topic": topic,
                "twitch_sub_id": sub_id,
                "status": "enabled",
            }, severity="info")
            
            return True
        
        except Exception as e:
            LOGGER.error(f"❌ Failed to create subscription: {e}")
            
            # Log to audit
            self._audit_log("eventsub_create_failed", {
                "channel_id": channel_id,
                "topic": topic,
                "error": str(e),
            }, severity="error")
            
            return False
    
    async def _delete_subscription(self, twitch_sub_id: str) -> bool:
        """
        Delete EventSub subscription.
        
        Note: pyTwitchAPI doesn't have a direct delete method for WebSocket subs.
        We'll just remove from active_subscriptions and let it expire naturally.
        """
        try:
            LOGGER.info(f"🗑️  Deleting subscription: {twitch_sub_id}")
            
            # Remove from active_subscriptions
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM active_subscriptions
                    WHERE twitch_sub_id = ?
                """, (twitch_sub_id,))
                conn.commit()
            
            LOGGER.info(f"✅ Subscription deleted: {twitch_sub_id}")
            
            # Log to audit
            self._audit_log("eventsub_delete", {
                "twitch_sub_id": twitch_sub_id,
            }, severity="info")
            
            return True
        
        except Exception as e:
            LOGGER.error(f"❌ Failed to delete subscription: {e}")
            
            # Log to audit
            self._audit_log("eventsub_delete_failed", {
                "twitch_sub_id": twitch_sub_id,
                "error": str(e),
            }, severity="error")
            
            return False
    
    # ========================================================================
    # Event Handlers (WebSocket → IPC routing)
    # ========================================================================
    
    async def _handle_stream_online_event(self, event: StreamOnlineEvent):
        """Route stream.online event to bot."""
        await self._route_event("stream.online", event)
    
    async def _handle_stream_offline_event(self, event: StreamOfflineEvent):
        """Route stream.offline event to bot."""
        await self._route_event("stream.offline", event)
    
    async def _route_event(self, topic: str, event):
        """
        Route EventSub event to appropriate bot via IPC.
        
        Args:
            topic: Event topic (stream.online, stream.offline)
            event: EventSub event object
        """
        event_data = event.to_dict() if hasattr(event, 'to_dict') else {}
        channel_id = event_data.get("broadcaster_user_id")
        
        if not channel_id:
            LOGGER.warning(f"⚠️  Event missing broadcaster_user_id: {event_data}")
            return
        
        # Find bot client_id from mapping
        client_id = self._channel_mapping.get(channel_id)
        if not client_id:
            LOGGER.warning(f"⚠️  No bot connected for channel_id: {channel_id}")
            return
        
        # Create event message
        msg = EventMessage(
            topic=topic,
            channel_id=channel_id,
            twitch_event_id=event_data.get("id", "unknown"),
            payload=event_data
        )
        
        # Send to bot
        await self.ipc_server.send_to_client(client_id, msg)
        
        # Update metrics
        self._total_events_routed += 1
        self._update_hub_state("total_events_routed", str(self._total_events_routed))
        
        LOGGER.debug(f"📤 Event routed: {topic} → {client_id}")
    
    # ========================================================================
    # Health Check Loop
    # ========================================================================
    
    async def _health_check_loop(self):
        """Monitor WebSocket health and reconnect if needed."""
        LOGGER.info("🏥 Health check loop started")
        
        _consecutive_failures = 0
        
        while self._running:
            try:
                await asyncio.sleep(self.config.health_timeout)
                
                # Multi-layer health check
                ws_healthy = True
                
                # Check 1: Internal state
                if not self._ws_connected or not self.eventsub:
                    LOGGER.warning("⚠️  Health check: internal state indicates disconnected")
                    ws_healthy = False
                
                # Check 2: pyTwitchAPI EventSub status (if available)
                if ws_healthy and self.eventsub:
                    # Check if EventSub has active connection
                    # pyTwitchAPI uses _running or similar attribute
                    eventsub_running = getattr(self.eventsub, '_running', None)
                    if eventsub_running is not None and not eventsub_running:
                        LOGGER.warning("⚠️  Health check: EventSub._running is False")
                        ws_healthy = False
                
                if ws_healthy:
                    _consecutive_failures = 0
                    LOGGER.info(f"💓 Hub health check OK - WS connected, {len(self._channel_mapping)} channels mapped")
                else:
                    _consecutive_failures += 1
                    LOGGER.warning(f"⚠️  WebSocket health check failed (failures: {_consecutive_failures})")
                    
                    # Attempt reconnect after 2 consecutive failures
                    if _consecutive_failures >= 2:
                        LOGGER.warning("🔄 Forcing WebSocket reconnect...")
                        self._ws_reconnect_count += 1
                        self._update_hub_state("ws_reconnect_count", str(self._ws_reconnect_count))
                        
                        # Stop existing eventsub if any
                        if self.eventsub:
                            try:
                                await self.eventsub.stop()
                            except Exception:
                                pass
                        
                        await self._connect_websocket(attempt=1)
                        _consecutive_failures = 0
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                LOGGER.error(f"❌ Health check error: {e}")
        
        LOGGER.info("🛑 Health check loop stopped")


# ============================================================================
# Main
# ============================================================================

async def main():
    parser = argparse.ArgumentParser(description="EventSub Hub - Centralized WebSocket manager")
    parser.add_argument(
        "--config",
        type=str,
        default="config/config.yaml",
        help="Path to config file"
    )
    parser.add_argument(
        "--db",
        type=str,
        default="kissbot.db",
        help="Path to database file"
    )
    parser.add_argument(
        "--socket",
        type=str,
        default="/tmp/kissbot_hub.sock",
        help="Unix socket path for IPC"
    )
    parser.add_argument(
        "--broadcaster",
        type=str,
        default=None,
        help="Broadcaster login to use for EventSub (default: first in config)"
    )
    
    args = parser.parse_args()
    
    # Load config
    with open(args.config, 'r') as f:
        config_data = yaml.safe_load(f)
    
    # Create Hub config from YAML
    hub_config = HubConfig.from_yaml(config_data, socket_path=args.socket)
    
    LOGGER.info(f"🔧 Hub config: reconcile={hub_config.reconcile_interval}s, "
                f"rate={hub_config.req_rate_per_s}req/s, "
                f"jitter={hub_config.req_jitter_ms}ms")
    
    # Connect to database (it will load encryption key internally)
    db = DatabaseManager(db_path=args.db, key_file=".kissbot.key")
    
    # IMPORTANT: EventSub WebSocket needs a USER token, not app token
    # Use --broadcaster arg, or first channel from config
    
    # Determine broadcaster login
    if args.broadcaster:
        broadcaster_login = args.broadcaster
    else:
        # Get first channel from config
        channels = config_data.get('channels', [])
        if channels:
            broadcaster_login = channels[0] if isinstance(channels[0], str) else channels[0].get('name', 'el_serda')
        else:
            broadcaster_login = 'el_serda'
    
    LOGGER.info(f"🎯 Using broadcaster: {broadcaster_login}")
    
    try:
        # Load and decrypt broadcaster token
        user_info = db.get_user_by_login(broadcaster_login)
        if not user_info:
            LOGGER.error(f"❌ User {broadcaster_login} not found in database")
            sys.exit(1)
        
        user_id = user_info['id']
        tokens = db.get_tokens(user_id, token_type='broadcaster')
        if not tokens:
            LOGGER.error(f"❌ No broadcaster token found for {broadcaster_login}")
            LOGGER.error("   Run: python scripts/oauth_flow.py to authenticate")
            sys.exit(1)
        
        access_token = tokens['access_token']
        refresh_token = tokens['refresh_token']
        scopes = tokens['scopes']
        
        LOGGER.info(f"✅ Loaded broadcaster token for {broadcaster_login}")
    
    except Exception as e:
        LOGGER.error(f"❌ Failed to load broadcaster token: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Create Twitch API client with broadcaster token
    twitch = Twitch(
        app_id=config_data['twitch']['client_id'],
        app_secret=config_data['twitch']['client_secret']
    )
    
    # =========================================================================
    # CRITICAL: Token refresh callback - save refreshed tokens to DB
    # =========================================================================
    def save_refreshed_token(new_access_token: str, new_refresh_token: str):
        """Callback invoked by pyTwitchAPI when token is auto-refreshed."""
        try:
            LOGGER.info(f"🔄 Token refreshed for {broadcaster_login}, saving to DB...")
            # Get current scopes from DB
            current_tokens = db.get_tokens(user_id, token_type='broadcaster')
            current_scopes = current_tokens.get('scopes', scopes) if current_tokens else scopes
            
            # Calculate new expiry (~4 hours from now)
            from datetime import datetime, timedelta
            new_expiry = datetime.now() + timedelta(hours=4)
            
            # Store refreshed token
            db.store_token(
                user_id=user_id,
                token_type='broadcaster',
                access_token=new_access_token,
                refresh_token=new_refresh_token,
                expires_at=new_expiry,
                scopes=[s.value if hasattr(s, 'value') else str(s) for s in current_scopes]
            )
            LOGGER.info(f"✅ Refreshed token saved for {broadcaster_login}")
        except Exception as e:
            LOGGER.error(f"❌ Failed to save refreshed token: {e}")
    
    # Register callback BEFORE set_user_authentication
    twitch.user_auth_refresh_callback = save_refreshed_token
    
    # Set user authentication (broadcaster token for EventSub)
    await twitch.set_user_authentication(
        token=access_token,
        scope=scopes,
        refresh_token=refresh_token,
        validate=False  # We trust our DB token
    )
    
    # Create Hub (provide broadcaster id for fallback first-subscription)
    hub = EventSubHub(config=hub_config, db=db, twitch=twitch, default_broadcaster_id=str(user_id))
    
    # Signal handlers
    def handle_shutdown(sig, frame):
        LOGGER.info(f"🛑 Received signal {sig}, shutting down...")
        asyncio.create_task(hub.stop())
    
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    # Start Hub
    await hub.start()
    
    # Keep running
    try:
        while hub._running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await hub.stop()


if __name__ == "__main__":
    asyncio.run(main())
