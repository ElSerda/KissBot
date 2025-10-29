# 🧪 KissBot Testing Guide

> **Stratégie Hybride** - Shannon validation + CI mocks + Local real APIs

---

## 📋 Table of Contents

- [Test Strategy](#test-strategy)
- [Test Suites](#test-suites)
- [Running Tests](#running-tests)
- [Writing Tests](#writing-tests)
- [CI/CD Integration](#cicd-integration)
- [Coverage Report](#coverage-report)

---

## 🎯 Test Strategy

KissBot utilise une **stratégie de test hybride** en 3 niveaux :

```
┌─────────────────────────────────────────────────────────┐
│  tests/ (Shannon)                                        │
│  ├─ 15 tests mathématiques                              │
│  ├─ Validation formules sacrées                         │
│  └─ 0 mocks, 0 API, calculs purs                        │
└─────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────┐
│  tests-ci/ (CI/CD)                                       │
│  ├─ 86 tests structure + imports                        │
│  ├─ Mocks pour API (pas de clés privées)                │
│  └─ 60 passed, 26 skipped (GitHub Actions)              │
└─────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────┐
│  tests-local/ (Dev)                                      │
│  ├─ 7 tests pipeline réel                               │
│  ├─ Vraies API keys (config.yaml)                       │
│  └─ 7 passed (RAWG + LLM real)                          │
└─────────────────────────────────────────────────────────┘
```

### Philosophie
- ✅ **Shannon tests** → Garantir exactitude mathématique
- ✅ **CI tests** → Valider structure sans dépendances externes
- ✅ **Local tests** → Tester intégration complète en dev

---

## 📦 Test Suites

### 1. Shannon Tests (`tests/`)

**Objectif** : Valider les formules mathématiques sacrées

```bash
tests/
└── test_intelligence_integration.py (15 tests)
    ├── Shannon Entropy Calculation (H(X) = -Σ p(x)log₂(p(x)))
    ├── Multi-Factor Confidence (0.7*shannon + 0.2*prob + 0.1*dom)
    ├── Probability Distribution
    ├── Dominance Factor
    ├── Classification Thresholds
    └── Pattern Matching
```

**Caractéristiques** :
- ✅ 0 mocks
- ✅ 0 API calls
- ✅ Calculs purs mathématiques
- ✅ 100% deterministic

**Commande** :
```bash
pytest tests/ -v
```

**Résultat attendu** :
```
tests/test_intelligence_integration.py::test_shannon_entropy_calculation PASSED
tests/test_intelligence_integration.py::test_multi_factor_confidence PASSED
... (15 tests) ...
===================== 15 passed in 0.45s =====================
```

---

### 2. CI Tests (`tests-ci/`)

**Objectif** : Valider structure et imports pour GitHub Actions (sans clés API)

```bash
tests-ci/
├── pytest-ci.ini (config markers)
├── test_core.py (11 tests)
│   ├── Cache operations
│   ├── Rate limiter cooldowns
│   ├── Event handlers
│   └── Cache interface
├── test_neural_v2.py (17 tests)
│   ├── NeuralPathwayManager
│   ├── LocalSynapse / CloudSynapse
│   ├── Reflexes
│   ├── Prometheus metrics
│   └── QuantumMetrics
├── test_backends.py (12 tests)
│   ├── GameCache
│   ├── QuantumGameCache
│   └── GameLookup (RAWG API)
├── test_twitch.py (10 tests)
│   ├── Twitch module structure
│   ├── EventSub handlers
│   ├── Token management
│   └── Config validation
├── test_commands.py (18 tests)
│   ├── TranslationCommands
│   ├── QuantumCommands
│   ├── UtilsCommands
│   └── GameCommands
└── test_intelligence.py (18 tests)
    ├── UnifiedQuantumClassifier
    ├── PatternLoader
    └── Enhanced Patterns
```

**Caractéristiques** :
- ✅ Mocks pour Bot objects
- ✅ Skip tests nécessitant LLM/RAWG
- ✅ Validation imports & instantiation
- ✅ GitHub Actions ready

**Markers** :
```python
@pytest.mark.unit           # Tests unitaires isolés
@pytest.mark.integration    # Tests intégration (mocked)
@pytest.mark.intelligence   # Tests système Neural V2
@pytest.mark.requires_llm   # Skip si pas de LLM (CI)
@pytest.mark.requires_rawg  # Skip si pas de RAWG key (CI)
```

**Commande** :
```bash
pytest tests-ci/ -c tests-ci/pytest-ci.ini -v
```

**Résultat attendu** :
```
tests-ci/test_core.py ................ [ 60%]
tests-ci/test_neural_v2.py ........... [ 80%]
tests-ci/test_backends.py ............ [ 90%]
tests-ci/test_twitch.py .............. [100%]
============ 60 passed, 26 skipped in 2.34s ============
```

---

### 3. Local Tests (`tests-local/`)

**Objectif** : Valider pipeline réel avec vraies API keys (dev uniquement)

```bash
tests-local/
├── pytest-local.ini (config markers)
├── README.md (setup instructions)
├── test_backends_with_api.py (3 tests)
│   ├── RAWG API real search
│   ├── Game lookup "Minecraft"
│   └── Quantum cache with real data
└── test_neural_with_llm.py (4 tests)
    ├── NeuralPathwayManager real LLM
    ├── LocalSynapse Ollama generation
    ├── CloudSynapse OpenRouter generation
    └── End-to-end stimulus processing
```

**Caractéristiques** :
- ✅ 0 mocks
- ✅ Uses real config.yaml
- ✅ RAWG API key required
- ✅ LLM endpoint required (Ollama or OpenRouter)
- ✅ Catches production bugs (like QuantumMetrics bug)

**Markers** :
```python
@pytest.mark.local          # Local dev tests only
@pytest.mark.requires_api   # Needs real API keys
```

**Commande** :
```bash
pytest tests-local/ -c tests-local/pytest-local.ini -v
```

**Résultat attendu** :
```
tests-local/test_backends_with_api.py::test_rawg_real_search PASSED
tests-local/test_neural_with_llm.py::test_llm_generation_real PASSED
... (7 tests) ...
===================== 7 passed in 2.28s =====================
```

---

## 🚀 Running Tests

### Pre-commit Workflow (Dev)
```bash
# 1. Valider Shannon (formules sacrées)
pytest tests/ -v

# 2. Valider pipeline réel (avec clés)
pytest tests-local/ -c tests-local/pytest-local.ini -v

# 3. Optionnel : Valider CI tests
pytest tests-ci/ -c tests-ci/pytest-ci.ini -v
```

### GitHub Actions (CI)
```yaml
# Automatique sur push/PR
- Run Shannon tests (15 tests)
- Run CI tests (86 tests, 60 pass, 26 skip)
- Skip local tests (no API keys in CI)
```

### Quick Commands
```bash
# Tous les tests Shannon
pytest tests/

# Tests CI rapides (skip slow)
pytest tests-ci/ -m "not slow" -c tests-ci/pytest-ci.ini

# Test spécifique
pytest tests-local/test_neural_with_llm.py::test_llm_generation_real -v

# Avec coverage
pytest tests/ --cov=intelligence --cov-report=html

# Verbose avec traceback
pytest tests-ci/ -c tests-ci/pytest-ci.ini -vv --tb=short
```

---

## ✍️ Writing Tests

### Shannon Test Pattern
```python
def test_shannon_entropy_calculation():
    """Test Shannon entropy formula H(X) = -Σ p(x)log₂(p(x))"""
    probs = {'python': 0.6, 'javascript': 0.3, 'cpp': 0.1}
    
    entropy = calculate_entropy(probs)
    
    expected = -(0.6 * log2(0.6) + 0.3 * log2(0.3) + 0.1 * log2(0.1))
    assert abs(entropy - expected) < 0.01
```

### CI Test Pattern (with Mocks)
```python
@pytest.mark.requires_llm
@pytest.mark.integration
def test_neural_pathway_with_mock():
    """Test neural pathway with mocked LLM"""
    with patch('intelligence.local_synapse.LocalSynapse') as mock_synapse:
        mock_synapse.fire.return_value = "Mocked response"
        
        manager = NeuralPathwayManager()
        response = await manager.process_stimulus("test", "general")
        
        assert response == "Mocked response"
```

### Local Test Pattern (Real APIs)
```python
@pytest.mark.local
@pytest.mark.requires_api
async def test_neural_pathway_real_llm():
    """Test neural pathway with real LLM endpoint"""
    manager = NeuralPathwayManager()  # Uses real config
    
    response = await manager.process_stimulus(
        stimulus="Explain Python in 10 words",
        context="general"
    )
    
    assert response is not None
    assert len(response) > 0
    assert "python" in response.lower()
```

---

## 🔄 CI/CD Integration

### GitHub Actions Workflow (`.github/workflows/ci.yml`)

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Run Shannon tests
        run: pytest tests/ -v
      
      - name: Run CI tests (with mocks)
        run: pytest tests-ci/ -c tests-ci/pytest-ci.ini -v
      
      # Local tests NOT run (no API keys in CI)
```

### Expected CI Results
```
✅ Shannon Tests: 15/15 passed
✅ CI Tests: 60 passed, 26 skipped
⚠️ Local Tests: Not run (requires API keys)
✅ Total: 75 passed, 26 skipped
```

---

## 📊 Coverage Report

### Current Coverage (108 tests total)

| Suite | Tests | Passed | Skipped | Failed | Coverage |
|-------|-------|--------|---------|--------|----------|
| **tests/** (Shannon) | 15 | 15 | 0 | 0 | 100% |
| **tests-ci/** (CI) | 86 | 60 | 26 | 0 | 85% |
| **tests-local/** (Local) | 7 | 7 | 0 | 0 | 100% |
| **TOTAL** | **108** | **82** | **26** | **0** | **90%** |

### Module Coverage

```
intelligence/
├── unified_quantum_classifier.py    100% (Shannon + CI + Local)
├── neural_pathway_manager.py        100% (CI + Local)
├── local_synapse.py                 100% (Local)
├── cloud_synapse.py                 100% (Local)
├── neural_reflexes.py               95% (CI)
├── quantum_metrics.py               100% (CI)
└── neural_prometheus.py             90% (CI)

commands/
├── quantum_commands.py              85% (CI)
├── translation.py                   80% (CI, requires DeepL)
└── utils_commands.py                90% (CI)

core/
├── cache.py                         75% (CI, optional impl)
├── rate_limiter.py                  100% (CI)
└── handlers.py                      70% (CI, optional impl)

backends/
├── game_cache.py                    90% (CI + Local)
├── quantum_game_cache.py            95% (CI + Local)
└── game_lookup.py                   100% (Local)
```

---

## 🐛 Bug Discovery

### Example: QuantumMetrics Bug (Found by Local Tests)

**CI Tests** : ✅ Passed (mocked QuantumMetrics)
**Local Tests** : ❌ Failed (real method call)

```python
# Bug revealed by tests-local/test_neural_with_llm.py
TypeError: QuantumMetrics.record_classification() got unexpected keyword argument 'result'
```

**Root Cause** : Production code passing dict instead of unpacking parameters

**Fix** : Changed from `result=quantum_result` to individual params

**Lesson** : **Local tests with real APIs catch production bugs that mocked CI tests miss!**

---

## 🎯 Best Practices

### Do ✅
- Run Shannon tests before every commit
- Run local tests before pushing
- Use markers correctly (`@pytest.mark.local`, etc.)
- Write descriptive test names
- Test edge cases (empty input, None, errors)
- Validate formulas with known values

### Don't ❌
- Skip Shannon tests (sacred formulas)
- Mock Shannon calculations (must be real)
- Put API keys in CI tests
- Commit with failing local tests
- Test implementation details (test behavior)

---

## 📚 Related Documentation

- **[CI/CD Workflow](CI_CD.md)** - GitHub Actions details
- **[Architecture](ARCHITECTURE.md)** - System design
- **[Intelligence](INTELLIGENCE.md)** - Shannon formulas

---

<div align="center">

**[⬆️ Back to Index](INDEX.md)** | **[Next: CI/CD →](CI_CD.md)**

</div>
