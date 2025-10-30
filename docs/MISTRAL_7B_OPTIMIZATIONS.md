# 🎯 Optimisations Mistral 7B Instruct v0.3

Documentation complète des configurations optimales pour KissBot avec Mistral 7B Instruct v0.3.

## 📊 Résultats Globaux

**Total : 80 tests, 100% réussis, 0% dépassements**

| Contexte | Tests | Succès | Dépassements | Longueur moy | Status |
|----------|-------|--------|--------------|--------------|--------|
| **gen_short** (mentions) | 45 | 45/45 (100%) | 0/45 (0%) | 55 chars | ✅ OPTIMAL |
| **ask** (tech) | 8 | 8/8 (100%) | 0/8 (0%) | 138.8 chars | ✅ OPTIMAL |
| **ask** (sciences) | 22 | 22/22 (100%) | 0/22 (0%) | 142.0 chars | ✅ OPTIMAL |
| **gen_long** (explicatif) | 5 | 5/5 (100%) | 0/5 (0%) | ~130 chars | ✅ OPTIMAL |

---

## 🎯 Context 1 : !ask (Questions Factuelles)

### Configuration Optimale

```python
# SYSTÈME À DOUBLE SÉCURITÉ
max_tokens = 200        # Limite souple (guidage modèle)
temperature = 0.3       # Factuel, peu de créativité
repeat_penalty = 1.1    # Optimal pour max_tokens=200
stop_tokens = ["\n", "🔚"]

# Post-traitement (ligne ~491)
hard_cut = 250 chars    # Limite brute (+25% marge)
```

### Prompt

```python
"Réponds EN 1 PHRASE MAX {lang}, SANS TE PRÉSENTER, comme un bot Twitch factuel. "
"Max 200 caractères : {stimulus}"
```

### Résultats Prouvés (30 tests)

**Tech (8 tests) :**
- ✅ 8/8 réussis (100%)
- ✅ 0 dépassements >250 chars (0%)
- ✅ Longueur moyenne : 138.8 chars
- ✅ Range : 102-179 chars

**Sciences (22 tests) :**
- ✅ 22/22 réussis (100%)
- ✅ 0 dépassements >250 chars (0%)
- ✅ Longueur moyenne : 142.0 chars
- ✅ Range : 61-233 chars

**Distribution des longueurs :**
```
< 100 chars   : 18.2% ███
100-150 chars : 45.5% █████████  (Sweet spot)
150-200 chars : 22.7% ████
200-250 chars : 13.6% ██
> 250 chars   :  0.0%
```

### Exemples de Questions Testées

**Tech :** Python, GPU, Twitch, Linux, IA, serveur, JavaScript, RAM

**Sciences :** gravité, photon, relativité, énergie cinétique, atome, molécule, ADN, ion, photosynthèse, algorithme, dérivée, nombre premier, matrice, cellule, évolution, virus, trou noir, galaxie, Big Bang, blockchain, machine learning, GPU quantique

### Fonctionnement du Système à Double Sécurité

1. **Limite souple (guidage) : max_tokens=200**
   - Guide le modèle vers concision
   - Respectée dans 100% des cas testés
   - Permet flexibilité selon complexité sujet

2. **Limite brute (hard-cut) : 250 chars**
   - Post-traitement avec `_hard_truncate()`
   - Marge de sécurité : 200 + 25% = 250
   - Coupe brutalement à la dernière phrase complète
   - **Jamais déclenchée dans tests** (preuve que guidage suffit)

### Avantages

✅ **Robustesse** : Fonctionne même sur sujets complexes (physique quantique, biologie moléculaire)  
✅ **Flexibilité** : S'adapte à la complexité (61-233 chars selon besoin)  
✅ **Qualité** : Définitions complètes et précises  
✅ **Sécurité** : Double filet garantit ≤250 chars  
✅ **Twitch-compatible** : Largement sous limite 400 chars  

---

## 🎯 Context 2 : gen_short (Mentions Courtes)

### Configuration Optimale

```python
max_tokens = 200        # Réponses développées
temperature = 0.7       # Créatif et naturel
repeat_penalty = 1.1    # Évite répétitions
stop_tokens = ["\n"]
```

### Résultats Prouvés (45 tests)

- ✅ 45/45 réussis (100%)
- ✅ 0 dépassements >200 chars (0%)
- ✅ Longueur moyenne : 55 chars (ultra-punchy)
- ✅ Emojis : 43/45 (95.6%)

### Status

**✅ CONFIG ACTUELLE DÉJÀ OPTIMALE - AUCUN CHANGEMENT NÉCESSAIRE**

Questions testées : "ça va?", "t'es qui?", "tu fais quoi?", "tu stream quoi?", "t'es cool?"

---

## 🎯 Context 3 : gen_long (Mentions Explicatives)

### Configuration Optimale

