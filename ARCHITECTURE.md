# 🏗️ KissBot Architecture

**Version**: V4.0  
**Date**: 16 novembre 2025  
**Statut**: Production Ready

---

## 📊 Vue d'ensemble

KissBot est un bot Twitch multi-channel avec architecture hybride **Python + Rust** pour des performances optimales.

```
┌─────────────────────────────────────────────────────────────────┐
│                         KissBot V4                              │
│                    (Python + Rust Hybrid)                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   IRC Client │  │ Helix API    │  │ EventSub WS  │         │
│  │   (Python)   │  │ (Read-Only)  │  │ (Real-time)  │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
│         │                 │                  │                  │
│         └─────────────────┼──────────────────┘                  │
│                           ▼                                     │
│                  ┌─────────────────┐                           │
│                  │   MessageBus    │                           │
│                  │  (Event-Driven) │                           │
│                  └────────┬────────┘                           │
│                           │                                     │
│        ┌──────────────────┼──────────────────┐                │
│        ▼                  ▼                   ▼                 │
│  ┌───────────┐   ┌──────────────┐   ┌──────────────┐         │
│  │ Message   │   │  Analytics   │   │   Stream     │         │
│  │ Handler   │   │  Handler     │   │  Announcer   │         │
│  └─────┬─────┘   └──────────────┘   └──────────────┘         │
│        │                                                        │
│        ├─────► Commands (!gi, !gc, !ask, etc.)                │
│        │                                                        │
│        └─────► 🦀 Rust Game Engine (cache + search)           │
│                     ↓ fallback                                 │
│                🐍 Python GameLookup (RAWG/Steam/IGDB)         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

External Services:
  🐉 DRAKON (Rust) - Fuzzy matching engine (port 8000)
  💾 SQLite - Cache persistent (kissbot.db)
  🎮 Steam API - Metadata de jeux
  📊 RAWG API - Ratings et descriptions
  🎯 IGDB API - Données enrichies
  🤖 OpenAI GPT - Intelligence conversationnelle
```

---

## 🔧 Stack Technique

### Core (Python)
- **Python 3.12+** - Runtime principal
- **asyncio** - Programmation asynchrone
- **twitchAPI** - Intégration Twitch officielle
- **httpx** - Client HTTP async
- **SQLite3** - Base de données cache

### Performance (Rust)
- **kissbot-game-engine** - Moteur de recherche de jeux (PyO3)
- **DRAKON** - Fuzzy matching ultra-rapide
- **Tokio** - Runtime async Rust
- **Reqwest** - Client HTTP Rust

### APIs Externes
- **Twitch IRC** - Chat temps réel
- **Twitch Helix** - API REST Twitch
- **Twitch EventSub** - Webhooks temps réel
- **Steam Web API** - Métadonnées jeux
- **RAWG API** - Base de données jeux
- **IGDB API** - Informations enrichies
- **OpenAI GPT-4** - Intelligence conversationnelle

---

## 📁 Structure du Projet

```
KissBot-standalone/
├── main.py                      # Point d'entrée principal
├── config/
│   ├── config.yaml             # Configuration principale
│   └── enhanced_patterns.yaml  # Patterns LLM
│
├── core/                       # Composants centraux
│   ├── message_bus.py         # Event bus (pub/sub)
│   ├── message_handler.py     # Handler de commandes
│   ├── analytics_handler.py   # Métriques et analytics
│   ├── chat_logger.py         # Logs de chat
│   ├── stream_announcer.py    # Annonces stream
│   └── system_monitor.py      # Monitoring système
│
├── backends/                   # Backends de données
│   ├── game_lookup_rust.py    # 🦀 Wrapper Rust (NOUVEAU)
│   ├── game_lookup.py         # 🐍 Fallback Python enrichi
│   ├── llm_handler.py         # Handler OpenAI GPT
│   └── music_cache.py         # Cache musique
│
├── kissbot-game-engine/        # 🦀 Moteur Rust
│   ├── src/
│   │   ├── engine.rs          # Moteur principal
│   │   ├── cache.rs           # Cache SQLite
│   │   ├── providers/         # Steam, IGDB, RAWG
│   │   └── ranking/           # DRAKON + Rapidfuzz
│   ├── python.rs              # Bindings PyO3
│   └── Cargo.toml             # Dépendances Rust
│
├── DRAKON/rust/                # 🐉 Fuzzy matching
│   ├── target/release/
│   │   └── drakon-server      # Binary serveur HTTP
│   ├── start_drakon.sh        # Démarrer DRAKON
│   ├── stop_drakon.sh         # Arrêter DRAKON
│   └── status_drakon.sh       # Statut DRAKON
│
├── database/
│   ├── manager.py             # DatabaseManager
│   └── schema.sql             # Schéma SQLite
│
├── twitchapi/                  # Intégration Twitch
│   ├── auth_manager.py        # Gestion tokens OAuth
│   ├── transports/
│   │   ├── irc_client.py     # Client IRC
│   │   ├── helix_readonly.py # API Helix
│   │   └── eventsub_client.py # EventSub WebSocket
│   └── monitors/
│       └── stream_monitor.py  # Monitoring streams
│
├── intelligence/               # IA conversationnelle
│   ├── core.py                # Extraction mentions
│   ├── synapses/              # Providers LLM
│   └── reflexes/              # Réponses rapides
│
├── commands/                   # Système de commandes
│   ├── user_commands/         # Commandes publiques
│   ├── mod_commands/          # Commandes mods
│   └── admin_commands/        # Commandes admin
│
├── logs/                       # Logs hiérarchiques
│   └── broadcast/
│       └── {channel}/
│           ├── instance.log   # Bot principal
│           ├── chat.log       # Messages chat
│           ├── commands.log   # Exécution commandes
│           └── system.log     # Métriques système
│
└── pids/                       # Fichiers de statut
    └── {channel}.{status}     # ready, irc, eventsub
```

