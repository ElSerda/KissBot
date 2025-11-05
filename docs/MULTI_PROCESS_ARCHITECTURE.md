# KissBot V5 - Multi-Process Architecture + SQLite

**Date:** 2025-11-04  
**Status:** Planning Phase  
**Goal:** Architecture multi-process isolée avec gestion sécurisée des tokens OAuth

---

## 🎯 **Vision Globale**

### **Architecture Actuelle (V4)**
```
1 KissBot = 1 channel = 1 config.yaml = 1 process Python
❌ Si crash → tout crash
❌ Tokens en clair dans config.yaml
❌ Pas de gestion centralisée
```

### **Architecture Cible (V5)**
```
Supervisor (process manager)
    ├──> [Process 1] KissBot → #channel1 (token en mémoire)
    ├──> [Process 2] KissBot → #channel2 (token en mémoire)
    └──> [Process N] KissBot → #channelN (token en mémoire)
    
SQLite Database (WAL mode, tokens chiffrés)
    ├──> users
    ├──> oauth_tokens (AES-GCM encrypted)
    ├──> instances (status, heartbeat, PID)
    └──> audit_log (compliance, GDPR)

Auth Server (OAuth Flow)
    └──> Onboarding automatique → DB → Supervisor start bot
```

**Avantages:**
- ✅ **Isolation**: 1 crash = 1 bot affecté
- ✅ **Sécurité**: Tokens chiffrés au repos, en mémoire dans les process
- ✅ **Scalabilité**: N bots sur 1 machine, distribuer sur N machines plus tard
- ✅ **Ops**: Restart individuel, logs séparés, monitoring par channel
- ✅ **Compliance**: GDPR-ready, audit logs, révocation

---

## 🎯 **Production Checklist (Finitions)**

### **SQLite Configuration**
- [x] `busy_timeout=5000` (5s anti-lock)
- [x] `synchronous=NORMAL` (WAL + SSD optimal)
- [x] `journal_mode=WAL` (concurrent reads/writes)
- [ ] File permissions: `600` (owner-only)
- [ ] Owner dédié: `kissbot:kissbot` user/group
- [ ] DB path: `/var/lib/kissbot/kissbot.db` (not /tmp!)

### **IPC Security**
- [x] Unix sockets in `/run/kissbot/` (not /tmp)
- [x] Socket permissions: `600` (owner-only)
- [ ] Close socket immediately after token transfer
- [ ] Heartbeat bot→supervisor: 30-60s interval
- [ ] Timeout detection: 2x heartbeat interval

### **Token Refresh Strategy**
- [x] Proactive refresh at T-60s (before expiry)
- [ ] Deduplication: ONE refresh inflight per user (lock)
- [ ] Retry backoff: 1s, 5s, 15s
- [ ] After 3 failures: `status='needs_reauth'` + alert
- [ ] Webhook notification (Discord/Slack)

### **Systemd Integration (Production)**
- [ ] Template: `kissbot@<user>.service`
- [ ] Resource limits:
  - `MemoryHigh=200M` (soft limit)
  - `MemoryMax=350M` (hard limit, OOM kill)
  - `MemorySwapMax=0` (no swap)
  - `CPUWeight=100` (default scheduling)
- [ ] Restart policy: `Restart=always` (except clean exit)
- [ ] Logs: `StandardOutput=journal` (systemd journal)

### **Backup & Recovery**
- [ ] Daily backup: `sqlite3 .backup` + GPG encryption
- [ ] Retention: 7 days rolling
- [ ] Weekly restore test (automated)
- [ ] Offsite backup (S3/Backblaze/rsync)
- [ ] Recovery time objective: < 5 min

### **EventSub Pool (Scalability)**
- [ ] Central pool manager (shared across bots)
- [ ] Limits: 300 subs/WebSocket, 10k cost/WebSocket
- [ ] Headroom: Keep 10-20% free per WebSocket
- [ ] Metrics:
  - `eventsub_subs_per_ws` (gauge)
  - `eventsub_cost_per_ws` (gauge)
  - `eventsub_ws_count` (gauge)
  - `eventsub_reconnect_per_min` (rate)
- [ ] Auto-sharding: New WebSocket when headroom < threshold
- [ ] Health checks: Ping interval, reconnect on stale

### **Monitoring (Minimum Viable)**
- [ ] 5 core metrics (Prometheus):
  - `kissbot_instance_rss_bytes{user_id}`
  - `kissbot_instance_cpu_percent{user_id}`
  - `kissbot_msgs_out_per_min{user_id}`
  - `kissbot_say_latency_ms_p95{user_id}`
  - `kissbot_refresh_fail_total{user_id}`
- [ ] Grafana dashboard (simple)
- [ ] WireGuard-only access (no public exposure)

---

## 📋 **TODO - Phase par Phase**

