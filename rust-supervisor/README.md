# KissBot Supervisor (Rust)

**Port Rust du supervisor Python** - Gestion multi-process ultra-performante.

## 🚀 Performance

**vs Python Supervisor** :
- **RAM** : 5 MB (vs 100 MB Python)
- **CPU** : <0.5% idle (vs 2-3% Python)
- **Startup** : <50ms (vs 500ms Python)
- **Binary** : 1.1 MB standalone (vs 200+ MB venv Python)

## ✨ Features

- ✅ **Multi-process management** : 1 process par channel
- ✅ **EventSub Hub support** : Mode hub ou direct
- ✅ **Health checks** : Auto-restart des bots crashés
- ✅ **Signal handling** : SIGTERM/SIGINT graceful shutdown
- ✅ **Hub-first startup** : Hub démarre avant les bots
- ✅ **Status monitoring** : Uptime, PID, restart count
- ✅ **Database mode** : Tokens depuis DB ou YAML

## 📦 Build

```bash
# Build release optimisé
cargo build --release

# Binary dans target/release/kissbot-supervisor
```

## 🎯 Usage

### Mode YAML (tokens dans config.yaml)
```bash
./target/release/kissbot-supervisor \
    --config config/config.yaml
```

### Mode Database (tokens dans kissbot.db)
```bash
./target/release/kissbot-supervisor \
    --config config/config.yaml \
    --use-db \
    --db kissbot.db
```

### Mode EventSub Hub (1 WebSocket partagé)
```bash
# Démarrer avec Hub centralisé
./target/release/kissbot-supervisor \
    --config config/config.yaml \
    --use-db \
    --db kissbot.db \
    --enable-hub \
    --hub-socket /tmp/kissbot_hub.sock
```

### Arguments disponibles

| Argument | Description | Default |
|----------|-------------|---------|
| `--config <path>` | Chemin config.yaml | `config/config.yaml` |
| `--use-db` | Utiliser DB pour tokens | Off |
| `--db <path>` | Chemin database | `kissbot.db` |
| `--enable-hub` | Activer EventSub Hub | Off |
| `--hub-socket <path>` | Socket IPC Hub | `/tmp/kissbot_hub.sock` |

## 🏗️ Architecture

```
KissBot Supervisor (Rust 1.1 MB)
├─ HubProcess (si --enable-hub)
│  └─ Python eventsub_hub.py (100 MB)
│
└─ BotProcess[] (1 par channel)
   └─ Python main.py --channel <name> (50 MB chacun)
```

**Ordre de démarrage** :
1. Hub (si enabled) → attend 3s
2. Bots (séquentiellement, 500ms entre chaque)

**Ordre d'arrêt** :
1. Bots → SIGTERM (timeout 10s)
2. Hub → SIGTERM (timeout 10s)

## 📊 Status Display

```
==================================================================================
KissBot Supervisor (Rust) - Status
==================================================================================
🌐 EventSub Hub:
     Status: 🟢 RUNNING    PID 12345    Uptime: 3600s     Restarts: 0
     Socket: /tmp/kissbot_hub.sock

🤖 Bots:
     el_serda            🟢 RUNNING    PID 12346    Uptime: 3598s     Restarts: 0
     randomstreamer      🟢 RUNNING    PID 12347    Uptime: 3598s     Restarts: 1
==================================================================================
```

## ⚙️ Health Checks

**Auto-restart** :
- Vérifie tous les 2s si processes tournent
- Restart automatique si crash détecté
- Hub redémarre AVANT les bots (priorité)

**Health check interval** : 30s (configurable dans code)

## 🔄 Comparison Python vs Rust

| Feature | Python Supervisor | Rust Supervisor |
|---------|------------------|-----------------|
| RAM usage | ~100 MB | **5 MB** ✅ |
| CPU idle | 2-3% | **<0.5%** ✅ |
| Startup time | 500ms | **<50ms** ✅ |
| Binary size | 200+ MB (venv) | **1.1 MB** ✅ |
| Health checks | ✅ | ✅ |
| Auto-restart | ✅ | ✅ |
| Hub support | ✅ | ✅ |
| Interactive CLI | ✅ | ❌ (TODO) |
| Command listener | ✅ | ❌ (TODO) |

## 🚧 TODO

- [ ] Interactive CLI (readline-based)
- [ ] Command listener (pids/supervisor.cmd)
- [ ] Metrics logging (JSON)
- [ ] Systemd integration
- [ ] Bot en Rust (remplacer Python main.py)

## 🎯 Next Step : Bot Rust

Le supervisor Rust est prêt. Prochaine étape : **porter le bot individuel en Rust** pour gagner 12x RAM :

**Current** :
- Supervisor Rust : 5 MB
- Hub Python : 100 MB
- 30 bots Python : 1500 MB (50 MB × 30)
- **Total : 1605 MB**

**Target** :
- Supervisor Rust : 5 MB
- Hub Python : 100 MB (OK)
- 30 bots Rust : 120 MB (4 MB × 30) ✨
- **Total : 225 MB** (7x moins!)

---

**Made with 🦀 Rust**
