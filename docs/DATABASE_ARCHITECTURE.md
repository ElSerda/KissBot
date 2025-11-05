# 🔐 Architecture Base de Données - KissBot

**Mode Database** : Stockage sécurisé des tokens OAuth avec chiffrement Fernet

---

## 📋 Table des Matières

- [Vue d'ensemble](#vue-densemble)
- [Installation](#installation)
- [Migration](#migration)
- [Architecture](#architecture)
- [Sécurité](#sécurité)
- [Utilisation](#utilisation)
- [Maintenance](#maintenance)
- [Troubleshooting](#troubleshooting)

---

## 🎯 Vue d'ensemble

Le mode Database permet de stocker les tokens OAuth de manière sécurisée dans une base SQLite avec chiffrement Fernet (AES-128-CBC + HMAC).

### Pourquoi passer en mode Database ?

**Avant (YAML)** :
```yaml
twitch:
  tokens:
    serda_bot:
      access_token: yrxyuiyffxiqsbc6cpr5y7utl7xmtd  # ⚠️ En clair !
      refresh_token: kwgxkn1ylz67vho6yoh6q88pj26xve9m4hwwa8ztcx82bd3n1z
```

**Après (Database)** :
```sql
-- Token chiffré avec Fernet
access_token_encrypted: Z0FBQUFBQnBDb29tamhTNGtwSnJ3WU9iLVgyS1Q2OHBtbmVrNUxlNkpTNWhaVlNRMHA3Tk8z...
```

### Avantages

✅ **Sécurité** : Tokens chiffrés au repos (AES-128-CBC + HMAC)  
✅ **Audit** : Logs de tous les événements (création, refresh, erreurs)  
✅ **Gestion** : Suivi des instances, crashes, refresh failures  
✅ **Performance** : SQLite WAL mode pour accès concurrent  
✅ **Maintenance** : Scripts de backup/migration/cleanup  

---

## 📦 Installation

### 1. Initialiser la base de données

```bash
# Créer la base avec le schéma complet
python database/init_db.py --db kissbot.db

# Vérifier la création
ls -lh kissbot.db
```

**Sortie attendue** :
```
2025-11-05 00:33:48 INFO     📦 Creating database: kissbot.db
2025-11-05 00:33:48 INFO     ✅ WAL mode enabled: wal
2025-11-05 00:33:48 INFO     ✅ Tables created: audit_log, config, instances, oauth_tokens, users
2025-11-05 00:33:48 INFO     ✅ Database initialized successfully: kissbot.db
```

### 2. Générer la clé de chiffrement

La clé est générée automatiquement au premier accès :

```bash
# La clé sera créée lors de la première utilisation
python scripts/migrate_yaml_to_db.py --dry-run
```

**⚠️ BACKUP IMPORTANT** :
```bash
# Sauvegarder la clé (sans elle, tokens inaccessibles !)
cp .kissbot.key .kissbot.key.backup
chmod 600 .kissbot.key.backup
```

---

## 🔄 Migration

### Migration depuis config.yaml

```bash
# 1. Test en dry-run (simulation)
python scripts/migrate_yaml_to_db.py --dry-run

# 2. Migration réelle (avec backup automatique)
python scripts/migrate_yaml_to_db.py

# 3. Vérifier les résultats
python scripts/migrate_yaml_to_db.py --dry-run  # Devrait voir "users_updated: 2"
```

### Migration depuis .tio.tokens.json (tokens actifs)

Si vos tokens YAML sont périmés, utilisez `.tio.tokens.json` :

```python
# Script de migration manuelle
import sys
sys.path.insert(0, '.')
from database.manager import DatabaseManager
import json

mgr = DatabaseManager()

# Lire les tokens actifs
with open('.tio.tokens.json', 'r') as f:
    tokens = json.load(f)

# Migrer chaque utilisateur
for user_id, data in tokens.items():
    # Récupérer l'utilisateur depuis la DB
    user = mgr.get_user(user_id)  # ou get_user_by_login()
    
    if user:
        mgr.store_tokens(
            user_id=user['id'],
            access_token=data['token'],
            refresh_token=data['refresh'],
            expires_in=14400  # 4 heures
        )
        print(f"✅ Updated tokens for user {user['twitch_login']}")
```

---

## 🏗️ Architecture

### Schéma de la base de données

```
┌─────────────────────────────────────────────────────────────┐
│                     KissBot Database                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐      ┌──────────────┐      ┌──────────────┐ │
│  │  users   │──────│ oauth_tokens │      │  instances   │ │
│  │          │ 1:1  │  (encrypted) │      │   (PIDs)     │ │
│  └──────────┘      └──────────────┘      └──────────────┘ │
│       │                                          │          │
│       │                                          │          │
│       └─────────────┬────────────────────────────┘          │
│                     │                                       │
│              ┌──────────────┐         ┌─────────┐          │
│              │  audit_log   │         │ config  │          │
│              │  (events)    │         │ (KV)    │          │
│              └──────────────┘         └─────────┘          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Tables détaillées

#### `users` - Utilisateurs Twitch

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    twitch_user_id TEXT NOT NULL UNIQUE,  -- ID Twitch (ex: "1209350837")
    twitch_login TEXT NOT NULL UNIQUE,     -- Login (ex: "serda_bot")
    display_name TEXT,                     -- Nom affiché (ex: "Serda_Bot")
    is_bot BOOLEAN DEFAULT 0,              -- Flag bot
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `oauth_tokens` - Tokens OAuth chiffrés

```sql
CREATE TABLE oauth_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    access_token_encrypted TEXT NOT NULL,   -- Token chiffré Fernet
    refresh_token_encrypted TEXT NOT NULL,  -- Refresh token chiffré
    scopes TEXT,                            -- JSON array des scopes
    expires_at TIMESTAMP NOT NULL,          -- Date d'expiration
    needs_reauth BOOLEAN DEFAULT 0,         -- Flag réautorisation nécessaire
    refresh_failures INTEGER DEFAULT 0,     -- Compteur échecs refresh
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

**Index** :
- `idx_oauth_user` : Lookup rapide par user_id
- `idx_oauth_expires` : Scan des tokens expirant bientôt

#### `instances` - Instances de bot actives

```sql
CREATE TABLE instances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER NOT NULL,           -- user_id du channel
    bot_user_id INTEGER NOT NULL,          -- user_id du bot
    status TEXT NOT NULL DEFAULT 'stopped', -- running, stopped, crashed
    pid INTEGER,                           -- PID du processus
    start_time TIMESTAMP,
    stop_time TIMESTAMP,
    last_heartbeat TIMESTAMP,
    crash_count INTEGER DEFAULT 0,
    config_overrides TEXT,                 -- JSON overrides
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (channel_id) REFERENCES users(id),
    FOREIGN KEY (bot_user_id) REFERENCES users(id)
);
```

#### `audit_log` - Logs d'audit

```sql
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,              -- user_created, tokens_refreshed, etc.
    user_id INTEGER,
    channel_id INTEGER,
    details TEXT,                          -- JSON avec détails
    severity TEXT DEFAULT 'info',          -- info, warning, error
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (channel_id) REFERENCES users(id)
);
```

**Index** :
- `idx_audit_timestamp` : Tri chronologique
- `idx_audit_event_type` : Filtrage par type
- `idx_audit_user` : Filtrage par utilisateur

#### `config` - Configuration système

```sql
CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Valeurs par défaut** :
```
encryption_key_version = 1           # Version de la clé Fernet
token_refresh_interval = 60          # Secondes avant expiration
health_check_interval = 30           # Secondes entre checks
max_crash_count = 3                  # Crashes avant désactivation
log_retention_days = 30              # Rétention des audit logs
```

---

## 🔐 Sécurité

### Chiffrement Fernet

**Algorithme** : AES-128-CBC + HMAC-SHA256

```python
from cryptography.fernet import Fernet

# Génération de clé (fait automatiquement)
key = Fernet.generate_key()  # 32 bytes (256 bits)
fernet = Fernet(key)

# Chiffrement
plaintext = "yrxyuiyffxiqsbc6cpr5y7utl7xmtd"
encrypted = fernet.encrypt(plaintext.encode())
# → Z0FBQUFBQnBDb29t...

# Déchiffrement
decrypted = fernet.decrypt(encrypted).decode()
# → "yrxyuiyffxiqsbc6cpr5y7utl7xmtd"
```

### Protection de la clé

**Permissions** :
```bash
# La clé est créée avec permissions 600 (owner read/write only)
ls -l .kissbot.key
# -rw------- 1 serda serda 44 Nov 5 00:33 .kissbot.key
```

**Backup** :
```bash
# Backup dans un endroit sûr (hors dépôt Git)
cp .kissbot.key ~/backups/kissbot-key-$(date +%Y%m%d).key
chmod 600 ~/backups/kissbot-key-*.key

# ⚠️ NE JAMAIS commit .kissbot.key dans Git !
# (déjà dans .gitignore)
```

### SQLite Security

**Configuration sécurisée** :
```python
# WAL mode pour accès concurrent
PRAGMA journal_mode = WAL;

# Timeout pour éviter les locks
PRAGMA busy_timeout = 5000;

# Mode synchronous normal (équilibre performance/sécurité)
PRAGMA synchronous = NORMAL;

# Contraintes FK activées
PRAGMA foreign_keys = ON;
```

---

## 💻 Utilisation

### Démarrage avec le mode Database

```bash
# Option 1 : Via kissbot.sh
./kissbot.sh start --use-db

# Option 2 : Via supervisor directement
python supervisor_v1.py --use-db

# Option 3 : Single channel pour test
python main.py --channel el_serda --use-db
```

### Vérification du status

```bash
# Status complet (tous les bots)
./kissbot.sh status

# Logs d'un channel spécifique
./kissbot.sh logs el_serda -f

# Vérifier la base de données
python -c "
from database.manager import DatabaseManager
mgr = DatabaseManager()
stats = mgr.get_stats()
print(f'Users: {stats[\"users_count\"]}')
print(f'Tokens: {stats[\"tokens_count\"]}')
print(f'Active instances: {stats[\"active_instances\"]}')
"
```

### DatabaseManager API

```python
from database.manager import DatabaseManager

# Initialisation
mgr = DatabaseManager(db_path="kissbot.db", key_file=".kissbot.key")

# === USERS ===
user = mgr.get_user_by_login("serda_bot")
user_id = mgr.create_user(
    twitch_user_id="1209350837",
    twitch_login="serda_bot",
    display_name="Serda_Bot",
    is_bot=True
)

# === TOKENS ===
# Stocker (chiffrement automatique)
mgr.store_tokens(
    user_id=user_id,
    access_token="yrxyuiyffxiqsbc6cpr5y7utl7xmtd",
    refresh_token="kwgxkn1ylz67vho6yoh6q88pj26xve9m4hwwa8ztcx82bd3n1z",
    expires_in=3600,  # secondes
    scopes=["chat:read", "chat:edit"]
)

# Récupérer (déchiffrement automatique)
tokens = mgr.get_tokens(user_id)
print(tokens['access_token'])  # Token en clair
print(tokens['expires_at'])    # Timestamp d'expiration

# Tokens expirant bientôt (pour refresh proactif)
expiring = mgr.get_tokens_needing_refresh(buffer_minutes=10)
for token in expiring:
    print(f"User {token['user_id']} expires at {token['expires_at']}")

# === INSTANCES ===
instance_id = mgr.register_instance(
    channel_login="el_serda",
    bot_login="serda_bot",
    pid=12345
)

mgr.update_instance_heartbeat(instance_id, status='running')
mgr.stop_instance(instance_id, crash=False)

# === AUDIT LOG ===
logs = mgr.get_audit_log(limit=10, event_type="tokens_refreshed")
for log in logs:
    print(f"[{log['timestamp']}] {log['event_type']}: {log['details']}")

# === CONFIG ===
interval = mgr.get_config("token_refresh_interval", default=60)
mgr.set_config("custom_setting", "value", description="Mon setting")

# === STATS ===
stats = mgr.get_stats()
print(f"Database size: {stats['db_size_bytes'] / 1024:.1f} KB")
```

---

## 🛠️ Maintenance

### Backups automatiques

Le script de migration crée des backups automatiquement :

```bash
# Backup avant migration
python scripts/migrate_yaml_to_db.py
# → kissbot.db.backup_20251105_004608

# Liste des backups
ls -lht kissbot.db.backup_*

# Restaurer un backup
cp kissbot.db.backup_20251105_004608 kissbot.db
```

### Backup manuel

```bash
# Backup complet (DB + WAL + clé)
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p backups/$DATE
cp kissbot.db backups/$DATE/
cp kissbot.db-wal backups/$DATE/ 2>/dev/null || true
cp kissbot.db-shm backups/$DATE/ 2>/dev/null || true
cp .kissbot.key backups/$DATE/
tar -czf backups/kissbot-backup-$DATE.tar.gz backups/$DATE/
echo "✅ Backup créé: backups/kissbot-backup-$DATE.tar.gz"
```

### Nettoyage des logs anciens

```python
from database.manager import DatabaseManager

mgr = DatabaseManager()

# Supprimer les logs de plus de 30 jours
deleted = mgr.cleanup_old_logs(days=30)
print(f"✅ Supprimé {deleted} logs d'audit anciens")
```

### Optimisation

```bash
# Compacter la base SQLite
sqlite3 kissbot.db "VACUUM;"

# Analyser pour optimiser les index
sqlite3 kissbot.db "ANALYZE;"

# Checkpoint WAL (flusher vers DB principale)
sqlite3 kissbot.db "PRAGMA wal_checkpoint(TRUNCATE);"
```

---

## 🔍 Troubleshooting

### Problème : Token invalide

```bash
# Symptôme
❌ Failed to set user authentication: invalid access token

# Diagnostic
python -c "
from database.manager import DatabaseManager
mgr = DatabaseManager()
user = mgr.get_user_by_login('serda_bot')
tokens = mgr.get_tokens(user['id'])
print(f'Access token: {tokens[\"access_token\"][:20]}...')
print(f'Expires at: {tokens[\"expires_at\"]}')
print(f'Needs reauth: {tokens[\"needs_reauth\"]}')
"

# Solution : Re-migrer depuis .tio.tokens.json (tokens actifs)
# Voir section Migration ci-dessus
```

### Problème : Clé de chiffrement perdue

```bash
# Symptôme
❌ Failed to decrypt tokens for user 1: Invalid token

# Solution : AUCUNE (tokens inaccessibles sans clé)
# Prévention : TOUJOURS sauvegarder .kissbot.key !

# Recréer la base depuis les tokens YAML
rm kissbot.db .kissbot.key
python database/init_db.py --db kissbot.db
python scripts/migrate_yaml_to_db.py
```

### Problème : Database locked

```bash
# Symptôme
sqlite3.OperationalError: database is locked

# Cause : Process concurrent ou timeout
# Solution : Vérifier les processus
ps aux | grep "main.py\|supervisor"

# Forcer checkpoint WAL
sqlite3 kissbot.db "PRAGMA wal_checkpoint(RESTART);"
```

### Problème : Trop de refresh failures

```python
# Diagnostic
from database.manager import DatabaseManager
mgr = DatabaseManager()

# Vérifier les tokens en échec
tokens = mgr.get_tokens_needing_refresh(buffer_minutes=999999)
for t in tokens:
    if t['refresh_failures'] >= 3 or t['needs_reauth']:
        print(f"⚠️ User {t['user_id']}: {t['refresh_failures']} failures, needs_reauth={t['needs_reauth']}")

# Solution : Réautoriser manuellement via Twitch OAuth flow
```

### Debug mode

```python
# Activer les logs SQL
import logging
logging.basicConfig(level=logging.DEBUG)

from database.manager import DatabaseManager
mgr = DatabaseManager()  # Verra tous les SQL queries
```

---

## 📚 Ressources

### Fichiers clés

```
database/
├── __init__.py           # Module init
├── schema.sql            # Schéma complet SQLite
├── crypto.py             # TokenEncryptor (Fernet)
├── manager.py            # DatabaseManager (API principale)
└── init_db.py            # Script d'initialisation

scripts/
└── migrate_yaml_to_db.py # Script de migration

.kissbot.key              # ⚠️ Clé de chiffrement (À SAUVEGARDER !)
kissbot.db                # Base de données SQLite
kissbot.db-wal            # Write-Ahead Log (WAL)
kissbot.db-shm            # Shared Memory
```

### Commandes utiles

```bash
# Inspection directe de la DB
sqlite3 kissbot.db

# Liste des tables
.tables

# Schema d'une table
.schema oauth_tokens

# Requêtes
SELECT twitch_login, is_bot FROM users;
SELECT COUNT(*) FROM audit_log WHERE event_type = 'tokens_refreshed';

# Export en CSV
.mode csv
.output users.csv
SELECT * FROM users;
.quit
```

---

## ✅ Checklist Migration

- [ ] Backup de `config.yaml`
- [ ] Backup de `.tio.tokens.json`
- [ ] Initialisation de la DB : `python database/init_db.py`
- [ ] Migration : `python scripts/migrate_yaml_to_db.py`
- [ ] Backup de `.kissbot.key` (⚠️ CRITIQUE !)
- [ ] Test : `python main.py --channel test --use-db`
- [ ] Vérification connexion IRC
- [ ] Déploiement : `./kissbot.sh start --use-db`
- [ ] Monitoring : `./kissbot.sh status`
- [ ] Backup régulier de la DB + clé

---

## 🚀 Next Steps

**Fonctionnalités futures** :

1. **Token Refresh Proactif** : Worker qui refresh les tokens avant expiration
2. **EventSub Pool** : Gestion optimisée des connexions EventSub
3. **Rotation de clé** : Support de rotation de la clé de chiffrement
4. **Réplication** : Backup automatique vers S3/cloud storage
5. **Monitoring avancé** : Dashboard Grafana avec métriques DB

---

**Questions ou problèmes ?** Ouvre une issue sur GitHub ! 🐛