### **Phase 0 : Database Layer (PRIORITÉ #1)**

#### **0.1 - SQLite Setup & Schema**

**Fichier:** `database/schema.sql`

```sql
-- ============================================================================
-- KissBot V5 Database Schema
-- SQLite 3.x with WAL mode
-- ============================================================================

-- Configuration SQLite (à exécuter au PRAGMA init)
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;        -- 5s timeout pour éviter "database is locked"
PRAGMA synchronous=NORMAL;       -- WAL + SSD = bon compromis
PRAGMA temp_store=MEMORY;

-- ============================================================================
-- TABLE: users
-- ============================================================================
CREATE TABLE users (
    user_id TEXT PRIMARY KEY,          -- Twitch user ID
    login TEXT NOT NULL UNIQUE,        -- Twitch login (lowercase)
    display_name TEXT,                 -- Display name
    plan_tier TEXT DEFAULT 'free',     -- 'free', 'pro' (future monetization)
    created_at INTEGER NOT NULL,       -- Unix timestamp
    updated_at INTEGER NOT NULL        -- Unix timestamp
);

CREATE INDEX idx_users_login ON users(login);

-- ============================================================================
-- TABLE: oauth_tokens
-- Tokens chiffrés avec Fernet (AES-128-CBC + HMAC)
-- ============================================================================
CREATE TABLE oauth_tokens (
    user_id TEXT PRIMARY KEY,
    access_token_enc BLOB NOT NULL,    -- Encrypted access token
    refresh_token_enc BLOB NOT NULL,   -- Encrypted refresh token
    expires_at INTEGER NOT NULL,       -- Unix timestamp
    scopes TEXT NOT NULL,              -- JSON array ["chat:read", ...]
    key_version INTEGER DEFAULT 1,     -- For key rotation
    updated_at INTEGER NOT NULL,       -- Last token update
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_tokens_expires ON oauth_tokens(expires_at);

-- ============================================================================
-- TABLE: instances
-- Track bot processes (1 process = 1 user/channel)
-- ============================================================================
CREATE TABLE instances (
    user_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,              -- 'running', 'stopped', 'crashed', 'needs_reauth'
    worker_id TEXT,                    -- PID or hostname
    last_heartbeat INTEGER,            -- Last heartbeat timestamp
    error_count INTEGER DEFAULT 0,     -- Consecutive errors
    started_at INTEGER,
    updated_at INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_instances_status ON instances(status);
CREATE INDEX idx_instances_worker ON instances(worker_id);
CREATE INDEX idx_instances_heartbeat ON instances(last_heartbeat);

-- ============================================================================
-- TABLE: audit_log
-- Security & compliance (GDPR-ready)
-- ============================================================================
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,                      -- NULL si user supprimé (GDPR)
    action TEXT NOT NULL,              -- 'connect', 'disconnect', 'refresh', 'error', 'revoke', 'deleted'
    details TEXT,                      -- JSON compact (PAS de PII, PAS de tokens)
    ip_address TEXT,                   -- Optionnel
    timestamp INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE INDEX idx_audit_user_time ON audit_log(user_id, timestamp);
CREATE INDEX idx_audit_action ON audit_log(action);

-- ============================================================================
-- TABLE: metrics (optionnel - peut être en Prometheus)
-- ============================================================================
CREATE TABLE metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    metric_name TEXT NOT NULL,         -- 'msgs_out', 'cpu_percent', 'rss_mb'
    metric_value REAL NOT NULL,
    timestamp INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_metrics_name_time ON metrics(metric_name, timestamp);
```

**Permissions fichier DB:**
```bash
# Créer dossier dédié (PAS /tmp)
mkdir -p /var/lib/kissbot
chmod 700 /var/lib/kissbot

# Créer user/group dédié
sudo useradd -r -s /bin/false -d /var/lib/kissbot kissbot

# Ownership
sudo chown -R kissbot:kissbot /var/lib/kissbot

# DB file permissions (owner-only read/write)
chmod 600 /var/lib/kissbot/kissbot.db

# Socket directory
mkdir -p /run/kissbot
chmod 700 /run/kissbot
chown kissbot:kissbot /run/kissbot
```

---

#### **0.2 - Encryption Layer**

**Fichier:** `database/crypto.py`

