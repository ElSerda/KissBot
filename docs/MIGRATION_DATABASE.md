# 🚀 Guide de Migration - Mode Database

**Guide rapide** pour migrer du mode YAML vers le mode Database avec tokens chiffrés.

---

## ⚡ Migration Express (5 minutes)

```bash
# 1. Backup de sécurité
cp config/config.yaml config/config.yaml.backup
cp .tio.tokens.json .tio.tokens.json.backup

# 2. Initialiser la base de données
python database/init_db.py --db kissbot.db

# 3. Migrer les tokens (dry-run d'abord)
python scripts/migrate_yaml_to_db.py --dry-run
python scripts/migrate_yaml_to_db.py

# 4. Backup de la clé de chiffrement (⚠️ CRITIQUE !)
cp .kissbot.key ~/.kissbot.key.backup
chmod 600 ~/.kissbot.key.backup

# 5. Test en single-channel
python main.py --channel el_serda --use-db

# 6. Si OK, déployer en production
./kissbot.sh stop
./kissbot.sh start --use-db
./kissbot.sh status
```

---

## 📋 Checklist Pré-Migration

- [ ] Python 3.11+ installé
- [ ] `pip install cryptography` (déjà dans requirements.txt)
- [ ] Backup de `config/config.yaml`
- [ ] Backup de `.tio.tokens.json` (si existe)
- [ ] Git commit de l'état actuel
- [ ] Espace disque suffisant (DB ~100KB)

---

## 🔍 Vérifications Post-Migration

### 1. Vérifier la base de données

```bash
# Vérifier que la DB existe
ls -lh kissbot.db

# Vérifier les tables
sqlite3 kissbot.db ".tables"
# Attendu: audit_log config instances oauth_tokens sqlite_sequence users

# Compter les utilisateurs
sqlite3 kissbot.db "SELECT COUNT(*) FROM users;"
# Attendu: 2 (ou plus selon vos tokens)

# Compter les tokens
sqlite3 kissbot.db "SELECT COUNT(*) FROM oauth_tokens;"
# Attendu: 2 (ou plus selon vos tokens)
```

### 2. Vérifier le chiffrement

```python
# Lancer ce script pour tester le déchiffrement
python -c "
from database.manager import DatabaseManager

mgr = DatabaseManager()
user = mgr.get_user_by_login('serda_bot')
if user:
    tokens = mgr.get_tokens(user['id'])
    print(f'✅ Access Token déchiffré: {tokens[\"access_token\"][:20]}...')
    print(f'✅ Expires at: {tokens[\"expires_at\"]}')
else:
    print('❌ User serda_bot not found in database')
"
```

### 3. Vérifier la connexion IRC

```bash
# Démarrer un seul bot
timeout 30 python main.py --channel el_serda --use-db 2>&1 | grep "Connecté"

# Attendu:
# ✅ Connecté à #el_serda → VIP 👑 | Rate: 100 msg/30s | Delay: 0.43s
```

### 4. Vérifier le multi-process

```bash
# Démarrer tous les bots
./kissbot.sh start --use-db

# Attendre 10 secondes
sleep 10

# Vérifier le status
./kissbot.sh status

# Attendu: 6 bot(s) running (ou votre nombre de channels)
```

---

## 🔐 Sécurité

### Backup de la clé

**⚠️ LA CLÉ `.kissbot.key` EST CRITIQUE !**

Sans elle, **impossible** de déchiffrer les tokens. Vous perdriez l'accès !

```bash
# Backup local
cp .kissbot.key ~/.kissbot.key.backup

# Backup sur un autre disque/serveur
scp .kissbot.key user@backup-server:/secure/backups/

# Backup chiffré avec GPG
gpg --symmetric --cipher-algo AES256 .kissbot.key
# → .kissbot.key.gpg (protégé par mot de passe)
```

### Permissions

```bash
# Vérifier les permissions (doit être 600)
ls -l .kissbot.key
# -rw------- 1 serda serda 44 Nov 5 00:33 .kissbot.key

# Corriger si nécessaire
chmod 600 .kissbot.key
```

---

## 🔄 Retour en arrière (Rollback)

Si vous rencontrez des problèmes :

```bash
# 1. Arrêter les bots
./kissbot.sh stop

# 2. Supprimer la DB et la clé
rm kissbot.db kissbot.db-wal kissbot.db-shm .kissbot.key

# 3. Restaurer le config YAML
cp config/config.yaml.backup config/config.yaml
cp .tio.tokens.json.backup .tio.tokens.json

# 4. Redémarrer en mode YAML
./kissbot.sh start

# → Retour à l'état d'avant migration
```

---

## 🐛 Problèmes Courants

### Token invalide après migration

**Cause** : Tokens dans `config.yaml` périmés

**Solution** : Migrer depuis `.tio.tokens.json` (tokens actifs)

```python
import sys, json
sys.path.insert(0, '.')
from database.manager import DatabaseManager

mgr = DatabaseManager()

with open('.tio.tokens.json', 'r') as f:
    tokens = json.load(f)

for user_id, data in tokens.items():
    user = mgr.get_user(user_id)
    if user:
        mgr.store_tokens(
            user_id=user['id'],
            access_token=data['token'],
            refresh_token=data['refresh'],
            expires_in=14400
        )
        print(f"✅ Updated {user['twitch_login']}")
```

### Database locked

**Cause** : Process concurrent ou timeout

**Solution** :
```bash
# Vérifier les processus
ps aux | grep "main.py\|supervisor"

# Killer si nécessaire
./kissbot.sh stop

# Checkpoint WAL
sqlite3 kissbot.db "PRAGMA wal_checkpoint(RESTART);"
```

### Clé perdue

**Solution** : AUCUNE (tokens inaccessibles)

**Prévention** : TOUJOURS sauvegarder `.kissbot.key` !

Si perdue, recréer la base :
```bash
rm kissbot.db .kissbot.key
python database/init_db.py
python scripts/migrate_yaml_to_db.py
# Nouvelle clé générée
```

---

## 📊 Monitoring

### Stats de la base

```python
from database.manager import DatabaseManager

mgr = DatabaseManager()
stats = mgr.get_stats()

print(f"Users: {stats['users_count']}")
print(f"Tokens: {stats['tokens_count']}")
print(f"Active instances: {stats['active_instances']}")
print(f"Audit logs: {stats['audit_logs_count']}")
print(f"DB size: {stats['db_size_bytes'] / 1024:.1f} KB")
```

### Derniers événements

```python
from database.manager import DatabaseManager

mgr = DatabaseManager()
logs = mgr.get_audit_log(limit=10)

for log in logs:
    print(f"[{log['timestamp']}] {log['event_type']} - {log['severity']}")
```

### Tokens expirant bientôt

```python
from database.manager import DatabaseManager

mgr = DatabaseManager()
expiring = mgr.get_tokens_needing_refresh(buffer_minutes=10)

for token in expiring:
    print(f"⚠️ User {token['user_id']} expires at {token['expires_at']}")
```

---

## ✅ C'est tout !

Votre bot est maintenant en mode Database avec tokens chiffrés ! 🎉

**Prochaines étapes** :
- Monitorer les logs : `./kissbot.sh logs el_serda -f`
- Vérifier le status : `./kissbot.sh status`
- Sauvegarder régulièrement : `.kissbot.key` + `kissbot.db`

**Support** : Voir `docs/DATABASE_ARCHITECTURE.md` pour documentation complète
