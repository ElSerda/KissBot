# KissBot V5 - Production Deployment Guide

**Date:** 2025-11-04  
**Complément de:** `MULTI_PROCESS_ARCHITECTURE.md`

---

## 🎯 **Production Checklist**

### **SQLite Configuration (Finitions)**

```python
# database/manager.py - _init_db()
def _init_db(self):
    with sqlite3.connect(self.db_path) as db:
        # CRITICAL: Production pragmas
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=5000")      # 5s anti-lock
        db.execute("PRAGMA synchronous=NORMAL")     # WAL + SSD optimal
        db.execute("PRAGMA temp_store=MEMORY")
        db.execute("PRAGMA mmap_size=30000000000")  # 30GB mmap (if large DB)
```

**Filesystem Setup:**
```bash
# User/group dédié
sudo useradd -r -s /bin/false -d /var/lib/kissbot kissbot

# Directories
sudo mkdir -p /var/lib/kissbot
sudo mkdir -p /run/kissbot
sudo mkdir -p /var/log/kissbot
sudo mkdir -p /var/backups/kissbot

# Permissions
sudo chmod 700 /var/lib/kissbot
sudo chmod 700 /run/kissbot
sudo chmod 755 /var/log/kissbot
sudo chmod 700 /var/backups/kissbot

# Ownership
sudo chown -R kissbot:kissbot /var/lib/kissbot
sudo chown -R kissbot:kissbot /run/kissbot
sudo chown -R kissbot:kissbot /var/log/kissbot
sudo chown -R kissbot:kissbot /var/backups/kissbot

# DB file (600 = owner read/write only)
sudo chmod 600 /var/lib/kissbot/kissbot.db
```

---

## 🔐 **Backup & Recovery**

### **Daily Backup Script**

**File:** `/opt/kissbot/scripts/backup_db.sh`

```bash
#!/bin/bash
# KissBot Database Backup (encrypted with GPG)
set -euo pipefail

BACKUP_DIR="/var/backups/kissbot"
DB_PATH="/var/lib/kissbot/kissbot.db"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/kissbot_$DATE.db"
RETENTION_DAYS=7
GPG_KEY_FILE="/etc/kissbot/backup.key"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# SQLite backup (hot backup with WAL)
echo "📦 [$(date)] Creating backup: $BACKUP_FILE"
sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"

# Verify backup integrity
echo "🔍 [$(date)] Verifying backup..."
if ! sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;" | grep -q "ok"; then
    echo "❌ [$(date)] Backup integrity check FAILED!"
    rm -f "$BACKUP_FILE"
    exit 1
fi

# Get DB stats
USERS=$(sqlite3 "$BACKUP_FILE" "SELECT COUNT(*) FROM users;")
TOKENS=$(sqlite3 "$BACKUP_FILE" "SELECT COUNT(*) FROM oauth_tokens;")
INSTANCES=$(sqlite3 "$BACKUP_FILE" "SELECT COUNT(*) FROM instances WHERE status='running';")
SIZE=$(du -h "$BACKUP_FILE" | cut -f1)

echo "📊 [$(date)] Backup stats: $USERS users, $TOKENS tokens, $INSTANCES running, size: $SIZE"

# Encrypt with GPG (symmetric AES-256)
echo "🔐 [$(date)] Encrypting backup..."
gpg --batch --yes \
    --passphrase-file "$GPG_KEY_FILE" \
    --symmetric \
    --cipher-algo AES256 \
    --compress-algo ZLIB \
    "$BACKUP_FILE"

# Remove unencrypted backup
rm "$BACKUP_FILE"

echo "✅ [$(date)] Encrypted backup: ${BACKUP_FILE}.gpg"

# Cleanup old backups (retention)
echo "🗑️  [$(date)] Cleaning old backups (retention: $RETENTION_DAYS days)..."
find "$BACKUP_DIR" -name "kissbot_*.db.gpg" -mtime +$RETENTION_DAYS -delete

# List current backups
echo "📋 [$(date)] Current backups:"
ls -lh "$BACKUP_DIR" | grep kissbot_

# Optional: Upload to S3/Backblaze
# aws s3 cp "${BACKUP_FILE}.gpg" s3://my-bucket/kissbot-backups/

echo "✅ [$(date)] Backup complete"
```

