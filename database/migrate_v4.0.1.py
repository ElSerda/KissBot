#!/usr/bin/env python3
"""
Migration script: v4.0.0 → v4.0.1

Adds new columns to oauth_tokens table:
- token_type (bot/broadcaster)
- last_refresh
- status (valid/expired/revoked)
- key_version

Also migrates existing tokens to new format.
"""

import sqlite3
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def check_schema_version(conn: sqlite3.Connection) -> str:
    """Check if database has old or new schema."""
    cursor = conn.execute("PRAGMA table_info(oauth_tokens)")
    columns = {row[1] for row in cursor.fetchall()}
    
    if 'token_type' in columns:
        return "v4.0.1"
    elif 'access_token_encrypted' in columns:
        return "v4.0.0"
    else:
        return "unknown"


def backup_database(db_path: str) -> str:
    """Create backup before migration."""
    from datetime import datetime
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    import shutil
    shutil.copy2(db_path, backup_path)
    logger.info(f"✅ Backup created: {backup_path}")
    return backup_path


def migrate_schema(conn: sqlite3.Connection):
    """Migrate oauth_tokens table to v4.0.1 schema."""
    logger.info("🔧 Starting schema migration...")
    
    # Create new table with updated schema
    conn.execute("""
        CREATE TABLE oauth_tokens_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_type TEXT NOT NULL CHECK(token_type IN ('bot','broadcaster')),
            access_token_encrypted TEXT NOT NULL,
            refresh_token_encrypted TEXT NOT NULL,
            scopes TEXT NOT NULL DEFAULT '[]',
            expires_at TIMESTAMP NOT NULL,
            last_refresh INTEGER,
            status TEXT NOT NULL DEFAULT 'valid' CHECK(status IN ('valid','expired','revoked')),
            key_version INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            needs_reauth BOOLEAN DEFAULT 0,
            refresh_failures INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id, token_type)
        )
    """)
    
    # Migrate existing data
    # Detect if user is bot by checking users.is_bot
    conn.execute("""
        INSERT INTO oauth_tokens_new 
        (id, user_id, token_type, access_token_encrypted, refresh_token_encrypted, 
         scopes, expires_at, last_refresh, status, key_version, created_at, updated_at, 
         needs_reauth, refresh_failures)
        SELECT 
            ot.id,
            ot.user_id,
            CASE WHEN u.is_bot = 1 THEN 'bot' ELSE 'broadcaster' END,
            ot.access_token_encrypted,
            ot.refresh_token_encrypted,
            COALESCE(ot.scopes, '[]'),
            ot.expires_at,
            NULL,  -- last_refresh unknown
            CASE WHEN ot.needs_reauth = 1 THEN 'expired' ELSE 'valid' END,
            1,  -- key_version
            ot.created_at,
            ot.updated_at,
            ot.needs_reauth,
            ot.refresh_failures
        FROM oauth_tokens ot
        JOIN users u ON ot.user_id = u.id
    """)
    
    # Drop old table
    conn.execute("DROP TABLE oauth_tokens")
    
    # Rename new table
    conn.execute("ALTER TABLE oauth_tokens_new RENAME TO oauth_tokens")
    
    # Recreate indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_oauth_user ON oauth_tokens(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_oauth_type ON oauth_tokens(token_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_oauth_status ON oauth_tokens(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_oauth_expires ON oauth_tokens(expires_at)")
    
    # Recreate trigger
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS update_oauth_timestamp 
        AFTER UPDATE ON oauth_tokens
        BEGIN
            UPDATE oauth_tokens SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END
    """)
    
    # Add new config entry
    conn.execute("""
        INSERT OR IGNORE INTO config (key, value, description) 
        VALUES ('app_token_cache_ttl', '3600', 'TTL du cache pour app access token (secondes)')
    """)
    
    conn.commit()
    logger.info("✅ Schema migration completed")


def verify_migration(conn: sqlite3.Connection):
    """Verify migration was successful."""
    logger.info("🔍 Verifying migration...")
    
    # Check columns exist
    cursor = conn.execute("PRAGMA table_info(oauth_tokens)")
    columns = {row[1] for row in cursor.fetchall()}
    
    required = {'token_type', 'last_refresh', 'status', 'key_version'}
    if not required.issubset(columns):
        missing = required - columns
        raise Exception(f"Migration failed: missing columns {missing}")
    
    # Check data migrated
    cursor = conn.execute("SELECT COUNT(*) FROM oauth_tokens")
    count = cursor.fetchone()[0]
    logger.info(f"✅ {count} token(s) migrated")
    
    # Check token types
    cursor = conn.execute("SELECT token_type, COUNT(*) FROM oauth_tokens GROUP BY token_type")
    for token_type, count in cursor.fetchall():
        logger.info(f"   - {token_type}: {count}")
    
    logger.info("✅ Migration verification passed")


def main():
    if len(sys.argv) < 2:
        print("Usage: python database/migrate_v4.0.1.py <db_path>")
        print("Example: python database/migrate_v4.0.1.py kissbot.db")
        sys.exit(1)
    
    db_path = sys.argv[1]
    
    if not Path(db_path).exists():
        logger.error(f"❌ Database not found: {db_path}")
        sys.exit(1)
    
    logger.info(f"🚀 Migrating database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    try:
        # Check version
        version = check_schema_version(conn)
        logger.info(f"📊 Current schema version: {version}")
        
        if version == "v4.0.1":
            logger.info("✅ Database already at v4.0.1, nothing to do")
            return
        
        if version != "v4.0.0":
            logger.error(f"❌ Cannot migrate from {version}, expected v4.0.0")
            sys.exit(1)
        
        # Backup
        backup_path = backup_database(db_path)
        
        # Migrate
        migrate_schema(conn)
        
        # Verify
        verify_migration(conn)
        
        logger.info("🎉 Migration completed successfully!")
        logger.info(f"💾 Backup saved at: {backup_path}")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
