# 📡 KissBot Monitor Protocol - Fire-and-Forget JSONL

Version 1.0 | Multi-Language Compatible (Python, Rust, Go, Node.js)

## 🎯 Overview

The KissBot Monitor uses a **fire-and-forget** architecture with **JSONL** (JSON Lines) protocol over Unix domain sockets. Clients send messages and do NOT wait for ACK, enabling non-blocking communication.

```
🤖 Bot Process          📨 Unix Socket           🖥️ Monitor Process
    │                        │                          │
    ├─ register ────────────→ /tmp/kissbot_monitor.sock ─→ queue
    │                        │                          │
    ├─ heartbeat (every 30s)→                           ├─ _event_worker()
    │ (fire-and-forget)      │                          │  processes queue
    │                        │                          ├─ _handle_register()
    ├─ llm_usage ───────────→                           ├─ _handle_heartbeat()
    │                        │                          ├─ _handle_llm_usage()
    │                        │                          │
    └─ unregister ──────────→                           └─ Database
```

### Key Features

✅ **Fire-and-Forget**: Client sends message + drains writer, no read() call  
✅ **Non-Blocking**: Event queue decouples socket I/O from processing  
✅ **JSONL Protocol**: JSON messages delimited by newline (`\n`)  
✅ **Multi-Language**: Simple protocol, easy to implement in any language  
✅ **Fail-Safe**: Bot continues if Monitor unavailable

---

## 📋 Message Format

All messages are **JSON objects** followed by a **newline** character (`\n`).

### Frame Structure

```
{
  "type": "register|heartbeat|unregister|llm_usage",
  "channel": "twitch_channel_name",
  "pid": 12345,
  ...message-specific fields...
}
\n
```

### Message Types

#### 1️⃣ **register** - Bot Startup

Sent once when bot starts, after feature initialization.

```json
{
  "type": "register",
  "channel": "el_serda",
  "pid": 12345,
  "features": {
    "llm": true,
    "translator": false,
    "music": true
  }
}
```

**Fields:**
- `type` (string): Always `"register"`
- `channel` (string): Twitch channel name
- `pid` (int): Process ID of bot
- `features` (dict): Map of feature_name → enabled (boolean)

**Handler:** `_handle_register()`  
**Processing:** Bot registered in memory, written to database

---

#### 2️⃣ **heartbeat** - Periodic Health Check

Sent every 30 seconds (configurable) to indicate bot is alive.

```json
{
  "type": "heartbeat",
  "channel": "el_serda",
  "pid": 12345
}
```

**Fields:**
- `type` (string): Always `"heartbeat"`
- `channel` (string): Twitch channel name
- `pid` (int): Process ID of bot

**Handler:** `_handle_heartbeat()`  
**Processing:** Updates `last_heartbeat` timestamp  
**Timeout:** Monitor marks bot as "stale" if no heartbeat > 120s

---

#### 3️⃣ **unregister** - Bot Shutdown

Sent when bot gracefully shuts down.

```json
{
  "type": "unregister",
  "channel": "el_serda",
  "pid": 12345
}
```

**Fields:**
- `type` (string): Always `"unregister"`
- `channel` (string): Twitch channel name
- `pid` (int): Process ID of bot

**Handler:** `_handle_unregister()`  
**Processing:** Bot removed from memory, status updated to "offline" in database

---

#### 4️⃣ **llm_usage** - Language Model Usage Tracking

Sent after each LLM call (GPT-4, Claude, etc.) for analytics.

```json
{
  "type": "llm_usage",
  "channel": "el_serda",
  "model": "gpt-4",
  "feature": "jokes",
  "tokens_in": 145,
  "tokens_out": 87,
  "latency_ms": 1850
}
```

**Fields:**
- `type` (string): Always `"llm_usage"`
- `channel` (string): Twitch channel name
- `model` (string): Model name (e.g., "gpt-4", "claude-3-opus", "gemini-pro")
- `feature` (string): Feature name using LLM (e.g., "jokes", "translator")
- `tokens_in` (int): Input tokens consumed
- `tokens_out` (int): Output tokens generated
- `latency_ms` (int, optional): Response latency in milliseconds

**Handler:** `_handle_llm_usage()`  
**Processing:** Logged to SQLite `llm_usage` table for analytics

---

## 🔌 Connection Protocol

### Client (Bot) Side

```python
# Pseudo-code for sending a message
socket = connect_unix_socket("/tmp/kissbot_monitor.sock", timeout=2.0)
message = json.dumps({
    "type": "register",
    "channel": "my_channel",
    "pid": os.getpid(),
    "features": {"llm": True}
})

socket.send(message.encode('utf-8') + b'\n')
socket.drain()  # Wait for buffer flush
socket.close()

# ✅ NO socket.recv() - Fire-and-forget!
```

### Server (Monitor) Side

```python
# Monitor listens on Unix socket
server = await asyncio.start_unix_server(
    callback=_handle_client,
    path="/tmp/kissbot_monitor.sock"
)

# _handle_client reads line-by-line
while True:
    line = await reader.readline()  # Blocks until \n
    if not line:
        break
    message = json.loads(line.decode('utf-8'))
    await event_queue.put(message)

# _event_worker processes queue asynchronously
while True:
    message = await event_queue.get()
    dispatch_to_handler(message)
```

---

## 🛠️ Implementation Examples

### Python (Recommended)