**Make executable:**
```bash
sudo chmod +x /opt/kissbot/scripts/backup_db.sh
```

---

### **Restore Script**

**File:** `/opt/kissbot/scripts/restore_db.sh`

```bash
#!/bin/bash
# Restore KissBot Database from encrypted backup
set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: $0 <backup_file.db.gpg>"
    echo "Example: $0 /var/backups/kissbot/kissbot_20251104_030000.db.gpg"
    exit 1
fi

BACKUP_FILE="$1"
RESTORE_PATH="/var/lib/kissbot/kissbot_restored.db"
GPG_KEY_FILE="/etc/kissbot/backup.key"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "🔓 [$(date)] Decrypting backup..."
gpg --batch --yes \
    --passphrase-file "$GPG_KEY_FILE" \
    --decrypt \
    "$BACKUP_FILE" > "$RESTORE_PATH"

echo "🔍 [$(date)] Verifying restored database..."
if ! sqlite3 "$RESTORE_PATH" "PRAGMA integrity_check;" | grep -q "ok"; then
    echo "❌ Restored database integrity check FAILED!"
    rm "$RESTORE_PATH"
    exit 1
fi

# Display stats
USERS=$(sqlite3 "$RESTORE_PATH" "SELECT COUNT(*) FROM users;")
TOKENS=$(sqlite3 "$RESTORE_PATH" "SELECT COUNT(*) FROM oauth_tokens;")
echo "📊 [$(date)] Restored: $USERS users, $TOKENS tokens"

echo "✅ [$(date)] Database restored successfully: $RESTORE_PATH"
echo ""
echo "⚠️  To use restored database:"
echo "   1. Stop supervisor: sudo systemctl stop kissbot-supervisor"
echo "   2. Backup current DB: sudo mv /var/lib/kissbot/kissbot.db /var/lib/kissbot/kissbot.db.old"
echo "   3. Replace: sudo mv $RESTORE_PATH /var/lib/kissbot/kissbot.db"
echo "   4. Fix permissions: sudo chmod 600 /var/lib/kissbot/kissbot.db"
echo "   5. Start supervisor: sudo systemctl start kissbot-supervisor"
```

---

### **Automated Restore Test (Weekly)**

**File:** `/opt/kissbot/scripts/test_restore.sh`

```bash
#!/bin/bash
# Weekly automated restore test
set -euo pipefail

BACKUP_DIR="/var/backups/kissbot"
LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/kissbot_*.db.gpg 2>/dev/null | head -1)
TEST_DB="/tmp/kissbot_test_restore_$$.db"
GPG_KEY_FILE="/etc/kissbot/backup.key"
DISCORD_WEBHOOK="${DISCORD_WEBHOOK_URL:-}"

if [ -z "$LATEST_BACKUP" ]; then
    echo "❌ No backups found in $BACKUP_DIR"
    exit 1
fi

echo "🧪 [$(date)] Testing restore of: $LATEST_BACKUP"

# Decrypt
if ! gpg --batch --yes \
    --passphrase-file "$GPG_KEY_FILE" \
    --decrypt \
    "$LATEST_BACKUP" > "$TEST_DB" 2>/dev/null; then
    
    echo "❌ [$(date)] DECRYPTION FAILED!"
    if [ -n "$DISCORD_WEBHOOK" ]; then
        curl -X POST "$DISCORD_WEBHOOK" -H "Content-Type: application/json" \
            -d '{"content":"⚠️ **KissBot Backup Test FAILED**: Decryption error"}'
    fi
    exit 1
fi

# Integrity check
if ! sqlite3 "$TEST_DB" "PRAGMA integrity_check;" | grep -q "ok"; then
    echo "❌ [$(date)] INTEGRITY CHECK FAILED!"
    rm "$TEST_DB"
    if [ -n "$DISCORD_WEBHOOK" ]; then
        curl -X POST "$DISCORD_WEBHOOK" -H "Content-Type: application/json" \
            -d '{"content":"⚠️ **KissBot Backup Test FAILED**: Database corrupted"}'
    fi
    exit 1
fi

# Test queries
USER_COUNT=$(sqlite3 "$TEST_DB" "SELECT COUNT(*) FROM users;" 2>/dev/null || echo "0")
TOKEN_COUNT=$(sqlite3 "$TEST_DB" "SELECT COUNT(*) FROM oauth_tokens;" 2>/dev/null || echo "0")
INSTANCE_COUNT=$(sqlite3 "$TEST_DB" "SELECT COUNT(*) FROM instances;" 2>/dev/null || echo "0")

echo "✅ [$(date)] Restore test successful"
echo "   📊 Users: $USER_COUNT"
echo "   🔐 Tokens: $TOKEN_COUNT"
echo "   🤖 Instances: $INSTANCE_COUNT"

# Cleanup
rm "$TEST_DB"

# Success notification (optional)
if [ -n "$DISCORD_WEBHOOK" ]; then
    curl -X POST "$DISCORD_WEBHOOK" -H "Content-Type: application/json" \
        -d "{\"content\":\"✅ **KissBot Weekly Backup Test**: Success (Users: $USER_COUNT, Tokens: $TOKEN_COUNT)\"}"
fi
```

