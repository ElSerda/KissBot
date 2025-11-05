#!/usr/bin/env python3
"""
Initialize KissBot Database
Creates SQLite database with schema and WAL mode
"""

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s"
)

LOGGER = logging.getLogger(__name__)


def init_database(db_path: str = "kissbot.db", force: bool = False):
    """
    Initialize database with schema
    
    Args:
        db_path: Path to SQLite database file
        force: If True, drop existing database
    """
    db_file = Path(db_path)
    
    # Check if database exists
    if db_file.exists():
        if not force:
            LOGGER.error(f"❌ Database already exists: {db_path}")
            LOGGER.error("   Use --force to recreate it (WARNING: deletes all data!)")
            return False
        else:
            LOGGER.warning(f"⚠️ Dropping existing database: {db_path}")
            db_file.unlink()
    
    # Read schema
    schema_file = Path(__file__).parent / "schema.sql"
    if not schema_file.exists():
        LOGGER.error(f"❌ Schema file not found: {schema_file}")
        return False
    
    with open(schema_file, 'r') as f:
        schema_sql = f.read()
    
    try:
        # Create database
        LOGGER.info(f"📦 Creating database: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Execute schema
        cursor.executescript(schema_sql)
        conn.commit()
        
        # Enable WAL mode for concurrent reads/writes
        cursor.execute("PRAGMA journal_mode=WAL")
        result = cursor.fetchone()
        LOGGER.info(f"✅ WAL mode enabled: {result[0]}")
        
        # Set busy timeout (5 seconds)
        cursor.execute("PRAGMA busy_timeout=5000")
        
        # Set synchronous mode to NORMAL (good balance)
        cursor.execute("PRAGMA synchronous=NORMAL")
        result = cursor.fetchone()
        LOGGER.info(f"✅ Synchronous mode: {result[0] if result else 'NORMAL'}")
        
        # Verify tables created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        LOGGER.info(f"✅ Tables created: {', '.join(tables)}")
        
        # Show config defaults
        cursor.execute("SELECT key, value, description FROM config")
        configs = cursor.fetchall()
        LOGGER.info("✅ Default config values:")
        for key, value, desc in configs:
            LOGGER.info(f"   {key} = {value} ({desc})")
        
        conn.close()
        
        LOGGER.info(f"✅ Database initialized successfully: {db_path}")
        LOGGER.info(f"📝 Next steps:")
        LOGGER.info(f"   1. Generate encryption key: Will be auto-created on first use")
        LOGGER.info(f"   2. Migrate data: python scripts/migrate_yaml_to_db.py")
        LOGGER.info(f"   3. Run supervisor: python supervisor_v1.py --use-db")
        
        return True
        
    except Exception as e:
        LOGGER.error(f"❌ Failed to initialize database: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Initialize KissBot Database")
    parser.add_argument(
        '--db',
        type=str,
        default='kissbot.db',
        help='Path to database file (default: kissbot.db)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force recreation (deletes existing database!)'
    )
    
    args = parser.parse_args()
    
    success = init_database(args.db, args.force)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
