# 🧹 KissBot Cleanup Guide

**Date**: 16 novembre 2025  
**Objectif**: Nettoyer les fichiers legacy et organiser le projet

---

## 📋 Fichiers à Supprimer

### Anciens Tests (Legacy)
```bash
rm -f test_*.py
rm -rf tests-local/
```

Fichiers concernés:
- `test_dataset.py`
- `test_disambiguation.py`
- `test_format_truncation.py`
- `test_gi_choice.py`
- `test_gi_command.py`
- `test_hub.py`
- `test_igdb_lookup.py`
- `test_multiple_games.py`
- `test_rate_limiter.py`
- `test_request_coalescing.py`
- `test_shorthand.py`
- `test_splinter_cell.py`
- `test_smart_responses.py`
- `test_chatbot_conversation.py`
- `test_ttl_validation.py`
- `test_cache_fuzzy.py`
- `test_igdb_id_enrichment.py`
- `test_cleanup_refacto.py`
- `test_drakon_flow.py`
- `test_drakon_candidates.py`
- `test_igdb_integration.py`
- `test_igdb_debug.py`
- `test_query_variants.py`

### Backups Anciens
```bash
rm -f kissbot.db.backup_*
rm -f *.pyc
rm -rf __pycache__/
```

### Scripts Legacy
```bash
rm -rf _scripts_legacy/
rm -f test_supervisor.sh
```

### Documentations Obsolètes
```bash
rm -f TEST_RESULTS_*.md
rm -f VALIDATION_FINALE.md
rm -f SUMMARY_DISAMBIGUATION.md
rm -f SMART_RESPONSES_SUMMARY.md
```

### Code Legacy
```bash
# Anciens wrappers
rm -f backends/game_lookup_drakon.py
rm -f backends/game_lookup_python_original.py
rm -f backends/game_cache.py.legacy

# Supervisor V1 (obsolète)
rm -f supervisor_v1.py
```

---

## 🎯 Fichiers à Conserver

### Core
- `main.py` ✅
- `config/config.yaml` ✅
- `requirements.txt` ✅
- `pyproject.toml` ✅

### Production Code
- `core/` ✅
- `backends/` ✅
- `twitchapi/` ✅
- `intelligence/` ✅
- `commands/` ✅
- `database/` ✅

### Rust Components
- `kissbot-game-engine/` ✅
- `DRAKON/rust/` ✅

### Tests Valides (CI)
- `tests-ci/` ✅

### Documentation
- `README.md` ✅
- `CHANGELOG.md` ✅
- `LICENSE` ✅
- `EULA_FR.md` ✅
- `ARCHITECTURE.md` ✅ (nouveau)
- `RUST_INTEGRATION_SUCCESS.md` ✅

### Nouveaux Tests
- `test_rust_wrapper.py` ✅
- `test_rust_integration.py` ✅

---

## 🔄 Réorganisation

### 1. Créer dossier archive
```bash
mkdir -p archive/legacy
```

### 2. Déplacer fichiers obsolètes
```bash
# Tests legacy
mv test_*.py archive/legacy/ 2>/dev/null

# Docs obsolètes
mv TEST_RESULTS_*.md archive/legacy/ 2>/dev/null
mv VALIDATION_FINALE.md archive/legacy/ 2>/dev/null
mv SUMMARY_DISAMBIGUATION.md archive/legacy/ 2>/dev/null

# Scripts legacy
mv _scripts_legacy/ archive/legacy/ 2>/dev/null

# Backups
mv kissbot.db.backup_* archive/legacy/ 2>/dev/null
```

### 3. Nettoyer cache Python
```bash
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete
find . -type f -name "*.pyo" -delete
```

### 4. Nettoyer builds Rust
```bash
cd kissbot-game-engine
cargo clean
cd ../DRAKON/rust
cargo clean
```

---

## 📦 Structure Finale

```
KissBot-standalone/
├── main.py
├── config/
├── core/
├── backends/
│   ├── game_lookup_rust.py     # 🦀 NOUVEAU
│   ├── game_lookup.py          # 🐍 Fallback enrichi
│   ├── llm_handler.py
│   └── music_cache.py
├── twitchapi/
├── intelligence/
├── commands/
├── database/
├── kissbot-game-engine/        # 🦀 Rust engine
├── DRAKON/rust/                # 🐉 Fuzzy matching
├── tests-ci/                   # Tests CI/CD
├── logs/
├── pids/
├── docs/
├── archive/                    # 📦 Legacy code
│   └── legacy/
└── README.md
```

---

## ✅ Checklist Post-Cleanup

- [ ] Tous les tests legacy archivés
- [ ] Cache Python nettoyé
- [ ] Backups déplacés
- [ ] Documentation à jour
- [ ] Tests CI/CD fonctionnels
- [ ] Bot démarre sans erreurs
- [ ] DRAKON opérationnel
- [ ] Game engine Rust fonctionnel
- [ ] Logs propres

---

## 🧪 Validation

### 1. Tester le bot
```bash
python main.py --channel el_serda
```

### 2. Vérifier DRAKON
```bash
cd DRAKON/rust
./status_drakon.sh
```

### 3. Tester game engine
```bash
python test_rust_integration.py
```

### 4. Lancer tests CI
```bash
pytest tests-ci/ -v
```

---

## 📝 Notes

- **Ne pas supprimer** `kissbot.db` (cache production)
- **Garder** les logs récents dans `logs/`
- **Archiver** plutôt que supprimer définitivement
- **Documenter** toute suppression majeure

---

## 🚨 Rollback

Si problème après cleanup:

```bash
# Restaurer depuis archive
cp -r archive/legacy/* .

# Ou git restore
git restore .
```
