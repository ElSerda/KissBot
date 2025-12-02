#!/usr/bin/env python3
"""
Migration script: Add EventSub Hub tables (v5.0)

Adds 3 new tables for EventSub Hub:
- desired_subscriptions: Source of truth for wanted subscriptions
- active_subscriptions: Observed state from Twitch API
- hub_state: Hub health and metrics

Safe to run multiple times (idempotent).
Creates backup before migration.
"""

import argparse
import logging
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s"
)
LOGGER = logging.getLogger(__name__)


def create_backup(db_path: Path) -> Path:
    """Create timestamped backup of database."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"{db_path.name}.backup_{timestamp}"
    
    LOGGER.info(f"📦 Creating backup: {backup_path}")
    shutil.copy2(db_path, backup_path)
    
    return backup_path


def check_migration_needed(conn: sqlite3.Connection) -> bool:
    """Check if migration is needed (tables don't exist yet)."""
    cursor = conn.cursor()
    
    # Check if desired_subscriptions exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='desired_subscriptions'
    """)
    
    exists = cursor.fetchone() is not None
    
    if exists:
        LOGGER.info("✅ Migration already applied (desired_subscriptions exists)")
        return False
    
    LOGGER.info("🔍 Migration needed (Hub tables missing)")
    return True


def apply_migration(conn: sqlite3.Connection) -> None:
    """Apply migration SQL."""
    LOGGER.info("🚀 Applying migration...")
    
    cursor = conn.cursor()
    
    # Add new config entries for EventSub Hub
    LOGGER.info("📝 Adding EventSub Hub config entries...")
    cursor.executemany("""
        INSERT OR IGNORE INTO config (key, value, description) 
        VALUES (?, ?, ?)
    """, [
        ('eventsub_reconcile_interval', '60', 'EventSub Hub: Intervalle de réconciliation (secondes)'),
        ('eventsub_req_rate_per_s', '2', 'EventSub Hub: Rate limit pour créations de subs (req/s)'),
        ('eventsub_req_jitter_ms', '200', 'EventSub Hub: Jitter entre requêtes (ms)'),
        ('eventsub_ws_backoff_base', '2', 'EventSub Hub: Base pour backoff exponentiel (secondes)'),
        ('eventsub_ws_backoff_max', '60', 'EventSub Hub: Backoff max pour reconnexion WS (secondes)'),
    ])
    
    # Create desired_subscriptions table
    LOGGER.info("📝 Creating desired_subscriptions table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS desired_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT NOT NULL,
            topic TEXT NOT NULL,
            version TEXT NOT NULL DEFAULT '1',
            transport TEXT NOT NULL DEFAULT 'websocket',
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            UNIQUE(channel_id, topic)
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_desired_channel 
        ON desired_subscriptions(channel_id)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_desired_topic 
        ON desired_subscriptions(topic)
    """)
    
    # Create active_subscriptions table
    LOGGER.info("📝 Creating active_subscriptions table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS active_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            twitch_sub_id TEXT NOT NULL UNIQUE,
            channel_id TEXT NOT NULL,
            topic TEXT NOT NULL,
            status TEXT NOT NULL,
            cost INTEGER DEFAULT 1,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            UNIQUE(channel_id, topic)
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_active_channel 
        ON active_subscriptions(channel_id)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_active_status 
        ON active_subscriptions(status)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_active_twitch_id 
        ON active_subscriptions(twitch_sub_id)
    """)
    
    # Create hub_state table
    LOGGER.info("📝 Creating hub_state table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hub_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at INTEGER NOT NULL
        )
    """)
    
    # Initialize hub_state with default values
    cursor.executemany("""
        INSERT OR IGNORE INTO hub_state (key, value, updated_at) 
        VALUES (?, ?, strftime('%s', 'now'))
    """, [
        ('ws_state', 'down'),
        ('last_ws_connect_ts', '0'),
        ('last_reconcile_ts', '0'),
        ('error_burst_level', '0'),
        ('total_events_routed', '0'),
        ('ws_reconnect_count', '0'),
    ])
    
    conn.commit()
    LOGGER.info("✅ Migration applied successfully")


