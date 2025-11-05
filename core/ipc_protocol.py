"""
IPC Protocol for EventSub Hub ↔ Bot communication.

Protocol uses JSON messages over Unix sockets (or TCP localhost).
Each message is a single JSON object terminated by newline.

Message Flow:
    1. Bot connects to Hub socket
    2. Bot sends "hello" with desired subscriptions
    3. Hub responds with "ack" for each subscription
    4. Hub routes "event" messages to bot
    5. Bot can "subscribe"/"unsubscribe" dynamically
    6. Bot disconnects → Hub removes desired_subscriptions

Message Types:
    Bot → Hub:
        - hello: Initial connection with channel info
        - subscribe: Request subscription
        - unsubscribe: Remove subscription
        - ping: Keepalive
    
    Hub → Bot:
        - ack: Acknowledge command
        - error: Command failed
        - event: EventSub event routed to bot
        - pong: Keepalive response
"""

import asyncio
import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

LOGGER = logging.getLogger(__name__)


# ============================================================================
# Message Types (Bot → Hub)
# ============================================================================

@dataclass
class HelloMessage:
    """
    Bot announces itself to Hub and declares desired subscriptions.
    
    Example:
        {
            "type": "hello",
            "channel": "el_serda",
            "channel_id": "44456636",
            "topics": ["stream.online", "stream.offline"]
        }
    """
    type: str = "hello"
    channel: str = ""  # Channel login (ex: "el_serda")
    channel_id: str = ""  # Twitch broadcaster_user_id
    topics: List[str] = None  # Desired topics
    
    def __post_init__(self):
        if self.topics is None:
            self.topics = []


@dataclass
class SubscribeMessage:
    """
    Bot requests a subscription (dynamic add).
    
    Example:
        {
            "type": "subscribe",
            "channel_id": "44456636",
            "topic": "stream.online"
        }
    """
    type: str = "subscribe"
    channel_id: str = ""
    topic: str = ""


@dataclass
class UnsubscribeMessage:
    """
    Bot requests unsubscription (dynamic remove).
    
    Example:
        {
            "type": "unsubscribe",
            "channel_id": "44456636",
            "topic": "stream.online"
        }
    """
    type: str = "unsubscribe"
    channel_id: str = ""
    topic: str = ""


@dataclass
class PingMessage:
    """
    Keepalive ping from bot.
    
    Example:
        {
            "type": "ping",
            "timestamp": 1699123456
        }
    """
    type: str = "ping"
    timestamp: int = 0


# ============================================================================
# Message Types (Hub → Bot)
# ============================================================================

@dataclass
class AckMessage:
    """
    Hub acknowledges bot command.
    
    Example:
        {
            "type": "ack",
            "cmd": "subscribe",
            "channel_id": "44456636",
            "topic": "stream.online",
            "status": "ok"
        }
    """
    type: str = "ack"
    cmd: str = ""  # Original command: hello|subscribe|unsubscribe
    channel_id: str = ""
    topic: str = ""
    status: str = "ok"  # ok|pending|error


@dataclass
class ErrorMessage:
    """
    Hub reports error for bot command.
    
    Example:
        {
            "type": "error",
            "cmd": "subscribe",
            "code": "rate_limited",
            "detail": "Backoff 2s"
        }
    """
    type: str = "error"
    cmd: str = ""
    code: str = ""  # rate_limited|cost_exceeded|invalid_token|not_found
    detail: str = ""


@dataclass
class EventMessage:
    """
    Hub routes EventSub event to bot.
    
    Example:
        {
            "type": "event",
            "topic": "stream.online",
            "channel_id": "44456636",
            "twitch_event_id": "abc-123-def",
            "payload": {
                "broadcaster_user_id": "44456636",
                "broadcaster_user_login": "el_serda",
                "type": "live",
                "started_at": "2025-11-05T10:30:00Z"
            }
        }
    """
    type: str = "event"
    topic: str = ""
    channel_id: str = ""
    twitch_event_id: str = ""
    payload: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.payload is None:
            self.payload = {}


@dataclass
class PongMessage:
    """
    Hub responds to ping.
    
    Example:
        {
            "type": "pong",
            "timestamp": 1699123456
        }
    """
    type: str = "pong"
    timestamp: int = 0