---

### **Cronjobs**

**File:** `/etc/cron.d/kissbot`

```cron
# KissBot Backup & Maintenance

# Daily backup at 3 AM
0 3 * * * kissbot /opt/kissbot/scripts/backup_db.sh >> /var/log/kissbot/backup.log 2>&1

# Weekly restore test (Sunday 4 AM)
0 4 * * 0 kissbot /opt/kissbot/scripts/test_restore.sh >> /var/log/kissbot/restore-test.log 2>&1

# Monthly log rotation (1st of month, 5 AM)
0 5 1 * * kissbot find /var/log/kissbot -name "*.log" -mtime +30 -delete
```

---

## 🚀 **Systemd Services**

### **Supervisor Service**

**File:** `/etc/systemd/system/kissbot-supervisor.service`

```ini
[Unit]
Description=KissBot Supervisor (Multi-Process Manager)
Documentation=https://github.com/ElSerda/KissBot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=kissbot
Group=kissbot
WorkingDirectory=/opt/kissbot

# Resource limits
MemoryHigh=500M
MemoryMax=1G
CPUWeight=100

# Environment
EnvironmentFile=/etc/kissbot/environment
Environment="PYTHONUNBUFFERED=1"

# Start supervisor
ExecStart=/opt/kissbot/venv/bin/python3 supervisor.py

# Graceful shutdown
ExecStop=/bin/kill -TERM $MAINPID
TimeoutStopSec=30

# Restart policy
Restart=always
RestartSec=10
StartLimitInterval=5min
StartLimitBurst=5

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=kissbot-supervisor

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/kissbot /run/kissbot /var/log/kissbot /opt/kissbot/pids /opt/kissbot/logs

[Install]
WantedBy=multi-user.target
```

---

### **Per-Instance Template Service**

**File:** `/etc/systemd/system/kissbot@.service`

```ini
[Unit]
Description=KissBot Instance for channel %i
Documentation=https://github.com/ElSerda/KissBot
After=network-online.target kissbot-supervisor.service
PartOf=kissbot-supervisor.service

[Service]
Type=simple
User=kissbot
Group=kissbot
WorkingDirectory=/opt/kissbot

# Resource limits (per bot instance)
MemoryHigh=200M
MemoryMax=350M
MemorySwapMax=0
CPUWeight=100

# Environment
EnvironmentFile=/etc/kissbot/environment
Environment="PYTHONUNBUFFERED=1"

# Start bot instance
ExecStart=/opt/kissbot/venv/bin/python3 main.py --channel %i

# Restart policy
Restart=always
RestartSec=10
StartLimitInterval=5min
StartLimitBurst=5

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=kissbot-%i

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/kissbot /run/kissbot /var/log/kissbot

[Install]
WantedBy=multi-user.target
```

---

### **Environment File**

**File:** `/etc/kissbot/environment`

```bash
# KissBot Environment Variables
KISSBOT_SECRET_KEY=<generated_fernet_key>
TWITCH_CLIENT_ID=<your_client_id>
TWITCH_CLIENT_SECRET=<your_client_secret>
DISCORD_WEBHOOK_URL=<webhook_for_alerts>
```

**Permissions:**
```bash
sudo chmod 600 /etc/kissbot/environment
sudo chown kissbot:kissbot /etc/kissbot/environment
```

---

### **Service Management**

