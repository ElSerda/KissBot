# 🚀 KissBot Stack - Scripts de Démarrage

## 📋 Vue d'ensemble

La stack KissBot se compose de **5 processus principaux** + **N processus bot** gérés par le supervisor.

---

## 🎯 Processus Principaux

### 1️⃣ **EventSub Hub** (Centralisateur WebSocket)
**Rôle**: Gère 1 seule connexion WebSocket Twitch pour tous les bots  
**Script**: `eventsub_hub.py`  
**Port**: N/A (Unix socket `/tmp/kissbot_hub.sock`)  
**Dépendances**: Base de données `kissbot.db`

```bash
# Démarrage
python3 eventsub_hub.py --config config/config.yaml --db kissbot.db

# Logs
tail -f eventsub_hub.log

# Status
ps aux | grep eventsub_hub.py
```

**Fonctionnalités**:
- 1 WebSocket pour tous les channels (limite Twitch: 3 transports)
- Multiplexage des subscriptions (stream.online, channel.update, etc.)
- Routage via IPC vers les bots
- Réconciliation automatique (desired vs active subscriptions)
- Rate limiting: 1-2 req/s avec jitter 150-300ms

---

### 2️⃣ **Supervisor** (Gestionnaire Multi-Process)
**Rôle**: Lance et surveille N processus bot (1 par channel)  
**Script**: `supervisor_v1.py`  
**Config**: `config/config.yaml` (mode YAML) ou DB (mode base de données)  
**Logs**: `supervisor.log` + `logs/{channel}.log` par bot

```bash
# Démarrage (mode YAML)
python3 supervisor_v1.py --config config/config.yaml

# Démarrage (mode DB)
python3 supervisor_v1.py --use-db --db kissbot.db

# Mode EventSub Hub
python3 supervisor_v1.py --eventsub=hub --hub-socket=/tmp/kissbot_hub.sock

# Commands
# stop {channel}  - Arrêter un bot spécifique
# start {channel} - Démarrer un bot spécifique
# restart {channel} - Redémarrer un bot
# list - Lister tous les bots
# quit - Arrêter le supervisor
```

**Fonctionnalités**:
- Process isolation: 1 process = 1 channel
- Auto-restart en cas de crash
- Logs séparés par channel (`logs/{channel}.log`)
- PID tracking (`pids/{channel}.pid`)
- Modes EventSub: `direct` (1 WS par bot), `hub` (multiplexé), `disabled`

---

### 3️⃣ **Bot Process** (Instance par Channel)
**Rôle**: Bot Twitch pour un channel spécifique  
**Script**: `main.py`  
**Logs**: `logs/{channel}.log`  
**PID**: `pids/{channel}.pid`

```bash
# Démarrage manuel (mode standalone)
python3 main.py --channel el_serda --config config/config.yaml

# Mode Hub EventSub
python3 main.py --channel el_serda --eventsub=hub --hub-socket=/tmp/kissbot_hub.sock

# Mode DB
python3 main.py --channel el_serda --use-db --db kissbot.db

# Logs
tail -f logs/el_serda.log
```

**Composants**:
- **IRC Client**: Chat messages (lecture/écriture)
- **Helix API**: User info, stream data
- **EventSub**: Events temps réel (stream.online, etc.)
- **MessageHandler**: Commandes (!gi, !gc, etc.)
- **StreamAnnouncer**: Annonces stream online/offline
- **SystemMonitor**: Métriques performance

---

### 4️⃣ **DRAKON Server** (Fuzzy Ranking Rust)
**Rôle**: API HTTP pour fuzzy matching avancé (Damerau-Levenshtein + NAHL)  
**Binaire**: `DRAKON/rust/target/release/drakon-server`  
**Port**: `8000`  
**Health**: `http://127.0.0.1:8000/health`

```bash
# Démarrage
cd DRAKON/rust
./start_drakon.sh

# Status
./status_drakon.sh

# Arrêt
./stop_drakon.sh

# Logs
tail -f /tmp/drakon.log

# Health check
curl http://127.0.0.1:8000/health
```

**Scripts de gestion**:
- `DRAKON/rust/start_drakon.sh` - Démarre le serveur (PID tracking)
- `DRAKON/rust/stop_drakon.sh` - Arrête proprement
- `DRAKON/rust/status_drakon.sh` - Status + health check

**Endpoints**:
- `GET /health` - Health check
- `POST /rank` - Fuzzy ranking (JSON: `{query, candidates, top_k}`)

**Performance**:
- 0.5-2ms par requête (100-275k candidats)
- Fallback: RapidFuzz en Python si DRAKON down

---

### 5️⃣ **Game Engine Rust** (Cache SQLite Ultra-Rapide)
**Rôle**: Cache de jeux avec recherche < 1ms  
**Binaire**: `kissbot-game-engine/target/release/game-engine-server` (optionnel)  
**Module Python**: `kissbot_game_engine` (PyO3)  
**Base de données**: `kissbot-game-engine/game_cache.db`

