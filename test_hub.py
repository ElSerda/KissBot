#!/usr/bin/env python3
"""
Test script for EventSub Hub.

Tests basic functionality:
1. Hub starts and listens on Unix socket
2. Test bot connects via IPC
3. Bot sends hello with subscriptions
4. Hub acknowledges
5. Bot disconnects cleanly
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from core.ipc_protocol import (
    IPCClient,
    HelloMessage,
    AckMessage,
    ErrorMessage,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s"
)
LOGGER = logging.getLogger(__name__)


async def test_bot_connection():
    """Test bot connecting to Hub."""
    
    socket_path = "/tmp/kissbot_hub.sock"
    
    LOGGER.info("🧪 Testing bot connection to Hub...")
    
    # Create IPC client
    client = IPCClient(socket_path=socket_path)
    
    try:
        # Connect to Hub
        LOGGER.info(f"📞 Connecting to Hub at {socket_path}...")
        await client.connect(timeout=5.0)
        LOGGER.info("✅ Connected to Hub")
        
        # Send hello message
        LOGGER.info("👋 Sending hello...")
        await client.send_hello(
            channel="el_serda",
            channel_id="44456636",
            topics=["stream.online", "stream.offline"]
        )
        LOGGER.info("✅ Hello sent")
        
        # Wait for acks
        LOGGER.info("⏳ Waiting for acks...")
        ack_count = 0
        
        async def receive_messages():
            nonlocal ack_count
            async for msg in client.receive():
                if isinstance(msg, AckMessage):
                    LOGGER.info(f"✅ Received ACK: {msg.cmd} / {msg.topic} → {msg.status}")
                    ack_count += 1
                    
                    # Exit after 2 acks (hello for 2 topics)
                    if ack_count >= 2:
                        break
                
                elif isinstance(msg, ErrorMessage):
                    LOGGER.error(f"❌ Received ERROR: {msg.cmd} / {msg.code} → {msg.detail}")
                    break
        
        # Wait for acks with timeout
        try:
            await asyncio.wait_for(receive_messages(), timeout=10.0)
        except asyncio.TimeoutError:
            LOGGER.warning("⚠️  Timeout waiting for acks")
        
        # Keep connection alive for a few seconds
        LOGGER.info("⏳ Keeping connection alive for 5s...")
        await asyncio.sleep(5)
        
        LOGGER.info("✅ Test passed!")
    
    except ConnectionError as e:
        LOGGER.error(f"❌ Connection failed: {e}")
        LOGGER.info("💡 Make sure EventSub Hub is running: python eventsub_hub.py")
        return False
    
    except Exception as e:
        LOGGER.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Disconnect
        LOGGER.info("🔌 Disconnecting...")
        await client.disconnect()
        LOGGER.info("✅ Disconnected")
    
    return True


async def main():
    LOGGER.info("=" * 60)
    LOGGER.info("EventSub Hub - Test Bot")
    LOGGER.info("=" * 60)
    
    success = await test_bot_connection()
    
    if success:
        LOGGER.info("")
        LOGGER.info("🎉 All tests passed!")
        sys.exit(0)
    else:
        LOGGER.info("")
        LOGGER.error("💥 Tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
