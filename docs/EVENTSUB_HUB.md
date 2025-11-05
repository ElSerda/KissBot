# EventSub Hub - Centralized WebSocket Architecture

**Version**: 5.0  
**Author**: KissBot Team  
**Status**: ✅ Production Ready

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Why Hub Mode?](#why-hub-mode)
4. [Components](#components)
5. [IPC Protocol](#ipc-protocol)
6. [Database Schema](#database-schema)
7. [Configuration](#configuration)
8. [Deployment](#deployment)
9. [Operations](#operations)
10. [Troubleshooting](#troubleshooting)
11. [Performance](#performance)
12. [Migration Guide](#migration-guide)

---

## 🎯 Overview

**EventSub Hub** replaces multiple WebSocket connections (1 per bot) with a **single persistent WebSocket** that multiplexes all subscriptions and routes events to bots via IPC.

### Key Benefits

- ✅ **Scale**: Handle hundreds of channels with **1 WebSocket** (Twitch limit: 3 transports per app)
- ✅ **Reliability**: Centralized reconnection logic, no per-bot WebSocket failures
- ✅ **Efficiency**: Single broadcaster token for EventSub, bots keep their own tokens for IRC/Helix
- ✅ **Observability**: Centralized metrics, reconciliation, health monitoring

### Before vs After

**Before (Direct Mode)**:
```
[Twitch EventSub] ←→ [Bot #1 WS]
[Twitch EventSub] ←→ [Bot #2 WS]
[Twitch EventSub] ←→ [Bot #3 WS]
...
[Twitch EventSub] ←→ [Bot #N WS]
```

**After (Hub Mode)**:
```
[Twitch EventSub] ←→ [Hub - 1 WS] ←→ [Bot #1, Bot #2, ..., Bot #N]
                                       (IPC via Unix sockets)
```

---

## 🏗️ Architecture

### Components Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Twitch EventSub                              │
│                   (WebSocket - wss://...)                            │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               │ 1 persistent WebSocket
                               │ (broadcaster token)
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        EventSub Hub                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  WebSocket   │  │ Reconciliation│  │ Health Check │              │
│  │   Manager    │  │     Loop      │  │     Loop     │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                  │                  │                       │
│         └──────────────────┴──────────────────┘                       │
│                            │                                          │
│                     ┌──────▼──────┐                                  │
│                     │ IPC Server  │                                  │
│                     │ (Unix sock) │                                  │
│                     └──────┬──────┘                                  │
└────────────────────────────┼──────────────────────────────────────────┘
                             │
                             │ /tmp/kissbot_hub.sock
                             │
                             ▼
        ┌────────────────────┴────────────────────┐
        │                                          │
        ▼                                          ▼
┌───────────────┐                          ┌───────────────┐
│   Bot #1      │                          │   Bot #N      │
│  (el_serda)   │         ...              │ (other_chan)  │
│               │                          │               │
│ - IRC (VIP)   │                          │ - IRC (VIP)   │
│ - Helix API   │                          │ - Helix API   │
│ - IPC Client  │                          │ - IPC Client  │
└───────────────┘                          └───────────────┘
```

### Data Flow

1. **Bot Startup** → Connects to Hub via IPC (`/tmp/kissbot_hub.sock`)
2. **Hello Message** → Bot sends `HelloMessage(channel_id, channel_name)`
3. **Subscription Request** → Bot sends `SubscribeMessage(channel_id, topic)`
4. **Hub Records** → Adds to `desired_subscriptions` table
5. **Reconciliation** → Hub creates Twitch subscription via HTTP API (rate-limited)
6. **Event Routing** → Twitch sends event → Hub routes to correct bot via IPC
7. **Bot Processing** → Bot receives `EventMessage`, publishes to MessageBus

---

## 💡 Why Hub Mode?

### Problem: Twitch EventSub Limits

- **Max 3 WebSocket transports** per application (client_id)
- **Each bot** with direct mode = 1 WebSocket
- **Result**: Max 3 bots per application ❌

### Solution: Hub Mode

- **1 WebSocket** for entire application
- **Multiplexing**: 100s of subscriptions on 1 WS
- **IPC**: Bots communicate via Unix sockets
- **Result**: ∞ bots (limited by system resources) ✅

### When to Use Hub Mode?

| Scenario | Mode | Reason |
|----------|------|--------|
| **1-3 channels** | Direct | Simple, no IPC overhead |
| **4+ channels** | **Hub** | Required by Twitch limits |
| **Production** | **Hub** | Centralized observability |
| **Development** | Direct or Hub | Both work, Hub preferred for testing |

---

## 🧩 Components

### 1. EventSub Hub (`eventsub_hub.py`)

**Responsibilities**:
- Maintain **1 persistent WebSocket** to Twitch EventSub
- Run **IPC server** on Unix socket (`/tmp/kissbot_hub.sock`)
- **Reconciliation loop**: Diff `desired_subscriptions` vs `active_subscriptions`, create/delete via HTTP API
- **Event routing**: Forward Twitch events to correct bot via IPC
- **Health monitoring**: Auto-reconnect WebSocket if disconnected

**Process**:
```bash
python eventsub_hub.py --config config/config.yaml --db kissbot.db
```

**Logs**: `logs/eventsub_hub.log`, `logs/hub.out`

---

### 2. Hub Client (`twitchapi/transports/hub_eventsub_client.py`)

**Bot-side wrapper** for connecting to Hub via IPC.

**Interface**: Drop-in replacement for `EventSubClient` (same `start()`, `stop()`)

**Usage in bot**:
```python
# main.py --eventsub=hub
hub_client = HubEventSubClient(
    channel_id=user_id,
    channel_name=channel,
    socket_path=hub_socket
)
await hub_client.start()
```

**Features**:
- Connects to Hub via IPC
- Sends `HelloMessage` on connect
- Receives `EventMessage` from Hub
- Translates to `SystemEvent` and publishes to `MessageBus`

---

### 3. Supervisor (`supervisor_v1.py`)

**Multi-process manager** for Hub + Bots.

**Critical**: Hub **MUST start BEFORE bots** (bots need socket to exist).

**Usage**:
```bash
# Start all (Hub + 6 bots)
python supervisor_v1.py --use-db --enable-hub

# Interactive CLI
supervisor> status
supervisor> hub-restart
supervisor> stop el_serda
```

**Features**:
- Starts Hub first, waits 3s for stabilization
- Starts all bots in hub mode (`--eventsub=hub`)
- Health check every 30s (auto-restart crashed processes)
- Interactive CLI for management

---

### 4. Hub Control CLI (`scripts/hub_ctl.py`)

**Administrative tool** for Hub operations.

**Commands**:
```bash
# Show status
python scripts/hub_ctl.py status

# List subscriptions
python scripts/hub_ctl.py subscriptions

# Show metrics
python scripts/hub_ctl.py metrics

# Force reconciliation (TODO)
python scripts/hub_ctl.py resync

# Maintenance mode (TODO)
python scripts/hub_ctl.py drain
```

**Example Output**:
```
================================================================================
EventSub Hub - Status
================================================================================

🌐 WebSocket: 🟢 UP

📊 Subscriptions:
   Desired: 12
   Active:  12
   ✅ Perfect sync!

🔄 Last Reconciliation: 2025-11-05 13:42:38 UTC (30s ago)

📈 Metrics:
   Events Routed:   47
   Reconciliations: 1
   Reconnects:      0

📺 Channels:
   ✅ Channel 44456636: 2/2 subs
   ✅ Channel 135500767: 2/2 subs
   ...
```

---

## 📡 IPC Protocol

**Transport**: Unix sockets (domain socket at `/tmp/kissbot_hub.sock`)  
**Format**: JSON messages, newline-terminated  
**Module**: `core/ipc_protocol.py`

### Message Types

#### Bot → Hub

| Type | Description | Fields |
|------|-------------|--------|
| **hello** | Bot identification | `channel_id`, `channel_name` |
| **subscribe** | Request subscription | `channel_id`, `topic` (e.g., `stream.online`) |
| **unsubscribe** | Cancel subscription | `channel_id`, `topic` |
| **ping** | Keep-alive check | (none) |

#### Hub → Bot

| Type | Description | Fields |
|------|-------------|--------|
| **ack** | Acknowledge request | `ref_type` (what was acked) |
| **error** | Error response | `code`, `message` |
| **event** | Twitch event | `channel_id`, `topic`, `data` (event payload) |
| **pong** | Ping response | (none) |

### Example Flow

```json
Bot → Hub: {"type": "hello", "channel_id": 44456636, "channel_name": "el_serda"}
Hub → Bot: {"type": "ack", "ref_type": "hello"}

Bot → Hub: {"type": "subscribe", "channel_id": 44456636, "topic": "stream.online"}
Hub → Bot: {"type": "ack", "ref_type": "subscribe"}

... (Twitch sends stream.online event) ...

Hub → Bot: {
    "type": "event",
    "channel_id": 44456636,
    "topic": "stream.online",
    "data": {
        "event": {...},
        "subscription": {...}
    }
}
```

---

## 🗄️ Database Schema

### Tables (v5.0)

#### `desired_subscriptions`

**Purpose**: Source of truth for what subscriptions should exist.

| Column | Type | Description |
|--------|------|-------------|
| `channel_id` | TEXT | Twitch channel ID |
| `topic` | TEXT | EventSub topic (e.g., `stream.online`) |
| `version` | TEXT | EventSub version (default: `1`) |
| `transport` | TEXT | Transport type (default: `websocket`) |
| `created_at` | TEXT | ISO8601 timestamp |

**Constraints**:
- `UNIQUE(channel_id, topic)` - Prevents duplicates
- Indexed on `channel_id` and `topic`

#### `active_subscriptions`

**Purpose**: Observed Twitch state (what exists on Twitch).

| Column | Type | Description |
|--------|------|-------------|
| `twitch_sub_id` | TEXT | Twitch subscription UUID |
| `channel_id` | TEXT | Twitch channel ID |
| `topic` | TEXT | EventSub topic |
| `status` | TEXT | Status (`enabled`, `webhook_callback_verification_pending`) |
| `cost` | INTEGER | Cost of subscription |
| `created_at` | TEXT | ISO8601 timestamp |

**Constraints**:
- `UNIQUE(twitch_sub_id)` - Primary identifier
- `UNIQUE(channel_id, topic)` - Prevents duplicates
- Indexed on `status`

#### `hub_state`

**Purpose**: Key-value store for Hub metrics and state.

| Column | Type | Description |
|--------|------|-------------|
| `key` | TEXT | Metric key |
| `value` | TEXT | Metric value (JSON string) |
| `updated_at` | TEXT | ISO8601 timestamp |

**Keys**:
- `ws_state` - WebSocket state (`up`, `down`, `connecting`)
- `last_reconcile_ts` - Last reconciliation timestamp
- `total_events_routed` - Counter
- `total_reconciliations` - Counter
- `total_reconnects` - Counter

---

## ⚙️ Configuration

### `config.yaml`

```yaml
# 🌐 EventSub Hub (v5.0)
eventsub:
  # Hub configuration (single WebSocket for all bots)
  hub:
    enabled: false  # Set to true to use Hub mode
    socket_path: /tmp/kissbot_hub.sock
  
  # Reconciliation settings (Hub only)
  reconcile_interval: 60  # Seconds between reconciliation loops
  req_rate_per_s: 2  # Max subscription creates/deletes per second
  req_jitter_ms: 200  # Jitter between requests (milliseconds)
  
  # WebSocket reconnection settings (Hub only)
  ws_backoff_base: 2  # Backoff base for exponential backoff (seconds)
  ws_backoff_max: 60  # Max backoff for reconnection attempts (seconds)
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `KISSBOT_HUB_SOCKET` | Unix socket path | `/tmp/kissbot_hub.sock` |
| `KISSBOT_DB_PATH` | Database path | `kissbot.db` |
| `KISSBOT_CONFIG` | Config file path | `config/config.yaml` |

---

## 🚀 Deployment

### Step 1: Migrate Database

```bash
# Backup first!
cp kissbot.db kissbot.db.backup_$(date +%Y%m%d_%H%M%S)

# Run migration
python database/migrate_hub_v1.py
```

**Output**:
```
✅ Migration complete: v4.0.1 → v5.0
📊 Statistics:
   Users: 2
   Tokens: 2
   Subscriptions: 0 desired, 0 active
```

### Step 2: Enable Hub in Config

```yaml
# config/config.yaml
eventsub:
  hub:
    enabled: true  # ← Change this
```

### Step 3: Start with Supervisor

```bash
# Start everything (Hub + Bots)
python supervisor_v1.py --use-db --enable-hub

# Or manually:
# 1. Start Hub
python eventsub_hub.py --config config/config.yaml --db kissbot.db &

# 2. Wait 3s for socket creation

# 3. Start bots
python main.py --channel el_serda --use-db --eventsub=hub
```

### Step 4: Verify

```bash
# Check Hub status
python scripts/hub_ctl.py status

# Check subscriptions
python scripts/hub_ctl.py subscriptions

# Check logs
tail -f logs/eventsub_hub.log
```

---

## 🛠️ Operations

### Starting Hub

**Recommended**: Use supervisor
```bash
python supervisor_v1.py --use-db --enable-hub
```

**Manual**:
```bash
nohup python eventsub_hub.py \
    --config config/config.yaml \
    --db kissbot.db \
    --socket /tmp/kissbot_hub.sock \
    > logs/hub.out 2>&1 &
```

### Stopping Hub

**Graceful shutdown**:
```bash
# Find PID
ps aux | grep eventsub_hub

# Send SIGTERM
kill <PID>
```

**Emergency**:
```bash
kill -9 <PID>
rm /tmp/kissbot_hub.sock  # Clean up socket
```

### Restarting Hub

**With supervisor**:
```bash
supervisor> hub-restart
```

**Manual**:
```bash
kill <HUB_PID>
# Wait 2s for cleanup
python eventsub_hub.py ... &
```

### Adding a New Channel

**With database**:
```bash
# 1. Add user + token to DB (via oauth_flow.py)

# 2. Start bot in hub mode
python main.py --channel new_channel --use-db --eventsub=hub

# 3. Hub will auto-create subscriptions within 60s
```

**Verify**:
```bash
python scripts/hub_ctl.py subscriptions | grep new_channel
```

### Removing a Channel

**Stop bot**:
```bash
supervisor> stop channel_name
```

**Hub will**:
- Detect bot disconnect
- Mark subscriptions for deletion (optional)
- Remove from `desired_subscriptions` (manual step currently)

### Force Reconciliation

```bash
# TODO: Implement hub_ctl.py resync
# Workaround: Hub reconciles automatically every 60s
```

---

## 🐛 Troubleshooting

### Hub Won't Start

**Symptom**: `eventsub_hub.py` exits immediately

**Causes**:
1. **Socket already exists**:
   ```bash
   rm /tmp/kissbot_hub.sock
   ```

2. **No broadcaster token**:
   ```
   ❌ No broadcaster token found for el_serda
   ```
   **Fix**: Run `python scripts/oauth_flow.py` to authenticate

3. **Database not migrated**:
   ```
   ❌ no such table: desired_subscriptions
   ```
   **Fix**: Run `python database/migrate_hub_v1.py`

---

### Bot Can't Connect to Hub

**Symptom**: Bot logs show `❌ Failed to connect to Hub`

**Causes**:
1. **Hub not running**:
   ```bash
   ps aux | grep eventsub_hub
   ```

2. **Socket doesn't exist**:
   ```bash
   ls -la /tmp/kissbot_hub.sock
   ```

3. **Wrong socket path**:
   ```bash
   # Bot
   python main.py --eventsub=hub --hub-socket /correct/path
   ```

---

### Subscriptions Not Creating

**Symptom**: `python scripts/hub_ctl.py status` shows "Missing: 10"

**Causes**:
1. **Rate limiting**: Hub creates 2 req/s, wait 5s per subscription
2. **WebSocket down**: Check `ws_state` in `hub_ctl.py status`
3. **Invalid token**: Check logs for 401 errors

**Debug**:
```bash
# Check Hub logs
tail -100 logs/eventsub_hub.log | grep -i "error\|subscription"

# Check active subscriptions on Twitch
curl -H "Authorization: Bearer <TOKEN>" \
     -H "Client-Id: <CLIENT_ID>" \
     https://api.twitch.tv/helix/eventsub/subscriptions
```

---

### WebSocket 4003 Error

**Symptom**: Hub logs show `WebSocket closed with code 4003: Connection unused`

**Cause**: No subscription created within 10s of WebSocket connect

**Fix**: Hub creates first subscription immediately (see `_create_first_subscription()`)

**Verify**:
```bash
# Check logs for "Creating first subscription"
grep "first subscription" logs/eventsub_hub.log
```

---

### Events Not Routing

**Symptom**: Bot doesn't receive events, but Hub shows `ws_state: up`

**Causes**:
1. **Bot disconnected**: Check `ps aux | grep main.py`
2. **Wrong channel_id**: Check IPC logs for bot identification
3. **Hub routing bug**: Check `total_events_routed` metric

**Debug**:
```bash
# Check Hub event routing
tail -f logs/eventsub_hub.log | grep "📤 Routing event"

# Check bot received event
tail -f logs/<channel>.log | grep "EventMessage"
```

---

### High CPU Usage

**Symptom**: Hub process using 100% CPU

**Causes**:
1. **Reconnect loop**: Check `total_reconnects` metric
2. **Invalid token**: Hub retries connection → fix token
3. **Too many bots**: 100+ bots may saturate IPC

**Fix**:
```bash
# Check metrics
python scripts/hub_ctl.py metrics

# Restart Hub (with backoff)
supervisor> hub-restart
```

---

## 📊 Performance

### Tested Configurations

**Real Test** (November 2025):
- **6 channels, 12 subscriptions**
- CPU: <2%
- RAM: 60 MB (Hub process only)
- Latency: <20ms (IPC Unix socket)
- Test Duration: 25 seconds
- Result: ✅ Stable, no errors

### Estimated Scaling (Theoretical)

⚠️ **Warning**: The following are extrapolations, not real measurements.

| Channels | Subscriptions | CPU | RAM | Latency | Notes |
|----------|---------------|-----|-----|---------|-------|
| **1-10** | 2-20 | <5% | 100 MB | <20ms | ✅ Stable (tested) |
| **10-50** | 20-100 | 5-15% | 500 MB | <50ms | 🟡 SQLite OK |
| **50-100** | 100-200 | 15-30% | 1-2 GB | <100ms | 🟠 SQLite locks |
| **100-500** | 200-1000 | 30-60% | 5-15 GB | 100-500ms | 🔴 PostgreSQL needed |

### Bottlenecks

1. **Rate limiting**: 2 req/s for subscription creates → 500 subs = **4min to reconcile**
2. **IPC overhead**: Unix sockets add ~5ms latency per event
3. **SQLite locks**: `desired_subscriptions` writes may block on high concurrency (>50 bots)
4. **Memory per bot**: Each bot process = 30-50 MB → 500 bots = **15-25 GB RAM**
5. **Twitch limits**: 10,000 subscriptions per app (theoretical max ~5000 channels with 2 topics each)

### Optimization Tips

#### For 10-50 Channels (Current Architecture OK)

1. **Keep SQLite**: Current setup is sufficient
2. **Monitor disk I/O**: Enable WAL mode (already enabled in schema)
3. **Adjust rate limit** (if Twitch allows):
   ```yaml
   eventsub:
     req_rate_per_s: 3  # Increase cautiously
   ```

#### For 50-100 Channels (SQLite Edge)

1. **Monitor SQLite locks**: Check `sqlite3_busy_timeout`
2. **Increase reconciliation interval**:
   ```yaml
   eventsub:
     reconcile_interval: 120  # Reduce reconciliation frequency
   ```
3. **Use SSD storage**: Reduce disk I/O latency

#### For 100+ Channels (PostgreSQL Recommended)

1. **Migrate to PostgreSQL**:
   - Better concurrency (no DB-level locks)
   - Connection pooling
   - Better performance under load

2. **Split Bot instances**: Run multiple supervisor instances on different machines

3. **Use Redis for metrics**: Move `hub_state` to Redis for faster updates

4. **Consider multiple Hubs**: Split channels across multiple Hub instances (advanced)

---

## 📚 Migration Guide

### From Direct Mode to Hub Mode

**Steps**:

1. **Prepare**: Ensure all bots are using `--use-db` (tokens from database)

2. **Migrate database**:
   ```bash
   python database/migrate_hub_v1.py
   ```

3. **Stop all bots**:
   ```bash
   supervisor> stop-all  # If using supervisor
   # Or manually kill all main.py processes
   ```

4. **Enable Hub in config**:
   ```yaml
   # config.yaml
   eventsub:
     hub:
       enabled: true
   ```

5. **Start with supervisor**:
   ```bash
   python supervisor_v1.py --use-db --enable-hub
   ```

6. **Verify**:
   ```bash
   python scripts/hub_ctl.py status
   ```

**Rollback**:
```yaml
# config.yaml
eventsub:
  hub:
    enabled: false  # Back to direct mode
```

**Note**: Database schema v5.0 is forward-compatible, no rollback migration needed.

---

## 🎯 Best Practices

### Production Deployment

1. **Always use supervisor**: Auto-restart on crashes
2. **Monitor metrics**: Set up alerts on `ws_state: down`
3. **Log rotation**: Hub logs can grow large (use `logrotate`)
4. **Database backups**: Schedule daily backups of `kissbot.db`
5. **Health checks**: External monitoring (e.g., Nagios, Prometheus)

### Security

1. **Unix socket permissions**:
   ```bash
   chmod 600 /tmp/kissbot_hub.sock
   ```

2. **Firewall**: Block external access to Hub (no network ports exposed)

3. **Token security**: Use encrypted database (`.kissbot.key`)

### Debugging

1. **Enable debug logs**:
   ```python
   # eventsub_hub.py
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **Use hub_ctl.py**: Quick status checks without restarting Hub

3. **Check audit_log**: Database tracks all EventSub operations

---

## 📖 References

- [Twitch EventSub Documentation](https://dev.twitch.tv/docs/eventsub/)
- [EventSub WebSocket Guide](https://dev.twitch.tv/docs/eventsub/handling-websocket-events/)
- [pyTwitchAPI Documentation](https://pytwitchapi.dev/)
- [KissBot Architecture Analysis](../braindev/ARCHITECTURE_ANALYSIS.md)

---

## 📝 Changelog

### v5.0 (2025-11-05)

- ✅ Initial EventSub Hub release
- ✅ IPC protocol (Unix sockets)
- ✅ Reconciliation loop with rate limiting
- ✅ Supervisor integration
- ✅ Hub Control CLI (`hub_ctl.py`)
- ✅ Database schema v5.0

### Planned Features (v5.1)

- ⏸️ `hub_ctl.py resync` - Force reconciliation via IPC
- ⏸️ `hub_ctl.py drain` - Maintenance mode
- ⏸️ Multi-broadcaster support (not hardcoded `el_serda`)
- ⏸️ Prometheus metrics exporter
- ⏸️ EventSub retries (automatic subscription recovery)

---

**🎉 Congratulations! You're now a Hub expert! 🚀**
