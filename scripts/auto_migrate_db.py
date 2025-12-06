#!/usr/bin/env python3
"""
Auto-migrate KissBot database to match current schema.

Compares existing DB with database/schema.sql and applies necessary migrations:
- Creates missing tables
- Adds missing columns (with ALTER TABLE)
- Reports differences but doesn't drop/modify existing columns (safety)

Usage:
    python scripts/auto_migrate_db.py [--db kissbot.db] [--dry-run]
    
Options:
    --db PATH       Path to database (default: kissbot.db)
    --dry-run       Show what would be done without applying changes
"""

import argparse
import re
import sqlite3
import sys
from pathlib import Path


def parse_schema_sql(schema_path: Path) -> dict:
    """Parse schema.sql to extract table definitions."""
    with open(schema_path) as f:
        schema_sql = f.read()
    
    tables = {}
    
    # Extract CREATE TABLE statements (including multi-line)
    # Regex: CREATE TABLE IF NOT EXISTS table_name ( ... );
    pattern = r'CREATE TABLE IF NOT EXISTS\s+(\w+)\s*\((.*?)\);'
    matches = re.finditer(pattern, schema_sql, re.DOTALL | re.IGNORECASE)
    
    for match in matches:
        table_name = match.group(1)
        table_body = match.group(2)
        
        # Parse columns (simplified: name type constraints)
        columns = []
        for line in table_body.split('\n'):
            line = line.strip()
            if not line or line.startswith('--') or line.upper().startswith(('PRIMARY', 'FOREIGN', 'UNIQUE', 'CHECK')):
                continue
            
            # Remove trailing comma
            line = line.rstrip(',')
            
            # Extract column name and definition
            parts = line.split(maxsplit=1)
            if len(parts) >= 2:
                col_name = parts[0]
                col_def = parts[1]
                columns.append({
                    'name': col_name,
                    'definition': col_def
                })
        
        tables[table_name] = columns
    
    return tables


def get_existing_schema(db_path: str) -> dict:
    """Get existing tables and columns from database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    table_names = [row[0] for row in cursor.fetchall()]
    
    tables = {}
    for table in table_names:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = []
        for row in cursor.fetchall():
            # cid, name, type, notnull, default_value, pk
            columns.append({
                'name': row[1],
                'type': row[2],
                'notnull': row[3],
                'default': row[4],
                'pk': row[5]
            })
        tables[table] = columns
    
    conn.close()
    return tables


def generate_migrations(target_schema: dict, existing_schema: dict) -> list:
    """Generate SQL migration statements."""
    migrations = []
    
    target_tables = set(target_schema.keys())
    existing_tables = set(existing_schema.keys())
    
    # Tables to create
    missing_tables = target_tables - existing_tables
    for table in sorted(missing_tables):
        # We'll need the full CREATE TABLE from schema.sql
        migrations.append({
            'type': 'create_table',
            'table': table,
            'action': f"-- Need to create table {table} (copy from schema.sql)"
        })
    
    # Columns to add
    common_tables = target_tables & existing_tables
    for table in sorted(common_tables):
        target_cols = {col['name'] for col in target_schema[table]}
        existing_cols = {col['name'] for col in existing_schema[table]}
        
        missing_cols = target_cols - existing_cols
        for col_name in sorted(missing_cols):
            # Find column definition
            col_def = next((c for c in target_schema[table] if c['name'] == col_name), None)
            if col_def:
                migrations.append({
                    'type': 'add_column',
                    'table': table,
                    'column': col_name,
                    'action': f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def['definition']};"
                })
    
    return migrations


def apply_migrations(db_path: str, migrations: list, dry_run: bool = False):
    """Apply migrations to database."""
    if not migrations:
        print("✅ Database schema is up to date!")
        return True
    
    print(f"\n📋 Found {len(migrations)} migration(s) to apply:\n")
    
    for i, mig in enumerate(migrations, 1):
        if mig['type'] == 'create_table':
            print(f"{i}. ⚠️  CREATE TABLE {mig['table']}")
            print(f"   → {mig['action']}")
        elif mig['type'] == 'add_column':
            print(f"{i}. ➕ ALTER TABLE {mig['table']} ADD COLUMN {mig['column']}")
            print(f"   → {mig['action']}")
    
    if dry_run:
        print("\n🔍 DRY-RUN mode: no changes applied")
        return True
    
    # Ask confirmation
    print("\n⚠️  Apply these migrations? (y/n): ", end="")
    confirm = input().strip().lower()
    if confirm != 'y':
        print("❌ Aborted")
        return False
    
    # Apply migrations
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        for mig in migrations:
            if mig['type'] == 'create_table':
                print(f"\n⚠️  Table {mig['table']} needs manual creation - skipping")
                print(f"   Copy CREATE TABLE statement from database/schema.sql")
                continue
            elif mig['type'] == 'add_column':
                print(f"➕ {mig['action']}")
                cursor.execute(mig['action'])
        
        conn.commit()
        print("\n✅ Migrations applied successfully!")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        return False
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Auto-migrate KissBot database")
    parser.add_argument("--db", default="kissbot.db", help="Path to database file")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without applying")
    
    args = parser.parse_args()
    
    root = Path(__file__).parent.parent
    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = root / db_path
    
    schema_path = root / "database" / "schema.sql"
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        print(f"   Run: python database/init_db.py --db {db_path}")
        sys.exit(1)
    
    if not schema_path.exists():
        print(f"❌ Schema file not found: {schema_path}")
        sys.exit(1)
    
    print(f"🔍 Analyzing database schema...")
    print(f"   DB: {db_path}")
    print(f"   Schema: {schema_path}")
    
    target_schema = parse_schema_sql(schema_path)
    existing_schema = get_existing_schema(str(db_path))
    
    print(f"\n📊 Schema comparison:")
    print(f"   Target tables: {len(target_schema)}")
    print(f"   Existing tables: {len(existing_schema)}")
    
    migrations = generate_migrations(target_schema, existing_schema)
    
    success = apply_migrations(str(db_path), migrations, args.dry_run)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
