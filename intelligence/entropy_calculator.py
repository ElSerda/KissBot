#!/usr/bin/env python3
"""
🧮 Entropy Calculator - Module de Calcul d'Entropie Shannon
Mesure l'incertitude d'une classification pour fallback intelligent
"""

import logging
import math
from typing import Dict, Any


class EntropyCalculator:
    """
    🧮 ENTROPY CALCULATOR - Calcul d'Entropie Shannon

    Théorie : H(S) = -∑P(si)log₂P(si)
    - Entropie faible (< 0.5) → Haute confiance
    - Entropie élevée (> 1.5) → Incertitude → Fallback
    - Entropie maximale = log₂(n) pour n classes équiprobables
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # 📊 SEUILS D'ENTROPIE (basés sur théorie Shannon)
        self.entropy_thresholds = {
            "high_confidence": 0.5,    # < 0.5 → Très confiant
            "moderate_confidence": 1.0, # 0.5-1.0 → Confiance modérée
            "low_confidence": 1.9,     # > 1.9 → Incertitude → Fallback (augmenté pour plus de liberté)
            "max_entropy": 2.0         # log₂(4) pour 4 classes équiprobables
        }

        # 🎯 CLASSES QUANTUMBOT
        self.known_classes = ["ping", "gen_short", "lookup", "gen_long"]

        self.logger.debug("🧮 EntropyCalculator initialisé - Seuils Shannon configurés")

    def calculate_shannon_entropy(self, probabilities: Dict[str, float]) -> float:
        """
        🎯 Calcul de l'Entropie Shannon H(S) = -∑P(si)log₂P(si)

        Args:
            probabilities: Dict avec probabilités par classe
                          Ex: {"ping": 0.1, "gen_short": 0.6, "lookup": 0.2, "gen_long": 0.1}

        Returns:
            float: Entropie Shannon (0 = certitude absolue, log₂(n) = incertitude maximale)
        """
        if not probabilities:
            self.logger.warning("⚠️ Probabilités vides - retour entropie maximale")
            return self.entropy_thresholds["max_entropy"]

        # 🔍 Validation et normalisation
        total_prob = sum(probabilities.values())
        if abs(total_prob - 1.0) > 1e-6:
            self.logger.debug(f"📊 Normalisation probabilités: {total_prob:.3f} → 1.0")
            probabilities = {k: v / total_prob for k, v in probabilities.items()}

        # 🧮 Calcul Shannon: H(S) = -∑P(si)log₂P(si)
        entropy = 0.0
        for class_name, prob in probabilities.items():
            if prob > 0:  # Éviter log(0)
                entropy -= prob * math.log2(prob)

        self.logger.debug(f"🧮 Entropie calculée: {entropy:.3f} (seuils: {self.entropy_thresholds})")
        return entropy

    def evaluate_confidence(self, entropy: float) -> Dict[str, Any]:
        """
        📊 Évaluation de la confiance basée sur l'entropie

        Args:
            entropy: Valeur d'entropie Shannon

        Returns:
            Dict avec évaluation complète de confiance
        """
        confidence_level = "unknown"
        should_fallback = False
        confidence_score = 0.0

        if entropy < self.entropy_thresholds["high_confidence"]:
            confidence_level = "high"
            confidence_score = 1.0 - (entropy / self.entropy_thresholds["high_confidence"])
            should_fallback = False
        elif entropy < self.entropy_thresholds["moderate_confidence"]:
            confidence_level = "moderate"
            confidence_score = 1.0 - (entropy / self.entropy_thresholds["moderate_confidence"])
            should_fallback = False
        elif entropy < self.entropy_thresholds["low_confidence"]:
            confidence_level = "low"
            confidence_score = 1.0 - (entropy / self.entropy_thresholds["low_confidence"])
            should_fallback = False
        else:
            confidence_level = "very_low"
            confidence_score = 0.0
            should_fallback = True

        return {
            "entropy": entropy,
            "confidence_level": confidence_level,
            "confidence_score": confidence_score,  # 0.0-1.0
            "should_fallback": should_fallback,
            "is_certain": confidence_level in ["high", "moderate"],
            "threshold_used": self._get_threshold_name(entropy)
        }

    def _get_threshold_name(self, entropy: float) -> str:
        """🎯 Détermine quel seuil a été franchi"""
        if entropy < self.entropy_thresholds["high_confidence"]:
            return "high_confidence"
        elif entropy < self.entropy_thresholds["moderate_confidence"]:
            return "moderate_confidence"
        elif entropy < self.entropy_thresholds["low_confidence"]:
            return "low_confidence"
        else:
            return "fallback_required"

    def analyze_distribution(self, probabilities: Dict[str, float]) -> Dict[str, Any]:
        """
        🔍 Analyse complète d'une distribution de probabilités

        Args:
            probabilities: Distribution de probabilités par classe

        Returns:
            Analyse complète : entropie, confiance, statistiques
        """
        entropy = self.calculate_shannon_entropy(probabilities)
        confidence_eval = self.evaluate_confidence(entropy)

        # 📊 Statistiques additionnelles
        max_prob = max(probabilities.values()) if probabilities else 0.0
        max_class = max(probabilities.items(), key=lambda x: x[1])[0] if probabilities else None

        # 🎯 Ratio de dominance (classe max vs autres)
        other_probs = [v for k, v in probabilities.items() if k != max_class]
        second_max = max(other_probs) if other_probs else 0.0
        dominance_ratio = max_prob / (second_max + 1e-6)  # Éviter division par 0

        return {
            **confidence_eval,
            "probabilities": probabilities,
            "max_probability": max_prob,
            "predicted_class": max_class,
            "dominance_ratio": dominance_ratio,
            "num_classes": len(probabilities),
            "distribution_type": self._classify_distribution_type(probabilities, entropy)
        }

    def _classify_distribution_type(self, probabilities: Dict[str, float], entropy: float) -> str:
        """🔍 Classifie le type de distribution"""
        if not probabilities:
            return "empty"

        max_prob = max(probabilities.values())

        if max_prob > 0.8:
            return "concentrated"  # Une classe domine fortement
        elif entropy > 1.8:
            return "uniform"       # Distribution quasi-uniforme
        elif len([p for p in probabilities.values() if p > 0.1]) > 2:
            return "multimodal"    # Plusieurs classes significatives
        else:
            return "bimodal"       # Deux classes principales

    def get_fallback_recommendation(self, probabilities: Dict[str, float]) -> str:
        """
        🎯 Recommandation de fallback en cas d'incertitude élevée

        Args:
            probabilities: Distribution de probabilités

        Returns:
            Classe recommandée pour fallback
        """
        analysis = self.analyze_distribution(probabilities)

        if analysis["should_fallback"]:
            # 🎯 Stratégie de fallback : gen_short est le plus sûr
            self.logger.info(f"🔄 Fallback recommandé: entropy={analysis['entropy']:.3f} > seuil={self.entropy_thresholds['low_confidence']}")
            return "gen_short"  # Réponse sûre et polyvalente

        return analysis["predicted_class"]

    def get_entropy_stats(self) -> Dict[str, float]:
        """📊 Statistiques et seuils d'entropie configurés"""
        return {
            "thresholds": self.entropy_thresholds,
            "max_possible_entropy": math.log2(len(self.known_classes)),
            "known_classes_count": len(self.known_classes),
            "theoretical_max": 2.0  # log₂(4) pour 4 classes
        }


