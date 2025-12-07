#!/usr/bin/env python3
"""
Migration vers DB unifiée (kissbot.db) - Pour déploiement VPS

Ce script migre:
1. kissbot_monitor.db → kissbot.db (table llm_usage)
2. Vérifie l'intégrité des tables
3. Nettoie les anciens fichiers si demandé

Usage:
    python database/migrate_to_unified.py --check            # Vérifier seulement
    python database/migrate_to_unified.py --migrate          # Migrer kissbot_monitor.db
    python database/migrate_to_unified.py --migrate --clean  # Migrer + supprimer l'ancien
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# Paths
DB_UNIFIED = "kissbot.db"
DB_MONITOR = "kissbot_monitor.db"


def check_tables(db_path: str) -> dict:
    """Vérifie quelles tables existent dans une DB."""
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return {
        "exists": Path(db_path).exists(),
        "tables": tables
    }


def migrate_llm_usage():
    """
    Migre la table llm_usage de kissbot_monitor.db vers kissbot.db.
    
    Stratégie:
    - Crée llm_usage dans kissbot.db si elle n'existe pas
    - Copie toutes les lignes de kissbot_monitor.db
    - Gère les doublons (ON CONFLICT IGNORE)
    """
    if not Path(DB_MONITOR).exists():
        print(f"⚠️  {DB_MONITOR} n'existe pas, rien à migrer")
        return False
    
    print(f"📦 Migration de {DB_MONITOR} → {DB_UNIFIED}...")
    
    # Connecter aux deux DBs
    conn_monitor = sqlite3.connect(DB_MONITOR)
    conn_unified = sqlite3.connect(DB_UNIFIED)
    
    # Créer la table llm_usage dans kissbot.db si elle n'existe pas
    conn_unified.execute("""
        CREATE TABLE IF NOT EXISTS llm_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel TEXT NOT NULL,
            model TEXT NOT NULL,
            feature TEXT NOT NULL,
            tokens_in INTEGER NOT NULL,
            tokens_out INTEGER NOT NULL,
            cost_usd REAL,
            latency_ms REAL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Compter les lignes à migrer
    cursor = conn_monitor.execute("SELECT COUNT(*) FROM llm_usage")
    count = cursor.fetchone()[0]
    
    if count == 0:
        print("✅ Aucune ligne à migrer (table vide)")
        conn_monitor.close()
        conn_unified.close()
        return True
    
    print(f"   {count} lignes trouvées dans {DB_MONITOR}")
    
    # Copier les données
    cursor = conn_monitor.execute("""
        SELECT channel, model, feature, tokens_in, tokens_out, cost_usd, latency_ms, timestamp
        FROM llm_usage
    """)
    
    migrated = 0
    for row in cursor:
        try:
            conn_unified.execute("""
                INSERT OR IGNORE INTO llm_usage 
                (channel, model, feature, tokens_in, tokens_out, cost_usd, latency_ms, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, row)
            migrated += 1
        except Exception as e:
            print(f"⚠️  Erreur migration ligne: {e}")
    
    conn_unified.commit()
    conn_monitor.close()
    conn_unified.close()
    
    print(f"✅ {migrated}/{count} lignes migrées")
    return True


def verify_migration():
    """Vérifie que la migration est réussie."""
    if not Path(DB_UNIFIED).exists():
        print(f"❌ {DB_UNIFIED} n'existe pas !")
        return False
    
    conn = sqlite3.connect(DB_UNIFIED)
    
    # Vérifier que llm_usage existe
    cursor = conn.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='llm_usage'
    """)
    if not cursor.fetchone():
        print("❌ Table llm_usage manquante dans kissbot.db")
        conn.close()
        return False
    
    # Compter les lignes
    cursor = conn.execute("SELECT COUNT(*) FROM llm_usage")
    count = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"✅ Vérification OK: llm_usage contient {count} lignes")
    return True


def cleanup_old_db():
    """Supprime kissbot_monitor.db après migration."""
    if not Path(DB_MONITOR).exists():
        print(f"⚠️  {DB_MONITOR} déjà supprimé")
        return True
    
    # Backup avant suppression
    backup_path = f"{DB_MONITOR}.backup"
    Path(DB_MONITOR).rename(backup_path)
    print(f"✅ {DB_MONITOR} → {backup_path}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Migration DB unifiée pour KissBot")
    parser.add_argument("--check", action="store_true", help="Vérifier l'état des DBs")
    parser.add_argument("--migrate", action="store_true", help="Migrer kissbot_monitor.db")
    parser.add_argument("--clean", action="store_true", help="Supprimer l'ancien DB après migration")
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("🔄 Migration DB Unifiée - KissBot")
    print("=" * 70)
    
    # Check mode
    if args.check or not args.migrate:
        print("\n📊 État actuel des bases de données:\n")
        
        unified_info = check_tables(DB_UNIFIED)
        monitor_info = check_tables(DB_MONITOR)
        
        print(f"📁 {DB_UNIFIED}:")
        print(f"   Existe: {'✅' if unified_info['exists'] else '❌'}")
        if unified_info['exists']:
            print(f"   Tables: {len(unified_info['tables'])}")
            if 'llm_usage' in unified_info['tables']:
                conn = sqlite3.connect(DB_UNIFIED)
                cursor = conn.execute("SELECT COUNT(*) FROM llm_usage")
                count = cursor.fetchone()[0]
                conn.close()
                print(f"   llm_usage: {count} lignes")
        
        print(f"\n📁 {DB_MONITOR}:")
        print(f"   Existe: {'✅' if monitor_info['exists'] else '❌'}")
        if monitor_info['exists']:
            print(f"   Tables: {len(monitor_info['tables'])}")
            if 'llm_usage' in monitor_info['tables']:
                conn = sqlite3.connect(DB_MONITOR)
                cursor = conn.execute("SELECT COUNT(*) FROM llm_usage")
                count = cursor.fetchone()[0]
                conn.close()
                print(f"   llm_usage: {count} lignes")
        
        if not args.migrate:
            print("\n💡 Pour migrer: python database/migrate_to_unified.py --migrate")
            return
    
    # Migration mode
    if args.migrate:
        print("\n🔄 Migration en cours...\n")
        
        # 1. Migrer llm_usage
        if not migrate_llm_usage():
            print("❌ Migration échouée")
            sys.exit(1)
        
        # 2. Vérifier
        if not verify_migration():
            print("❌ Vérification échouée")
            sys.exit(1)
        
        # 3. Cleanup si demandé
        if args.clean:
            print("\n🧹 Nettoyage...\n")
            cleanup_old_db()
        
        print("\n" + "=" * 70)
        print("✅ Migration terminée avec succès !")
        print("=" * 70)
        print("\n💡 Prochaines étapes:")
        print("   1. Vérifier: python database/migrate_to_unified.py --check")
        print("   2. Redémarrer: ./kissbot.sh restart --use-db")
        print("   3. Tester: !ask test")


if __name__ == "__main__":
    main()
