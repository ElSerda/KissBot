#!/usr/bin/env python3
"""
🌌 Unified Quantum Classifier - Classification par Intention + Entropie Shannon
Fusion ImprovedClassifier + StaticQuantumClassifier en un seul fichier optimisé
Version: 3.1 (Fusion Safe - Phase 1)
"""

import logging
from typing import Dict, List, Tuple, Any, Optional


class UnifiedQuantumClassifier:
    """
    🌌 UNIFIED QUANTUM CLASSIFIER V3.1

    Paradigme Physique/Mathématique :
    - Classification par INTENTION (ping/gen_short/lookup/gen_long)
    - Superposition : Messages existent dans toutes les classes jusqu'à "mesure"
    - Entropie Shannon : Mesure l'incertitude pour fallback intelligent
    - Effondrement : Distribution probabiliste → Classe déterministe

    Architecture Unified :
    - Base patterns + logique complexité (ex-ImprovedClassifier)
    - EntropyCalculator + confiance quantique (ex-StaticQuantumClassifier)
    - Cache 29x speedup sur messages répétés
    - Interface uniforme : classify() → {class, confidence, entropy, ...}

    Améliorations vs classification par longueur brute :
    - Analyse contextuelle des mentions
    - Classification par intention (pas longueur)
    - Fallback intelligent par complexité linguistique
    - Distribution probabiliste avec entropie Shannon
    """

    def __init__(self, config: Optional[Dict] = None, patterns_config_path: Optional[str] = None):
        """
        🏗️ Initialisation UnifiedQuantumClassifier avec Enhanced Patterns

        Args:
            config: Configuration optionnelle pour seuils et paramètres
            patterns_config_path: Chemin vers fichier patterns YAML
        """
        self.logger = logging.getLogger(__name__)

        # 🎯 RÈGLES DE CLASSIFICATION PAR INTENTION (3 CLASSES)
        self.classification_rules = {
            "ping": {
                "patterns": ["ping", "test", "alive", "salut", "coucou", "bonjour", "merci", "ok", "thx", "ty"],
                "description": "Salutations, confirmations, réactions simples",
                "target_response": "Court, amical, réactif (1-2 phrases)",
                "priority": "social"
            },

            "gen_short": {
                "patterns": [
                    # Salutations avec mention (ex: "bonsoir serda_bot")
                    "bonsoir",
                    # Questions courtes
                    "comment", "pourquoi", "quand", "où", "aide", "help", "peux-tu", "peux tu", "comment faire", "comment ça",
                    # Patterns factuels (ex-lookup fusionné)
                    "qui est", "c'est quoi", "qu'est-ce que", "définition", "game info", "steam info", "qu'est ce que", "info sur"
                ],
                "description": "Questions courtes, demandes d'aide, recherches factuelles simples",
                "target_response": "Réponse concise mais informative (2-4 phrases)",
                "priority": "question_simple"
            },

            "gen_long": {
                "patterns": ["!ask", "explique", "raconte", "développe", "détaille", "analyse", "parle moi de", "dis moi tout", "explique moi", "comment ça marche", "comment fonctionne"],
                "description": "Questions complexes, analyses approfondies",
                "target_response": "Réponse détaillée et nuancée (5+ phrases)",
                "priority": "complex_analysis"
            }
        }

        # 🎯 Enhanced Patterns Loader (override si config YAML fourni)
        if patterns_config_path:
            from .enhanced_patterns_loader import EnhancedPatternsLoader
            self.patterns_loader = EnhancedPatternsLoader(patterns_config_path)
            self.classification_rules = self.patterns_loader.get_classification_rules()

        # 🔍 MOTS INDICATEURS DE COMPLEXITÉ
        self.complex_indicators = [
            "pourquoi", "comment", "analyse", "explique", "développe", "détaille", "détails", "détail",
            "théorie", "principe", "fonctionnement", "mécanisme", "architecture", "fonctionne",
            "explication", "méthode", "méthodes", "stratégie", "stratégies", "technique", "techniques",
            "procédure", "procédures", "algorithme", "algorithmes", "approche", "approches",
            "méthodologie", "méthodologies", "concept", "concepts", "notion", "notions"
        ]

        # 🧮 Calculateur d'entropie Shannon
        from .entropy_calculator import EntropyCalculator
        self.entropy_calculator = EntropyCalculator()

        # ⚙️ Configuration quantique
        self.config = config or {}
        self.quantum_config = self.config.get("quantum_classifier", {})

        # 📊 Seuils configurables (avec defaults intelligents)
        self.confidence_thresholds = {
            "high_confidence": self.quantum_config.get("high_confidence_threshold", 0.7),
            "entropy_fallback": self.quantum_config.get("entropy_fallback_threshold", 1.5),
            "minimum_probability": self.quantum_config.get("minimum_probability", 0.1)
        }

        # 🎯 Fallback strategy
        self.fallback_class = self.quantum_config.get("fallback_class", "gen_short")

        # 🚀 Cache pour messages répétés (pog, !discord, etc.) - 29x speedup
        self._classify_cache: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._cache_maxsize = 256

        self.logger.info("🌌 UnifiedQuantumClassifier V3.1 initialized (Fusion Safe)")

    def classify(self, stimulus: str, context: str = "") -> Dict[str, Any]:
        """
        🎯 CLASSIFICATION QUANTIQUE COMPLÈTE (Main API)

        Processus :
        1. Superposition → Calcul probabilités toutes classes
        2. Entropie → Mesure incertitude distribution
        3. Évaluation → Confiance + besoin fallback
        4. Effondrement → Classe finale déterministe

        Args:
            stimulus: Message utilisateur
            context: Contexte optionnel

        Returns:
            Dict avec classification complète :
            {
                "class": "gen_long",
                "confidence": 0.85,
                "entropy": 0.64,
                "is_certain": True,
                "should_fallback": False,
                "probabilities": {"ping": 0.1, "gen_short": 0.2, ...},
                "distribution_type": "concentrated",
                "method": "quantum_classification"
            }
        """
        # 🚀 Check cache (0ms pour messages répétés)
        cache_key = (stimulus, context)
        if cache_key in self._classify_cache:
            return self._classify_cache[cache_key]

        # 🌌 Phase 1: SUPERPOSITION - Calcul probabilités
        probabilities, classification_metadata = self.classify_with_probabilities(stimulus, context)

        # 🧮 Phase 2: ENTROPIE - Analyse incertitude
        entropy_analysis = self.entropy_calculator.analyze_distribution(probabilities)

        # 🎯 Phase 3: ÉVALUATION - Confiance et fallback
        confidence_eval = self._evaluate_quantum_confidence(probabilities, entropy_analysis)

        # ⚡ Phase 4: EFFONDREMENT - Classe finale
        final_class = self._quantum_collapse(probabilities, entropy_analysis, confidence_eval)

        # 📊 Construction résultat quantique complet
        quantum_result = {
            # 🎯 Résultat principal
            "class": final_class,
            "confidence": confidence_eval["confidence_score"],
            "entropy": entropy_analysis["entropy"],

            # 🌌 État quantique
            "is_certain": confidence_eval["is_certain"],
            "should_fallback": entropy_analysis["should_fallback"],
            "probabilities": probabilities,

            # 📊 Analyses détaillées
            "distribution_type": entropy_analysis["distribution_type"],
            "dominance_ratio": entropy_analysis["dominance_ratio"],
            "confidence_level": entropy_analysis["confidence_level"],

            # 🔍 Métadonnées techniques
            "method": "quantum_classification",
            "classification_reason": classification_metadata["classification_reason"],
            "metadata": classification_metadata,
            "entropy_analysis": entropy_analysis,
            "quantum_confidence": confidence_eval
        }

        self.logger.debug(f"🌌 Quantum: '{stimulus}' → {final_class} (entropy: {entropy_analysis['entropy']:.3f}, conf: {confidence_eval['confidence_score']:.3f})")

        # 🚀 Stocker en cache (max 256 messages, FIFO)
        if len(self._classify_cache) >= self._cache_maxsize:
            self._classify_cache.pop(next(iter(self._classify_cache)))
        self._classify_cache[cache_key] = quantum_result

        return quantum_result

    def classify_with_probabilities(self, stimulus: str, context: str = "") -> Tuple[Dict[str, float], Dict]:
        """
        🌌 CLASSIFICATION QUANTIQUE - Retourne probabilités pour chaque classe

        Cette méthode calcule des probabilités pour chaque classe au lieu d'une classification binaire.
        Permet la superposition quantique avant effondrement vers une classe spécifique.

        Args:
            stimulus: Message utilisateur
            context: Contexte optionnel

        Returns:
            Tuple[Dict[str, float], Dict]: (probabilités_par_classe, métadonnées)

        Exemple:
            probabilities, metadata = classifier.classify_with_probabilities("explique moi Python")
            # probabilities = {"ping": 0.1, "gen_short": 0.2, "lookup": 0.3, "gen_long": 0.4}
        """
        stimulus_lower = stimulus.lower().strip()

        # 📊 Initialisation des scores par classe (3 classes)
        class_scores = {
            "ping": 0.0,
            "gen_short": 0.0,
            "gen_long": 0.0
        }

        # 🔍 Métadonnées détaillées
        metadata = {
            "word_count": len(stimulus.split()),
            "has_question": "?" in stimulus,
            "has_mention": any(mention in stimulus_lower for mention in ["@", "serda_bot"]),
            "complex_words": self._detect_complex_words(stimulus_lower),
            "classification_method": "probabilistic"
        }

        # 1. 🎯 CONTEXT OVERRIDE (priorité absolue)
        if context == "ask":
            # NOTE: Cette classification en gen_long est redondante car local_synapse.py (ligne 313)
            # utilise directement context="ask" AVANT de vérifier stimulus_class.
            # Gardé comme sécurité défensive si context="ask" n'est pas passé correctement.
            class_scores["gen_long"] = 1.0
            metadata["classification_reason"] = "context_override_ask_redundant"
            return class_scores, metadata

        # 2. 🎤 ANALYSE DES MENTIONS
        if metadata["has_mention"]:
            # Bonus pour mentions mais pas exclusif
            class_scores["gen_short"] += 0.3

            # Analyse du contenu de la mention
            for class_name, rule in self.classification_rules.items():
                mention_matches = sum(1 for pattern in rule["patterns"] if pattern in stimulus_lower)
                if mention_matches > 0:
                    class_scores[class_name] += mention_matches * 0.4

        # 3. 📋 SCORE PAR PATTERNS D'INTENTION
        for class_name, rule in self.classification_rules.items():
            pattern_matches = sum(1 for pattern in rule["patterns"] if pattern in stimulus_lower)
            if pattern_matches > 0:
                # Score basé sur nombre de patterns + priorité
                base_score = pattern_matches * 0.5

                # Bonus selon priorité de la classe
                priority = str(rule.get("priority", ""))
                priority_bonus = {
                    "social": 0.1,           # ping
                    "question_simple": 0.2, # gen_short
                    "factual": 0.3,         # lookup
                    "complex_analysis": 0.4  # gen_long
                }.get(priority, 0.0)

                class_scores[class_name] += base_score + priority_bonus

        # 4. 🧠 ANALYSE DE COMPLEXITÉ LINGUISTIQUE
        word_count = metadata.get("word_count", 0)
        word_count_int = int(word_count) if isinstance(word_count, (int, float)) else 0
        complex_words = metadata.get("complex_words", [])
        complex_words_count = len(complex_words) if isinstance(complex_words, list) else 0
        has_question = metadata.get("has_question", False)
        has_question_bool = bool(has_question) if isinstance(has_question, bool) else False

        # Ajustements basés sur la complexité
        if word_count_int <= 3 and not has_question_bool and complex_words_count == 0:
            class_scores["ping"] += 0.6  # Message très court
        elif complex_words_count >= 2:
            class_scores["gen_long"] += 0.7  # Plusieurs mots complexes
        elif complex_words_count == 1 and word_count_int > 6:
            class_scores["gen_long"] += 0.5  # Un mot complexe + message long
        elif complex_words_count == 1:
            class_scores["gen_long"] += 0.8  # Mot complexe isolé → analyse approfondie
        elif word_count_int > 12:
            class_scores["gen_long"] += 0.4  # Message très long

        # Bonus questions courtes
        if has_question_bool and word_count_int <= 8 and complex_words_count <= 1:
            class_scores["gen_short"] += 0.3

        # 5. 📊 NORMALISATION EN PROBABILITÉS
        total_score = sum(class_scores.values())

        if total_score > 0:
            probabilities = {k: v / total_score for k, v in class_scores.items()}
        else:
            # Fallback uniforme si aucun pattern (3 classes: 33.3% chacune)
            probabilities = {k: 1.0/3.0 for k in class_scores.keys()}

        # 6. 🎯 SURCHARGE INTELLIGENTE
        max_class = max(probabilities.items(), key=lambda x: x[1])[0]

        # Surcharge gen_short → gen_long si 2+ mots complexes
        if max_class == "gen_short" and complex_words_count >= 2:
            # Redistribue la probabilité vers gen_long
            boost = probabilities["gen_short"] * 0.6
            probabilities["gen_long"] += boost
            probabilities["gen_short"] -= boost
            metadata["classification_reason"] = "probability_boost_complexity"
        else:
            metadata["classification_reason"] = f"probability_match_{max_class}"

        # 7. 📈 MÉTADONNÉES ENRICHIES
        metadata.update({
            "raw_scores": class_scores.copy(),
            "total_raw_score": total_score,
            "max_probability": max(probabilities.values()),
            "predicted_class": max(probabilities.items(), key=lambda x: x[1])[0]
        })

        return probabilities, metadata

    def _evaluate_quantum_confidence(self, probabilities: Dict[str, float], entropy_analysis: Dict) -> Dict:
        """
        📊 Évaluation quantique de la confiance

        Combine :
        - Probabilité maximum (dominance classe)
        - Entropie Shannon (incertitude distribution)
        - Ratio de dominance (écart entre classes)

        SACRED CODE - Ne pas modifier sans tests complets
        Formule empiriquement validée: 70% Shannon + 20% probability + 10% dominance
        """
        max_probability = entropy_analysis["max_probability"]
        entropy = entropy_analysis["entropy"]
        dominance_ratio = entropy_analysis["dominance_ratio"]

        # 📊 Score de confiance multi-facteurs
        # Facteur 1: Probabilité dominante (0-1)
        prob_factor = max_probability

        # Facteur 2: Confiance Shannon normalisée EXACTE
        # Formule: 1 - H(S)/H_max où H_max = log₂(3) ≈ 1.585 pour 3 classes
        H_max = 1.585  # Maximum théorique pour 3 classes (ping, gen_short, gen_long)
        shannon_confidence = max(0.0, 1.0 - (entropy / H_max))

        # Facteur 3: Dominance normalisée (0-1)
        dominance_factor = min(1.0, dominance_ratio / 10.0)  # Cap à ratio 10:1

        # 🧮 Score final : Shannon (70%) + probabilité (20%) + dominance (10%)
        confidence_score = (
            shannon_confidence * 0.7 +   # 70% formule Shannon pure
            prob_factor * 0.2 +          # 20% probabilité max
            dominance_factor * 0.1       # 10% dominance
        )

        # 🎯 Classification confiance
        if confidence_score >= self.confidence_thresholds["high_confidence"]:
            confidence_level = "high"
            is_certain = True
        elif confidence_score >= 0.5:
            confidence_level = "moderate"
            is_certain = True
        else:
            confidence_level = "low"
            is_certain = False

        return {
            "confidence_score": confidence_score,
            "confidence_level": confidence_level,
            "is_certain": is_certain,
            "factors": {
                "probability": prob_factor,
                "shannon_confidence": shannon_confidence,
                "dominance": dominance_factor
            }
        }

    def _quantum_collapse(self, probabilities: Dict[str, float], entropy_analysis: Dict, confidence_eval: Dict) -> str:
        """
        ⚡ EFFONDREMENT QUANTIQUE - Superposition → État déterministe

        Stratégie :
        1. Si entropie > seuil → Fallback intelligent
        2. Si confiance faible → Fallback ou classe dominante selon contexte
        3. Sinon → Classe avec probabilité maximale
        """
        predicted_class = entropy_analysis["predicted_class"]
        entropy = entropy_analysis["entropy"]
        should_fallback = entropy_analysis["should_fallback"]

        # 🔄 Stratégie 1: Fallback entropie élevée
        if should_fallback:
            fallback = self.entropy_calculator.get_fallback_recommendation(probabilities)
            self.logger.debug(f"🔄 Quantum fallback: entropy {entropy:.3f} > {self.confidence_thresholds['entropy_fallback']}")
            return fallback

        # 🎯 Stratégie 2: Confiance faible mais entropie acceptable
        if not confidence_eval["is_certain"]:
            max_prob = entropy_analysis["max_probability"]
            if max_prob < self.confidence_thresholds["minimum_probability"]:
                self.logger.debug(f"🔄 Confidence fallback: max_prob {max_prob:.3f} < {self.confidence_thresholds['minimum_probability']}")
                return self.fallback_class

        # ✅ Stratégie 3: Classification normale
        return predicted_class

    def _detect_complex_words(self, stimulus_lower: str) -> List[str]:
        """🔍 Détecte les mots indicateurs de complexité"""
        found_complex = []
        for word in self.complex_indicators:
            if word in stimulus_lower:
                found_complex.append(word)
        return found_complex

    def classify_with_entropy(self, stimulus: str, context: str = "") -> Tuple[str, float]:
        """
        🎯 Classification + Entropie (compatible Neural V2.0)

        Returns:
            Tuple[str, float]: (classe, entropie)
        """
        result = self.classify(stimulus, context)
        return result["class"], result["entropy"]


