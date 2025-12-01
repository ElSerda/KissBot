# 🎯 Pre-Optimized Prompts System

Guide complet pour créer des commandes avec prompts pré-optimisés dans KissBot.

---

## 📖 Table des Matières

1. [Concept](#-concept)
2. [Architecture](#-architecture)
3. [Quick Start](#-quick-start)
4. [Guide Complet](#-guide-complet)
5. [Exemples](#-exemples)
6. [Validation Défensive](#-validation-défensive)
7. [Multilingual Support](#-multilingual-support)
8. [Best Practices](#-best-practices)

---

## 🧠 Concept

### Problème : Double-Wrapping

Lorsque vous utilisez le pipeline normal, votre prompt est automatiquement enrichi :

```python
# ❌ Problème : Votre prompt optimisé est re-wrappé
prompt = "Réponds EN 1 PHRASE MAX : raconte une blague"

# Pipeline ajoute automatiquement :
# "Réponds EN 1 PHRASE MAX, SANS TE PRÉSENTER, comme KissBot (bot sympa). 
#  Max 120 caractères : Réponds EN 1 PHRASE MAX : raconte une blague"
#                       └─────────────────────────────────────────────┘
#                                 Double instruction !
```

**Résultat :** Prompt pollu, LLM confus, réponses incohérentes.

### Solution : Pre-Optimized Prompts

```python
# ✅ Solution : Bypass le wrapping automatique
response = await process_llm_request(
    llm_handler=self.llm_handler,
    prompt="Réponds EN 1 PHRASE MAX : raconte une blague",
    pre_optimized=True,  # ← Skip automatic wrapping
    stimulus_class="gen_short"
)
```

**Résultat :** Prompt envoyé tel quel au LLM, contrôle total.

---

## 🏗️ Architecture

### Flux de Données

```
┌─────────────────────────────────────────────────────────────┐
│                      COMMANDE                               │
│  !joke / !fact / !tip                                       │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  │ prompt + pre_optimized=True/False
                  ▼
┌─────────────────────────────────────────────────────────────┐
│              process_llm_request()                          │
│           (intelligence/core.py)                            │
└─────────────────┬───────────────────────────────────────────┘
                  │
         ┌────────┴────────┐
         │                 │
    pre_optimized?         │
         │                 │
    ┌────┴─────┐      ┌────┴─────┐
    │   YES    │      │    NO    │
    └────┬─────┘      └────┬─────┘
         │                 │
         │                 │ + Smart Context wrapping
         │                 │ + Personality injection
         │                 ▼
         │           process_stimulus()
         │           (Neural Pathway)
         │                 │
         │                 │
         ▼                 ▼
    local_synapse.fire()   
    (context="direct")     
         │                 
         │ NO WRAPPING     
         ▼                 
    ┌────────────────┐     
    │   LM STUDIO    │     
    │ Mistral 7B     │     
    └────────────────┘     
```

### Composants

1. **Commands Layer** (`commands/intelligence_commands.py`)
   - Définit les commandes TwitchIO
   - Appelle `process_llm_request()` avec `pre_optimized=True`

2. **Core Layer** (`intelligence/core.py`)
   - Gère la logique de routing
   - Validation défensive (fork-safe)
   - Routing conditionnel (pre-optimized vs normal)

3. **Synapse Layer** (`intelligence/synapses/local_synapse.py`)
   - `context="direct"` → bypass `_optimize_signal_for_local()`
   - Injection langue automatique (`llm.language`)
   - Transmission directe au LLM

---

## 🚀 Quick Start

### 1. Créer la Commande

```python
# commands/intelligence_commands.py

@commands.command(name="joke")
async def joke_command(self, ctx: commands.Context):
    """🎭 Bot raconte une blague courte"""
    
    # Initialiser LLM handler
    if not self._ensure_llm_handler(ctx.bot):
        await ctx.send(f"@{ctx.author.name} ❌ IA indisponible")
        return
    
    # Rate limiting (optionnel)
    if hasattr(ctx.bot, 'rate_limiter'):
        if not ctx.bot.rate_limiter.is_allowed(ctx.author.name, cooldown=10.0):
            remaining = ctx.bot.rate_limiter.get_remaining_cooldown(ctx.author.name, cooldown=10.0)
            await ctx.send(f"@{ctx.author.name} ⏱️ Cooldown! Attends {remaining:.1f}s")
            return
    
    # Prompt pré-optimisé (validé en POC)
    prompt = "Réponds EN 1 PHRASE MAX EN FRANÇAIS, SANS TE PRÉSENTER, style humoristique : raconte une blague courte"
    
    # Appel avec pre_optimized=True
    response = await process_llm_request(
        llm_handler=self.llm_handler,
        prompt=prompt,
        context="ask",
        user_name=ctx.author.name,
        game_cache=None,
        pre_optimized=True,        # ← Pas de wrapping
        stimulus_class="gen_short"  # ← Force courte
    )
    
    # Envoyer réponse
    if response:
        await ctx.send(f"@{ctx.author.name} {response}")
    else:
        await ctx.send(f"@{ctx.author.name} ❌ Erreur IA")
```

### 2. Tester en Local

```bash
# POC test dans tests-local/
python tests-local/test_joke_poc.py

# Valider : latence, langue, contenu
# Expected: <3s, français, cohérent
```

### 3. Tester en Production

```bash
# Lancer bot
python main.py

# Twitch chat
!joke

# Vérifier logs
tail -f logs/kissbot.log | grep "🎯 Prompt pré-optimisé"
```

---

## 📚 Guide Complet

### Étape 1 : Validation POC

**TOUJOURS** valider votre prompt en POC avant production :

```python
# tests-local/test_my_command_poc.py
import asyncio
from modules.intelligence.neural_pathway_manager import NeuralPathwayManager
import yaml

async def test_my_command():
    # Load config
    with open("config/config.yaml") as f:
        config = yaml.safe_load(f)
    
    # Init handler
    llm_handler = NeuralPathwayManager(config)
    
    # Test prompt (itérez jusqu'à satisfaction)
    prompts = [
        "Réponds EN 1 PHRASE : partage un fait scientifique",
        "Réponds EN 1 PHRASE MAX EN FRANÇAIS : fait scientifique intéressant",
        "Réponds EN 1 PHRASE MAX EN FRANÇAIS, SANS TE PRÉSENTER : partage un fait scientifique fascinant"
    ]
    
    for prompt in prompts:
        print(f"\n🔍 Test: {prompt[:50]}...")
        
        response = await llm_handler.local_synapse.fire(
            stimulus=prompt,
            context="direct",  # Bypass wrapping
            stimulus_class="gen_short",
            correlation_id="poc_test"
        )
        
        print(f"✅ Response: {response}")
        print(f"   Length: {len(response)} chars")

asyncio.run(test_my_command())
```

**Critères de validation :**
- ✅ Latence < 3s (Mistral 7B)
- ✅ Langue correcte (français si `llm.language: fr`)
- ✅ Format respecté (1 phrase, pas d'auto-présentation)
- ✅ Contenu cohérent (pas de hallucination)

### Étape 2 : Intégration Production

Une fois le prompt validé, intégrez-le dans `commands/intelligence_commands.py` :

```python
@commands.command(name="fact")
async def fact_command(self, ctx: commands.Context):
    """🔬 Bot partage un fait scientifique"""
    
    # 1. Validation handler
    if not self._ensure_llm_handler(ctx.bot):
        await ctx.send(f"@{ctx.author.name} ❌ IA indisponible")
        return
    
    # 2. Rate limiting (10s cooldown recommandé)
    if hasattr(ctx.bot, 'rate_limiter'):
        if not ctx.bot.rate_limiter.is_allowed(ctx.author.name, cooldown=10.0):
            remaining = ctx.bot.rate_limiter.get_remaining_cooldown(ctx.author.name, cooldown=10.0)
            await ctx.send(f"@{ctx.author.name} ⏱️ Cooldown! Attends {remaining:.1f}s")
            return
    
    # 3. Prompt validé en POC
    prompt = "Réponds EN 1 PHRASE MAX EN FRANÇAIS, SANS TE PRÉSENTER : partage un fait scientifique fascinant"
    
    # 4. Appel pre-optimized
    response = await process_llm_request(
        llm_handler=self.llm_handler,
        prompt=prompt,
        context="ask",
        user_name=ctx.author.name,
        game_cache=None,
        pre_optimized=True,
        stimulus_class="gen_short"  # Ou "gen_long" si besoin
    )
    
    # 5. Réponse Twitch
    if response:
        await ctx.send(f"@{ctx.author.name} 🔬 {response}")
    else:
        await ctx.send(f"@{ctx.author.name} ❌ Erreur IA")
```

### Étape 3 : Mise à Jour !help

```python
# commands/utils_commands.py

@commands.command(name="help")
async def help_command(self, ctx: commands.Context):
    """❓ Liste des commandes disponibles"""
    help_text = (
        "🤖 KissBot - Commandes: "
        "!ping !stats !help !game [nom] !gc [nom] !ask [question] !joke !fact"
        #                                                                  ^^^^^ Ajoutez ici
    )
    await ctx.send(help_text)
```

### Étape 4 : Tests Unitaires

```python
# tests-local/test_fact_command.py
import pytest
from unittest.mock import AsyncMock
from modules.intelligence.core import process_llm_request

@pytest.mark.asyncio
async def test_fact_pipeline_success():
    """Test pipeline !fact avec prompt pré-optimisé"""
    
    # Mock LLM handler
    llm_handler = AsyncMock()
    llm_handler.local_synapse = AsyncMock()
    llm_handler.local_synapse.fire = AsyncMock(
        return_value="Le cerveau humain contient environ 86 milliards de neurones."
    )
    
    # Execute pipeline
    response = await process_llm_request(
        llm_handler=llm_handler,
        prompt="Réponds EN 1 PHRASE MAX : partage un fait scientifique",
        context="ask",
        user_name="TestUser",
        game_cache=None,
        pre_optimized=True,
        stimulus_class="gen_short"
    )
    
    # Verify
    assert response is not None
    assert len(response) > 10
    llm_handler.local_synapse.fire.assert_called_once()
```

---

## 💡 Exemples

### Example 1: !joke (Implémenté)

```python
@commands.command(name="joke")
async def joke_command(self, ctx: commands.Context):
    """🎭 Blague courte"""
    
    prompt = "Réponds EN 1 PHRASE MAX EN FRANÇAIS, SANS TE PRÉSENTER, style humoristique : raconte une blague courte"
    
    response = await process_llm_request(
        llm_handler=self.llm_handler,
        prompt=prompt,
        context="ask",
        user_name=ctx.author.name,
        game_cache=None,
        pre_optimized=True,
        stimulus_class="gen_short"
    )
    
    if response:
        await ctx.send(f"@{ctx.author.name} {response}")
```

**Résultat :**
```
User: !joke
Bot: @user Un singe et un cochon sont dans la jungle. le singe a un crayon sous la queue...
```

### Example 2: !fact (À implémenter)

```python
@commands.command(name="fact")
async def fact_command(self, ctx: commands.Context):
    """🔬 Fait scientifique"""
    
    prompt = "Réponds EN 1 PHRASE MAX EN FRANÇAIS, SANS TE PRÉSENTER : partage un fait scientifique fascinant"
    
    response = await process_llm_request(
        llm_handler=self.llm_handler,
        prompt=prompt,
        context="ask",
        user_name=ctx.author.name,
        game_cache=None,
        pre_optimized=True,
        stimulus_class="gen_short"
    )
    
    if response:
        await ctx.send(f"@{ctx.author.name} 🔬 {response}")
```

### Example 3: !tip (À implémenter)

```python
@commands.command(name="tip")
async def tip_command(self, ctx: commands.Context):
    """💡 Conseil productivité"""
    
    prompt = "Réponds EN 1 PHRASE MAX EN FRANÇAIS, SANS TE PRÉSENTER : donne un conseil de productivité"
    
    response = await process_llm_request(
        llm_handler=self.llm_handler,
        prompt=prompt,
        context="ask",
        user_name=ctx.author.name,
        game_cache=None,
        pre_optimized=True,
        stimulus_class="gen_short"
    )
    
    if response:
        await ctx.send(f"@{ctx.author.name} 💡 {response}")
```

### Example 4: !quote (À implémenter)

```python
@commands.command(name="quote")
async def quote_command(self, ctx: commands.Context):
    """📜 Citation inspirante"""
    
    prompt = "Réponds EN 1 PHRASE MAX EN FRANÇAIS, SANS TE PRÉSENTER : partage une citation inspirante sur la technologie"
    
    response = await process_llm_request(
        llm_handler=self.llm_handler,
        prompt=prompt,
        context="ask",
        user_name=ctx.author.name,
        game_cache=None,
        pre_optimized=True,
        stimulus_class="gen_short"
    )
    
    if response:
        await ctx.send(f"@{ctx.author.name} 📜 {response}")
```

---

## 🛡️ Validation Défensive

Le système inclut une validation défensive pour garantir la fork-safety (ports C++/Rust) :

### Code (`intelligence/core.py`)

```python
async def process_llm_request(
    llm_handler, 
    prompt: str, 
    context: str, 
    user_name: str, 
    game_cache=None,
    pre_optimized: bool = False,
    stimulus_class: str = "gen_short"
) -> str | None:
    
    import logging
    logger = logging.getLogger(__name__)
    
    # ✅ VALIDATION DÉFENSIVE (fork-safe, language-agnostic)
    
    # 1. Null check on llm_handler (prevent AttributeError/segfault)
    if not llm_handler:
        logger.error("❌ llm_handler est None")
        return None
    
    # 2. Type conversion for pre_optimized (handle None/string/int → bool)
    if not isinstance(pre_optimized, bool):
        logger.warning(f"⚠️ pre_optimized type invalide ({type(pre_optimized)}), conversion bool")
        pre_optimized = bool(pre_optimized)
    
    # 3. Whitelist validation for stimulus_class (prevent invalid values)
    valid_classes = ["ping", "gen_short", "gen_long"]
    if stimulus_class not in valid_classes:
        logger.warning(f"⚠️ stimulus_class invalide '{stimulus_class}', fallback 'gen_short'")
        stimulus_class = "gen_short"
    
    # ... reste du code
```

### Pourquoi c'est Important ?

**Python (dynamique) :**
- `llm_handler = None` → `AttributeError: 'NoneType' has no attribute 'local_synapse'` (récupérable)
- `pre_optimized = "true"` → Interprété comme `True` (truthy)

**C++ (compilé) :**
- `llm_handler = nullptr` → **SEGFAULT** (crash fatal)
- `pre_optimized = "true"` → **ERREUR DE COMPILATION**

**Rust (compilé, sûr) :**
- `llm_handler = None` → **PANIC** (crash contrôlé)
- `pre_optimized = "true"` → **ERREUR DE COMPILATION**

La validation défensive garantit que :
1. Les contrats sont clairs (types, valeurs attendues)
2. Les erreurs sont gérées gracieusement
3. Les futurs ports C++/Rust ne crashent pas
4. Le code est documenté pour les contributeurs

---

## 🌐 Multilingual Support

### Configuration

```yaml
# config/config.yaml
llm:
  language: fr  # Supported: fr, en, es, de
```

### Injection Automatique

Le système injecte automatiquement la directive de langue dans tous les prompts :

```python
# Votre prompt
prompt = "Réponds EN 1 PHRASE MAX : raconte une blague"

# Système injecte (si language: fr)
# "Réponds EN 1 PHRASE MAX EN FRANÇAIS : raconte une blague"
```

**Mapping langue :**
- `fr` → "EN FRANÇAIS"
- `en` → "IN ENGLISH"
- `es` → "EN ESPAÑOL"
- `de` → "AUF DEUTSCH"

### Multi-langue dans Prompts

Si vous voulez forcer une langue spécifique (ignorer config) :

```python
# Force English (ignore config language)
prompt = "Answer IN 1 SENTENCE MAX IN ENGLISH, NO SELF-INTRODUCTION: tell a short joke"

response = await process_llm_request(
    llm_handler=self.llm_handler,
    prompt=prompt,
    context="ask",
    user_name=ctx.author.name,
    game_cache=None,
    pre_optimized=True,
    stimulus_class="gen_short"
)
```

**Note :** Le système n'injecte PAS de directive langue si `pre_optimized=True` et `context="direct"`, car il bypass `_optimize_signal_for_local()`.

---

## 🎯 Best Practices

### 1. Toujours Valider en POC

```bash
# ❌ MAL : Commiter prompt non testé
git commit -m "Add !fact command"

# ✅ BON : Valider POC d'abord
python tests-local/test_fact_poc.py
# → Itérer prompts jusqu'à satisfaction
git commit -m "Add !fact command (validated latency 2.1s, French)"
```

### 2. Pattern de Prompt Recommandé

```python
# ✅ Pattern validé Mistral AI
"Réponds EN 1 PHRASE MAX EN FRANÇAIS, SANS TE PRÉSENTER, style {style} : {instruction}"

# Exemples :
# style=humoristique : raconte une blague courte
# style=scientifique : partage un fait fascinant
# style=inspirant : donne un conseil de productivité
# style=neutre : explique un concept technique
```

**Pourquoi ce pattern ?**
- ✅ **"EN 1 PHRASE MAX"** → Force concision (limite tokens)
- ✅ **"EN FRANÇAIS"** → Force langue (ou injecté par config)
- ✅ **"SANS TE PRÉSENTER"** → Évite "Bonjour ! Je suis KissBot..." (hallucination)
- ✅ **"style {style}"** → Guide ton/personnalité
- ✅ **": {instruction}"** → Instruction claire

### 3. Choisir le Bon Stimulus Class

| Class | Timeout | Max Tokens | Usage |
|-------|---------|------------|-------|
| `"ping"` | 2s | 20 | Réponses ultra-courtes ("ok", "oui", "non") |
| `"gen_short"` | 4s | 100 | Réponses courtes (1 phrase, <120 chars) |
| `"gen_long"` | 8s | 150 | Réponses longues (2-3 phrases, <400 chars) |

```python
# ✅ BON : !joke = gen_short (1 phrase courte)
stimulus_class="gen_short"

# ❌ MAL : !joke = gen_long (trop de tokens alloués)
stimulus_class="gen_long"  # Gaspillage, LLM peut divaguer
```

### 4. Rate Limiting Systématique

```python
# ✅ TOUJOURS ajouter rate limiting
if hasattr(ctx.bot, 'rate_limiter'):
    if not ctx.bot.rate_limiter.is_allowed(ctx.author.name, cooldown=10.0):
        remaining = ctx.bot.rate_limiter.get_remaining_cooldown(ctx.author.name, cooldown=10.0)
        await ctx.send(f"@{ctx.author.name} ⏱️ Cooldown! Attends {remaining:.1f}s")
        return
```

**Cooldowns recommandés :**
- `!joke`, `!fact`, `!tip` : **10s** (commandes légères)
- `!ask` : **10s** (commandes LLM standard)
- `@bot mentions` : **15s** (commandes conversationnelles)

### 5. Error Handling Gracieux

```python
# ✅ BON : Gérer les erreurs explicitement
response = await process_llm_request(...)

if response:
    await ctx.send(f"@{ctx.author.name} {response}")
else:
    await ctx.send(f"@{ctx.author.name} ❌ Erreur IA, réessaye plus tard")

# ❌ MAL : Pas de gestion d'erreur
await ctx.send(f"@{ctx.author.name} {response}")  # Si None → "@user None"
```

### 6. Documentation Inline

```python
# ✅ BON : Documenter le prompt validé
@commands.command(name="joke")
async def joke_command(self, ctx: commands.Context):
    """
    🎭 Commande !joke - Bot raconte une blague courte.
    Pattern optimisé Mistral AI validé (POC: 2.34s, français, 100% succès).
    """
    
    # Prompt POC validé : pattern Mistral AI (0.54s, ~19 tokens)
    # pre_optimized=True → bypass wrapping automatique
    prompt = "Réponds EN 1 PHRASE MAX EN FRANÇAIS, SANS TE PRÉSENTER, style humoristique : raconte une blague courte"
    
    response = await process_llm_request(
        llm_handler=self.llm_handler,
        prompt=prompt,
        context="ask",
        user_name=ctx.author.name,
        game_cache=None,
        pre_optimized=True,       # ← Prompt déjà au format optimal
        stimulus_class="gen_short" # ← Force classification courte
    )
```

### 7. Tests Unitaires

```python
# ✅ TOUJOURS créer tests unitaires
# tests-local/test_joke_command.py

@pytest.mark.asyncio
async def test_joke_pipeline_success():
    """Test pipeline !joke: process_llm_request avec prompt pré-optimisé"""
    
    llm_handler = AsyncMock()
    llm_handler.local_synapse.fire = AsyncMock(
        return_value="Une blague courte !"
    )
    
    response = await process_llm_request(
        llm_handler=llm_handler,
        prompt="Réponds EN 1 PHRASE MAX : raconte une blague courte",
        context="ask",
        user_name="TestUser",
        game_cache=None,
        pre_optimized=True,
        stimulus_class="gen_short"
    )
    
    assert response is not None
    assert len(response) > 0
```

---

## 🔍 Debugging

### Logs de Debug

```bash
# Activer logs détaillés
tail -f logs/kissbot.log | grep "🎯"

# Output attendu :
# 2025-10-30 03:22:15,660 INFO intelligence.core 🎯 Prompt pré-optimisé détecté → Appel direct synapse
# 2025-10-30 03:22:19,391 INFO intelligence.synapses.local_synapse 💡✅ [preopt_ask] Success 3.73s - Reward: 1.00
```

### Checklist Debug

- [ ] LLM handler initialisé ? (`_ensure_llm_handler()` return `True`)
- [ ] `pre_optimized=True` dans `process_llm_request()` ?
- [ ] Log "🎯 Prompt pré-optimisé détecté" présent ?
- [ ] `stimulus_class` valide ? (`"ping"`, `"gen_short"`, `"gen_long"`)
- [ ] Réponse LLM non-None ?
- [ ] Langue correcte ? (vérifier `llm.language` dans config)
- [ ] Latence < 5s ? (Mistral 7B baseline : 2-4s)

### Problèmes Communs

**1. Réponse en anglais alors que `language: fr`**

```yaml
# ❌ Problème : Langue ignorée
llm:
  language: fr  # Config correcte

# Mais prompt force langue :
prompt = "Answer IN ENGLISH: tell a joke"  # ← Override config
```

**Solution :** Retirer la directive langue du prompt, laisser config injecter.

**2. Double-wrapping malgré `pre_optimized=True`**

```python
# ❌ Problème : Pas de bypass
response = await process_llm_request(
    prompt=prompt,
    pre_optimized=True,
    context="ask"  # ← Problème : context="ask" active wrapping
)
```

**Solution :** Utiliser `context="direct"` dans synapse ou s'assurer que `pre_optimized=True` active le bypass.

**3. Timeout constant**

```python
# ❌ Problème : Stimulus class trop ambitieux
stimulus_class="gen_long"  # 8s timeout
# Mais LLM génère 200 tokens → 12s → Timeout

# ✅ Solution : Réduire ambition
stimulus_class="gen_short"  # 4s timeout
# Prompt force "1 PHRASE MAX" → LLM génère 50 tokens → 2s → Success
```

---

## 📖 Ressources

- **Code source :** `intelligence/core.py` (ligne 44-130)
- **Exemple implémenté :** `commands/intelligence_commands.py` (`joke_command`)
- **Tests unitaires :** `tests-local/test_joke_command.py`
- **POC validation :** `braindev/test_joke_command.py`

---

## 🎓 Conclusion

Le système **pre-optimized prompts** vous donne :
- ✅ **Contrôle total** sur les prompts LLM
- ✅ **Performance optimale** (pas de wrapping inutile)
- ✅ **Validation POC** avant production
- ✅ **Fork-safety** pour ports C++/Rust
- ✅ **Support multilingue** automatique

**Workflow recommandé :**
1. **POC** : Valider prompt en local (`tests-local/`)
2. **Intégration** : Créer commande dans `commands/intelligence_commands.py`
3. **Tests** : Ajouter tests unitaires (`tests-local/test_*.py`)
4. **Production** : Tester en live, monitorer logs
5. **Documentation** : Mettre à jour `!help` et README.md

**Next steps :**
- 🎭 Implémenter `!fact`, `!tip`, `!quote`
- 📊 Créer registre de commandes (dict mapping)
- 🌐 Support multi-langue avancé (détection auto)
- 🔧 Optimisation prompts per-modèle (Mistral vs LLaMA vs Qwen)

---

**Questions ?** Ouvrir une issue sur GitHub ou rejoindre le stream ! 🚀