def demo_entropy_calculator():
    """🧪 Démonstration du EntropyCalculator"""
    print("🧮 DEMONSTRATION ENTROPY CALCULATOR")
    print("=" * 45)

    calculator = EntropyCalculator()

    # 📊 Cas de test
    test_cases = [
        # Haute confiance
        {"ping": 0.9, "gen_short": 0.05, "lookup": 0.03, "gen_long": 0.02},

        # Confiance modérée
        {"ping": 0.1, "gen_short": 0.7, "lookup": 0.1, "gen_long": 0.1},

        # Incertitude élevée (uniforme)
        {"ping": 0.25, "gen_short": 0.25, "lookup": 0.25, "gen_long": 0.25},

        # Bimodale
        {"ping": 0.45, "gen_short": 0.45, "lookup": 0.05, "gen_long": 0.05}
    ]

    for i, probs in enumerate(test_cases, 1):
        print(f"\n🧪 Test {i}: {probs}")

        analysis = calculator.analyze_distribution(probs)

        print(f"   → Entropie: {analysis['entropy']:.3f}")
        print(f"   → Confiance: {analysis['confidence_level']} ({analysis['confidence_score']:.2f})")
        print(f"   → Fallback: {'OUI' if analysis['should_fallback'] else 'NON'}")
        print(f"   → Classe prédite: {analysis['predicted_class']}")
        print(f"   → Type distribution: {analysis['distribution_type']}")


if __name__ == "__main__":
    demo_entropy_calculator()
