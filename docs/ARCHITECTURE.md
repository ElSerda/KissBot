# 🏗️ KissBot Architecture

> **Neural V2 System** - Quantum Code Inference with Shannon Entropy

---

## 📋 Table of Contents

- [System Overview](#system-overview)
- [Core Components](#core-components)
- [Intelligence Layer](#intelligence-layer)
- [Command Layer](#command-layer)
- [Data Flow](#data-flow)
- [Scalability](#scalability)

---

## 🎯 System Overview

KissBot utilise une **architecture Neural V2** basée sur trois piliers :

1. **🧮 Quantum Code Inference** - Classification de code avec Shannon Entropy
2. **🧠 Neural Pathways** - Routage intelligent des stimuli
3. **⚡ Hybrid Response** - Local Reflexes + Cloud LLM

```
┌─────────────────────────────────────────────────────────┐
│                    Twitch Chat Input                     │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Neural Pathway Manager                      │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Quantum Classifier (Shannon Entropy)            │  │
│  │  H(X) = -Σ p(x)log₂(p(x))                       │  │
│  │  Confidence = 0.7*shannon + 0.2*prob + 0.1*dom   │  │
│  └──────────────────────────────────────────────────┘  │
│                       │                                  │
│         ┌─────────────┴─────────────┐                   │
│         ▼                           ▼                    │
│  ┌──────────────┐          ┌──────────────┐            │
│  │   Reflexes   │          │   Synapses   │            │
│  │ (Local/Fast) │          │ (LLM/Smart)  │            │
│  └──────────────┘          └──────────────┘            │
└─────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                 Commands Components                      │
│  TranslationCommands | QuantumCommands | Utils | ...    │
└─────────────────────────────────────────────────────────┘
```

---

## 🔧 Core Components

### 1. Intelligence Layer (`intelligence/`)

#### **Neural Pathway Manager** (`neural_pathway_manager.py`)
- **Rôle** : Routage central des stimuli utilisateur
- **Méthode** : `process_stimulus(stimulus: str, context: str) → str | None`
- **Pipeline** :
  1. Classification Quantique (Shannon Entropy)
  2. Sélection Reflex vs Synapse
  3. Génération réponse
  4. Métriques & Logs

#### **Unified Quantum Classifier** (`unified_quantum_classifier.py`)
- **Rôle** : Classification de code avec multi-facteurs
- **Formule Sacrée** :
  ```python
  confidence = shannon_confidence * 0.7 + prob_factor * 0.2 + dominance_factor * 0.1
  ```
- **Output** :
  ```python
  {
    'class': 'python' | 'javascript' | 'uncertain',
    'confidence': 0.0-1.0,
    'entropy': float,
    'is_certain': bool,
    'should_fallback': bool,
    'distribution_type': 'dominant' | 'balanced' | 'uncertain'
  }
  ```

#### **Synapses** (Local/Cloud)
- **LocalSynapse** (`local_synapse.py`) : Ollama local (rapide, privé)
- **CloudSynapse** (`cloud_synapse.py`) : OpenRouter cloud (puissant, API)
- **Interface** : `fire(stimulus, context, stimulus_class, correlation_id) → str`

#### **Reflexes** (`neural_reflexes.py`)
- **Rôle** : Réponses instantanées sans LLM
- **Patterns** : Salutations, aide, commandes simples
- **Avantage** : Latence < 10ms, pas de coût API

---

### 2. Command Layer (`commands/`)

#### **TwitchIO 3.x Components**
```python
class QuantumCommands(Component):
    def __init__(self):  # Pas de bot param
        super().__init__()
    
    @command(name='quantum')
    async def quantum_cmd(self, ctx: Context):
        bot = ctx.bot  # Accès via ctx
```

#### **26 Commandes Actives**
- **Translation** : `!trad`, `!translate`, `!lang`
- **Quantum** : `!quantum`, `!classify`, `!entropy`
- **Utils** : `!ping`, `!uptime`, `!stats`
- **Game** : `!game`, `!setgame`, `!playing`
- **Modération** : `!timeout`, `!ban`, `!clear`

---

### 3. Backend Layer (`backends/`)

#### **Game Cache** (`game_cache.py`)
- RAWG API integration
- Cache Redis-like (30min TTL)
- Quantum state tracking

#### **Quantum Game Cache** (`quantum_game_cache.py`)
- Classification de jeux avec Shannon
- Fallback intelligent si API fail

---

### 4. Core Layer (`core/`)

#### **Rate Limiter** (`rate_limiter.py`)
- Cooldown par user/command
- Protection spam

#### **Cache Interface** (`cache_interface.py`)
- Abstraction cache générique
- TTL, invalidation

#### **Handlers** (`handlers.py`)
- Event handlers Twitch
- EventSub webhooks

---

## 🔄 Data Flow

### 1️⃣ Message Twitch → Neural Pathway
```
User: "!quantum print('hello')"
  ↓
TwitchIO Context
  ↓
QuantumCommands.quantum_cmd(ctx)
  ↓
neural_pathway_manager.process_stimulus("print('hello')", context="quantum")
```

### 2️⃣ Neural Pathway → Classification
```
UnifiedQuantumClassifier.classify_code("print('hello')")
  ↓
Shannon Entropy: H(X) = 1.23
  ↓
Classification: 'python' (confidence: 0.87)
  ↓
Distribution: 'dominant' (python: 0.75, javascript: 0.15, cpp: 0.10)
```

### 3️⃣ Classification → Routing
```
is_certain = True (confidence > 0.7)
  ↓
Try Reflex first (fast)
  ↓
If no reflex match → LocalSynapse.fire() (Ollama)
  ↓
If LocalSynapse fail → CloudSynapse.fire() (OpenRouter)
```

### 4️⃣ Response → Metrics
```
QuantumMetrics.record_classification(
  stimulus="print('hello')",
  classification="python",
  confidence=0.87,
  entropy=1.23,
  response_time_ms=45
)
```

---

## 📊 Scalability

### Performance Targets
- **Reflex Response** : < 10ms
- **Local LLM** : < 200ms
- **Cloud LLM** : < 1000ms
- **Cache Hit** : < 5ms

### Bottlenecks & Solutions
| Bottleneck | Solution |
|------------|----------|
| LLM latency | Reflexes + Local fallback |
| API rate limits | Cache + cooldowns |
| Memory usage | TTL eviction + max size |
| CPU spikes | Async processing |

### Horizontal Scaling
- **Multi-channel** : 1 bot instance = N channels
- **Load balancing** : EventSub webhook distribution
- **Cache clustering** : Redis/Memcached

---

## 🎛️ Configuration

Voir **[CONFIG.md](CONFIG.md)** pour détails complets.

### Key Settings
```yaml
intelligence:
  enabled: true
  classifier:
    confidence_threshold: 0.7  # SACRED
    
neural_v2:
  pathway_manager:
    use_reflexes: true
    use_local_synapse: true
    use_cloud_synapse: true
  
  local_synapse:
    endpoint: "http://localhost:11434"
    model: "llama3.2:latest"
    
  cloud_synapse:
    provider: "openrouter"
    model: "meta-llama/llama-3.1-8b-instruct:free"
```

---

## 🔍 Debugging

### Intelligence Logs
```python
logger.info(f"🧠 [STIMULUS] {stimulus[:50]}")
logger.info(f"📊 [CLASSIFICATION] {classification} ({confidence:.2f})")
logger.info(f"⚡ [ROUTING] {'Reflex' if is_reflex else 'Synapse'}")
logger.info(f"✅ [RESPONSE] Generated in {response_time_ms}ms")
```

### Metrics Dashboard
- **Prometheus** : `intelligence/neural_prometheus.py`
- **Métriques** : Classifications, latences, erreurs
- **Quantum Metrics** : Distribution types, entropie

---

## 📚 Related Documentation

- **[Intelligence System](INTELLIGENCE.md)** - Deep dive Shannon Entropy
- **[Commands System](COMMANDS.md)** - TwitchIO 3.x Components
- **[Testing Guide](TESTING.md)** - Architecture de tests

---

<div align="center">

**[⬆️ Back to Index](INDEX.md)** | **[Next: Intelligence →](INTELLIGENCE.md)**

</div>
