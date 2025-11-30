# 🔄 Migration Plan — V1 → V2

> **Objectif** : Restructurer en architecture modulaire (core KISS + modules)  
> **Approche** : Migration progressive, tests continus  
> **Rollback** : Git branches + backups

---

## 📊 État des lieux

### Structure actuelle (V1)
```
├── core/          ⚠️ Mixte (infra + business logic)
├── commands/      → modules/classic_commands/
├── intelligence/  → modules/intelligence/
├── backends/      → modules/integrations/
└── twitchapi/     ✅ OK (infrastructure pure)
```

### Problèmes identifiés
1. `core/` contient business logic (analytics, cache)
2. Pas de séparation claire infra vs features
3. Impossible d'ajouter modules sans toucher core
4. Tests couplés à l'implémentation

---

## 🎯 Architecture cible (V2)

```
├── core/                   # Infrastructure UNIQUEMENT
│   ├── types.py           # BotEvent, BotResponse
│   ├── message_handler.py # Parsing + validation
│   ├── command_router.py  # Dispatch vers modules
│   ├── rate_limiter.py    # Anti-spam
│   ├── security.py        # Filtres, tokens
│   └── ipc_protocol.py    # IPC Unix sockets
│
├── modules/                # Features isolées
│   ├── base_module.py     # Interface abstraite
│   ├── intelligence/      # Classifier, reflexes, synapses
│   ├── classic_commands/  # Commandes existantes
│   ├── custom_commands/   # !kbadd (NOUVEAU)
│   ├── personality/       # !persona (NOUVEAU)
│   ├── outputs/           # Router multi-target (NOUVEAU)
│   ├── integrations/      # Game engine, APIs
│   ├── analytics/         # Metrics
│   └── cache/             # Cache manager
│
└── twitchapi/              # Infrastructure Twitch (unchanged)
```

---

## 🔄 Étapes de migration

### ✅ Phase 0 : Backup & Branche
```bash
# Backup DB
cp kissbot.db kissbot.db.backup_v1
cp .kissbot.key .kissbot.key.backup

# Créer branche migration
git checkout -b refactor/v2-modular-architecture
git push -u origin refactor/v2-modular-architecture
```

---

### 📦 Phase 1 : Créer structure modules/ (30 min)

**Actions** :
```bash
# Créer arborescence
mkdir -p modules/{intelligence,classic_commands,custom_commands,personality,outputs,integrations,analytics,cache}

# Créer __init__.py partout
find modules -type d -exec touch {}/__init__.py \;
```

**Créer fichiers base** :
1. `modules/base_module.py` (interface abstraite)
2. `core/types.py` (BotEvent, BotResponse dataclasses)
3. `core/command_router.py` (skeleton)

**Validation** :
```bash
python -c "import modules; print('OK')"
```

---

### 🔀 Phase 2 : Migrer intelligence/ (45 min)

**Actions** :
```bash
# Copier fichiers (garder original pour rollback)
cp -r intelligence/* modules/intelligence/

# Fixer imports dans modules/intelligence/
find modules/intelligence -name "*.py" -exec sed -i 's/from intelligence\./from modules.intelligence./g' {} \;
find modules/intelligence -name "*.py" -exec sed -i 's/import intelligence\./import modules.intelligence./g' {} \;
```

**Adapter entry points** :
```python
# main.py, supervisor_v1.py
# OLD:
from intelligence.unified_quantum_classifier import UnifiedQuantumClassifier
from intelligence.synapses.cloud_synapse import CloudSynapse

# NEW:
from modules.intelligence.unified_quantum_classifier import UnifiedQuantumClassifier
from modules.intelligence.synapses.cloud_synapse import CloudSynapse
```

**Tests** :
```bash
# Test classification
python -c "from modules.intelligence.unified_quantum_classifier import UnifiedQuantumClassifier; print('OK')"

# Test bot startup
python main.py  # Vérifier logs, pas d'import error
```

**Rollback si problème** :
```bash
git checkout -- modules/ main.py supervisor_v1.py
```

---

### 🎮 Phase 3 : Migrer commands/ (30 min)

**Actions** :
```bash
cp -r commands/* modules/classic_commands/

# Fixer imports
find modules/classic_commands -name "*.py" -exec sed -i 's/from commands\./from modules.classic_commands./g' {} \;
```

**Adapter entry points** :
```python
# main.py
# OLD:
from commands.user_commands import game, wiki_basic, intelligence as intel_cmd
from commands.mod_commands import ...

# NEW:
from modules.classic_commands.user_commands import game, wiki_basic, intelligence as intel_cmd
from modules.classic_commands.mod_commands import ...
```

**Tests** :
```bash
# Test commandes user
# !gc, !gi, !wiki, !joke, !ask

# Test commandes mod
# !persona (future), autres commandes mod

# Test commandes admin
# Commandes broadcaster only
```

---

### 🔧 Phase 4 : Migrer backends/ → integrations/ (45 min)

**Actions** :
```bash
# Game engine
mkdir -p modules/integrations/game_engine
cp backends/game_lookup_rust.py modules/integrations/game_engine/rust_wrapper.py
cp backends/game_lookup.py modules/integrations/game_engine/python_fallback.py

# LLM provider
mkdir -p modules/integrations/llm_provider
cp backends/llm_handler.py modules/integrations/llm_provider/handler.py

# Translator
mkdir -p modules/integrations/translator
cp backends/translator.py modules/integrations/translator/client.py

# Wikipedia
mkdir -p modules/integrations/wikipedia
cp backends/wikipedia_handler.py modules/integrations/wikipedia/handler.py
```

