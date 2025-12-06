#!/usr/bin/env python3
"""
Quick health check for KissBot DB/key.
- Ensures the main SQLite DB exists; if absent, initializes it from schema.
- Verifies required tables are present (oauth_tokens, users, banwords, config).
- Warns if the Fernet key (.kissbot.key) is missing (does not auto-create).

Usage:
    python scripts/check_db.py [--db /path/to/kissbot.db]
"""

import argparse
import sqlite3
import sys
from pathlib import Path

from database.init_db import init_database

REQUIRED_TABLES = {
    "oauth_tokens",
    "users",
    "banwords",
    "config",
}


def ensure_db(db_path: Path) -> None:
    """Create DB if missing, else validate required tables."""
    if not db_path.exists():
        print(f"🔧 DB missing, initializing: {db_path}")
        ok = init_database(str(db_path), force=False)
        if not ok:
            print("❌ Failed to create database")
            sys.exit(1)
    else:
        print(f"✅ DB found: {db_path}")

    # Validate tables
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cur.fetchall()}

    missing = REQUIRED_TABLES - tables
    if missing:
        print(f"❌ Missing tables: {', '.join(sorted(missing))}")
        print("   Run migrations or recreate the DB with init_db.py if appropriate.")
        sys.exit(1)
    else:
        print(f"✅ Required tables present: {', '.join(sorted(REQUIRED_TABLES))}")


def check_key(key_path: Path) -> None:
    """Warn if the Fernet key is absent."""
    if key_path.exists():
        print(f"✅ Key present: {key_path}")
    else:
        print(f"⚠️  Key missing: {key_path}")
        print("   Copy your existing .kissbot.key to this path before starting the bot.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check KissBot DB and key")
    parser.add_argument("--db", default="kissbot.db", help="Path to kissbot.db")
    args = parser.parse_args()

    root = Path(__file__).parent.parent
    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = root / db_path
    key_path = root / ".kissbot.key"

    ensure_db(db_path)
    check_key(key_path)
    print("\n🎯 DB/key check complete")


if __name__ == "__main__":
    main()
