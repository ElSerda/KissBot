# 🤖 MonitorClient - Usage Guide

Complete guide for integrating KissBot monitoring into your bot.

## 📦 Installation

MonitorClient is built-in to KissBot:

```python
from core.monitor_client import MonitorClient, features_to_dict
import os
```

## 🚀 Quick Start

### Minimal Integration (3 lines)

```python
from core.monitor_client import MonitorClient

client = MonitorClient(channel="my_channel", pid=os.getpid())
await client.register()
await client.start_heartbeat()
```

### Full Integration with Features

```python
from core.monitor_client import MonitorClient, features_to_dict
from core.feature_manager import FeatureManager
import os

# Your bot initialization
feature_manager = FeatureManager()
features = features_to_dict(feature_manager)

# Create monitor client
monitor_client = MonitorClient(
    channel="el_serda",
    pid=os.getpid(),
    socket_path="/tmp/kissbot_monitor.sock",
    timeout=2.0
)

# Register with features
await monitor_client.register(features=features)

# Start automatic heartbeat (every 30 seconds)
await monitor_client.start_heartbeat()

# ... your bot code runs ...

# Graceful shutdown
await monitor_client.stop_heartbeat()
await monitor_client.unregister()
```

---

## 📚 API Reference

### Class: `MonitorClient`

```python
class MonitorClient:
    def __init__(
        self,
        channel: str,
        pid: int,
        socket_path: str = "/tmp/kissbot_monitor.sock",
        timeout: float = 2.0
    )
```

**Parameters:**
- `channel` (str): Twitch channel name (e.g., "el_serda")
- `pid` (int): Process ID of bot (usually `os.getpid()`)
- `socket_path` (str): Path to Monitor Unix socket (default: `/tmp/kissbot_monitor.sock`)
- `timeout` (float): Connection timeout in seconds (default: 2.0)

**Example:**
```python
client = MonitorClient(
    channel="my_channel",
    pid=os.getpid(),
    socket_path="/tmp/kissbot_monitor.sock",
    timeout=2.0
)
```

---

### Method: `register()`

Register bot with Monitor on startup.

```python
async def register(
    features: Optional[Dict[str, bool]] = None
) -> bool
```

**Parameters:**
- `features` (dict, optional): Map of feature_name → enabled

**Returns:** `True` if successful, `False` if Monitor unavailable

**Example:**
```python
result = await client.register(features={
    "llm": True,
    "translator": False,
    "music": True
})

if result:
    logger.info("✅ Registered with Monitor")
else:
    logger.warning("⚠️ Monitor unavailable, continuing without monitoring")
```

**What happens:**
1. Sends `{"type": "register", ...}` message to Monitor
2. Monitor stores bot info in memory and database
3. Monitor samples initial CPU baseline
4. Returns True immediately (fire-and-forget)

---

### Method: `heartbeat()`

Send a single heartbeat message. Usually called automatically by `start_heartbeat()`.

```python
async def heartbeat() -> bool
```

**Returns:** `True` if sent, `False` if Monitor unavailable

**Example:**
```python
# Usually not called directly - use start_heartbeat() instead
success = await client.heartbeat()
```

**What happens:**
1. Sends `{"type": "heartbeat", ...}` message
2. Monitor updates `last_heartbeat` timestamp
3. Monitor checks if bot is stale (no heartbeat > 120s)

---

### Method: `unregister()`

Gracefully unregister bot on shutdown.

```python
async def unregister() -> bool
```

**Returns:** `True` if successful, `False` if Monitor unavailable

**Example:**
```python
await client.unregister()
logger.info("👋 Unregistered from Monitor")
```

**What happens:**
1. Sends `{"type": "unregister", ...}` message
2. Monitor marks bot as "offline" in database
3. Removes bot from in-memory tracking

---

### Method: `log_llm_usage()`

Log LLM usage for analytics.

```python
async def log_llm_usage(
    model: str,
    feature: str,
    tokens_in: int,
    tokens_out: int,
    latency_ms: Optional[int] = None
) -> bool
```

**Parameters:**
- `model` (str): LLM model name (e.g., "gpt-4", "claude-3-opus")
- `feature` (str): Feature using LLM (e.g., "jokes", "translator")
- `tokens_in` (int): Input tokens consumed
- `tokens_out` (int): Output tokens generated
- `latency_ms` (int, optional): Response latency in milliseconds

**Returns:** `True` if logged, `False` if Monitor unavailable

**Example:**
```python
start_time = time.time()
response = await openai.ChatCompletion.acreate(...)
latency = int((time.time() - start_time) * 1000)

await client.log_llm_usage(
    model="gpt-4",
    feature="jokes",
    tokens_in=145,
    tokens_out=87,
    latency_ms=latency
)
```

**What happens:**
1. Sends `{"type": "llm_usage", ...}` message
2. Monitor stores in `llm_usage` database table
3. Used for analytics and cost tracking

---

### Method: `start_heartbeat()`

Start automatic periodic heartbeat task.

```python
async def start_heartbeat(
    interval: int = 30
)
```

**Parameters:**
- `interval` (int): Heartbeat interval in seconds (default: 30)

**Example:**
```python
# Start heartbeat (every 30 seconds)
await client.start_heartbeat()

# Or custom interval (every 60 seconds)
await client.start_heartbeat(interval=60)
```

