# Tests Locaux KissBot

Tests complets utilisant la **configuration réelle** (clés API, LLM, etc.)

## 🎯 Objectif

Ces tests **NE DOIVENT PAS** tourner en CI/CD GitHub Actions.  
Ils nécessitent :
- ✅ Clé RAWG API valide
- ✅ LLM local actif (http://127.0.0.1:1234) ou clé OpenAI
- ✅ Config complète dans `config/config.yaml`

## 🚀 Utilisation

```bash
# Activer venv
source kissbot-venv/bin/activate

# Lancer tous les tests locaux
pytest tests-local/ -c tests-local/pytest-local.ini -v

# Lancer uniquement tests RAWG
pytest tests-local/ -c tests-local/pytest-local.ini -v -m requires_rawg

# Lancer uniquement tests LLM
pytest tests-local/ -c tests-local/pytest-local.ini -v -m requires_llm

# Lancer sans les tests lents
pytest tests-local/ -c tests-local/pytest-local.ini -v -m "not slow"
```

## 📋 Markers

- `@pytest.mark.local` : Test local uniquement (pas CI)
- `@pytest.mark.requires_rawg` : Nécessite clé RAWG API
- `@pytest.mark.requires_llm` : Nécessite LLM actif
- `@pytest.mark.slow` : Test lent (appels API réels)
- `@pytest.mark.integration` : Test d'intégration complet

## ⚠️ Important

Ces tests **ne sont PAS dans tests-ci/** pour une raison :
- CI/CD GitHub n'a pas accès aux clés API privées
- CI/CD GitHub n'a pas de LLM local
- Ces tests valident le fonctionnement réel en environnement de dev

## 📊 Couverture

- ✅ **Backends** : GameLookup + QuantumGameCache avec vraie API RAWG
- ✅ **Neural V2** : NeuralPathwayManager + Synapses avec vrai LLM
- ✅ **Integration** : Pipeline complet bot → LLM → réponse

## 🔗 Voir aussi

- `/tests-ci/` : Tests CI/CD (sans clés privées)
- `/tests/` : Tests Shannon originaux (15 tests)