```python
from core.monitor_client import MonitorClient
import os

# Initialize client
client = MonitorClient(
    channel="my_channel",
    pid=os.getpid(),
    socket_path="/tmp/kissbot_monitor.sock",
    timeout=2.0
)

# Register on startup
await client.register(features={"llm": True, "translator": False})

# Start automatic heartbeat (every 30s)
await client.start_heartbeat()

# Log LLM usage
await client.log_llm_usage(
    model="gpt-4",
    feature="jokes",
    tokens_in=100,
    tokens_out=50,
    latency_ms=1200
)

# Graceful shutdown
await client.stop_heartbeat()
await client.unregister()
```

### Rust (Future Implementation)

```rust
use tokio::net::UnixStream;
use serde_json::json;

async fn send_heartbeat(channel: &str, pid: u32) -> Result<()> {
    let message = json!({
        "type": "heartbeat",
        "channel": channel,
        "pid": pid
    });
    
    let mut socket = UnixStream::connect("/tmp/kissbot_monitor.sock").await?;
    socket.write_all(format!("{}\n", message).as_bytes()).await?;
    socket.flush().await?;
    // No read() call - fire-and-forget!
    Ok(())
}
```

### Go (Future Implementation)

```go
package main

import (
    "encoding/json"
    "net"
)

func sendHeartbeat(channel string, pid int) error {
    conn, err := net.Dial("unix", "/tmp/kissbot_monitor.sock")
    if err != nil {
        return err
    }
    defer conn.Close()

    msg := map[string]interface{}{
        "type":    "heartbeat",
        "channel": channel,
        "pid":     pid,
    }
    
    data, _ := json.Marshal(msg)
    conn.Write(append(data, '\n'))
    // No read() call
    return nil
}
```

---

## ⚠️ Error Handling

### Client-Side

Clients should **never crash** if Monitor is unavailable:

```python
try:
    result = await client.register(features={...})
    if not result:
        logger.warning("Monitor not available, continuing without monitoring")
except Exception as e:
    logger.debug(f"Monitor connection failed: {e}")
    # Continue - monitor is optional for bot operation
```

### Server-Side

Monitor gracefully handles malformed messages:

- **Invalid JSON**: Logs error, continues
- **Missing fields**: Logs warning, skips message
- **Connection timeout**: Closes connection, continues
- **Slow processing**: Uses event queue, never blocks socket handlers

---

## 🔐 Security Considerations

### Socket Permissions

Monitor socket is world-readable/writable:

```bash
-rwxrwxrwx 1 bot bot ... /tmp/kissbot_monitor.sock
chmod 0o777 /tmp/kissbot_monitor.sock
```

⚠️ **Future:** Implement authentication tokens for multi-user systems.

### Payload Validation

- Max message size: **4KB** (per readline buffer)
- Timeout on slow clients: **30 seconds**
- Channel name: **alphanumeric + underscore only** (validated in DB)
- PID: **must be positive integer**

---

## 📊 Database Schema

Monitor stores data in SQLite at `kissbot_monitor.db`:

### `bot_status` Table

```sql
CREATE TABLE bot_status (
    channel TEXT PRIMARY KEY,
    pid INTEGER NOT NULL,
    status TEXT,  -- 'online', 'offline', 'stale'
    features TEXT,  -- JSON dict
    registered_at TIMESTAMP,
    last_heartbeat TIMESTAMP
);
```

### `llm_usage` Table

```sql
CREATE TABLE llm_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT NOT NULL,
    model TEXT NOT NULL,
    feature TEXT NOT NULL,
    tokens_in INTEGER,
    tokens_out INTEGER,
    latency_ms INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🔄 Event Queue Architecture

The Monitor uses an async event queue to decouple socket I/O from processing:

```
┌──────────────────────┐
│  Socket Handlers     │
│ (_handle_client)     │
└──────────┬───────────┘
           │ put(message)
           ▼
┌──────────────────────┐
│   Event Queue        │  ← Non-blocking
│   (asyncio.Queue)    │
└──────────┬───────────┘
           │ get()
           ▼
┌──────────────────────┐
│   Event Worker       │
│ (_event_worker)      │
└──────────┬───────────┘
           │ dispatch
           ▼
┌──────────────────────┐
│   Message Handlers   │
│  - _handle_register  │
│  - _handle_heartbeat │
│  - _handle_llm_usage │
└──────────┬───────────┘
           │ write
           ▼
     ┌──────────┐
     │ Database │
     └──────────┘
```

**Benefits:**
- ✅ Socket handlers return immediately (non-blocking)
- ✅ Slow DB operations don't block new connections
- ✅ Messages processed in order (FIFO)
- ✅ Monitors can be arbitrarily slow without affecting bots

---

## 📈 Metrics & Monitoring

Monitor exposes metrics every 15 seconds:

```python
for channel, bot in self.bots.items():
    metrics = bot.get_metrics()
    # {
    #   "cpu_percent": 15.2,
    #   "memory_mb": 256.4,
    #   "is_alive": true,
    #   "is_stale": false,
    #   "uptime_seconds": 3600
    # }
```

Metrics logged to `logs/broadcast/{channel}/instance.log`

---

## 🔗 References

- **Monitor Server**: `core/monitor.py` (`KissBotMonitor` class)
- **Client Library**: `core/monitor_client.py` (`MonitorClient` class)
- **Test Suite**: `test_new_monitor.py`

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-06 | Initial fire-and-forget JSONL protocol |

---

**Status:** ✅ **Production Ready** | Last Updated: 2025-12-06