**Fixer imports** :
```bash
# Dans tous les fichiers qui utilisent backends.*
sed -i 's/from backends.game_lookup_rust/from modules.integrations.game_engine.rust_wrapper/g' **/*.py
sed -i 's/from backends.llm_handler/from modules.integrations.llm_provider.handler/g' **/*.py
```

**Tests** :
```bash
# Test game lookup
python -c "from modules.integrations.game_engine.rust_wrapper import search_game; print(search_game('celeste'))"

# Test LLM
python -c "from modules.integrations.llm_provider.handler import LLMHandler; print('OK')"
```

---

### 🧹 Phase 5 : Nettoyer core/ (1h)

**Actions** :
```bash
# Déplacer analytics
cp core/analytics_handler.py modules/analytics/tracker.py

# Déplacer cache
cp core/cache.py modules/cache/manager.py

# Créer nouveaux fichiers core
touch core/types.py
touch core/security.py
touch core/command_router.py
```

**core/ doit contenir UNIQUEMENT** :
- `types.py` (nouveaux types)
- `message_handler.py` (parsing)
- `rate_limiter.py` (anti-spam)
- `security.py` (validation)
- `command_router.py` (dispatch)
- `ipc_protocol.py` (IPC)
- `message_bus.py` (EventBus)
- `registry.py` (simplifié)

**Supprimer de core/** :
- `analytics_handler.py` (→ modules/analytics/)
- `cache.py` (→ modules/cache/)
- `chat_logger.py` (évaluer si garder)
- `command_logger.py` (évaluer si garder)
- `outbound_logger.py` (évaluer si garder)
- `performance_tracker.py` (→ modules/analytics/)

**Tests** :
```bash
pytest tests/core/ -v
python main.py  # Full bot test
```

---

### 🧪 Phase 6 : Tests globaux (1h)

**Checklist** :
- [ ] Bot démarre sans erreur
- [ ] IRC connection stable
- [ ] EventSub Hub fonctionne
- [ ] Commandes user (!gc, !gi, !wiki)
- [ ] Commandes mod
- [ ] Intelligence (mentions, !ask)
- [ ] Rate limiting OK
- [ ] Logs propres (pas d'import error)
- [ ] DB access OK (tokens chiffrés)
- [ ] Rust engine fonctionne

**Tests automatisés** :
```bash
# Tests unitaires
pytest tests/ -v --cov=core --cov=modules

# Tests intégration
python test_rust_integration.py
python test_rate_limiting.py

# Test production-like
./kissbot.sh start
tail -f logs/broadcast/el_serda/instance.log
# Vérifier 5-10 min sans crash
```

---

### 📝 Phase 7 : Documentation (1h)

**Mettre à jour** :
- `README.md` : Nouvelle structure
- `ARCHITECTURE.md` : Schémas modules
- `CONTRIBUTING.md` : Guidelines modules

**Créer** :
- `docs/MODULES.md` : Liste modules + interfaces
- `docs/CORE_API.md` : API core/ (types, router)

---

### 🚀 Phase 8 : Merge & Deploy

**Pre-merge checklist** :
- [ ] Tous les tests passent
- [ ] Docs à jour
- [ ] Aucune régression fonctionnelle
- [ ] Performance équivalente V1
- [ ] Code review (self ou peer)

**Merge** :
```bash
git checkout main
git merge refactor/v2-modular-architecture
git push origin main

# Tag version
git tag -a v2.0.0-alpha -m "Modular architecture"
git push origin v2.0.0-alpha
```

**Deploy production** :
```bash
./kissbot.sh stop
git pull
./kissbot.sh start
```

**Monitoring** :
```bash
# Surveiller logs 24h
tail -f logs/broadcast/*/instance.log

# Vérifier métriques
tail -f metrics.jsonl
```

---

## 🆘 Rollback Plan

### Si problème mineur (import error, bug isolé)
```bash
# Fix rapide
git add <fichier>
git commit -m "fix: <description>"
git push
```

### Si problème majeur (bot crash, perte fonctionnalité)
```bash
# Rollback complet
git revert HEAD
git push

# Ou retour branch main
git checkout main
git branch -D refactor/v2-modular-architecture

# Restore DB si nécessaire
cp kissbot.db.backup_v1 kissbot.db
```

---

## 📊 Métriques de succès

### Technique
- ✅ Tous les tests passent
- ✅ Coverage core > 80%
- ✅ Latency équivalente V1
- ✅ Memory usage stable

### Fonctionnel
- ✅ Zéro régression commandes
- ✅ Bot stable 24h+
- ✅ Logs propres (pas d'erreur)

### Qualité code
- ✅ Séparation claire core/modules
- ✅ Imports explicites (pas de *)
- ✅ Docstrings complets
- ✅ Type hints partout

---

## 🎯 Après migration : Nouveaux modules

Une fois V2 stable, développer :

1. **modules/custom_commands/** (!kbadd)
2. **modules/personality/** (!persona)
3. **modules/outputs/** (router multi-target)

Voir `ROADMAP_V2.md` pour détails.

---

**Date création** : 30 novembre 2025  
**Auteur** : ElSerda + GitHub Copilot  
**Status** : Draft (à valider avant exécution)