```python
# OPTIMISATIONS MISTRAL AI
max_tokens = 100        # Strict pour éviter dérive
temperature = 0.4       # Moins de créativité = moins divagations
repeat_penalty = 1.2    # Évite répétitions
stop_tokens = ["🔚", "\n", "400.", "Exemple :", "En résumé,"]

# Post-traitement obligatoire (ligne ~492)
_remove_derives()       # Coupe mots dérivants
_hard_truncate(400)     # Force ≤400 chars
```

### Prompt Anti-Dérive

```python
"RÈGLES STRICTES (NON NÉGOCIABLES):
1. **MAX 2 PHRASES** (pas de listes 1. 2. 3.)
2. **MAX 400 CARACTÈRES** (coupe-toi si tu dépasses)
3. **Réponds {lang}, SANS TE PRÉSENTER**
4. **Termine par 🔚**

FORMAT OBLIGATOIRE:
\"Définition courte avec exemple concret 💡. Cas d'usage pratique 🎯. 🔚\"

Question : {stimulus}"
```

### Résultats Prouvés (5 tests)

- ✅ 5/5 réussis (100%)
- ✅ 0 dépassements >400 chars (0%)
- ✅ Longueur moyenne : ~130 chars
- ✅ 0% de dérive (vs 100% avant optimisation)

### Fonctionnement Anti-Dérive

1. **Prompt strict** : Contraintes claires + format obligatoire + exemple référence
2. **max_tokens=100** : Limite drastique force concision
3. **stop_tokens agressifs** : Coupe listes et divagations
4. **Post-processing** : `_remove_derives()` + `_hard_truncate(400)`

### Mots Dérivants Détectés (13)

```python
DERIVE_TRIGGERS = [
    "par exemple", "notamment", "en particulier",
    "également", "aussi", "en outre",
    "de plus", "par ailleurs", "d'autre part",
    "en effet", "ainsi", "donc", "c'est-à-dire"
]
```

---

## 📋 Récapitulatif des Limites

| Contexte | Limite Twitch | Limite Souple | Limite Brute | Marge |
|----------|---------------|---------------|--------------|-------|
| **ask** | 400 chars | 200 tokens | 250 chars | +25% |
| **gen_short** | 400 chars | 200 tokens | 200 chars | 0% |
| **gen_long** | 400 chars | 100 tokens | 400 chars | 0% |

---

## 🔍 Méthodologie de Test

### Tests Matrix (gen_short & ask)

```python
configs = [
    # Baseline (config actuelle)
    (max_tokens, temperature, repeat_penalty),
    
    # Variations systématiques
    max_tokens: [100, 150, 200, 250]
    temperature: [0.2, 0.3, 0.5, 0.7, 0.9]
    repeat_penalty: [1.0, 1.1, 1.2, 1.3]
    
    # Combinaisons optimales ciblées
]

# Score = 100 (base) + bonuses - penalties
# Bonus : sweet spot length (+10)
# Penalties : overruns, missing emojis, too many phrases
```

### Tests Validation (production-like)

```python
questions = [
    # Tech basique
    "c'est quoi Python", "c'est quoi un GPU", ...
    
    # Sciences complexes
    "c'est quoi la relativité", "c'est quoi un trou noir", ...
]

# Métriques : longueur, dépassements, qualité, distribution
```

---

## 🚀 Recommandations

### ✅ Déploiement Production

1. **Configs actuelles validées** : Déployer tel quel
2. **Monitoring** : Vérifier logs pour dépassements rares
3. **A/B testing** : Comparer avec anciennes configs si besoin

### 📊 Métriques à Surveiller

- **Taux de dépassements** (doit rester <5%)
- **Longueur moyenne** par contexte
- **Feedback utilisateurs** (qualité réponses)
- **Variété des réponses** (éviter répétitions)

### 🔧 Ajustements Possibles

Si dépassements en production :
- **ask** : Réduire hard_cut 250→200 chars
- **gen_long** : Réduire max_tokens 100→80
- **gen_short** : Réduire max_tokens 200→180

---

## 📝 Changelog

### 2025-10-30 : Optimisations Mistral 7B

- ✅ **gen_long** : Implémenté anti-dérive (Mistral AI recommendations)
- ✅ **ask** : Système double sécurité (200 tokens + hard_cut 250)
- ✅ **gen_short** : Confirmé config optimale (aucun changement)
- ✅ **Tests** : 80 tests, 100% réussite, 0% dépassements

### Résultats Avant/Après

| Metric | Avant | Après | Amélioration |
|--------|-------|-------|--------------|
| gen_long dépassements | 100% | 0% | **-100%** |
| gen_long longueur | 426 chars | 130 chars | **-69%** |
| ask dépassements | 22% | 0% | **-100%** |
| ask qualité | Coupée | Complète | **+100%** |

---

## 🔗 Références

- **Modèle** : Mistral 7B Instruct v0.3
- **LM Studio** : localhost:1234
- **Tests** : `tests-local/test_*.py`
- **Code** : `intelligence/synapses/local_synapse.py`

**Testé et validé par A+B** ✅
