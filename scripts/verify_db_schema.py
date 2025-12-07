#!/usr/bin/env python3
"""
Vérification du schéma DB avant déploiement
Vérifie que la DB VPS est compatible avec les nouveaux changements.
"""
import sqlite3
import sys
from pathlib import Path

def check_db_schema(db_path: str = "kissbot.db") -> bool:
    """
    Vérifie que la DB a le bon schéma pour les nouvelles features.
    
    Returns:
        True si compatible, False sinon
    """
    print("=" * 70)
    print("🔍 Vérification du schéma de base de données")
    print("=" * 70)
    
    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    issues = []
    
    # ============================================================
    # CHECK 1: Table users - Colonne twitch_user_id
    # ============================================================
    print("\n📋 Vérification table 'users'...")
    cursor.execute("PRAGMA table_info(users)")
    users_columns = {row[1]: row[2] for row in cursor.fetchall()}
    
    if 'twitch_user_id' not in users_columns:
        issues.append("❌ Table 'users': Colonne 'twitch_user_id' manquante")
        print("   ❌ Colonne 'twitch_user_id' manquante")
    else:
        print(f"   ✅ Colonne 'twitch_user_id' présente ({users_columns['twitch_user_id']})")
    
    if 'twitch_login' not in users_columns:
        issues.append("❌ Table 'users': Colonne 'twitch_login' manquante")
        print("   ❌ Colonne 'twitch_login' manquante")
    else:
        print(f"   ✅ Colonne 'twitch_login' présente ({users_columns['twitch_login']})")
    
    # ============================================================
    # CHECK 2: Table oauth_tokens - Colonne token_type
    # ============================================================
    print("\n🔐 Vérification table 'oauth_tokens'...")
    cursor.execute("PRAGMA table_info(oauth_tokens)")
    tokens_columns = {row[1]: row[2] for row in cursor.fetchall()}
    
    if 'token_type' not in tokens_columns:
        issues.append("❌ Table 'oauth_tokens': Colonne 'token_type' manquante")
        print("   ❌ Colonne 'token_type' manquante")
    else:
        print(f"   ✅ Colonne 'token_type' présente ({tokens_columns['token_type']})")
    
    if 'access_token_encrypted' not in tokens_columns:
        issues.append("❌ Table 'oauth_tokens': Colonne 'access_token_encrypted' manquante")
        print("   ❌ Colonne 'access_token_encrypted' manquante")
    else:
        print(f"   ✅ Colonne 'access_token_encrypted' présente")
    
    # ============================================================
    # CHECK 3: Vérifier si des tokens existent
    # ============================================================
    print("\n📊 Vérification des tokens existants...")
    cursor.execute("SELECT COUNT(*) FROM oauth_tokens")
    token_count = cursor.fetchone()[0]
    print(f"   Nombre de tokens en DB: {token_count}")
    
    if token_count > 0:
        cursor.execute("""
            SELECT u.twitch_login, t.token_type, t.status 
            FROM oauth_tokens t 
            JOIN users u ON t.user_id = u.id
        """)
        for row in cursor.fetchall():
            login, token_type, status = row
            status_icon = "✅" if status == "valid" else "⚠️"
            print(f"   {status_icon} {login} [{token_type}] - {status}")
    
    # ============================================================
    # CHECK 4: Vérifier la clé de chiffrement
    # ============================================================
    print("\n🔑 Vérification de la clé de chiffrement...")
    key_path = Path(".kissbot.key")
    if key_path.exists():
        print(f"   ✅ Clé de chiffrement trouvée: {key_path}")
    else:
        issues.append("❌ Clé de chiffrement manquante: .kissbot.key")
        print(f"   ❌ Clé de chiffrement manquante: {key_path}")
    
    conn.close()
    
    # ============================================================
    # RÉSUMÉ
    # ============================================================
    print("\n" + "=" * 70)
    if not issues:
        print("✅ SCHÉMA COMPATIBLE - Le code peut être déployé")
        print("=" * 70)
        return True
    else:
        print("❌ SCHÉMA INCOMPATIBLE - Migration requise")
        print("=" * 70)
        print("\n🔧 Problèmes détectés:")
        for issue in issues:
            print(f"   {issue}")
        print("\n💡 Solution:")
        print("   1. Exécuter la migration DB: python database/migrate_to_v2.py")
        print("   2. Ou copier une DB compatible depuis dev")
        print("=" * 70)
        return False

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "kissbot.db"
    success = check_db_schema(db_path)
    sys.exit(0 if success else 1)
