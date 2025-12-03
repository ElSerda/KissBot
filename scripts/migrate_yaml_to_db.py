#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
KissBot - Migration YAML → Database

Copyright (c) 2025 Sεrda - Tous droits réservés
License: Voir LICENSE et EULA_FR.md

Ce script migre les tokens OAuth depuis config.yaml vers la base de données SQLite.
"""

import sys
import os
import argparse
import yaml
import shutil
from datetime import datetime
from pathlib import Path

# Ajout du répertoire parent au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.manager import DatabaseManager


def load_yaml_config(config_path: str) -> dict:
    """
    Charge le fichier config.yaml.
    
    Args:
        config_path: Chemin vers config.yaml
    
    Returns:
        Dict avec la configuration
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def backup_database(db_path: str) -> str:
    """
    Crée une sauvegarde de la base de données.
    
    Args:
        db_path: Chemin vers la base de données
    
    Returns:
        Chemin vers le fichier de sauvegarde
    """
    if not os.path.exists(db_path):
        print(f"⚠️ No existing database to backup: {db_path}")
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.backup_{timestamp}"
    
    shutil.copy2(db_path, backup_path)
    print(f"✅ Database backed up: {backup_path}")
    
    # Backup WAL files if they exist
    for suffix in ['-wal', '-shm']:
        src = f"{db_path}{suffix}"
        if os.path.exists(src):
            dst = f"{backup_path}{suffix}"
            shutil.copy2(src, dst)
    
    return backup_path