# ============================================================================
# Message Serialization/Deserialization
# ============================================================================

def serialize_message(msg: Any) -> str:
    """
    Serialize dataclass message to JSON string.
    
    Args:
        msg: Message dataclass instance
    
    Returns:
        JSON string with newline
    """
    data = asdict(msg)
    return json.dumps(data) + "\n"


def deserialize_message(line: str) -> Optional[Any]:
    """
    Deserialize JSON string to message dataclass.
    
    Args:
        line: JSON string (may include newline)
    
    Returns:
        Message dataclass instance or None if invalid
    """
    try:
        data = json.loads(line.strip())
        msg_type = data.get("type")
        
        # Map type to dataclass
        type_map = {
            "hello": HelloMessage,
            "subscribe": SubscribeMessage,
            "unsubscribe": UnsubscribeMessage,
            "ping": PingMessage,
            "ack": AckMessage,
            "error": ErrorMessage,
            "event": EventMessage,
            "pong": PongMessage,
        }
        
        msg_class = type_map.get(msg_type)
        if not msg_class:
            LOGGER.warning(f"Unknown message type: {msg_type}")
            return None
        
        # Create instance from dict
        return msg_class(**data)
    
    except json.JSONDecodeError as e:
        LOGGER.error(f"Failed to decode JSON: {e}")
        return None
    except TypeError as e:
        LOGGER.error(f"Failed to create message: {e}")
        return None


# ============================================================================
# Unix Socket Server (Hub side)
# ============================================================================

class IPCServer:
    """
    Unix socket server for Hub to listen for bot connections.
    
    Usage:
        server = IPCServer(socket_path="/tmp/kissbot_hub.sock")
        await server.start(handler=handle_bot_message)
        # ... server runs ...
        await server.stop()
    """
    
    def __init__(self, socket_path: str):
        self.socket_path = Path(socket_path)
        self.server: Optional[asyncio.Server] = None
        self.clients: Dict[str, asyncio.StreamWriter] = {}  # channel -> writer
        self._running = False
    
    async def start(self, handler: Callable):
        """
        Start IPC server.
        
        Args:
            handler: Async callback(message, client_id) for incoming messages
        """
        # Remove stale socket if exists
        if self.socket_path.exists():
            LOGGER.warning(f"⚠️  Removing stale socket: {self.socket_path}")
            self.socket_path.unlink()
        
        # Ensure parent directory exists
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Start server
        self.server = await asyncio.start_unix_server(
            lambda r, w: self._handle_client(r, w, handler),
            path=str(self.socket_path)
        )
        
        self._running = True
        LOGGER.info(f"🔌 IPC Server listening on {self.socket_path}")
    
    async def _handle_client(
        self, 
        reader: asyncio.StreamReader, 
        writer: asyncio.StreamWriter,
        handler: Callable
    ):
        """Handle individual bot connection."""
        client_addr = writer.get_extra_info('peername', 'unknown')
        client_id = f"client_{id(writer)}"  # Temporary ID until hello
        
        LOGGER.info(f"🔗 Bot connected: {client_addr}")
        
        try:
            while self._running:
                # Read line (JSON message)
                line = await reader.readline()
                
                if not line:
                    # Client disconnected
                    break
                
                # Deserialize message
                msg = deserialize_message(line.decode('utf-8'))
                if not msg:
                    continue
                
                # Update client_id if hello message
                if isinstance(msg, HelloMessage):
                    client_id = msg.channel
                    self.clients[client_id] = writer
                    LOGGER.info(f"✅ Bot identified: {client_id}")
                
                # Call handler
                await handler(msg, client_id)
        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            LOGGER.error(f"❌ Client error: {e}")
        
        finally:
            # Remove client
            if client_id in self.clients:
                del self.clients[client_id]
            
            writer.close()
            await writer.wait_closed()
            LOGGER.info(f"🔌 Bot disconnected: {client_id}")
    
    async def send_to_client(self, client_id: str, msg: Any):
        """
        Send message to specific bot.
        
        Args:
            client_id: Bot channel name (ex: "el_serda")
            msg: Message dataclass to send
        """
        writer = self.clients.get(client_id)
        if not writer:
            LOGGER.warning(f"⚠️  Client {client_id} not connected")
            return
        
        try:
            data = serialize_message(msg)
            writer.write(data.encode('utf-8'))
            await writer.drain()
        except Exception as e:
            LOGGER.error(f"❌ Failed to send to {client_id}: {e}")
    
    async def broadcast(self, msg: Any):
        """
        Send message to all connected bots.
        
        Args:
            msg: Message dataclass to broadcast
        """
        data = serialize_message(msg)
        
        for client_id, writer in list(self.clients.items()):
            try:
                writer.write(data.encode('utf-8'))
                await writer.drain()
            except Exception as e:
                LOGGER.error(f"❌ Failed to broadcast to {client_id}: {e}")
    
    async def stop(self):
        """Stop IPC server and close all connections."""
        self._running = False
        
        # Close all clients
        for client_id, writer in list(self.clients.items()):
            writer.close()
            await writer.wait_closed()
        
        self.clients.clear()
        
        # Close server
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        # Remove socket file
        if self.socket_path.exists():
            self.socket_path.unlink()
        
        LOGGER.info("🛑 IPC Server stopped")