```bash
# Compilation du module Python
cd kissbot-game-engine
maturin develop --release --features python

# Test du serveur standalone (optionnel)
cd kissbot-game-engine
./start_server.sh  # Port 3030

# Test du module
python3 -c "import kissbot_game_engine; print(kissbot_game_engine.__version__)"
```

**Scripts**:
- `kissbot-game-engine/start_server.sh` - Démarre le serveur HTTP (optionnel)
- `kissbot-game-engine/test_server.sh` - Test du serveur

**Performance**:
- **Cache hit**: 0.08-0.12ms (SQLite Rust)
- **Cache miss**: 3-4s (fallback Python avec enrichment RAWG/IGDB/Steam)
- **Throughput**: 202.5 req/s

**Intégration**:
- Import: `from backends.game_lookup_rust import get_game_lookup`
- Hybride: Rust cache → fallback Python enrichment si données incomplètes

---

## 🔄 Ordre de Démarrage Recommandé

```bash
# 1. DRAKON Server (fuzzy ranking)
cd DRAKON/rust && ./start_drakon.sh

# 2. EventSub Hub (si mode hub)
python3 eventsub_hub.py --config config/config.yaml --db kissbot.db &

# 3. Supervisor (lance tous les bots)
python3 supervisor_v1.py --eventsub=hub --hub-socket=/tmp/kissbot_hub.sock

# Alternative: Bot unique (standalone)
python3 main.py --channel el_serda --eventsub=hub
```

---

## 🛠️ Scripts Utilitaires

### Gestion Base de Données
```bash
# Initialiser la DB
python3 database/init_db.py

# Migration game cache
python3 database/migrate_game_cache.py

# Migration Hub v1
python3 database/migrate_hub_v1.py

# Migration v4.0.1
python3 database/migrate_v4.0.1.py

# YAML → DB
python3 scripts/migrate_yaml_to_db.py
```

### Gestion Hub
```bash
# Hub control
python3 scripts/hub_ctl.py status
python3 scripts/hub_ctl.py reconcile
python3 scripts/hub_ctl.py cleanup
```

### Scripts de Lancement
```bash
# Lancement avec venv
./run_with_venv.sh

# Script principal (wrapper supervisor)
./kissbot.sh

# Backend switcher
./switch-backend.sh
```

### Tests
```bash
# Tests CI
./tests-ci/run_ci_tests.sh

# Test supervisor
./test_supervisor.sh

# Tests Rust
source kissbot-venv/bin/activate
python3 -m pytest test_rust_wrapper.py test_rust_integration.py -v
```

---

## 📊 Monitoring & Logs

### Logs Principaux
| Processus | Fichier Log |
|-----------|-------------|
| Supervisor | `supervisor.log` |
| EventSub Hub | `eventsub_hub.log` |
| Bot (el_serda) | `logs/el_serda.log` |
| DRAKON | `/tmp/drakon.log` |
| System Monitor | `system_monitor.log` |

### PIDs
```bash
# Supervisor
cat pids/supervisor.pid

# Bot par channel
cat pids/{channel}.pid

# DRAKON
cat /tmp/drakon.pid
```

### Metrics
```bash
# System monitor (temps réel)
tail -f system_monitor.log

# Analytics (via MessageBus)
# Intégré dans les logs du bot
grep "game.search" logs/el_serda.log
```

---

## 🔧 Configuration

### `config/config.yaml`
```yaml
twitch:
  client_id: "..."
  client_secret: "..."
  
channels:
  - name: "el_serda"
    oauth_token: "..."
    refresh_token: "..."
    
bot:
  prefix: "!"
  cooldown: 5
  
game_lookup:
  steam_api_key: "..."
  rawg_api_key: "..."
  igdb_client_id: "..."
  igdb_client_secret: "..."
```

### Base de Données `kissbot.db`
**Tables principales**:
- `channels` - Configuration channels
- `oauth_tokens` - Tokens OAuth refresh
- `desired_subscriptions` - Subscriptions EventSub voulues
- `active_subscriptions` - Subscriptions EventSub actives
- `hub_state` - État du Hub
- `game_cache` - Cache de jeux (legacy, avant Rust)

---

## 🏗️ Architecture Complète