```python
#!/usr/bin/env python3
"""
Token Encryption Layer
- Uses Fernet (AES-128-CBC + HMAC-SHA256)
- Key from environment variable (KISSBOT_SECRET_KEY)
- Supports key rotation (key_version)
"""

import os
import logging
from cryptography.fernet import Fernet, MultiFernet
from typing import Dict

logger = logging.getLogger(__name__)


class TokenEncryptor:
    """
    Chiffre/déchiffre les tokens OAuth avec rotation de clés.
    
    Environment variables:
        KISSBOT_SECRET_KEY: Primary encryption key (required)
        KISSBOT_SECRET_KEY_V1: Old key for rotation (optional)
    """
    
    def __init__(self):
        # Clé primaire (version courante)
        primary_key = os.environ.get('KISSBOT_SECRET_KEY')
        if not primary_key:
            raise ValueError("❌ KISSBOT_SECRET_KEY not set in environment!")
        
        self.ciphers = [Fernet(primary_key.encode())]
        self.current_version = 1
        
        # Clés anciennes (pour rotation)
        old_key = os.environ.get('KISSBOT_SECRET_KEY_V1')
        if old_key:
            self.ciphers.append(Fernet(old_key.encode()))
            logger.info("✅ Key rotation enabled (v1 available)")
        
        # MultiFernet essaie les clés dans l'ordre
        self.multi_cipher = MultiFernet(self.ciphers)
        
        logger.info(f"🔐 TokenEncryptor initialized (version={self.current_version})")
    
    def encrypt(self, plaintext: str) -> bytes:
        """
        Chiffre un token.
        
        Args:
            plaintext: Token en clair (access_token ou refresh_token)
        
        Returns:
            bytes: Token chiffré
        """
        if not plaintext:
            raise ValueError("Cannot encrypt empty token")
        
        return self.ciphers[0].encrypt(plaintext.encode())
    
    def decrypt(self, ciphertext: bytes) -> str:
        """
        Déchiffre un token (essaie toutes les clés disponibles).
        
        Args:
            ciphertext: Token chiffré
        
        Returns:
            str: Token déchiffré
        """
        if not ciphertext:
            raise ValueError("Cannot decrypt empty ciphertext")
        
        try:
            return self.multi_cipher.decrypt(ciphertext).decode()
        except Exception as e:
            logger.error(f"❌ Decryption failed: {e}")
            raise
    
    def rotate(self, old_ciphertext: bytes) -> bytes:
        """
        Re-chiffre avec la clé courante (pour migration).
        
        Args:
            old_ciphertext: Token chiffré avec ancienne clé
        
        Returns:
            bytes: Token re-chiffré avec clé courante
        """
        plaintext = self.decrypt(old_ciphertext)
        return self.encrypt(plaintext)


def generate_key() -> str:
    """
    Génère une nouvelle clé Fernet.
    
    Usage:
        python3 -c "from database.crypto import generate_key; print(generate_key())"
    """
    return Fernet.generate_key().decode()


# ============================================================================
# Masquage de tokens dans les logs (sécurité)
# ============================================================================

def mask_token(token: str, show_chars: int = 4) -> str:
    """
    Masque un token pour les logs.
    
    Examples:
        "eyJhbGciOiJSUzI1..." → "eyJh...***"
        "oauth:abc123def456" → "oaut...***"
    """
    if not token or len(token) < show_chars:
        return "***"
    
    # Détection de JWT (commence par eyJ)
    if token.startswith("eyJ"):
        return f"{token[:4]}...***"
    
    # Détection de token long (> 20 chars)
    if len(token) > 20:
        return f"{token[:show_chars]}...***"
    
    return "***"
```

**Script de génération de clé:**

**Fichier:** `scripts/generate_key.py`

```python
#!/usr/bin/env python3
"""Generate encryption key for KissBot tokens"""

from cryptography.fernet import Fernet

key = Fernet.generate_key()
print("\n🔐 Add this to your .env file:")
print(f"KISSBOT_SECRET_KEY={key.decode()}\n")
print("⚠️  KEEP THIS SECRET! Never commit to Git!")
```

**Usage:**
```bash
python3 scripts/generate_key.py >> .env
```

---

#### **0.3 - Database Manager**

**Fichier:** `database/manager.py`

