# 🤖 KissBot AI Coding Agent Instructions

Bienvenue dans KissBot ! Ce guide est destiné aux agents IA pour une productivité immédiate sur ce projet Twitch bot hybride Python/Rust.

## 🏗️ Architecture & Composants
- **Entrée principale** : `main.py` (mono-process) ou `supervisor_v1.py` (multi-process)
- **Multi-process** : Utilisez `kissbot.sh` pour gérer les instances (start/stop/status/logs)
- **EventSub Hub** : Centralise WebSocket Twitch, IPC via Unix sockets (`eventsub_hub.py`, `twitchapi/transports/hub_eventsub_client.py`)
- **Rust Game Engine** : Recherche ultra-rapide via `kissbot-game-engine/` (bindings PyO3)
- **Fallback Python** : `backends/game_lookup.py` pour enrichissement si cache Rust vide
- **Commandes** : Organisées par rôle dans `commands/` (`user_commands/`, `mod_commands/`, `admin_commands/`)
- **Logs** : Hiérarchiques par channel dans `logs/broadcast/{channel}/`
- **Database** : Tokens OAuth chiffrés en SQLite (`kissbot.db`, `.kissbot.key`)

## 🔧 Workflows Développeur
- **Mono-process** : `python main.py`
- **Multi-process** : `./kissbot.sh start` (voir aussi `status`, `logs`, `stop`)
- **Mode DB** : `./kissbot.sh start --use-db` (tokens chiffrés)
- **Rust Engine** :
  - Compiler : `cd kissbot-game-engine && maturin develop --features python --release`
  - Tester : voir exemple dans `ARCHITECTURE.md`
- **DRAKON Fuzzy** :
  - Démarrer : `cd DRAKON/rust && ./start_drakon.sh`
  - Statut : `./status_drakon.sh`
- **Logs live** : `tail -f logs/broadcast/{channel}/instance.log`

## 📚 Conventions & Patterns
- **Recherche de jeu** :
  1. Rust cache (`kissbot_game_engine.search()`)
  2. Fallback Python enrichi (`game_lookup.py.search_game()`)
  3. Résultat formaté et envoyé via IRC
- **Config** : `config/config.yaml` (tokens, clés API, channels)
- **Monitoring** : Métriques et logs dans `system.log`, analytics via `core/analytics_handler.py`
- **EventBus** : Communication interne via `core/message_bus.py`
- **Sécurité** : Clé `.kissbot.key` indispensable pour déchiffrer les tokens

## 🧠 Points d'attention
- **Ne modifiez jamais `.kissbot.key` ou la structure de `kissbot.db` sans migration**
- **Respectez la séparation Rust/Python pour la recherche de jeux**
- **Utilisez les scripts de migration pour passer du mode YAML au mode DB**
- **Consultez `ARCHITECTURE.md` et `README.md` pour les schémas et exemples précis**

## 📂 Fichiers clés
- `main.py`, `supervisor_v1.py`, `eventsub_hub.py`, `backends/game_lookup_rust.py`, `backends/game_lookup.py`, `kissbot-game-engine/`, `DRAKON/rust/`, `commands/`, `config/config.yaml`, `logs/broadcast/`, `kissbot.db`, `.kissbot.key`

---

Pour toute ambiguïté ou workflow non documenté, demandez à l'utilisateur de préciser ou consultez la documentation dans `docs/`.