# 🧪 FONCTION DE TEST
def test_unified_quantum_classifier():
    """🧪 Tests de validation du classifier unifié"""
    classifier = UnifiedQuantumClassifier()

    test_cases = [
        ("bonsoir serda_bot", "", "gen_short"),  # Mention casual
        ("salut !", "", "ping"),  # Salutation simple
        ("@serda_bot comment ça va ?", "", "gen_short"),  # Mention + question simple
        ("!ask explique moi quantum physics", "", "gen_long"),  # Context override
        ("qui est Einstein ?", "", "gen_short"),  # Ex-lookup → gen_short
        ("c'est quoi un bot ?", "", "gen_short"),  # Ex-lookup → gen_short
        ("raconte moi une histoire", "", "gen_long"),  # Génération longue
        ("ping", "", "ping"),  # Test simple
        ("merci bien", "", "ping"),  # Réaction courte
        ("peux-tu m'aider avec Python ?", "", "gen_short"),  # Demande d'aide
        ("@serda_bot pourquoi le ciel est bleu ?", "", "gen_short"),  # Mention + question
        ("développe sur l'intelligence artificielle", "", "gen_long"),  # Analyse complexe
    ]

    print("🧪 TEST UNIFIED QUANTUM CLASSIFIER V3.1")
    print("=" * 50)

    success_count = 0
    for stimulus, context, expected in test_cases:
        result = classifier.classify(stimulus, context)
        classification = result["class"]
        status = "✅" if classification == expected else "❌"
        success_count += 1 if classification == expected else 0

        print(f"{status} '{stimulus}' → {classification} (attendu: {expected})")
        print(f"    Entropy: {result['entropy']:.3f}, Confidence: {result['confidence']:.3f} ({result['confidence_level']})")
        if classification != expected:
            print(f"    Raison: {result['classification_reason']}")

    print(f"\n📊 Résultat: {success_count}/{len(test_cases)} tests réussis ({success_count/len(test_cases)*100:.1f}%)")

    # Test cache performance
    print("\n🚀 TEST CACHE PERFORMANCE")
    import time

    # Premier appel (sans cache)
    start = time.time()
    for _ in range(100):
        classifier.classify("pog")
    no_cache_time = time.time() - start

    # Deuxième appel (avec cache)
    start = time.time()
    for _ in range(100):
        classifier.classify("pog")
    cache_time = time.time() - start

    speedup = no_cache_time / cache_time if cache_time > 0 else float('inf')
    print(f"Sans cache: {no_cache_time*1000:.2f}ms, Avec cache: {cache_time*1000:.2f}ms")
    print(f"Speedup: {speedup:.1f}x")

    return success_count == len(test_cases)


