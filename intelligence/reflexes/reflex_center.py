"""
🛡️ Reflex Center V2.0 - Système de Réflexes Intelligent

Fallback neural avec patterns contextuels et réponses adaptatives
"""

import logging
import random
import time
from typing import Any


class ReflexCenter:
    """
    🛡️ REFLEX CENTER V2.0

    Métaphore : Réflexes neuronaux de survie
    - Patterns contextuels intelligents
    - Réponses adaptatives par stimulus
    - Fallback toujours disponible (never fails)
    - Simulation bandit pour compatibilité UCB
    - Métriques de performance des réflexes
    """

    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(__name__)

        # 🎭 PATTERNS RÉFLEXES CONTEXTUELS
        self.reflex_patterns = {
            "ping": [
                "🤖 Je suis là !",
                "⚡ Présent et opérationnel !",
                "👋 Salut ! Tout va bien ici",
                "🎯 En ligne et prêt !",
                "🔥 Toujours actif !",
            ],
            "lookup": [
                "🔍 Info temporairement indisponible...",
                "📚 Base de données en cours de sync...",
                "🎮 Recherche en cours, patience !",
                "⏳ Données gaming en chargement...",
                "🔄 Mise à jour des infos jeux...",
            ],
            "gen_short": [
                "😊 Petit souci technique, mais je reviens vite !",
                "🛠️ Recalibrage en cours...",
                "⚡ Redémarrage rapide des neurones !",
                "🎲 Plot twist : mode manuel activé !",
                "🚀 Houston, on a un petit delay...",
            ],
            "gen_long": [
                "🤔 Je réfléchis encore... Pose ta question plus tard !",
                "🧠 Cerveau en surchauffe, pause café nécessaire ☕",
                "📝 Consultation des archives... Patiente un moment !",
                "🎯 Analyse approfondie requise, reviens dans 2 min !",
                "💡 Inspiration en cours de téléchargement... 42% ⬛",
            ],
            "error": [
                "🤖 Système en cours de recalibrage...",
                "⚙️ Maintenance éclair en cours !",
                "🔧 Réparation des connexions neuronales...",
                "🎮 Respawn du bot dans 3... 2... 1...",
                "🌟 Mise à jour quantum en arrière-plan !",
            ],
        }

        # 🎰 BANDIT SIMULATION (pour compatibilité UCB)
        self.reflex_calls = 0
        self.total_reward = 0.0
        self.avg_response_time = 0.001  # Réflexe = ultra rapide

        # 📊 MÉTRIQUES RÉFLEXES
        self.usage_stats = {stimulus: 0 for stimulus in self.reflex_patterns.keys()}
        self.last_responses = []
        self.max_history = 20

        self.logger.info("🛡️ Reflex Center V2.0 initialisé - Fallback toujours disponible")

    def can_execute(self) -> bool:
        """⚡ TOUJOURS DISPONIBLE - Jamais de panne"""
        return True

    async def fire(
        self,
        stimulus: str,
        context: str = "general",
        stimulus_class: str = "gen_short",
        correlation_id: str = "",
    ) -> str | None:
        """🔥 RÉFLEXE NEURAL INSTANTANÉ"""
        start_time = time.time()

        # Classification stimulus pour pattern optimal
        pattern_key = self._classify_for_pattern(stimulus, context, stimulus_class)

        # Sélection réponse contextuelle
        response = self._select_contextual_response(pattern_key, stimulus)

        # Métriques réflexe
        latency = time.time() - start_time
        self._record_reflex_usage(pattern_key, latency)

        self.logger.info(f"🛡️⚡ [{correlation_id}] Reflex {pattern_key} - {latency*1000:.1f}ms")
        return response

    def _classify_for_pattern(self, stimulus: str, context: str, stimulus_class: str) -> str:
        """🎯 CLASSIFICATION POUR PATTERN RÉFLEXE"""
        stimulus_lower = stimulus.lower()

        # Classification prioritaire par context/stimulus_class
        if stimulus_class == "ping" or any(
            word in stimulus_lower for word in ["ping", "test", "alive", "ça va"]
        ):
            return "ping"
        elif stimulus_class == "lookup" or any(
            word in stimulus_lower for word in ["qui est", "c'est quoi", "info"]
        ):
            return "lookup"
        elif stimulus_class == "gen_long" or context == "ask":
            return "gen_long"
        elif stimulus_class == "gen_short":
            return "gen_short"
        else:
            return "error"  # Fallback général

    def _select_contextual_response(self, pattern_key: str, stimulus: str) -> str:
        """🎭 SÉLECTION RÉPONSE CONTEXTUELLE"""
        responses = self.reflex_patterns.get(pattern_key, self.reflex_patterns["error"])

        # Éviter répétitions récentes
        recent_responses = [r["response"] for r in self.last_responses[-5:]]
        available_responses = [r for r in responses if r not in recent_responses]

        if not available_responses:
            available_responses = responses  # Reset si toutes utilisées

        # Sélection adaptative
        if len(stimulus) > 50 and pattern_key in ["gen_short", "gen_long"]:
            # Stimulus long = réponse plus élaborée
            selected = max(available_responses, key=len)
        else:
            # Sélection aléatoire pondérée
            selected = random.choice(available_responses)

        return selected

    def _record_reflex_usage(self, pattern_key: str, latency: float):
        """📊 ENREGISTREMENT USAGE RÉFLEXE"""
        self.reflex_calls += 1
        self.usage_stats[pattern_key] += 1

        # Simulation reward (réflexe = toujours reward modéré)
        reflex_reward = 0.5  # Moins qu'une vraie synapse, mais stable
        self.total_reward += reflex_reward

        # Historique
        self.last_responses.append(
            {
                "pattern": pattern_key,
                "timestamp": time.time(),
                "latency": latency,
                "response": f"Pattern: {pattern_key}",
            }
        )

        if len(self.last_responses) > self.max_history:
            self.last_responses.pop(0)

    def get_bandit_stats(self) -> dict[str, float]:
        """🎰 STATS BANDIT RÉFLEXE (simulation)"""
        if self.reflex_calls == 0:
            return {"avg_reward": 0.5, "trials": 0, "ucb_score": 0.5}

        avg_reward = self.total_reward / self.reflex_calls
        return {
            "avg_reward": avg_reward,
            "trials": self.reflex_calls,
            "ucb_score": avg_reward,  # Pas d'exploration pour réflexe
        }

    def get_neural_metrics(self) -> dict[str, Any]:
        """📊 MÉTRIQUES RÉFLEXES COMPLÈTES"""
        avg_latency = (
            sum(r["latency"] for r in self.last_responses) / len(self.last_responses)
            if self.last_responses
            else 0.001
        )

        # Pattern usage distribution
        total_usage = sum(self.usage_stats.values())
        pattern_distribution = {
            pattern: round(count / total_usage, 3) if total_usage > 0 else 0.0
            for pattern, count in self.usage_stats.items()
        }

        return {
            "synapse_type": "reflex",
            "is_enabled": True,
            "can_execute": True,
            "reflex_calls": self.reflex_calls,
            "avg_reward": (
                round(self.total_reward / self.reflex_calls, 3) if self.reflex_calls > 0 else 0.5
            ),
            "avg_latency_ms": round(avg_latency * 1000, 2),
            "pattern_usage": self.usage_stats,
            "pattern_distribution": pattern_distribution,
            "available_patterns": list(self.reflex_patterns.keys()),
            "total_pattern_variations": sum(
                len(responses) for responses in self.reflex_patterns.values()
            ),
            "recent_activity": len(
                [r for r in self.last_responses if time.time() - r["timestamp"] < 300]
            ),  # 5 min
            "response_variety_recent": len(set(r["pattern"] for r in self.last_responses[-10:])),
            "never_fails": True,
            "uptime": "100%",
        }
