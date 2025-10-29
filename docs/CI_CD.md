# 🔄 KissBot CI/CD Guide

> **GitHub Actions** - Automated Testing & Deployment

---

## 📋 Table of Contents

- [Overview](#overview)
- [Workflow Structure](#workflow-structure)
- [Jobs](#jobs)
- [Secrets Management](#secrets-management)
- [Deployment](#deployment)
- [Monitoring](#monitoring)

---

## 🎯 Overview

KissBot utilise **GitHub Actions** pour automatiser :
- ✅ Tests (Shannon + CI)
- ✅ Linting (Ruff + MyPy)
- ✅ Security audit (Safety)
- 🚀 Deployment (future)

### Workflow Triggers
```yaml
on:
  push:
    branches: [ main, develop, dev ]
  pull_request:
    branches: [ main, develop ]
```

---

## 🏗️ Workflow Structure

### File: `.github/workflows/ci.yml`

```yaml
name: KissBot CI

jobs:
  test:      # 15 Shannon + 86 CI tests
  lint:      # Ruff + MyPy
  security:  # Safety audit
```

---

## 🧪 Jobs

### 1. Test Job

**Objectif** : Valider code avec Shannon + CI tests

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
```

#### Steps

##### 📥 Checkout Code
```yaml
- name: 📥 Checkout code
  uses: actions/checkout@v4
```

##### 🐍 Setup Python
```yaml
- name: 🐍 Setup Python ${{ matrix.python-version }}
  uses: actions/setup-python@v5
  with:
    python-version: ${{ matrix.python-version }}
    cache: 'pip'
```

##### 📦 Install Dependencies
```yaml
- name: 📦 Install dependencies
  run: |
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    pip install pytest pytest-asyncio pytest-cov
```

##### 🧮 Run Shannon Tests
```yaml
- name: 🧮 Run Shannon tests (mathematical validation)
  run: |
    echo "::group::Shannon Entropy Tests (Sacred Formulas)"
    pytest tests/ -v --tb=short
    echo "::endgroup::"
```

**Expected Output** :
```
tests/test_intelligence_integration.py::test_shannon_entropy_calculation PASSED
tests/test_intelligence_integration.py::test_multi_factor_confidence PASSED
... (15 tests) ...
===================== 15 passed in 0.45s =====================
```

##### 🏗️ Run CI Tests
```yaml
- name: 🏗️ Run CI tests (structure validation with mocks)
  run: |
    echo "::group::CI Tests (Structure + Imports)"
    pytest tests-ci/ -c tests-ci/pytest-ci.ini -v --tb=short
    echo "::endgroup::"
```

**Expected Output** :
```
tests-ci/test_core.py ................ [ 60%]
tests-ci/test_neural_v2.py ........... [ 80%]
tests-ci/test_backends.py ............ [ 90%]
tests-ci/test_twitch.py .............. [100%]
============ 60 passed, 26 skipped in 2.34s ============
```

##### 📊 Generate Summary
```yaml
- name: 📊 Generate test summary
  if: always()
  run: |
    echo "## 🎯 KissBot Test Results" >> $GITHUB_STEP_SUMMARY
    echo "" >> $GITHUB_STEP_SUMMARY
    echo "### 🧮 Shannon Tests (Mathematical - 15 tests)" >> $GITHUB_STEP_SUMMARY
    pytest tests/ --tb=no -q >> $GITHUB_STEP_SUMMARY 2>&1 || true
    echo "" >> $GITHUB_STEP_SUMMARY
    echo "### 🏗️ CI Tests (Structure - 86 tests)" >> $GITHUB_STEP_SUMMARY
    pytest tests-ci/ -c tests-ci/pytest-ci.ini --tb=no -q >> $GITHUB_STEP_SUMMARY 2>&1 || true
```

**GitHub UI Output** :
```
🎯 KissBot Test Results

🧮 Shannon Tests (Mathematical - 15 tests)
15 passed in 0.45s

🏗️ CI Tests (Structure - 86 tests)
60 passed, 26 skipped in 2.34s

ℹ️ Note: Local tests (7 tests with real API keys) are not run in CI

Total Coverage: 101 tests (15 Shannon + 86 CI)
```

---

### 2. Lint Job

**Objectif** : Code quality & type checking

```yaml
jobs:
  lint:
    runs-on: ubuntu-latest
```

#### Steps

##### 🔍 Ruff (Fast Linter)
```yaml
- name: 🔍 Lint with Ruff (fast Python linter)
  run: |
    ruff check . --select E,F,W --ignore E501
  continue-on-error: true
```

**Checks** :
- **E** : PEP8 errors
- **F** : Pyflakes errors (imports, undefined vars)
- **W** : Warnings
- **Ignore E501** : Line too long (we accept long lines)

##### 🔍 MyPy (Type Checker)
```yaml
- name: 🔍 Type check with MyPy
  run: |
    mypy intelligence/ commands/ core/ backends/ --ignore-missing-imports
  continue-on-error: true
```

**Output Example** :
```
intelligence/neural_pathway_manager.py:45: error: Argument 1 has incompatible type
commands/quantum_commands.py:123: note: Revealed type is 'Optional[str]'
Found 2 errors in 2 files (checked 42 source files)
```

---

### 3. Security Job

**Objectif** : Audit dépendances pour vulnérabilités

```yaml
jobs:
  security:
    runs-on: ubuntu-latest
```

#### Steps

##### 🔒 Safety Check
```yaml
- name: 🔒 Security audit (dependencies)
  run: |
    python -m pip install --upgrade pip
    pip install safety
    safety check --json || true
  continue-on-error: true
```

**Output Example** :
```json
{
  "vulnerabilities": [
    {
      "package": "requests",
      "installed_version": "2.25.0",
      "affected_versions": "<2.31.0",
      "advisory": "CVE-2023-32681",
      "severity": "HIGH"
    }
  ]
}
```

---

## 🔐 Secrets Management

### GitHub Secrets (Not Used in CI)

KissBot CI **n'utilise PAS de secrets** car :
- ✅ Shannon tests = calculs purs (pas d'API)
- ✅ CI tests = mocks (pas de vraies clés)
- ❌ Local tests = skipped in CI (nécessitent clés)

### Local Development Secrets

Pour `tests-local/` (dev uniquement) :

```yaml
# config.yaml (NOT committed)
apis:
  rawg:
    api_key: "your_rawg_key_here"

neural_v2:
  local_synapse:
    endpoint: "http://localhost:11434"
  cloud_synapse:
    api_key: "your_openrouter_key_here"
```

**⚠️ Ne JAMAIS commit config.yaml avec vraies clés !**

---

## 🚀 Deployment (Future)

### Planned Workflow

```yaml
jobs:
  deploy:
    needs: [test, lint, security]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    
    steps:
      - name: 🚀 Deploy to production
        run: |
          # SSH to server
          # Pull latest code
          # Restart bot service
```

### Deployment Checklist
- [ ] All tests passing (Shannon + CI)
- [ ] Lint clean
- [ ] Security audit clean
- [ ] Config validated
- [ ] Secrets configured on server
- [ ] Backup current version
- [ ] Deploy
- [ ] Verify bot online
- [ ] Monitor logs

---

## 📊 Monitoring

### GitHub Actions Dashboard

**URL** : `https://github.com/YourUsername/KissBot/actions`

**Metrics** :
- ✅ Build success rate
- ⏱️ Average build time
- 📊 Test pass rate
- 🔴 Failed builds

### Build Status Badge

```markdown
![CI Status](https://github.com/YourUsername/KissBot/workflows/KissBot%20CI/badge.svg)
```

---

## 🐛 Troubleshooting

### Common Issues

#### ❌ Shannon Tests Fail
```
FAILED tests/test_intelligence_integration.py::test_shannon_entropy
AssertionError: assert 1.234 == 1.456
```

**Cause** : Formula modification (SACRED)
**Solution** : Revert changes to Shannon calculations

#### ❌ CI Tests Fail (Import Errors)
```
ModuleNotFoundError: No module named 'intelligence'
```

**Cause** : Missing dependency in requirements.txt
**Solution** : Add missing package

#### ❌ Timeout
```
The job running on runner GitHub Actions 1 has exceeded the maximum execution time of 360 minutes.
```

**Cause** : Infinite loop or stuck test
**Solution** : Add timeouts to async tests

#### ⚠️ Tests Skipped
```
26 skipped (requires_llm, requires_rawg)
```

**Cause** : Normal behavior (LLM/API tests skip in CI)
**Solution** : This is expected! Run `tests-local/` in dev for full coverage

---

## 📈 Performance

### Target Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Total build time | < 5 min | ~3 min |
| Shannon tests | < 1 min | ~0.45s |
| CI tests | < 3 min | ~2.34s |
| Lint | < 30s | ~15s |
| Security | < 1 min | ~30s |

### Optimization Tips
- ✅ Use `cache: 'pip'` for dependencies
- ✅ Run tests in parallel (future)
- ✅ Skip slow tests with markers
- ✅ Use `continue-on-error: true` for non-critical jobs

---

## 🔄 Workflow Evolution

### Version History

**v1.0** (Initial)
- Basic pytest tests
- Manual run only

**v2.0** (Current)
- GitHub Actions automation
- Shannon + CI separation
- Lint + Security jobs
- Test summary in UI

**v3.0** (Future)
- Deployment automation
- Coverage reports
- Performance benchmarks
- Multi-environment testing

---

## 📚 Related Documentation

- **[Testing Guide](TESTING.md)** - Test suites details
- **[Architecture](ARCHITECTURE.md)** - System design
- **[Deployment](../DEPLOY_NEURAL_V2.md)** - Production deployment

---

<div align="center">

**[⬆️ Back to Index](INDEX.md)** | **[Previous: Testing](TESTING.md)**

</div>
