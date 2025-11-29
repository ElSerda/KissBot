# 🚀 Migration KissBot vers VPS

## ⚠️ Fichiers critiques à NE PAS oublier

Ces fichiers **NE SONT PAS** dans git et doivent être copiés manuellement :

### 1. `.kissbot.key` (CRITIQUE)
- **Emplacement dev** : racine du projet
- **Contenu** : Clé de chiffrement Fernet (32 bytes base64)
- **Sans ce fichier** : Impossible de déchiffrer les tokens OAuth
- **Backup** : Sauvegardez-le dans un gestionnaire de secrets !

### 2. `kissbot.db` (CRITIQUE)
- **Emplacement dev** : racine du projet
- **Contenu** : Base SQLite avec tokens OAuth chiffrés
- **Sans ce fichier** : Tous les bots échoueront à se connecter
- **Taille** : ~100-500 KB

### 3. `config/config.yaml` (CRITIQUE)
- **Emplacement dev** : `config/config.yaml`
- **Contenu** : Clés API (OpenAI, Steam, RAWG, IGDB, etc.)
- **Sans ce fichier** : Bot démarre mais fonctionnalités limitées

---

## 📋 Procédure de migration (étape par étape)

### Sur ta machine de dev

```bash
# 1. Créer une archive des fichiers sensibles
cd ~/Project/KissBot-standalone
tar -czf kissbot-secrets.tar.gz .kissbot.key kissbot.db config/config.yaml

# 2. Copier sur le VPS (remplace USER@VPS_IP)
scp kissbot-secrets.tar.gz USER@VPS_IP:/tmp/

# 3. (Optionnel) Supprimer l'archive locale
rm kissbot-secrets.tar.gz
```

### Sur le VPS

```bash
# 1. Pull le code depuis git
cd /opt/  # ou ton répertoire préféré
git clone https://github.com/ElSerda/KissBot-standalone.git
cd KissBot-standalone

# 2. Extraire les fichiers sensibles
tar -xzf /tmp/kissbot-secrets.tar.gz
rm /tmp/kissbot-secrets.tar.gz

# 3. Vérifier que tout est là
ls -lh .kissbot.key kissbot.db config/config.yaml

# 4. Lancer le script de migration
bash scripts/migrate_to_vps.sh

# 5. Démarrer le bot
./kissbot.sh start

# 6. Vérifier le statut
./kissbot.sh status
```

---

## 🔒 Sécurité VPS

### Permissions correctes
```bash
chmod 600 .kissbot.key          # Lecture seule propriétaire
chmod 600 kissbot.db            # Lecture seule propriétaire
chmod 600 config/config.yaml    # Lecture seule propriétaire
```

### Backup automatique (recommandé)
```bash
# Ajouter à crontab (backup quotidien)
0 3 * * * cd /opt/KissBot-standalone && tar -czf ~/backups/kissbot-$(date +\%Y\%m\%d).tar.gz .kissbot.key kissbot.db config/config.yaml
```

---

## 🐛 Troubleshooting

### Erreur: "no such table: users"
**Cause** : `kissbot.db` manquant ou corrompu  
**Solution** :
```bash
# Recréer la DB depuis zéro
python database/init_db.py --db kissbot.db
python scripts/migrate_yaml_to_db.py
```

### Erreur: "Invalid token"
**Cause** : `.kissbot.key` incorrect ou tokens expirés  
**Solution** :
```bash
# Régénérer les tokens OAuth
python scripts/oauth_flow.py
```

### Erreur: "Cannot connect to Hub"
**Cause** : EventSub Hub pas démarré ou socket bloqué  
**Solution** :
```bash
rm -f /tmp/kissbot_hub.sock
./kissbot.sh restart
```

---

## 📝 Checklist finale

- [ ] `.kissbot.key` copié et permissions 600
- [ ] `kissbot.db` copié et permissions 600
- [ ] `config/config.yaml` copié et permissions 600
- [ ] `kissbot-venv` créé et dépendances installées
- [ ] Moteur Rust compilé (`maturin develop`)
- [ ] Bot démarre sans erreur (`./kissbot.sh start`)
- [ ] Status OK avec 3+ bots running
- [ ] Logs propres (pas d'ERROR)

---

## 🆘 Support

Si problème persistant :
1. Vérifier les logs : `./kissbot.sh logs el_serda`
2. Vérifier le supervisor : `tail -f supervisor.log`
3. Vérifier le Hub : `tail -f logs/eventsub_hub.log`
