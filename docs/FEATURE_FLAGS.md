# 🎛️ Feature Flags & Memory Profiler

## Vue d'ensemble

KissBot intègre un système de **feature flags** et de **profiling mémoire** pour :
- Activer/désactiver des fonctionnalités sans modifier le code
- Économiser de la RAM en désactivant les features non utilisées
- Mesurer la consommation mémoire de chaque composant

## Architecture

```
core/
├── feature_manager.py    # Feature flags (enum + manager)
├── memory_profiler.py    # Profiling RAM/CPU
config/
└── config.yaml           # Section `features:` pour activer/désactiver
```

## Feature Flags

### Configuration (config.yaml)

```yaml
features:
  # === Core Features ===
  commands: true           # Système de commandes chat
  analytics: true          # Collecte métriques d'usage
  chat_logger: true        # Logging messages chat
  system_monitor: true     # Monitoring CPU/RAM

  # === Integrations ===
  translator: true         # 🔴 !trad - Charge langdetect (~57 MB)
  llm: true                # !ask et mentions LLM
  game_engine: true        # !gi, !gs - Rust Engine (ultra léger)
  music_cache: false       # Cache musique quantique (POC)
  wikipedia: true          # !wiki

  # === Stream Monitoring ===
  stream_monitor: true     # Polling Helix pour stream status
  eventsub: true           # EventSub WebSocket real-time
  stream_announcer: true   # Annonces stream online/offline

  # === Advanced Features ===
  devtools: false          # Outils développeur
  auto_persona: false      # Personnalité auto contextuelle
  auto_translate_streamers: false  # Traduction auto pour streamers
  broadcast: true          # Broadcast inter-channels
  memory_profiler: true    # 📊 Profiling mémoire/CPU
```

### Usage dans le code

```python
from core.feature_manager import get_feature_manager, Feature

features = get_feature_manager()

# Vérifier si une feature est activée
if features.is_enabled(Feature.TRANSLATOR):
    init_translator()

# Ou avec un string
if features.is_enabled_str("llm"):
    init_llm()
```

### Features disponibles

| Feature | Description | RAM estimée | Note |
|---------|-------------|-------------|------|
| `commands` | Système de commandes chat | ~2 MB | Core |
| `analytics` | Collecte métriques | ~1 MB | Core |
| `chat_logger` | Logging messages | ~1 MB | Core |
| `system_monitor` | Monitoring CPU/RAM | ~1 MB | Core |
| `translator` | Traduction (!trad) | **~60 MB** | 🔴 Heavy |
| `llm` | LLM Handler (!ask) | ~5 MB | Requiert API key |
| `game_engine` | Rust Engine (!gi) | ~0.1 MB | Ultra léger |
| `music_cache` | Cache musique | ~2 MB | POC |
| `wikipedia` | Wikipedia (!wiki) | ~1 MB | |
| `stream_monitor` | Polling stream | ~1 MB | |
| `eventsub` | EventSub WebSocket | ~3 MB | Real-time |
| `stream_announcer` | Annonces stream | ~1 MB | |
| `devtools` | Outils dev | ~0.5 MB | |
| `memory_profiler` | Ce système ! | ~1 MB | |

## Memory Profiler

### Décorateur `@log_feature_mem`

```python
from core.memory_profiler import log_feature_mem

@log_feature_mem("translator")
def init_translator():
    from langdetect import detect
    # ... initialisation lourde
```

Logs générés :
```
[MEM] Feature translator: +53.2 MB (total: 89.4 MB)
[CPU] Feature translator: 12.3% (init: 0.34s)
```

### Context Manager `profile_block`

```python
from core.memory_profiler import profile_block

with profile_block("custom_init"):
    heavy_operation()
    more_code()
```

### Async Context Manager

```python
from core.memory_profiler import async_profile_block

async with async_profile_block("async_init"):
    await heavy_async_operation()
```

### Rapport de profiling

```python
from core.memory_profiler import get_profiler

profiler = get_profiler()
print(profiler.get_report())
```

Output :
```
📊 Memory Profiler Report
==================================================

✅ translator: +53.15 MB 🔴 (init: 0.14s, CPU: 12.3%)
✅ llm_handler: +4.00 MB (init: 0.01s, CPU: 5.2%)
✅ game_engine: +0.01 MB (init: 0.00s, CPU: 0.1%)

--------------------------------------------------
📈 Total delta: +57.2 MB
📍 Current RSS: 82.4 MB

⚠️ Heavy features (>10MB):
   - translator: +53.15 MB
```

## Optimisation RAM

### Désactiver le translator (~57 MB économisés)

Si vous n'utilisez pas la commande `!trad` :

```yaml
features:
  translator: false  # Économise ~57 MB
```

### Désactiver le LLM (~5 MB économisés)

Si vous n'utilisez pas `!ask` et les mentions :

```yaml
features:
  llm: false  # Économise ~5 MB
```

### Configuration minimale

Pour un bot très léger (IRC + commandes de base) :

```yaml
features:
  commands: true
  analytics: false
  chat_logger: true
  system_monitor: true
  translator: false      # -57 MB
  llm: false             # -5 MB
  game_engine: true      # Ultra léger
  music_cache: false
  wikipedia: false
  stream_monitor: false
  eventsub: false
  stream_announcer: false
  devtools: false
  broadcast: false
  memory_profiler: false
```

RAM estimée : ~10 MB (au lieu de ~80 MB)

## Roadmap Rust

### Phase 1 : Remplacer langdetect

Le plus gros gain mémoire serait de remplacer `langdetect` (Python, 57 MB) par `whatlang-rs` (Rust, 0 MB runtime) :

```rust
// Dans kissbot-game-engine/src/lib.rs
use whatlang::detect;

#[pyfunction]
fn detect_language(text: &str) -> Option<String> {
    detect(text).map(|info| info.lang().code().to_string())
}
```

**Gain potentiel : -55 MB**

### Phase 2 : Core Rust

Migrer vers Rust :
- MessageBus (tokio::sync::broadcast)
- RateLimiter (HashMap Rust)
- Config loader (serde_yaml)

### Phase 3 : Full Rust

Réécriture complète du bot en Rust avec :
- IRC natif (twitch-irc crate)
- EventSub natif (tokio-tungstenite)
- Helix API (reqwest + serde)

**RAM finale estimée : ~15-20 MB**