```python
#!/usr/bin/env python3
"""
Database Manager - Abstraction layer for SQLite operations
Handles users, tokens, instances, audit logs
"""

import sqlite3
import json
import time
import logging
from typing import Optional, Dict, List
from pathlib import Path
from .crypto import TokenEncryptor, mask_token

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Gestion centralisée de la base SQLite.
    Thread-safe (chaque méthode ouvre/ferme sa connexion).
    """
    
    def __init__(self, db_path: str, encryptor: TokenEncryptor):
        self.db_path = db_path
        self.encryptor = encryptor
        self._init_db()
        logger.info(f"✅ DatabaseManager initialized (db={db_path})")
    
    def _init_db(self):
        """Initialize database with schema if not exists"""
        schema_path = Path(__file__).parent / "schema.sql"
        
        with sqlite3.connect(self.db_path) as db:
            # Configure SQLite
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA busy_timeout=5000")
            db.execute("PRAGMA synchronous=NORMAL")
            db.execute("PRAGMA temp_store=MEMORY")
            
            # Load schema if tables don't exist
            cursor = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
            )
            if not cursor.fetchone():
                logger.info("📋 Creating database schema...")
                with open(schema_path) as f:
                    db.executescript(f.read())
                logger.info("✅ Schema created")
    
    # ========================================================================
    # USER MANAGEMENT
    # ========================================================================
    
    def create_user(self, user_id: str, login: str, display_name: str) -> bool:
        """Create a new user"""
        try:
            with sqlite3.connect(self.db_path) as db:
                now = int(time.time())
                db.execute("""
                    INSERT INTO users (user_id, login, display_name, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, login.lower(), display_name, now, now))
                
                self._audit_log(db, user_id, 'user_created', {'login': login})
                logger.info(f"✅ User created: {login} (ID: {user_id})")
                return True
        except sqlite3.IntegrityError:
            logger.warning(f"⚠️  User already exists: {login}")
            return False
    
    def get_user(self, user_id: str) -> Optional[Dict]:
        """Get user info"""
        with sqlite3.connect(self.db_path) as db:
            cursor = db.execute("""
                SELECT user_id, login, display_name, plan_tier, created_at, updated_at
                FROM users WHERE user_id = ?
            """, (user_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return {
                'user_id': row[0],
                'login': row[1],
                'display_name': row[2],
                'plan_tier': row[3],
                'created_at': row[4],
                'updated_at': row[5]
            }
    
    def get_all_users(self) -> List[str]:
        """Get all user IDs"""
        with sqlite3.connect(self.db_path) as db:
            cursor = db.execute("SELECT user_id FROM users")
            return [row[0] for row in cursor.fetchall()]
    
    def delete_user(self, user_id: str):
        """
        Delete user (GDPR compliance).
        Cascade deletes tokens, instances.
        Anonymizes audit logs.
        """
        with sqlite3.connect(self.db_path) as db:
            # Audit before delete
            self._audit_log(db, user_id, 'user_deleted', {})
            
            # Delete user (cascade to tokens, instances)
            db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            
            # Anonymize audit logs
            db.execute("""
                UPDATE audit_log 
                SET user_id = NULL, details = json_set(details, '$.anonymized', true)
                WHERE user_id = ?
            """, (user_id,))
            
            logger.info(f"🗑️  User deleted: {user_id}")
    
    # ========================================================================
    # TOKEN MANAGEMENT
    # ========================================================================
    
    def store_token(
        self,
        user_id: str,
        access_token: str,
        refresh_token: str,
        expires_at: int,
        scopes: List[str]
    ):
        """
        Store encrypted OAuth token.
        
        Args:
            user_id: Twitch user ID
            access_token: Access token (will be encrypted)
            refresh_token: Refresh token (will be encrypted)
            expires_at: Unix timestamp
            scopes: List of OAuth scopes
        """
        # Encrypt tokens
        access_enc = self.encryptor.encrypt(access_token)
        refresh_enc = self.encryptor.encrypt(refresh_token)
        
        with sqlite3.connect(self.db_path) as db:
            db.execute("""
                INSERT OR REPLACE INTO oauth_tokens 
                (user_id, access_token_enc, refresh_token_enc, expires_at, scopes, key_version, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                access_enc,
                refresh_enc,
                expires_at,
                json.dumps(scopes),
                self.encryptor.current_version,
                int(time.time())
            ))
            
            # Audit (NO TOKEN LOGGING!)
            self._audit_log(db, user_id, 'token_stored', {
                'expires_at': expires_at,
                'scopes_count': len(scopes)
            })
            
            logger.info(f"🔐 Token stored: {user_id} (expires: {expires_at})")
    
    def get_token(self, user_id: str) -> Optional[Dict]:
        """
        Get and decrypt token.
        
        Returns:
            dict: {'access_token', 'refresh_token', 'expires_at', 'scopes'}
        """
        with sqlite3.connect(self.db_path) as db:
            cursor = db.execute("""
                SELECT access_token_enc, refresh_token_enc, expires_at, scopes
                FROM oauth_tokens WHERE user_id = ?
            """, (user_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            try:
                return {
                    'access_token': self.encryptor.decrypt(row[0]),
                    'refresh_token': self.encryptor.decrypt(row[1]),
                    'expires_at': row[2],
                    'scopes': json.loads(row[3])
                }
            except Exception as e:
                logger.error(f"❌ Token decryption failed for {user_id}: {e}")
                return None
    
    def needs_refresh(self, user_id: str, threshold_seconds: int = 60) -> bool:
        """Check if token expires soon (< threshold)"""
        with sqlite3.connect(self.db_path) as db:
            cursor = db.execute("""
                SELECT expires_at FROM oauth_tokens WHERE user_id = ?
            """, (user_id,))
            
            row = cursor.fetchone()
            if not row:
                return True
            
            return row[0] - time.time() < threshold_seconds
    
    def revoke_token(self, user_id: str):
        """Delete token (called after Twitch revocation)"""
        with sqlite3.connect(self.db_path) as db:
            db.execute("DELETE FROM oauth_tokens WHERE user_id = ?", (user_id,))
            self._audit_log(db, user_id, 'token_revoked', {})
            logger.info(f"🔓 Token revoked: {user_id}")
    
    # ========================================================================
    # INSTANCE MANAGEMENT
    # ========================================================================
    
    def create_instance(self, user_id: str, worker_id: str):
        """Create instance entry (bot starting)"""
        with sqlite3.connect(self.db_path) as db:
            now = int(time.time())
            db.execute("""
                INSERT OR REPLACE INTO instances 
                (user_id, status, worker_id, last_heartbeat, error_count, started_at, updated_at)
                VALUES (?, 'running', ?, ?, 0, ?, ?)
            """, (user_id, worker_id, now, now, now))
            
            self._audit_log(db, user_id, 'instance_started', {'worker_id': worker_id})
    
    def update_heartbeat(self, user_id: str):
        """Update instance heartbeat (bot is alive)"""
        with sqlite3.connect(self.db_path) as db:
            now = int(time.time())
            db.execute("""
                UPDATE instances 
                SET last_heartbeat = ?, updated_at = ?
                WHERE user_id = ?
            """, (now, now, user_id))
    
    def set_instance_status(self, user_id: str, status: str, increment_errors: bool = False):
        """Update instance status"""
        with sqlite3.connect(self.db_path) as db:
            if increment_errors:
                db.execute("""
                    UPDATE instances 
                    SET status = ?, error_count = error_count + 1, updated_at = ?
                    WHERE user_id = ?
                """, (status, int(time.time()), user_id))
            else:
                db.execute("""
                    UPDATE instances 
                    SET status = ?, error_count = 0, updated_at = ?
                    WHERE user_id = ?
                """, (status, int(time.time()), user_id))
            
            self._audit_log(db, user_id, 'instance_status_changed', {'status': status})
    
    def get_stale_instances(self, heartbeat_timeout: int = 60) -> List[str]:
        """Get instances with stale heartbeat (probably crashed)"""
        with sqlite3.connect(self.db_path) as db:
            threshold = int(time.time()) - heartbeat_timeout
            cursor = db.execute("""
                SELECT user_id FROM instances 
                WHERE status = 'running' AND last_heartbeat < ?
            """, (threshold,))
            
            return [row[0] for row in cursor.fetchall()]
    
    def get_instances_needing_refresh(self) -> List[str]:
        """Get instances with tokens expiring soon"""
        user_ids = []
        for user_id in self.get_all_users():
            if self.needs_refresh(user_id):
                user_ids.append(user_id)
        return user_ids
    
    # ========================================================================
    # AUDIT LOG
    # ========================================================================
    
    def _audit_log(self, db, user_id: str, action: str, details: Dict, ip: str = None):
        """Internal audit log helper"""
        db.execute("""
            INSERT INTO audit_log (user_id, action, details, ip_address, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, action, json.dumps(details), ip, int(time.time())))
```

