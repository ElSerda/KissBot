#!/usr/bin/env python3
"""
Fix llm_usage schema - Supprime et recrée avec le bon schéma

Le Monitor attend:
  - Column: ts (TEXT)
  - Pas de column 'timestamp' ou 'cost_usd'

Usage:
    python database/fix_llm_usage_schema.py kissbot.db
"""

import sqlite3
import sys
from pathlib import Path


def fix_schema(db_path: str):
    """Drop et recrée la table llm_usage avec le bon schéma."""
    
    if not Path(db_path).exists():
        print(f"❌ {db_path} n'existe pas")
        return False
    
    print(f"🔧 Fixing llm_usage schema in {db_path}...")
    
    conn = sqlite3.connect(db_path)
    
    # 1. Backup data si elle existe
    try:
        cursor = conn.execute("SELECT COUNT(*) FROM llm_usage")
        count = cursor.fetchone()[0]
        
        if count > 0:
            print(f"   Backing up {count} rows...")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS llm_usage_backup AS 
                SELECT * FROM llm_usage
            """)
            print(f"   ✅ Backup créé: llm_usage_backup")
    except sqlite3.OperationalError:
        print("   Table llm_usage n'existe pas encore")
    
    # 2. Drop la table
    print("   Dropping llm_usage...")
    conn.execute("DROP TABLE IF EXISTS llm_usage")
    
    # 3. Recréer avec le bon schéma (Monitor-compatible)
    print("   Creating llm_usage with correct schema...")
    conn.execute("""
        CREATE TABLE llm_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            channel TEXT NOT NULL,
            model TEXT NOT NULL,
            feature TEXT NOT NULL,
            tokens_in INTEGER NOT NULL,
            tokens_out INTEGER NOT NULL,
            latency_ms REAL
        )
    """)
    
    # 4. Index
    conn.execute("""
        CREATE INDEX idx_llm_usage_channel_ts 
        ON llm_usage(channel, ts)
    """)
    
    conn.commit()
    conn.close()
    
    print("✅ llm_usage schema fixed!")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python database/fix_llm_usage_schema.py <db_path>")
        print("Example: python database/fix_llm_usage_schema.py kissbot.db")
        sys.exit(1)
    
    db_path = sys.argv[1]
    success = fix_schema(db_path)
    sys.exit(0 if success else 1)