def verify_migration(conn: sqlite3.Connection) -> bool:
    """Verify migration was successful."""
    LOGGER.info("🔍 Verifying migration...")
    
    cursor = conn.cursor()
    
    # Check all 3 tables exist
    # nosec B608 - Safe: 'table' comes from hardcoded whitelist, value bound via ?
    tables = ['desired_subscriptions', 'active_subscriptions', 'hub_state']
    for table in tables:
        cursor.execute(f"""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name=?
        """, (table,))
        
        if cursor.fetchone() is None:
            LOGGER.error(f"❌ Table {table} not found after migration")
            return False
    
    # Check hub_state has default entries
    cursor.execute("SELECT COUNT(*) FROM hub_state")
    count = cursor.fetchone()[0]
    
    if count < 6:
        LOGGER.error(f"❌ hub_state has only {count} entries (expected 6)")
        return False
    
    # Check config entries added
    cursor.execute("""
        SELECT COUNT(*) FROM config 
        WHERE key LIKE 'eventsub_%'
    """)
    config_count = cursor.fetchone()[0]
    
    if config_count < 5:
        LOGGER.error(f"❌ Only {config_count} EventSub config entries found (expected 5)")
        return False
    
    LOGGER.info("✅ Migration verification passed")
    return True


def get_migration_stats(conn: sqlite3.Connection) -> dict:
    """Get statistics after migration."""
    cursor = conn.cursor()
    
    stats = {}
    
    # Count existing users
    cursor.execute("SELECT COUNT(*) FROM users")
    stats['users_count'] = cursor.fetchone()[0]
    
    # Count tokens
    cursor.execute("SELECT COUNT(*) FROM oauth_tokens")
    stats['tokens_count'] = cursor.fetchone()[0]
    
    # Count instances
    cursor.execute("SELECT COUNT(*) FROM instances WHERE status='running'")
    stats['running_instances'] = cursor.fetchone()[0]
    
    # Hub tables (should be empty after migration)
    cursor.execute("SELECT COUNT(*) FROM desired_subscriptions")
    stats['desired_subs'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM active_subscriptions")
    stats['active_subs'] = cursor.fetchone()[0]
    
    return stats


def main():
    parser = argparse.ArgumentParser(description="Migrate database to EventSub Hub v5.0")
    parser.add_argument(
        "--db",
        type=str,
        default="kissbot.db",
        help="Path to database file (default: kissbot.db)"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backup creation (not recommended)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force migration even if tables exist"
    )
    
    args = parser.parse_args()
    
    db_path = Path(args.db)
    
    # Check database exists
    if not db_path.exists():
        LOGGER.error(f"❌ Database not found: {db_path}")
        sys.exit(1)
    
    LOGGER.info(f"🗄️  Database: {db_path}")
    
    # Create backup
    if not args.no_backup:
        try:
            backup_path = create_backup(db_path)
            LOGGER.info(f"✅ Backup created: {backup_path}")
        except Exception as e:
            LOGGER.error(f"❌ Backup failed: {e}")
            sys.exit(1)
    else:
        LOGGER.warning("⚠️  Skipping backup (--no-backup)")
    
    # Connect to database
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
    except Exception as e:
        LOGGER.error(f"❌ Failed to connect to database: {e}")
        sys.exit(1)
    
    try:
        # Check if migration needed
        if not args.force:
            if not check_migration_needed(conn):
                LOGGER.info("✅ No migration needed")
                sys.exit(0)
        else:
            LOGGER.warning("⚠️  Force mode: applying migration anyway")
        
        # Apply migration
        apply_migration(conn)
        
        # Verify migration
        if not verify_migration(conn):
            LOGGER.error("❌ Migration verification failed")
            sys.exit(1)
        
        # Show stats
        stats = get_migration_stats(conn)
        LOGGER.info("📊 Migration stats:")
        LOGGER.info(f"   Users: {stats['users_count']}")
        LOGGER.info(f"   Tokens: {stats['tokens_count']}")
        LOGGER.info(f"   Running instances: {stats['running_instances']}")
        LOGGER.info(f"   Desired subscriptions: {stats['desired_subs']}")
        LOGGER.info(f"   Active subscriptions: {stats['active_subs']}")
        
        LOGGER.info("")
        LOGGER.info("✅ Migration completed successfully!")
        LOGGER.info("")
        LOGGER.info("Next steps:")
        LOGGER.info("1. Start EventSub Hub: python eventsub_hub.py")
        LOGGER.info("2. Start bots with --eventsub=hub flag")
        LOGGER.info("3. Monitor: python scripts/hub_ctl.py status")
        
    except Exception as e:
        LOGGER.error(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        conn.close()


if __name__ == "__main__":
    main()