---

### **Phase 1 : Process Isolation**

#### **1.1 - IPC Sécurisé (Token Passing)**

**Fichier:** `supervisor/ipc.py`

```python
#!/usr/bin/env python3
"""
Secure IPC for token passing (Supervisor → Bot)
Uses Unix sockets (preferred) or stdin fallback
"""

import socket
import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class TokenIPC:
    """
    Inter-Process Communication for secure token passing.
    
    Flow:
        1. Supervisor creates Unix socket
        2. Supervisor launches bot with --socket flag
        3. Bot connects to socket
        4. Supervisor sends token JSON
        5. Socket closed
    """
    
    def __init__(self, socket_dir: str = "/run/kissbot"):
        self.socket_dir = Path(socket_dir)
        self.socket_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        logger.info(f"🔌 IPC socket dir: {self.socket_dir}")
    
    def create_socket(self, user_id: str) -> str:
        """
        Create Unix socket for user.
        
        Returns:
            str: Socket path
        """
        socket_path = str(self.socket_dir / f"{user_id}.sock")
        
        # Remove old socket if exists
        if os.path.exists(socket_path):
            os.remove(socket_path)
        
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(socket_path)
        os.chmod(socket_path, 0o600)  # Owner-only
        sock.listen(1)
        
        logger.debug(f"🔌 Socket created: {socket_path}")
        return socket_path
    
    def send_token(self, socket_path: str, token_data: dict, timeout: int = 5):
        """
        Send token to bot via socket.
        
        Args:
            socket_path: Path to Unix socket
            token_data: {'access_token', 'refresh_token', 'expires_at', 'scopes'}
            timeout: Connection timeout
        """
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(socket_path)
        sock.listen(1)
        sock.settimeout(timeout)
        
        try:
            conn, _ = sock.accept()
            conn.send(json.dumps(token_data).encode('utf-8'))
            conn.close()
            logger.debug(f"✅ Token sent via socket")
        except socket.timeout:
            logger.error(f"❌ Socket timeout: bot didn't connect")
            raise
        finally:
            sock.close()
            if os.path.exists(socket_path):
                os.remove(socket_path)
    
    def receive_token(self, socket_path: str, timeout: int = 5) -> dict:
        """
        Receive token from supervisor (bot side).
        
        Args:
            socket_path: Path to Unix socket
            timeout: Connection timeout
        
        Returns:
            dict: Token data
        """
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        
        try:
            sock.connect(socket_path)
            data = sock.recv(4096)
            token_data = json.loads(data.decode('utf-8'))
            logger.debug(f"✅ Token received via socket")
            return token_data
        finally:
            sock.close()
```