# ============================================================================
# Unix Socket Client (Bot side)
# ============================================================================

class IPCClient:
    """
    Unix socket client for bot to connect to Hub.
    
    Usage:
        client = IPCClient(socket_path="/tmp/kissbot_hub.sock")
        await client.connect()
        await client.send_hello(channel="el_serda", channel_id="44456636")
        
        async for msg in client.receive():
            if isinstance(msg, EventMessage):
                handle_event(msg)
        
        await client.disconnect()
    """
    
    def __init__(self, socket_path: str):
        self.socket_path = Path(socket_path)
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self._connected = False
    
    async def connect(self, timeout: float = 5.0):
        """
        Connect to Hub IPC server.
        
        Args:
            timeout: Connection timeout in seconds
        
        Raises:
            ConnectionError: If connection fails
        """
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_unix_connection(str(self.socket_path)),
                timeout=timeout
            )
            self._connected = True
            LOGGER.info(f"🔗 Connected to Hub: {self.socket_path}")
        
        except asyncio.TimeoutError:
            raise ConnectionError(f"Timeout connecting to Hub socket: {self.socket_path}")
        except FileNotFoundError:
            raise ConnectionError(f"Hub socket not found: {self.socket_path}")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Hub: {e}")
    
    async def send(self, msg: Any):
        """
        Send message to Hub.
        
        Args:
            msg: Message dataclass
        """
        if not self._connected or not self.writer:
            raise ConnectionError("Not connected to Hub")
        
        try:
            data = serialize_message(msg)
            self.writer.write(data.encode('utf-8'))
            await self.writer.drain()
        except Exception as e:
            LOGGER.error(f"❌ Failed to send message: {e}")
            raise
    
    async def send_hello(self, channel: str, channel_id: str, topics: List[str]):
        """Convenience method to send hello message."""
        msg = HelloMessage(channel=channel, channel_id=channel_id, topics=topics)
        await self.send(msg)
    
    async def send_subscribe(self, channel_id: str, topic: str):
        """Convenience method to subscribe."""
        msg = SubscribeMessage(channel_id=channel_id, topic=topic)
        await self.send(msg)
    
    async def send_unsubscribe(self, channel_id: str, topic: str):
        """Convenience method to unsubscribe."""
        msg = UnsubscribeMessage(channel_id=channel_id, topic=topic)
        await self.send(msg)
    
    async def receive(self):
        """
        Generator to receive messages from Hub.
        
        Yields:
            Message dataclass instances
        """
        if not self._connected or not self.reader:
            raise ConnectionError("Not connected to Hub")
        
        try:
            while self._connected:
                line = await self.reader.readline()
                
                if not line:
                    # Server disconnected
                    LOGGER.warning("⚠️  Hub disconnected")
                    break
                
                msg = deserialize_message(line.decode('utf-8'))
                if msg:
                    yield msg
        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            LOGGER.error(f"❌ Receive error: {e}")
    
    async def disconnect(self):
        """Disconnect from Hub."""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
        
        self._connected = False
        LOGGER.info("🔌 Disconnected from Hub")
    
    def is_connected(self) -> bool:
        """Check if connected to Hub."""
        return self._connected
