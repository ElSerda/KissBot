# 🎛️ KissBot Monitor System

## Vue d'ensemble

Le système de monitoring de KissBot permet de superviser plusieurs instances de bot en temps réel, avec collecte de métriques (RAM, CPU) et tracking de l'utilisation LLM.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    KissBot Monitor                          │
│                 (python -m core.monitor)                    │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │  Unix Socket    │  │   SQLite DB     │                  │
│  │ /tmp/kissbot_   │  │ kissbot_monitor │                  │
│  │  monitor.sock   │  │      .db        │                  │
│  └────────┬────────┘  └────────┬────────┘                  │
│           │                    │                            │
└───────────┼────────────────────┼────────────────────────────┘
            │                    │
    ┌───────┴────────┐           │
    │   IPC JSON     │           │
    └───────┬────────┘           │
            │                    │
┌───────────┼────────────────────┼────────────────────────────┐
│           ▼                    ▼                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  Bot Instance #1                     │   │
│  │   MonitorClient → register, heartbeat, metrics      │   │
│  │   LLMUsageLogger → token tracking per channel       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  Bot Instance #2                     │   │
│  │   MonitorClient → register, heartbeat, metrics      │   │
│  │   LLMUsageLogger → token tracking per channel       │   │
│  └─────────────────────────────────────────────────────┘   │
│                          ...                                │
└─────────────────────────────────────────────────────────────┘
```

## Composants

### 1. KissBot Monitor (`core/monitor.py`)

Processus central de supervision. À démarrer **avant** les bots.

```bash
# Démarrage du Monitor
python -m core.monitor

# En arrière-plan
nohup python -m core.monitor > logs/monitor.log 2>&1 &
```

**Fonctionnalités :**
- Serveur Unix Socket pour IPC rapide
- Collecte de métriques toutes les 15s (configurable)
- Détection automatique des bots morts (timeout 60s)
- Stockage SQLite avec rétention 7 jours
- Nettoyage automatique des anciennes données

### 2. Monitor Client (`core/monitor_client.py`)

Client léger intégré dans chaque instance de bot.

```python
from core.monitor_client import MonitorClient

# Dans main.py
client = MonitorClient()
await client.register_with_monitor(
    channel="el_serda",
    pid=os.getpid(),
    features={"llm": True, "translator": False}
)

# Heartbeat automatique
heartbeat_task = asyncio.create_task(client.start_heartbeat(channel, interval=30))

# À l'arrêt
await client.unregister_from_monitor(channel, pid)
```

**Caractéristiques :**
- Fail-safe : ne crash jamais si le Monitor est indisponible
- Heartbeat async avec métriques (RAM/CPU)
- Reconnexion automatique

### 3. LLM Usage Logger (`core/llm_usage_logger.py`)

Tracking de l'utilisation des LLMs pour facturation/quotas.

```python
from core.llm_usage_logger import LLMUsageLogger

logger = LLMUsageLogger()

# Après un appel LLM
await logger.log_usage(
    channel="el_serda",
    model="deepseek-chat",
    feature="joke_command",
    tokens_in=150,
    tokens_out=80,
    latency_ms=1200,
    estimated_cost=0.0003
)

# Statistiques
stats = logger.get_usage_stats(channel="el_serda", days=30)
# {'total_tokens_in': 50000, 'total_tokens_out': 25000, 'total_cost': 0.15, ...}
```

**Stockage :**
- SQLite local : `llm_usage.db`
- Forward vers Monitor si disponible

## Base de données

### Schema `kissbot_monitor.db`

```sql
-- Métriques temporelles par bot
CREATE TABLE bot_metrics (
    id INTEGER PRIMARY KEY,
    ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    channel TEXT NOT NULL,
    pid INTEGER NOT NULL,
    rss_mb REAL,
    cpu_pct REAL,
    features_json TEXT
);