---

#### **1.2 - Supervisor v2 (with DB + IPC)**

**Fichier:** `supervisor.py`

```python
#!/usr/bin/env python3
"""
KissBot V5 Supervisor - Multi-Process Manager
- Manages N bot instances (1 process = 1 channel)
- Token refresh & health checks
- Secure IPC for token passing
"""

import subprocess
import os
import signal
import time
import logging
import sys
from typing import Dict
from pathlib import Path

from database.manager import DatabaseManager
from database.crypto import TokenEncryptor
from supervisor.ipc import TokenIPC

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('logs/supervisor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class BotSupervisor:
    """
    Process manager for KissBot instances.
    
    Features:
        - 1 process per channel (isolation)
        - Secure token passing (Unix sockets)
        - Health checks (heartbeat monitoring)
        - Auto-restart on crash
        - Token refresh (proactive + on-demand)
    """
    
    def __init__(self, db_path: str = "/var/lib/kissbot/kissbot.db"):
        self.db_path = db_path
        
        # Initialize database & crypto
        self.encryptor = TokenEncryptor()
        self.db = DatabaseManager(db_path, self.encryptor)
        self.ipc = TokenIPC()
        
        # Track running processes
        self.processes: Dict[str, subprocess.Popen] = {}
        
        # Config
        self.heartbeat_timeout = 60  # seconds
        self.refresh_threshold = 60  # refresh token if expires in < 60s
        
        logger.info("✅ BotSupervisor initialized")
    
    def start_bot(self, user_id: str) -> bool:
        """
        Start a bot instance for user.
        
        Flow:
            1. Get token from DB
            2. Create Unix socket
            3. Launch bot process
            4. Send token via IPC
            5. Track process
        """
        # Check if already running
        if user_id in self.processes and self.processes[user_id].poll() is None:
            logger.warning(f"⚠️  Bot already running: {user_id}")
            return False
        
        # Get user info
        user = self.db.get_user(user_id)
        if not user:
            logger.error(f"❌ User not found: {user_id}")
            return False
        
        channel = user['login']
        
        # Get token
        token_data = self.db.get_token(user_id)
        if not token_data:
            logger.error(f"❌ No token for user: {user_id}")
            self.db.set_instance_status(user_id, 'needs_reauth')
            return False
        
        # Refresh if needed
        if self.db.needs_refresh(user_id, self.refresh_threshold):
            logger.info(f"🔄 Token refresh needed: {user_id}")
            if not self._refresh_token(user_id):
                logger.error(f"❌ Token refresh failed: {user_id}")
                return False
            token_data = self.db.get_token(user_id)
        
        # Create socket
        socket_path = self.ipc.create_socket(user_id)
        
        # Launch bot process
        log_file = f"logs/{channel}.log"
        pid_file = f"pids/{channel}.pid"
        
        logger.info(f"🚀 Starting bot: {channel} (user_id={user_id})")
        
        with open(log_file, 'a') as log:
            process = subprocess.Popen(
                [
                    sys.executable,  # python3
                    'main.py',
                    '--channel', channel,
                    '--user-id', user_id,
                    '--socket', socket_path
                ],
                stdout=log,
                stderr=log,
                preexec_fn=os.setsid  # New session for isolation
            )
        
        # Save PID
        with open(pid_file, 'w') as f:
            f.write(str(process.pid))
        
        # Track process
        self.processes[user_id] = process
        
        # Update DB
        self.db.create_instance(user_id, str(process.pid))
        
        # Send token via IPC (non-blocking)
        try:
            self.ipc.send_token(socket_path, token_data)
            logger.info(f"✅ Bot started: {channel} (PID={process.pid})")
            return True
        except Exception as e:
            logger.error(f"❌ IPC failed: {e}")
            self.stop_bot(user_id)
            return False
    
    def stop_bot(self, user_id: str) -> bool:
        """Stop a bot instance"""
        if user_id not in self.processes:
            logger.warning(f"⚠️  Bot not tracked: {user_id}")
            return False
        
        process = self.processes[user_id]
        user = self.db.get_user(user_id)
        channel = user['login'] if user else user_id
        
        if process.poll() is not None:
            logger.warning(f"⚠️  Bot already stopped: {channel}")
            del self.processes[user_id]
            return False
        
        logger.info(f"🛑 Stopping bot: {channel} (PID={process.pid})")
        
        # Graceful shutdown (SIGTERM)
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
        
        # Wait up to 5s
        for _ in range(50):
            if process.poll() is not None:
                break
            time.sleep(0.1)
        
        # Force kill if needed
        if process.poll() is None:
            logger.warning(f"⚠️  Force killing: {channel}")
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        
        del self.processes[user_id]
        
        # Update DB
        self.db.set_instance_status(user_id, 'stopped')
        
        # Cleanup
        pid_file = f"pids/{channel}.pid"
        if os.path.exists(pid_file):
            os.remove(pid_file)
        
        logger.info(f"✅ Bot stopped: {channel}")
        return True
    
    def restart_bot(self, user_id: str) -> bool:
        """Restart a bot instance"""
        logger.info(f"🔄 Restarting bot: {user_id}")
        self.stop_bot(user_id)
        time.sleep(1)
        return self.start_bot(user_id)
    
    def start_all(self):
        """Start all bots from DB"""
        user_ids = self.db.get_all_users()
        logger.info(f"📋 Found {len(user_ids)} users in DB")
        
        for user_id in user_ids:
            self.start_bot(user_id)
            time.sleep(0.5)  # Stagger starts
    
    def stop_all(self):
        """Stop all running bots"""
        user_ids = list(self.processes.keys())
        for user_id in user_ids:
            self.stop_bot(user_id)
    
    def health_check_loop(self):
        """
        Periodic health checks:
        - Detect stale heartbeats (crashed bots)
        - Proactive token refresh
        """
        logger.info("🏥 Health check loop started")
        
        while True:
            time.sleep(30)  # Check every 30s
            
            try:
                # Check for stale heartbeats
                stale = self.db.get_stale_instances(self.heartbeat_timeout)
                for user_id in stale:
                    user = self.db.get_user(user_id)
                    channel = user['login'] if user else user_id
                    logger.warning(f"💀 Stale heartbeat detected: {channel}")
                    self.restart_bot(user_id)
                
                # Proactive token refresh
                need_refresh = self.db.get_instances_needing_refresh()
                for user_id in need_refresh:
                    if user_id in self.processes:
                        logger.info(f"🔄 Proactive refresh: {user_id}")
                        self._refresh_token(user_id)
            
            except Exception as e:
                logger.error(f"❌ Health check error: {e}", exc_info=True)
    
    def _refresh_token(self, user_id: str) -> bool:
        """
        Refresh OAuth token.
        
        TODO: Implement actual Twitch OAuth refresh
        For now, placeholder logic.
        """
        import httpx
        
        token_data = self.db.get_token(user_id)
        if not token_data:
            return False
        
        try:
            # TODO: Replace with real Twitch client_id/secret
            response = httpx.post(
                "https://id.twitch.tv/oauth2/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": token_data['refresh_token'],
                    "client_id": os.environ.get('TWITCH_CLIENT_ID'),
                    "client_secret": os.environ.get('TWITCH_CLIENT_SECRET')
                }
            )
            
            if response.status_code != 200:
                logger.error(f"❌ Refresh failed: {response.status_code}")
                self.db.set_instance_status(user_id, 'needs_reauth', increment_errors=True)
                return False
            
            data = response.json()
            new_access = data['access_token']
            new_refresh = data.get('refresh_token', token_data['refresh_token'])
            new_expires = int(time.time()) + data['expires_in']
            
            self.db.store_token(
                user_id,
                new_access,
                new_refresh,
                new_expires,
                token_data['scopes']
            )
            
            logger.info(f"✅ Token refreshed: {user_id}")
            return True
        
        except Exception as e:
            logger.error(f"❌ Refresh error: {e}")
            self.db.set_instance_status(user_id, 'needs_reauth', increment_errors=True)
            return False
    
    def run_interactive(self):
        """Interactive CLI mode"""
        self.start_all()
        
        print("\n📋 Commands: start [user_id], stop [user_id], restart [user_id], status, quit")
        
        try:
            while True:
                cmd = input("\n> ").strip().lower().split()
                
                if not cmd:
                    continue
                
                action = cmd[0]
                
                if action in ['quit', 'exit', 'q']:
                    print("👋 Stopping all bots...")
                    self.stop_all()
                    break
                
                elif action == 'status':
                    self._print_status()
                
                elif action == 'start' and len(cmd) > 1:
                    self.start_bot(cmd[1])
                
                elif action == 'stop' and len(cmd) > 1:
                    self.stop_bot(cmd[1])
                
                elif action == 'restart' and len(cmd) > 1:
                    self.restart_bot(cmd[1])
                
                elif action == 'logs' and len(cmd) > 1:
                    user = self.db.get_user(cmd[1])
                    if user:
                        subprocess.run(['tail', '-f', f"logs/{user['login']}.log"])
                
                else:
                    print("❌ Unknown command")
        
        except KeyboardInterrupt:
            print("\n👋 Stopping all bots...")
            self.stop_all()
    
    def _print_status(self):
        """Print status of all bots"""
        user_ids = self.db.get_all_users()
        
        print("\n" + "="*70)
        print("🤖 KissBot Supervisor Status")
        print("="*70)
        
        for user_id in user_ids:
            user = self.db.get_user(user_id)
            channel = user['login'] if user else user_id
            
            if user_id in self.processes:
                process = self.processes[user_id]
                if process.poll() is None:
                    status = f"✅ RUNNING (PID={process.pid})"
                else:
                    status = f"❌ CRASHED (exit={process.returncode})"
            else:
                status = "⚪ STOPPED"
            
            print(f"  {channel:20s} {status}")
        
        print("="*70 + "\n")


if __name__ == '__main__':
    supervisor = BotSupervisor()
    supervisor.run_interactive()
```