**What happens:**
1. Creates an async task
2. Sends heartbeat every `interval` seconds
3. Continues until `stop_heartbeat()` called
4. Errors logged and ignored (non-blocking)

**Why needed:**
- Tells Monitor bot is alive
- Monitor marks bot "stale" if no heartbeat > 120s
- Enables early detection of hung processes

---

### Method: `stop_heartbeat()`

Stop the automatic heartbeat task.

```python
async def stop_heartbeat()
```

**Example:**
```python
await client.stop_heartbeat()
```

**What happens:**
1. Cancels the heartbeat task
2. Cleans up resources
3. Safe to call multiple times

---

## 🔄 Complete Lifecycle Example

```python
import asyncio
import os
import logging
from core.monitor_client import MonitorClient, features_to_dict
from core.feature_manager import FeatureManager

logger = logging.getLogger(__name__)

async def main():
    # ═══════════════════════════════════════════════════════════════════
    # 🚀 Bot Startup
    # ═══════════════════════════════════════════════════════════════════
    
    # Initialize features
    feature_manager = FeatureManager()
    features = features_to_dict(feature_manager)
    
    # Create monitor client
    monitor_client = MonitorClient(
        channel="my_channel",
        pid=os.getpid()
    )
    
    # Register with Monitor
    registered = await monitor_client.register(features=features)
    if registered:
        logger.info("✅ Bot registered with Monitor")
    else:
        logger.warning("⚠️ Monitor unavailable (optional)")
    
    # Start periodic heartbeat
    await monitor_client.start_heartbeat(interval=30)
    logger.info("💓 Heartbeat started")
    
    # ═══════════════════════════════════════════════════════════════════
    # 🎭 Bot Runtime
    # ═══════════════════════════════════════════════════════════════════
    
    try:
        while True:
            # Your bot logic here
            
            # Log LLM usage when needed
            await monitor_client.log_llm_usage(
                model="gpt-4",
                feature="jokes",
                tokens_in=100,
                tokens_out=50,
                latency_ms=1200
            )
            
            await asyncio.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("CTRL+C detected, shutting down...")
    
    finally:
        # ═════════════════════════════════════════════════════════════
        # 🛑 Bot Shutdown
        # ═════════════════════════════════════════════════════════════
        
        # Stop heartbeat
        await monitor_client.stop_heartbeat()
        logger.info("💔 Heartbeat stopped")
        
        # Unregister gracefully
        await monitor_client.unregister()
        logger.info("👋 Unregistered from Monitor")
        
        logger.info("✅ Shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🔧 Configuration

### Socket Path

By default, Monitor listens on `/tmp/kissbot_monitor.sock`. Change via environment variable:

```bash
export KISSBOT_MONITOR_SOCKET=/var/run/kissbot/monitor.sock
```

```python
import os
socket_path = os.environ.get("KISSBOT_MONITOR_SOCKET", "/tmp/kissbot_monitor.sock")
client = MonitorClient(channel="my_channel", pid=os.getpid(), socket_path=socket_path)
```

### Timeout

Adjust timeout for slow networks:

```python
client = MonitorClient(
    channel="my_channel",
    pid=os.getpid(),
    timeout=5.0  # 5 seconds instead of 2
)
```

---

## ⚠️ Error Handling

### Monitor Not Available

MonitorClient is **fail-safe** - bot continues even if Monitor crashes:

```python
# This never raises an exception
result = await client.register()

if not result:
    logger.warning("Monitor unavailable, bot continues without monitoring")
    # Bot continues normally
```

### Graceful Shutdown

Always stop heartbeat and unregister:

```python
try:
    # ... bot code ...
except KeyboardInterrupt:
    pass
finally:
    await client.stop_heartbeat()  # Safe even if never started
    await client.unregister()       # Safe even if not registered
```

---

## 📊 Monitoring Dashboard

Monitor collects metrics accessible via:

1. **Database**: `kissbot_monitor.db`
   ```sql
   SELECT * FROM bot_status;
   SELECT * FROM llm_usage ORDER BY timestamp DESC;
   ```

2. **Logs**: `logs/broadcast/{channel}/instance.log`
   - Bot health
   - CPU/Memory usage
   - Stale warnings

3. **Web Dashboard**: (Future)
   - Real-time bot status
   - LLM usage analytics
   - Resource utilization

---

## 🚀 Advanced Usage

### Custom Message Format (Raw Protocol)

For implementing custom message types, use the underlying protocol:

```python
import json
import asyncio

async def send_custom_metric(channel: str, metric_name: str, value: float):
    """Send custom metric to Monitor"""
    message = {
        "type": "custom_metric",
        "channel": channel,
        "metric_name": metric_name,
        "value": value
    }
    
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_unix_connection("/tmp/kissbot_monitor.sock"),
            timeout=2.0
        )
        
        writer.write((json.dumps(message) + "\n").encode('utf-8'))
        await writer.drain()
        writer.close()
        await writer.wait_closed()
        return True
    except Exception as e:
        logger.debug(f"Failed to send custom metric: {e}")
        return False
```

---

## 📞 Support

- **Protocol Docs**: See `docs/PROTOCOL_MONITOR.md`
- **Source Code**: `core/monitor_client.py`, `core/monitor.py`
- **Tests**: `test_new_monitor.py`
- **Issues**: Report on GitHub

---

**Last Updated:** 2025-12-06  
**Status:** ✅ Production Ready