---

## ⚡ Performance

### Game Engine (Rust vs Python)

| Opération | Python | Rust | Gain |
|-----------|--------|------|------|
| Cache hit | 14ms | 0.15ms | **93x** |
| Construction objet | 3.3µs | 0.135µs | **25x** |
| Throughput | 71 req/s | 202 req/s | **2.8x** |
| Binary size | N/A | 7.4 MB | Compact |

### Hybrid Strategy (Actuel)

```python
# 1. Try Rust cache (ultra-fast)
result = rust_engine.search(query)  # 0.15ms if cached

# 2. Fallback Python enrichi si cache vide
if not result or not result.has_enriched_data():
    result = python_lookup.search_game(query)  # 50-3000ms with APIs
```

**Résultat**: 
- ✅ Cache hit: **0.15ms** (Rust)
- ✅ Cache miss: **50-3000ms** (Python + APIs)
- ✅ Données enrichies complètes (rating, summary, platforms, etc.)

---

## 🔄 Flow de Recherche de Jeu

```
User: !gi vampire survivors
         │
         ▼
  MessageHandler
         │
         ├─► 1. Try Rust Cache
         │   └─► kissbot_game_engine.search()
         │       ├─► Cache SQLite (0.15ms)
         │       └─► ✅ HIT → Return GameResult
         │
         ├─► 2. Fallback Python (si cache vide/incomplet)
         │   └─► game_lookup.py.search_game()
         │       ├─► Steam API (500ms)
         │       ├─► RAWG API (200ms)
         │       ├─► IGDB API (800ms)
         │       ├─► 🐉 DRAKON ranking (1ms)
         │       ├─► Enrichissement (500ms)
         │       └─► Cache → SQLite
         │
         ▼
  format_result()
         │
         ▼
  IRC Send
         │
         ▼
  serda_bot: 🎮 Vampire Survivors (2022)...
```

---

## 🚀 Démarrage

### Prérequis

```bash
# Python dependencies
pip install -r requirements.txt

# Rust toolchain
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Maturin (Python-Rust bindings)
pip install maturin
```

### Compilation Rust Game Engine

```bash
cd kissbot-game-engine
maturin develop --features python --release
```

### Démarrage DRAKON

```bash
cd DRAKON/rust
./start_drakon.sh
```

### Lancement Bot

```bash
# Single channel
python main.py --channel el_serda

# Database tokens
python main.py --channel el_serda --use-db --db kissbot.db
```

---

## 📊 Monitoring

### Logs Hiérarchiques

```bash
logs/broadcast/{channel}/
├── instance.log    # Main bot logs
├── chat.log       # All chat messages
├── commands.log   # Command executions
└── system.log     # CPU/RAM metrics
```

### Métriques Temps Réel

```python
analytics.get_stats()
{
    "game_searches": 1234,
    "game_cache_hits": 1200,
    "game_cache_misses": 34,
    "game_cache_hit_rate": "97.2%",
    "game_avg_latency_ms": "0.18ms"
}
```

### System Monitor

- CPU usage
- RAM usage  
- Thread count
- Logged to `system.log` every 60s

---

## 🔐 Configuration

### config.yaml

```yaml
bot:
  name: "serda_bot"
  channels:
    - "el_serda"

apis:
  rawg_key: "your_rawg_key"
  steam_key: "your_steam_key"
  openai_key: "your_openai_key"
  
  igdb:
    client_id: "your_client_id"
    client_secret: "your_client_secret"

database:
  path: "kissbot.db"
  
monitoring:
  method: "auto"  # auto, eventsub, polling
  polling_interval: 60
```

---

## 🎯 Commandes Disponibles

### Publiques
- `!ping` - Test du bot
- `!uptime` - Temps de fonctionnement
- `!stats` - Statistiques système
- `!help` - Liste des commandes
- `!gi <game>` - Info sur un jeu
- `!gc` - Jeu en cours du streamer
- `!ask <question>` - Question au LLM
- `@mention` - Conversation avec IA

### Mods/Admins
- `!decoherence [name]` - Cleanup cache
- `!kisscharity <msg>` - Broadcast multi-channel

---

## 🐛 Debugging

### Vérifier DRAKON

```bash
cd DRAKON/rust
./status_drakon.sh
```

### Tester Game Engine

```python
import kissbot_game_engine

engine = kissbot_game_engine.GameEngine('kissbot.db')
result = engine.search('vampire survivors', max_results=5)
print(f"Game: {result['game']['name']}")
print(f"Score: {result['score']}%")
print(f"Ranking: {result['ranking_method']}")
```

### Logs en Direct

```bash
tail -f logs/broadcast/el_serda/instance.log
```

---

## 📈 Prochaines Étapes

### Court Terme
- [ ] Nettoyer fichiers legacy
- [ ] Documentation API complète
- [ ] Tests d'intégration CI/CD

### Moyen Terme
- [ ] Support multi-providers IGDB/RAWG dans Rust
- [ ] Cache TTL et eviction policy
- [ ] Metrics dashboard (Grafana)

### Long Terme
- [ ] HTTP API pour autres services
- [ ] Clustering multi-instances
- [ ] Machine learning pour ranking

---

## 📄 Licence

Copyright (c) 2024-2025 ElSerda  
Licence propriétaire "Source-Disponible" - Voir LICENSE et EULA_FR.md