---

### **Phase 2 : OAuth Flow + DB Integration**

(À compléter dans la prochaine session...)

---

## 📁 **Structure Finale**

```
kissbot/
├── main.py                           # Bot instance (refactoré)
├── supervisor.py                     # Process manager
├── auth_server.py                    # OAuth web server
├── database/
│   ├── __init__.py
│   ├── schema.sql                    # SQLite schema
│   ├── manager.py                    # DatabaseManager
│   └── crypto.py                     # TokenEncryptor
├── supervisor/
│   ├── __init__.py
│   └── ipc.py                        # TokenIPC (Unix sockets)
├── scripts/
│   ├── generate_key.py               # Generate KISSBOT_SECRET_KEY
│   ├── rotate_key.py                 # Key rotation
│   ├── backup_db.sh                  # Encrypted backup
│   └── delete_user.py                # GDPR compliance
├── logs/
│   ├── supervisor.log
│   └── {channel}.log
├── pids/
│   └── {channel}.pid
├── backups/                          # Encrypted backups
├── /var/lib/kissbot/
│   ├── kissbot.db                    # SQLite database
│   ├── kissbot.db-wal                # Write-Ahead Log
│   └── kissbot.db-shm                # Shared memory
├── /run/kissbot/                     # Unix sockets (IPC)
│   └── {user_id}.sock
├── .env                              # KISSBOT_SECRET_KEY (NEVER commit!)
└── kissbot.sh                        # Wrapper script
```

