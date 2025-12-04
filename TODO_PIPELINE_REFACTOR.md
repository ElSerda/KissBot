# 🔧 TODO - Pipeline Refactor & Monitoring

> Session du 2025-12-04 - Branch: `refactor/v2-modular`

## 📊 État actuel du Pipeline

```
✅ Message vide         → return
✅ Known bots           → return  
✅ Dedupe               → return
✅ Banword              → return + ban
⏳ Rate limit           → TODO (hook réservé)
⏳ Spam detect          → TODO (hook réservé)
✅ Commandes !          → _handle_command → return
✅ Mentions             → _handle_mention → return
✅ Passif               → _handle_passive_features
```

---

## ✅ FAIT (Session 2025-12-04)

### Monitoring & Features
- [x] `core/feature_manager.py` - 17 feature flags configurables
- [x] `core/memory_profiler.py` - Decorators `@log_feature_mem`
- [x] `core/monitor.py` - Process Monitor (Unix socket + SQLite)
- [x] `core/monitor_client.py` - Client pour bots (register, heartbeat)
- [x] `core/llm_usage_logger.py` - Tracking tokens LLM
- [x] `config.yaml` - Section `features:` ajoutée
- [x] `kissbot.sh` - Intégration Monitor (start-monitor, logs-monitor, etc.)
- [x] `docs/FEATURE_FLAGS.md` - Documentation features
- [x] `docs/MONITORING.md` - Documentation monitoring

### Pipeline Fix
- [x] Réordonner pipeline dans `message_handler.py`
- [x] Commandes `!` prioritaires sur mentions (fix hack `!trad & serda_bot`)
- [x] Dedupe déplacé AVANT banword/auto-trad
- [x] Créer `_handle_command()` et `_handle_passive_features()`

---

## 🟧 À FAIRE - Priorité Haute

### 1. `analytics.mark_blocked()` 
**Fichier:** `core/analytics_handler.py`

```python
# À ajouter
async def mark_blocked(self, msg: ChatMessage, reason: str):
    """Track blocked message (banword, spam, rate limit)"""
    self.blocked_count += 1
    self.blocked_by_reason[reason] = self.blocked_by_reason.get(reason, 0) + 1
```

**Puis dans `message_handler.py`:**
- Après banword → `analytics.mark_blocked(msg, "banword")`
- Après spam → `analytics.mark_blocked(msg, "spam")`
- Après rate limit → `analytics.mark_blocked(msg, "flood")`

### 2. Injecter RateLimiter entrant
**Fichier:** `core/rate_limiter.py` (existe déjà)

**À faire dans `main.py`:**
```python
from core.rate_limiter import RateLimiter
global_limiter = RateLimiter(max_rate=100, per_seconds=10)
# Passer à MessageHandler
```

**À faire dans `message_handler.py`:**
```python
# Dans __init__
self.rate_limiter = rate_limiter

# Dans _handle_chat_message (après dedupe, avant banword)
if not self.rate_limiter.allow(msg.user_id):
    await self.analytics.mark_blocked(msg, "flood")
    return
```

### 3. Créer Spam Detector (stub)
**Fichier à créer:** `core/spam_detector.py`

```python
class SpamDetector:
    """Détection basique de spam - stub extensible"""
    
    def __init__(self):
        self.user_messages: Dict[str, List[str]] = {}
        self.user_timestamps: Dict[str, List[float]] = {}
    
    def check(self, user_id: str, text: str) -> Optional[str]:
        """
        Retourne la raison du spam ou None si OK.
        Raisons: "repetition", "flood", "caps", "links"
        """
        # TODO: Implémenter les checks
        return None
```

---

## 🟨 À FAIRE - Priorité Moyenne

### 4. Tests E2E automatisés
**Fichier à créer:** `tests/test_pipeline_e2e.py`

Cas à tester:
- [ ] `!trad ru: Bonjour & serda_bot` → 1 seule action (commande)
- [ ] `salut serda_bot` → mention
- [ ] `salut tout le monde` → passif
- [ ] spam 10 messages rapide → rate limit
- [ ] banword → timeout + STOP
- [ ] mention + banword → banword gagne
- [ ] spam + command → rate limit gagne

### 5. Helix Moderation API
**Fichier à créer:** `twitchapi/helix_moderation.py`

Actuellement: seulement IRC `/ban`
À implémenter:
- [ ] `ban_user()` via Helix API
- [ ] `timeout_user()` via Helix API  
- [ ] `delete_message()` via Helix API

Scopes requis: `moderator:manage:bans`, `moderator:manage:chat_messages`

---

## 🟦 À FAIRE - Priorité Basse (Future)

### 6. Migration whatlang-rs
**Fichier:** `kissbot-game-engine/` (Rust)

Remplacer `langdetect` Python (57 MB RAM) par `whatlang-rs` via PyO3.
Quick win pour économiser de la RAM.

### 7. API SaaS - Quotas par channel
Fondations posées avec Monitor, à étendre:
- [ ] Quotas LLM par channel
- [ ] Rate limits configurables par channel
- [ ] Dashboard usage

---

## 📁 Fichiers modifiés/créés cette session

### Créés
```
core/feature_manager.py      # Feature flags
core/memory_profiler.py      # RAM/CPU profiling
core/monitor.py              # Monitor process
core/monitor_client.py       # Monitor client
core/llm_usage_logger.py     # LLM tracking
docs/FEATURE_FLAGS.md        # Doc features
docs/MONITORING.md           # Doc monitoring
```

### Modifiés
```
core/message_handler.py      # Pipeline réordonné
config/config.yaml           # Section features ajoutée
kissbot.sh                   # Intégration Monitor
main.py                      # Feature init + Monitor registration
```

---

## 🧪 Tests rapides

### Vérifier le pipeline
```bash
cd /home/serda/Project/KissBot-standalone
source kissbot-venv/bin/activate
python -c "
from modules.intelligence.core import extract_mention_message

tests = [
    ('!trad ru: test & serda_bot', 'COMMANDE'),
    ('serda_bot ping', 'MENTION'),
    ('hello world', 'PASSIF'),
]

for text, expected in tests:
    if text.startswith('!'):
        result = 'COMMANDE'
    elif extract_mention_message(text, 'serda_bot'):
        result = 'MENTION'
    else:
        result = 'PASSIF'
    status = '✅' if result == expected else '❌'
    print(f'{status} {text[:30]:30} → {result}')
"
```

### Vérifier le Monitor
```bash
./kissbot.sh status
./kissbot.sh logs-monitor
sqlite3 kissbot_monitor.db "SELECT * FROM bot_status"
```

---

## 📌 Commandes utiles

```bash
# Stack complète
./kissbot.sh start          # Monitor + Hub + Supervisor + Bots
./kissbot.sh stop
./kissbot.sh status

# Monitor seul
./kissbot.sh start-monitor
./kissbot.sh logs-monitor -f

# Vérifier DB Monitor
sqlite3 kissbot_monitor.db "SELECT channel, status, last_seen FROM bot_status"
sqlite3 kissbot_monitor.db "SELECT * FROM llm_usage ORDER BY ts DESC LIMIT 10"
```

---

*Dernière mise à jour: 2025-12-04 00:45*