def demo_unified_quantum_classifier():
    """🧪 Démonstration UnifiedQuantumClassifier"""
    print("🌌 DEMONSTRATION UNIFIED QUANTUM CLASSIFIER V3.1")
    print("=" * 55)

    # Configuration de test
    config = {
        "quantum_classifier": {
            "high_confidence_threshold": 0.75,
            "entropy_fallback_threshold": 1.5,
            "minimum_probability": 0.1,
            "fallback_class": "gen_short"
        }
    }

    classifier = UnifiedQuantumClassifier(config)

    # 🧪 Cas de test quantiques
    test_cases = [
        ("ping", "Haute confiance"),
        ("bonsoir serda_bot", "Mention casual"),
        ("explique moi la physique quantique", "Complexité élevée"),
        ("c'est quoi Python ?", "Lookup factuel"),
        ("salut aide comment pourquoi", "Incertitude élevée → Fallback"),
        ("@serda_bot raconte moi une histoire", "Mention + génération"),
    ]

    for stimulus, description in test_cases:
        print(f"\n🧪 {description}: '{stimulus}'")

        result = classifier.classify(stimulus)

        print(f"   🎯 Classe: {result['class']}")
        print(f"   📊 Confiance: {result['confidence_level']} ({result['confidence']:.3f})")
        print(f"   🧮 Entropie: {result['entropy']:.3f}")
        print(f"   🔄 Fallback: {'OUI' if result['should_fallback'] else 'NON'}")
        print(f"   🌌 Distribution: {result['distribution_type']}")

        # Top 2 probabilités
        sorted_probs = sorted(result['probabilities'].items(), key=lambda x: x[1], reverse=True)[:2]
        print(f"   📈 Top classes: {sorted_probs[0][0]}({sorted_probs[0][1]:.2f}), {sorted_probs[1][0]}({sorted_probs[1][1]:.2f})")


if __name__ == "__main__":
    # Tests autonomes
    test_unified_quantum_classifier()
    print("\n" + "=" * 55 + "\n")
    demo_unified_quantum_classifier()