```bash
# Enable services
sudo systemctl enable kissbot-supervisor.service

# Start supervisor (will start all bots from DB)
sudo systemctl start kissbot-supervisor

# Check status
sudo systemctl status kissbot-supervisor

# View logs
sudo journalctl -u kissbot-supervisor -f

# Restart supervisor (graceful, all bots stopped then restarted)
sudo systemctl restart kissbot-supervisor

# Manual bot control (if needed, normally supervisor manages these)
sudo systemctl start kissbot@el_serda
sudo systemctl stop kissbot@el_serda
sudo systemctl restart kissbot@el_serda
sudo journalctl -u kissbot@el_serda -f
```

---

## 🔄 **Token Refresh (Proactive Strategy)**

### **Supervisor Refresh Logic**

```python
# supervisor.py - Enhanced refresh with deduplication

class BotSupervisor:
    def __init__(self):
        # ...existing init...
        
        # Refresh deduplication (one inflight per user)
        self._refresh_locks = {}  # user_id -> asyncio.Lock
        self._refresh_attempts = {}  # user_id -> int (failure count)
    
    async def _refresh_token(self, user_id: str) -> bool:
        """
        Refresh token with:
        - Deduplication (one refresh inflight per user)
        - Retry backoff (1s, 5s, 15s)
        - Alert after 3 failures
        """
        # Deduplication lock
        if user_id not in self._refresh_locks:
            self._refresh_locks[user_id] = asyncio.Lock()
        
        # Check if already refreshing
        if self._refresh_locks[user_id].locked():
            logger.debug(f"🔄 Refresh already inflight for {user_id}, skipping")
            return False
        
        async with self._refresh_locks[user_id]:
            token_data = self.db.get_token(user_id)
            if not token_data:
                return False
            
            # Retry logic with backoff
            retry_delays = [1, 5, 15]  # seconds
            
            for attempt in range(3):
                try:
                    # Call Twitch OAuth refresh endpoint
                    response = await self._call_twitch_refresh(
                        token_data['refresh_token']
                    )
                    
                    if response['success']:
                        # Store new tokens
                        self.db.store_token(
                            user_id,
                            response['access_token'],
                            response.get('refresh_token', token_data['refresh_token']),
                            response['expires_at'],
                            token_data['scopes']
                        )
                        
                        # Reset failure counter
                        self._refresh_attempts[user_id] = 0
                        
                        logger.info(f"✅ Token refreshed: {user_id}")
                        return True
                    
                except Exception as e:
                    logger.error(f"❌ Refresh attempt {attempt+1}/3 failed: {e}")
                    
                    if attempt < 2:  # Not last attempt
                        await asyncio.sleep(retry_delays[attempt])
            
            # All attempts failed
            self._refresh_attempts[user_id] = self._refresh_attempts.get(user_id, 0) + 1
            
            if self._refresh_attempts[user_id] >= 3:
                logger.error(f"💀 Token refresh failed 3 times: {user_id}")
                self.db.set_instance_status(user_id, 'needs_reauth', increment_errors=True)
                
                # Send alert
                await self._send_alert(
                    f"⚠️ KissBot: Token refresh failed for {user_id} (3 attempts). User needs to re-authorize."
                )
                
                # Stop bot
                self.stop_bot(user_id)
                
                return False
            
            return False
```

---

## 📊 **EventSub Pool (Scalability)**

### **Pool Manager Concept**