-- Statut des bots enregistrés
CREATE TABLE bot_status (
    id INTEGER PRIMARY KEY,
    channel TEXT UNIQUE NOT NULL,
    pid INTEGER NOT NULL,
    status TEXT DEFAULT 'online',  -- online, offline, stale
    features_json TEXT,
    registered_at TIMESTAMP,
    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Utilisation LLM par channel
CREATE TABLE llm_usage (
    id INTEGER PRIMARY KEY,
    ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    channel TEXT NOT NULL,
    model TEXT NOT NULL,
    feature TEXT,
    tokens_in INTEGER DEFAULT 0,
    tokens_out INTEGER DEFAULT 0,
    latency_ms INTEGER,
    estimated_cost REAL DEFAULT 0
);

-- Index pour requêtes fréquentes
CREATE INDEX idx_metrics_channel_ts ON bot_metrics(channel, ts);
CREATE INDEX idx_llm_channel_ts ON llm_usage(channel, ts);
CREATE INDEX idx_status_channel ON bot_status(channel);
```

## Protocole IPC

### Messages supportés

| Type | Direction | Description |
|------|-----------|-------------|
| `register` | Client → Monitor | Enregistre un bot |
| `heartbeat` | Client → Monitor | Signale que le bot est actif + métriques |
| `unregister` | Client → Monitor | Désinscrit un bot |
| `llm_usage` | Client → Monitor | Log une utilisation LLM |
| `get_status` | Client → Monitor | Récupère le statut de tous les bots |

### Exemples

```json
// Register
{
    "type": "register",
    "channel": "el_serda",
    "pid": 12345,
    "features": {"llm": true, "translator": false}
}

// Heartbeat
{
    "type": "heartbeat",
    "channel": "el_serda",
    "pid": 12345,
    "rss_mb": 150.5,
    "cpu_pct": 2.3
}

// LLM Usage
{
    "type": "llm_usage",
    "channel": "el_serda",
    "model": "deepseek-chat",
    "feature": "joke_command",
    "tokens_in": 150,
    "tokens_out": 80,
    "latency_ms": 1200,
    "estimated_cost": 0.0003
}
```

## Configuration

### Dans `config.yaml`

```yaml
monitoring:
  enabled: true
  socket_path: /tmp/kissbot_monitor.sock
  metrics_interval: 15  # secondes
  heartbeat_interval: 30  # secondes
  stale_timeout: 60  # secondes avant marquage "stale"
  data_retention_days: 7
```

## Scripts utiles

### Afficher le statut de tous les bots

```bash
# Via SQLite
sqlite3 kissbot_monitor.db "SELECT channel, status, last_heartbeat FROM bot_status"
```

### Statistiques LLM du mois

```bash
sqlite3 kissbot_monitor.db "
SELECT 
    channel,
    SUM(tokens_in) as total_in,
    SUM(tokens_out) as total_out,
    SUM(estimated_cost) as total_cost
FROM llm_usage
WHERE ts > datetime('now', '-30 days')
GROUP BY channel
ORDER BY total_cost DESC
"
```

### Métriques RAM par channel

```bash
sqlite3 kissbot_monitor.db "
SELECT 
    channel,
    AVG(rss_mb) as avg_ram,
    MAX(rss_mb) as max_ram,
    AVG(cpu_pct) as avg_cpu
FROM bot_metrics
WHERE ts > datetime('now', '-1 day')
GROUP BY channel
"
```

## Intégration avec le système de Features

Le Monitor s'intègre avec le `FeatureManager` pour :

1. **Savoir quelles features sont actives** par bot
2. **Corréler RAM/CPU** avec les features activées
3. **Identifier les features gourmandes** (ex: translator = +57MB)

Voir [FEATURE_FLAGS.md](./FEATURE_FLAGS.md) pour la configuration des features.

## Dépannage

### Le Monitor ne démarre pas

```bash
# Vérifier si le socket existe déjà
ls -la /tmp/kissbot_monitor.sock

# Supprimer l'ancien socket
rm /tmp/kissbot_monitor.sock
```

### Les bots ne se connectent pas

```bash
# Vérifier que psutil est installé
pip install psutil

# Vérifier les permissions du socket
ls -la /tmp/kissbot_monitor.sock
# Doit être : srwxrwxrwx
```

### Métriques non collectées

1. Vérifier que le bot envoie des heartbeats
2. Vérifier les logs du Monitor (`logs/monitor.log`)
3. S'assurer que `psutil` est installé

## Roadmap

- [ ] Dashboard web temps réel
- [ ] Alerting (Discord webhook) si bot down
- [ ] Export Prometheus/Grafana
- [ ] Agrégation multi-serveur

---

*Dernière mise à jour : 2025-01-04*
