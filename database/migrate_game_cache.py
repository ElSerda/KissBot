#!/usr/bin/env python3
"""
Migration script: Add game_cache table (v5.1)

Adds new Game domain with intelligent cache:
- game_cache table with confidence tracking
- Indexes for performance
- Triggers for auto-update

This migration is safe and non-destructive (only adds new tables).
"""

import sqlite3
import sys
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def backup_database(db_path: str) -> str:
    """Create timestamped backup of database."""
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    import shutil
    shutil.copy2(db_path, backup_path)
    logger.info(f"✅ Backup created: {backup_path}")
    return backup_path


def check_migration_needed(conn: sqlite3.Connection) -> bool:
    """Check if game_cache table needs migration."""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='game_cache'"
    )
    table_exists = cursor.fetchone() is not None
    
    if not table_exists:
        return True  # Need to create table
    
    # Check if table has new schema (confidence column)
    cursor = conn.execute("PRAGMA table_info(game_cache)")
    columns = {row[1] for row in cursor.fetchall()}
    
    if 'confidence' not in columns:
        logger.info("  Found old game_cache schema (cache_key, value, expires_at)")
        return True  # Need to migrate old schema
    
    return False  # Already has new schema


def apply_migration(conn: sqlite3.Connection) -> None:
    """Apply game_cache schema migration."""
    
    # Check if old table exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='game_cache'"
    )
    old_table_exists = cursor.fetchone() is not None
    
    if old_table_exists:
        # Check if it's the old schema
        cursor = conn.execute("PRAGMA table_info(game_cache)")
        columns = {row[1] for row in cursor.fetchall()}
        
        if 'confidence' not in columns:
            logger.info("🔧 Dropping old game_cache table (incompatible schema)...")
            conn.execute("DROP TABLE game_cache")
            logger.info("  ✓ Old table dropped")
    
    logger.info("🔧 Creating new game_cache table...")
    
    # Create game_cache table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS game_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            
            -- Query de recherche (normalisée en lowercase)
            query TEXT NOT NULL UNIQUE,
            
            -- Résultat du jeu (JSON sérialisé: GameResult.__dict__)
            game_data TEXT NOT NULL,
            
            -- Métadonnées de confiance (pour décisions intelligentes)
            confidence REAL NOT NULL,              -- Score 0.0 - 1.0 (DRAKON ranking)
            result_type TEXT NOT NULL,             -- SUCCESS, MULTIPLE_RESULTS, NO_MATCH, etc.
            alternatives TEXT,                     -- JSON array de GameResult (si MULTIPLE_RESULTS)
            canonical_query TEXT,                  -- Lien vers query plus précise/officielle
            
            -- Métadonnées d'usage
            hit_count INTEGER DEFAULT 0,           -- Nombre de fois utilisé
            last_hit INTEGER,                      -- Timestamp UNIX du dernier accès
            
            -- Timestamps
            cached_at INTEGER NOT NULL,            -- Timestamp UNIX de création du cache
            expires_at INTEGER,                    -- Timestamp UNIX d'expiration (NULL = never)
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    logger.info("  ✓ game_cache table created")
    
    # Create indexes
    logger.info("🔧 Creating indexes...")
    
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_game_cache_query 
            ON game_cache(query)
    """)
    logger.info("  ✓ idx_game_cache_query created")
    
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_game_cache_canonical 
            ON game_cache(canonical_query)
    """)
    logger.info("  ✓ idx_game_cache_canonical created")
    
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_game_cache_confidence 
            ON game_cache(confidence)
    """)
    logger.info("  ✓ idx_game_cache_confidence created")
    
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_game_cache_usage 
            ON game_cache(hit_count, last_hit)
    """)
    logger.info("  ✓ idx_game_cache_usage created")
    
    # Create trigger
    logger.info("🔧 Creating trigger...")
    
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS update_game_cache_timestamp 
        AFTER UPDATE ON game_cache
        BEGIN
            UPDATE game_cache SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END
    """)
    logger.info("  ✓ update_game_cache_timestamp trigger created")


def verify_migration(conn: sqlite3.Connection) -> bool:
    """Verify migration was successful."""
    logger.info("🔍 Verifying migration...")
    
    # Check table exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='game_cache'"
    )
    if not cursor.fetchone():
        logger.error("  ❌ game_cache table not found!")
        return False
    logger.info("  ✓ game_cache table exists")
    
    # Check columns
    cursor = conn.execute("PRAGMA table_info(game_cache)")
    columns = {row[1] for row in cursor.fetchall()}
    
    expected_columns = {
        'id', 'query', 'game_data', 'confidence', 'result_type',
        'alternatives', 'canonical_query', 'hit_count', 'last_hit',
        'cached_at', 'expires_at', 'created_at', 'updated_at'
    }
    
    missing = expected_columns - columns
    if missing:
        logger.error(f"  ❌ Missing columns: {missing}")
        return False
    logger.info(f"  ✓ All {len(expected_columns)} columns present")
    
    # Check indexes
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='game_cache'"
    )
    indexes = {row[0] for row in cursor.fetchall()}
    
    expected_indexes = {
        'idx_game_cache_query',
        'idx_game_cache_canonical',
        'idx_game_cache_confidence',
        'idx_game_cache_usage'
    }
    
    missing_indexes = expected_indexes - indexes
    if missing_indexes:
        logger.error(f"  ❌ Missing indexes: {missing_indexes}")
        return False
    logger.info(f"  ✓ All {len(expected_indexes)} indexes present")
    
    # Check trigger
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='game_cache'"
    )
    triggers = {row[0] for row in cursor.fetchall()}
    
    if 'update_game_cache_timestamp' not in triggers:
        logger.error("  ❌ Trigger update_game_cache_timestamp not found!")
        return False
    logger.info("  ✓ Trigger update_game_cache_timestamp exists")
    
    return True


def main():
    """Main migration function."""
    if len(sys.argv) < 2:
        print("Usage: python database/migrate_game_cache.py <db_path>")
        print("Example: python database/migrate_game_cache.py kissbot.db")
        sys.exit(1)
    
    db_path = sys.argv[1]
    
    # Check database exists
    if not Path(db_path).exists():
        logger.error(f"❌ Database not found: {db_path}")
        sys.exit(1)
    
    logger.info(f"🚀 Starting migration for: {db_path}")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    try:
        # Check if migration needed
        if not check_migration_needed(conn):
            logger.info("✅ Database already has game_cache table, nothing to do")
            return
        
        logger.info("📋 Migration needed: game_cache table missing")
        
        # Backup database
        backup_path = backup_database(db_path)
        
        # Apply migration
        apply_migration(conn)
        conn.commit()
        
        # Verify migration
        if not verify_migration(conn):
            logger.error("❌ Migration verification failed!")
            logger.info(f"🔄 Restore from backup: {backup_path}")
            sys.exit(1)
        
        logger.info("✅ Migration completed successfully!")
        logger.info(f"📦 Backup available at: {backup_path}")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        conn.rollback()
        sys.exit(1)
    
    finally:
        conn.close()


if __name__ == "__main__":
    main()
