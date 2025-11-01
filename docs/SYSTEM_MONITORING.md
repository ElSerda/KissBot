# System Monitoring

## 📊 Lightweight CPU/RAM monitoring

Le bot log automatiquement ses métriques système dans `metrics.json`.

### Fichier généré

**`metrics.json`** - Newline-delimited JSON (1 entrée par ligne)
```json
{"type": "header", "timestamp": 1730472000.0, "interval": 60, "thresholds": {"cpu_percent": 50.0, "ram_mb": 500}}
{"type": "sample", "timestamp": 1730472060.0, "cpu_percent": 2.3, "ram_mb": 145.2, "threads": 8}
{"type": "sample", "timestamp": 1730472120.0, "cpu_percent": 15.2, "ram_mb": 152.3, "threads": 8, "alerts": ["HIGH_CPU=15.2%"]}
```

### Lecture des métriques

#### 1. **Script Python fourni** (recommandé)
```bash
# Voir toutes les métriques
python3 view_metrics.py

# Mode live (tail -f)
python3 view_metrics.py --live

# Seulement les alertes
python3 view_metrics.py --alerts
```

#### 2. **cat / tail direct**
```bash
# Voir tout
cat metrics.json

# Live updates
tail -f metrics.json

# Dernières 10 entrées
tail -n 10 metrics.json
```

#### 3. **Avec jq (filtrage avancé)**
```bash
# Filtrer CPU > 50%
cat metrics.json | jq 'select(.type == "sample" and .cpu_percent > 50)'

# Calculer moyenne CPU
cat metrics.json | jq -s '[.[] | select(.type == "sample")] | map(.cpu_percent) | add / length'

# Trouver pic RAM
cat metrics.json | jq -s '[.[] | select(.type == "sample")] | max_by(.ram_mb)'
```

### Configuration

Dans `main.py` :
```python
system_monitor = SystemMonitor(
    interval=60,              # Log toutes les 60s
    log_file="metrics.json",  # Fichier de sortie
    cpu_threshold=50.0,       # Alerte si CPU > 50%
    ram_threshold_mb=500      # Alerte si RAM > 500MB
)
```

### Alertes automatiques

Si CPU ou RAM dépasse les seuils :
- ⚠️ Log WARNING dans console
- 🚨 Champ `"alerts"` ajouté dans JSON

Exemple :
```json
{
  "type": "sample",
  "timestamp": 1730472120.0,
  "cpu_percent": 65.2,
  "ram_mb": 521.3,
  "threads": 8,
  "alerts": ["HIGH_CPU=65.2%", "HIGH_RAM=521MB"]
}
```

### Performance Impact

- **CPU overhead** : < 0.1% (1 sample/60s)
- **RAM overhead** : Négligeable
- **Disk I/O** : 1 write/60s (~100 bytes)

### Désactiver le monitoring

Commenter dans `main.py` :
```python
# system_monitor = SystemMonitor(...)
# asyncio.create_task(system_monitor.start())
```

Ou modifier interval à 300s (5 min) pour moins de logs.

---

## 💬 !stats Command

### Usage

En chat Twitch, tape :
```
!stats
```

Le bot répond avec les métriques système actuelles :
```
@ton_pseudo 📊 CPU: 1.0% | RAM: 54MB | Threads: 9 | Uptime: 2h34m
```

### Format de sortie

**Métriques affichées :**
- **CPU**: Pourcentage d'utilisation CPU du process bot
- **RAM**: Mémoire utilisée en MB (RSS memory)
- **Threads**: Nombre de threads actifs
- **Uptime**: Temps depuis démarrage du monitoring (format `Xh Xm` ou `Xm`)

**Avec alertes** (si seuils dépassés) :
```
@ton_pseudo 📊 CPU: 65.2% | RAM: 521MB | Threads: 9 | Uptime: 3h12m | ⚠️ HIGH_CPU=65.2%, HIGH_RAM=521MB
```

### Caractéristiques techniques

- **Latence** : < 1ms (métriques cachées, pas de lecture fichier)
- **Source** : `SystemMonitor._last_sample` (cache mémoire)
- **Mise à jour** : Toutes les 60s (configurable via `interval`)
- **Disponibilité** : Immédiate (pas besoin d'attendre premier sample)
- **Format** : Single-line, optimisé pour Twitch chat

### Configuration

Aucune configuration nécessaire. La commande est automatiquement active si `SystemMonitor` est démarré dans `main.py`.

Pour désactiver :
```python
# Ne pas injecter SystemMonitor dans MessageHandler
# message_handler.set_system_monitor(system_monitor)  # Commenté
```

### Uptime Format

Le temps d'uptime est formaté de façon human-readable :
- **< 1h** : `45m` (minutes seulement)
- **≥ 1h** : `2h34m` (heures + minutes)
- **Source** : Calculé depuis `SystemMonitor._start_time`

### Exemples de sortie

**Bot idle** :
```
📊 CPU: 0.0% | RAM: 54MB | Threads: 9 | Uptime: 15m
```

**Bot actif** :
```
📊 CPU: 2.3% | RAM: 58MB | Threads: 9 | Uptime: 2h34m
```

**Avec alertes** :
```
📊 CPU: 65.2% | RAM: 521MB | Threads: 10 | Uptime: 5h12m | ⚠️ HIGH_CPU=65.2%, HIGH_RAM=521MB
```

### Dépannage

**!stats ne répond pas** :
- Vérifier que `SystemMonitor` est démarré dans `main.py`
- Vérifier injection : `message_handler.set_system_monitor(system_monitor)`
- Regarder logs : `⚠️ !stats called but SystemMonitor not injected`

**Métriques à 0** :
- Attendre 1s (psutil a besoin d'un sample interval)
- CPU à 0% est normal en idle (bot très efficient)

**Uptime incorrect** :
- Uptime mesure depuis le start du monitoring, pas du bot
- Redémarrer le bot réinitialise l'uptime

---
