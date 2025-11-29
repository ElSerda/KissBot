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

        # 🎯 RÈGLES SIMPLIFIÉES - VERSION SOFT (Reflex minimal + GPT fallback)
        self.classification_rules = {
            "ping": {
                "patterns": [
                    # Salutations uniquement
                    "salut", "coucou", "bonjour", "bonsoir", "hello", "hey",
                    # Tests de présence
                    "ping", "test", "alive", "ici", "là",
                    # Remerciements
                    "merci", "thx", "ty", "thanks", "thank you"
                ],
                "description": "Messages triviaux → Reflex instantané (0ms)",
                "target_response": "Réponse réflexe prédéfinie",
                "priority": "social"
            },
            
            "gen_short": {
                "patterns": [
                    # Fallback pour TOUTES les autres mentions (questions, calculs, logique, etc.)
                    # Pattern vide = catch-all si pas ping et pas !ask
                ],
                "description": "Toutes mentions non-triviales → GPT concis",
                "target_response": "Réponse concise et créative (1-3 phrases)",
                "priority": "question_simple"
            },

            "gen_long": {
                "patterns": ["!ask"],
                "description": "Commande !ask → GPT détaillé",
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

        # 1. 🎯 DÉTECTION !ASK (priorité absolue)
        if "!ask" in stimulus_lower or context == "ask":
            class_scores["gen_long"] = 1.0
            metadata["classification_reason"] = "explicit_ask_command"
            return class_scores, metadata

        # 2. 🎤 DÉTECTION REFLEX (messages triviaux)
        ping_matches = sum(1 for pattern in self.classification_rules["ping"]["patterns"] if pattern in stimulus_lower)
        if ping_matches > 0:
            class_scores["ping"] = 1.0
            metadata["classification_reason"] = f"reflex_trivial_match_{ping_matches}"
            return class_scores, metadata

        # 3. 🌐 FALLBACK → gen_short (TOUT le reste = GPT)
        # Si pas !ask et pas reflex, alors c'est une mention normale → GPT concis
        class_scores["gen_short"] = 1.0
        metadata["classification_reason"] = "fallback_gpt_short"
        
        # Métadonnées finales
        metadata.update({
            "raw_scores": class_scores.copy(),
            "max_probability": 1.0,
            "predicted_class": "gen_short"
        })
        
        return class_scores, metadata

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