```
┌─────────────────────────────────────────────────────────────────┐
│                        TWITCH API                               │
│  (IRC, Helix, EventSub WebSocket)                              │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ├─ EventSub WS (1 seule connexion)
                 │         │
                 ▼         ▼
         ┌───────────────────────┐
         │   EventSub Hub        │  eventsub_hub.py
         │   (Multiplexer)       │  Port: Unix socket
         └──────────┬────────────┘
                    │ IPC (Unix socket)
                    ├──────────┬──────────┬──────────┐
                    ▼          ▼          ▼          ▼
         ┌─────────────┬─────────────┬─────────────┬─────────────┐
         │   Bot #1    │   Bot #2    │   Bot #3    │   Bot #N    │
         │ (el_serda)  │ (channel2)  │ (channel3)  │ (channelN)  │
         │  main.py    │  main.py    │  main.py    │  main.py    │
         └──────┬──────┴──────┬──────┴──────┬──────┴──────┬──────┘
                │             │             │             │
                └─────────────┴─────────────┴─────────────┘
                              │
                              │ Managed by
                              ▼
                    ┌─────────────────────┐
                    │    Supervisor       │  supervisor_v1.py
                    │  (Process Manager)  │
                    └─────────────────────┘
                              │
                              │ Uses
                              ▼
         ┌────────────────────────────────────────────────┐
         │              Backends                          │
         ├────────────────────────────────────────────────┤
         │  • Game Lookup Rust (kissbot_game_engine)     │
         │    - PyO3 module (0.1ms cache hit)            │
         │    - Fallback Python (3-4s enrichment)        │
         │                                                │
         │  • DRAKON Server (Rust HTTP API)              │
         │    - Fuzzy ranking (0.5-2ms)                  │
         │    - Port 8000                                │
         │                                                │
         │  • LLM Handler (optional)                     │
         │  • Wikipedia Handler                          │
         └────────────────────────────────────────────────┘
                              │
                              │ Storage
                              ▼
         ┌────────────────────────────────────────────────┐
         │            Databases                           │
         ├────────────────────────────────────────────────┤
         │  • kissbot.db (SQLite)                        │
         │    - Channels, tokens, subscriptions          │
         │                                                │
         │  • game_cache.db (SQLite Rust)                │
         │    - Game metadata cache                      │
         └────────────────────────────────────────────────┘
```

---

## 🎮 Commandes Bot Disponibles

### Commandes Utilisateur
- `!gi <game>` - Info sur un jeu (cache Rust + enrichment)
- `!gc <game>` - Game choice (sélection multiple)
- `!8ball <question>` - Magic 8-ball
- `!joke` - Blague aléatoire
- `!hello` - Salutation
- `!uptime` - Uptime du bot

### Commandes Modérateur
- `!so <user>` - Shoutout
- `!title <new_title>` - Changer le titre du stream
- `!game <game_name>` - Changer la catégorie du stream

### Commandes Admin
- `!decoherence <game>` - Vider cache pour un jeu
- `!shutdown` - Arrêter le bot

---

## 🚨 Troubleshooting

### DRAKON ne répond pas
```bash
# Vérifier status
cd DRAKON/rust && ./status_drakon.sh

# Restart
./stop_drakon.sh && ./start_drakon.sh

# Logs
tail -f /tmp/drakon.log
```

### Bot crash loop
```bash
# Vérifier logs
tail -f logs/{channel}.log

# Vérifier supervisor
tail -f supervisor.log

# Restart manual
python3 supervisor_v1.py --eventsub=hub
```

### EventSub Hub déconnecté
```bash
# Vérifier logs
tail -f eventsub_hub.log

# Restart
pkill -f eventsub_hub.py
python3 eventsub_hub.py --config config/config.yaml --db kissbot.db &
```

### Cache Rust vide
```bash
# Importer données Python → Rust
cd kissbot-game-engine
cargo run --release --bin import_cache

# Vérifier DB
sqlite3 game_cache.db "SELECT COUNT(*) FROM games;"
```

---

## 📈 Performance Metrics

| Composant | Latence | Throughput |
|-----------|---------|------------|
| Game Engine (cache hit) | 0.08-0.12ms | 202.5 req/s |
| Game Engine (cache miss) | 3-4s | N/A (API rate limit) |
| DRAKON (fuzzy rank) | 0.5-2ms | 500-2000 req/s |
| IRC send message | 10-50ms | 20 msg/30s (Twitch limit) |
| EventSub Hub (routing) | < 5ms | 1000+ events/s |

---

## 📦 Dépendances

### Python
- `twitchAPI` - Twitch API wrapper
- `aiohttp` - HTTP async
- `websockets` - WebSocket client
- `pyyaml` - Config YAML
- `rapidfuzz` - Fuzzy matching (fallback DRAKON)
- `kissbot_game_engine` - Module Rust PyO3

### Rust
- `tokio` - Async runtime
- `axum` - HTTP server (DRAKON)
- `rusqlite` - SQLite bindings
- `pyo3` - Python bindings (game engine)
- `rapidfuzz` - Fuzzy matching (DRAKON)

---

## 🔐 Sécurité

- **Tokens OAuth**: Stockés dans `kissbot.db` (chiffrés recommandé)
- **API Keys**: Dans `config/config.yaml` (ne pas commit)
- **Unix Sockets**: Permissions 0600 (owner only)
- **DRAKON**: Bind 127.0.0.1 (localhost only)

---

## 📚 Documentation Complète

- `ARCHITECTURE.md` - Architecture technique détaillée
- `CLEANUP_GUIDE.md` - Guide de nettoyage projet
- `README.md` - Documentation utilisateur
- `CHANGELOG.md` - Historique des versions

---

**Version**: 4.0.1  
**Dernière mise à jour**: 16 novembre 2025  
**Auteur**: ElSerda