---

## 🔐 **Security Checklist**

- [ ] `KISSBOT_SECRET_KEY` in `.env` (not in Git)
- [ ] DB file permissions: `600` (owner-only)
- [ ] Socket dir permissions: `700` (owner-only)
- [ ] Never log tokens (mask with `***`)
- [ ] Audit logs (no PII, no tokens)
- [ ] Token rotation support (`key_version`)
- [ ] GDPR compliance (`delete_user()`)
- [ ] Encrypted backups (GPG)
- [ ] WireGuard-only for monitoring tools

---

## 📊 **Metrics to Expose (Prometheus)**

```python
# Minimum observability (Phase 4)
kissbot_instance_rss_bytes        # Memory usage per bot
kissbot_instance_cpu_percent      # CPU usage per bot
kissbot_msgs_out_per_min          # Messages sent rate
kissbot_say_latency_ms_p95        # IRC send latency
kissbot_eventsub_events_per_min   # EventSub events rate
kissbot_refresh_fail_total        # Token refresh failures (counter)
```

---

## 🚀 **Next Steps**

1. **Phase 0** : Database Layer (schema + crypto + manager)
2. **Phase 1** : Supervisor v2 (IPC + process management)
3. **Phase 2** : OAuth Flow (web server + DB integration)
4. **Phase 3** : Monitoring (metrics + dashboard)
5. **Phase 4** : EventSub pool (distributed sharding)

---

## 📚 **References**

- SQLite WAL mode: https://www.sqlite.org/wal.html
- Fernet encryption: https://cryptography.io/en/latest/fernet/
- Twitch OAuth: https://dev.twitch.tv/docs/authentication/
- Unix sockets: https://docs.python.org/3/library/socket.html#socket.AF_UNIX

---

**Date:** 2025-11-04  
**Version:** Draft v1  
**Status:** Ready for implementation Phase 0