def migrate_tokens(config: dict, manager: DatabaseManager, dry_run: bool = False) -> dict:
    """
    Migre les tokens depuis le YAML vers la base de données.
    
    Args:
        config: Configuration chargée depuis YAML
        manager: Instance de DatabaseManager
        dry_run: Si True, simule la migration sans modifier la DB
    
    Returns:
        Dict avec les statistiques de migration
    """
    stats = {
        'users_created': 0,
        'users_updated': 0,
        'tokens_stored': 0,
        'errors': []
    }
    
    # Récupérer les tokens depuis le YAML
    # La structure du config est: { twitch: { tokens: { login: { user_id, access_token, refresh_token } } } }
    twitch_config = config.get('twitch', {})
    tokens = twitch_config.get('tokens', {})
    
    if not tokens:
        print("⚠️ No tokens found in config.yaml")
        return stats
    
    print(f"\n📦 Found {len(tokens)} users in config.yaml:")
    for login in tokens.keys():
        print(f"   - {login}")
    
    print("\n🔄 Starting migration...\n")
    
    # Pour chaque utilisateur dans le YAML
    for twitch_login, token_data in tokens.items():
        try:
            print(f"Processing: {twitch_login}")
            
            # Extraire les données
            twitch_user_id = str(token_data['user_id'])
            access_token = token_data['access_token']
            refresh_token = token_data['refresh_token']
            
            # Déterminer si c'est un bot (basé sur le nom ou le flag is_bot dans le YAML)
            is_bot = token_data.get('is_bot', False) or twitch_login.endswith('_bot') or twitch_login == 'serda_bot'
            token_type = 'bot' if is_bot else 'broadcaster'
            
            if dry_run:
                print(f"   [DRY RUN] Would create/update user: {twitch_login} (ID: {twitch_user_id})")
                print(f"   [DRY RUN] Would store tokens (access: {access_token[:10]}..., refresh: {refresh_token[:10]}...)")
                print(f"   [DRY RUN] Is bot: {is_bot}")
                stats['users_created'] += 1
                stats['tokens_stored'] += 1
                continue
            
            # Vérifier si l'utilisateur existe déjà
            existing_user = manager.get_user_by_login(twitch_login)
            
            if existing_user:
                print(f"   ✓ User exists: ID={existing_user['id']}")
                user_id = existing_user['id']
                
                # Mettre à jour si nécessaire
                if existing_user['twitch_user_id'] != twitch_user_id:
                    print(f"   ⚠️ User ID mismatch! DB={existing_user['twitch_user_id']}, YAML={twitch_user_id}")
                    stats['errors'].append(f"{twitch_login}: User ID mismatch")
                    continue
                
                stats['users_updated'] += 1
            else:
                # Créer l'utilisateur
                user_id = manager.create_user(
                    twitch_user_id=twitch_user_id,
                    twitch_login=twitch_login,
                    display_name=twitch_login.capitalize(),  # Sera mis à jour par le bot
                    is_bot=is_bot
                )
                print(f"   ✓ User created: ID={user_id}")
                stats['users_created'] += 1
            
            # Stocker les tokens (chiffrés) avec le bon type
            manager.store_tokens(
                user_id=user_id,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=14400,  # 4 heures par défaut (sera mis à jour par le bot)
                scopes=None,  # Les scopes seront récupérés via validate token
                token_type=token_type  # 'bot' ou 'broadcaster'
            )
            print(f"   ✓ Tokens stored (encrypted, type={token_type})")
            stats['tokens_stored'] += 1
            
            print()
        
        except Exception as e:
            error_msg = f"{twitch_login}: {str(e)}"
            print(f"   ❌ Error: {e}")
            stats['errors'].append(error_msg)
            print()
    
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Migrate OAuth tokens from config.yaml to database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (simulation)
  python scripts/migrate_yaml_to_db.py --dry-run
  
  # Real migration
  python scripts/migrate_yaml_to_db.py
  
  # Custom paths
  python scripts/migrate_yaml_to_db.py --config config/config.yaml --db kissbot.db
  
  # Force (no backup)
  python scripts/migrate_yaml_to_db.py --force
        """
    )
    
    parser.add_argument(
        '--config',
        default='config/config.yaml',
        help='Path to config.yaml (default: config/config.yaml)'
    )
    
    parser.add_argument(
        '--db',
        default='kissbot.db',
        help='Path to database (default: kissbot.db)'
    )
    
    parser.add_argument(
        '--key-file',
        default='.kissbot.key',
        help='Path to encryption key (default: .kissbot.key)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulate migration without modifying database'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Skip database backup (not recommended)'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("KissBot - YAML to Database Migration")
    print("=" * 60)
    print()
    
    # Vérifier que config.yaml existe
    if not os.path.exists(args.config):
        print(f"❌ Config file not found: {args.config}")
        sys.exit(1)
    
    # Vérifier que la base existe
    if not os.path.exists(args.db):
        print(f"❌ Database not found: {args.db}")
        print(f"   Run: python database/init_db.py --db {args.db}")
        sys.exit(1)
    
    # Backup (sauf si --force ou --dry-run)
    if not args.dry_run and not args.force:
        backup_path = backup_database(args.db)
        if backup_path:
            print(f"💾 Backup created: {backup_path}")
        print()
    
    # Charger config.yaml
    print(f"📖 Loading config: {args.config}")
    try:
        config = load_yaml_config(args.config)
        print("✅ Config loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        sys.exit(1)
    
    # Créer DatabaseManager
    print(f"📦 Connecting to database: {args.db}")
    try:
        manager = DatabaseManager(db_path=args.db, key_file=args.key_file)
        print("✅ Database connected")
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        sys.exit(1)
    
    # Dry run warning
    if args.dry_run:
        print("\n" + "⚠️  DRY RUN MODE - NO CHANGES WILL BE MADE" + "\n")
    
    # Migrer
    stats = migrate_tokens(config, manager, dry_run=args.dry_run)
    
    # Afficher résultats
    print("=" * 60)
    print("Migration Results")
    print("=" * 60)
    print(f"Users created:  {stats['users_created']}")
    print(f"Users updated:  {stats['users_updated']}")
    print(f"Tokens stored:  {stats['tokens_stored']}")
    print(f"Errors:         {len(stats['errors'])}")
    
    if stats['errors']:
        print("\n❌ Errors encountered:")
        for error in stats['errors']:
            print(f"   - {error}")
        print()
        sys.exit(1)
    
    if args.dry_run:
        print("\n✅ Dry run completed successfully!")
        print("   Run without --dry-run to apply changes")
    else:
        print("\n✅ Migration completed successfully!")
        
        # Afficher statistiques DB
        db_stats = manager.get_stats()
        print(f"\n📊 Database stats:")
        print(f"   Users: {db_stats['users_count']}")
        print(f"   Tokens: {db_stats['tokens_count']}")
        print(f"   Instances: {db_stats['active_instances']}")
        print(f"   DB size: {db_stats['db_size_bytes'] / 1024:.1f} KB")
    
    print()


if __name__ == "__main__":
    main()