```python
# eventsub/pool_manager.py (à créer)

class EventSubPool:
    """
    Manage multiple EventSub WebSockets with smart sharding.
    
    Limits (per WebSocket):
        - 300 subscriptions max
        - 10,000 cost max
        - Keep 10-20% headroom
    """
    
    def __init__(self):
        self.websockets = []  # List of EventSubClient instances
        self.max_subs_per_ws = 300
        self.max_cost_per_ws = 10000
        self.headroom_percent = 0.15  # 15% headroom
    
    def get_available_websocket(self, required_cost: int = 1) -> EventSubClient:
        """
        Get WebSocket with available capacity.
        Creates new WebSocket if all are at capacity.
        """
        for ws in self.websockets:
            if self._has_capacity(ws, required_cost):
                return ws
        
        # No capacity, create new WebSocket
        new_ws = self._create_new_websocket()
        self.websockets.append(new_ws)
        return new_ws
    
    def _has_capacity(self, ws: EventSubClient, required_cost: int) -> bool:
        """Check if WebSocket has headroom"""
        current_subs = ws.get_subscription_count()
        current_cost = ws.get_total_cost()
        
        # Check headroom
        subs_limit = int(self.max_subs_per_ws * (1 - self.headroom_percent))
        cost_limit = int(self.max_cost_per_ws * (1 - self.headroom_percent))
        
        return (
            current_subs < subs_limit and
            current_cost + required_cost < cost_limit
        )
    
    def get_metrics(self) -> dict:
        """Expose metrics for monitoring"""
        return {
            'websocket_count': len(self.websockets),
            'total_subscriptions': sum(ws.get_subscription_count() for ws in self.websockets),
            'total_cost': sum(ws.get_total_cost() for ws in self.websockets),
            'per_websocket': [
                {
                    'id': i,
                    'subscriptions': ws.get_subscription_count(),
                    'cost': ws.get_total_cost(),
                    'headroom_subs': self.max_subs_per_ws - ws.get_subscription_count(),
                    'headroom_cost': self.max_cost_per_ws - ws.get_total_cost()
                }
                for i, ws in enumerate(self.websockets)
            ]
        }
```

**Prometheus Metrics:**
```python
# Expose ces métriques pour Grafana
kissbot_eventsub_websockets_total        # Nombre de WebSockets actifs
kissbot_eventsub_subscriptions_total     # Total subs across all WebSockets
kissbot_eventsub_cost_total              # Total cost across all WebSockets
kissbot_eventsub_headroom_percent{ws_id} # Headroom % par WebSocket
kissbot_eventsub_reconnects_per_min      # Taux de reconnect (santé)
```

---

## 🔍 **Monitoring (Minimum Viable)**

### **Prometheus Metrics**

```python
# monitoring/metrics.py (à créer)

from prometheus_client import Gauge, Counter, Histogram

# Instance metrics
instance_rss = Gauge('kissbot_instance_rss_bytes', 'Memory usage (RSS)', ['user_id'])
instance_cpu = Gauge('kissbot_instance_cpu_percent', 'CPU usage', ['user_id'])

# Message metrics
msgs_out_rate = Gauge('kissbot_msgs_out_per_min', 'Outbound messages rate', ['user_id'])
say_latency = Histogram('kissbot_say_latency_ms', 'IRC send latency', ['user_id'])

# Token refresh
refresh_fail = Counter('kissbot_refresh_fail_total', 'Token refresh failures', ['user_id'])

# EventSub
eventsub_events_rate = Gauge('kissbot_eventsub_events_per_min', 'EventSub events rate', ['user_id'])
```

**Grafana Dashboard Simple:**
- Panel 1: Instance count (gauge)
- Panel 2: Memory usage per bot (graph)
- Panel 3: Messages/min per bot (graph)
- Panel 4: Token refresh failures (alert panel)
- Panel 5: EventSub events/min (graph)

---

## 🛡️ **Security Hardening**

### **Checklist**

- [x] Database file: `600` permissions
- [x] Sockets: `/run/kissbot/` with `700` permissions
- [x] Tokens: Encrypted at rest (Fernet AES-128)
- [x] Tokens: In-memory only in bot processes (never written to disk)
- [x] Environment: `/etc/kissbot/environment` with `600` permissions
- [x] Logs: Never log tokens (mask with `***`)
- [x] Systemd: `NoNewPrivileges=true`, `ProtectSystem=strict`
- [x] Backups: GPG encrypted with separate key file
- [x] Monitoring: WireGuard-only access (no public ports)
- [x] User: Dedicated `kissbot` user (no login shell)

---

## 📈 **Scalability Path**

### **Current (Single VPS)**
- ✅ 1 Supervisor
- ✅ N bot processes (1 per channel)
- ✅ SQLite local (WAL mode)
- ✅ Unix sockets IPC
- **Capacity**: ~50-100 channels per VPS

### **Future (Multi-VPS)**
- Migrate SQLite → PostgreSQL (centralized)
- Supervisor per VPS (register with coordinator)
- Redis pub/sub for cross-VPS communication
- Load balancer for auth server
- **Capacity**: 500-1000+ channels

---

**Date:** 2025-11-04  
**Status:** Production-Ready Specifications  
**Next:** Implementation Phase 0 (Database Layer)
