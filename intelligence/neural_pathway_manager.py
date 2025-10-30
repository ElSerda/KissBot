"""
🧠 Neural Pathway Manager V3.0 - UCB Bandit Quantum
Orchestrateur neural avec sélection UCB pour synapses
"""

import logging
import math
import time
import uuid
from typing import Any, Protocol, runtime_checkable

from .neural_prometheus import neural_prometheus_metrics
from .unified_quantum_classifier import UnifiedQuantumClassifier


@runtime_checkable
class SynapseProtocol(Protocol):
    """
    🧬 INTERFACE SYNAPSE V2.0
    Contrat standardisé que toutes les synapses doivent respecter
    """

    async def fire(
        self,
        stimulus: str,
        context: str = "general",
        stimulus_class: str = "gen_short",
        correlation_id: str = "",
    ) -> str | None:
        """🔥 Transmission synaptique principale"""
        ...

    def can_execute(self) -> bool:
        """⚡ Vérification disponibilité synapse"""
        ...

    def get_bandit_stats(self) -> dict[str, float]:
        """🎰 Statistiques UCB bandit"""
        ...

    def get_neural_metrics(self) -> dict[str, Any]:
        """📊 Métriques observabilité complète"""
        ...


class NeuralPathwayManager:
    """
    🧠 NEURAL PATHWAY MANAGER V2.0

    Métaphore : Cerveau principal qui coordonne les synapses
    - UCB bandit (UCB = r̄ᵢ + c√(ln(N)/(nᵢ+1))) pour sélection optimale
    - Correlation ID tracking pour observabilité complète
    - Stimulus classification automatique (ping/lookup/gen_short/gen_long)
    - Load balancing intelligent avec circuit breakers
    - Métriques pro-grade et monitoring Prometheus-ready
    """

    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(__name__)

        # 🔗 SYNAPSES NEURALES - Import dynamique pour éviter les cycles
        from .reflexes.reflex_center import ReflexCenter
        from .synapses.cloud_synapse import CloudSynapse
        from .synapses.local_synapse import LocalSynapse

        self.local_synapse = LocalSynapse(config)
        self.cloud_synapse = CloudSynapse(config)
        self.reflex_center = ReflexCenter(config)
        self.synapses: dict[str, SynapseProtocol] = {
            "local": self.local_synapse,
            "cloud": self.cloud_synapse,
            "reflex": self.reflex_center,
        }

        # 🎰 UCB BANDIT CONFIG
        neural_config = config.get("neural_llm", {})
        self.ucb_exploration_factor = neural_config.get("ucb_exploration_factor", 1.4)
        self.min_trials_per_synapse = neural_config.get("min_trials_per_synapse", 3)
        self.global_trial_count = 0

        # 📊 CORRELATION TRACKING
        self.active_correlations: dict[str, dict[str, Any]] = {}
        self.correlation_history: list[dict[str, Any]] = []
        self.max_correlation_history = neural_config.get("max_correlation_history", 100)

        # 🌌 UNIFIED QUANTUM CLASSIFIER V3.0 - Classification quantique avec Enhanced Patterns
        patterns_path = config.get("enhanced_patterns_path", None)
        self.stimulus_classifier = UnifiedQuantumClassifier(config, patterns_path)

        # 📊 QUANTUM METRICS V3.0 - Observabilité quantique avancée
        from .quantum_metrics import QuantumMetrics
        quantum_metrics_config = neural_config.get("quantum_metrics", {})
        self.quantum_metrics = QuantumMetrics(
            buffer_size=quantum_metrics_config.get("buffer_size", 10000),
            enable_prometheus=quantum_metrics_config.get("enable_prometheus", True),
            prometheus_prefix=quantum_metrics_config.get("prometheus_prefix", "kissbot_quantum"),
            enable_structured_logging=quantum_metrics_config.get("enable_structured_logging", True)
        )

        # ⚡ PERFORMANCE METRICS
        self.total_requests = 0
        self.successful_requests = 0
        self.avg_response_time = 0.0
        self.last_performance_reset = time.time()

        self.logger.info("🧠 Neural Pathway Manager V2.0 initialisé - UCB bandit activé")

    def classify_stimulus(self, stimulus: str, context: str) -> str:
        """🌌 CLASSIFICATION QUANTIQUE V3.0 - UnifiedQuantumClassifier avec entropie Shannon"""
        start_time = time.time()
        quantum_result = self.stimulus_classifier.classify(stimulus, context)
        response_time_ms = (time.time() - start_time) * 1000

        # 📊 Enregistrement dans QuantumMetrics
        self.quantum_metrics.record_classification(
            stimulus=stimulus,
            classification=quantum_result['class'],
            confidence=quantum_result['confidence'],
            entropy=quantum_result['entropy'],
            is_certain=quantum_result['is_certain'],
            should_fallback=quantum_result['should_fallback'],
            distribution_type=quantum_result.get('distribution_type', 'unknown'),
            method=quantum_result.get('method', 'quantum'),
            response_time_ms=response_time_ms
        )

        # Log avec métadonnées quantiques
        self.logger.debug(
            f"🌌 Quantum: '{stimulus}' → {quantum_result['class']} "
            f"(conf: {quantum_result['confidence']:.3f}, entropy: {quantum_result['entropy']:.3f}, "
            f"certain: {quantum_result['is_certain']}, fallback: {quantum_result['should_fallback']})"
        )

        # Retour de la classe pour compatibilité Neural V2.0
        return quantum_result['class']

    def classify_with_entropy(self, stimulus: str, context: str = "general") -> dict:
        """🌌 NOUVELLE API - Classification quantique complète avec métadonnées"""
        start_time = time.time()
        result = self.stimulus_classifier.classify(stimulus, context)
        response_time_ms = (time.time() - start_time) * 1000

        # 📊 Enregistrement dans QuantumMetrics avec classe attendue optionnelle
        self.quantum_metrics.record_classification(
            stimulus=stimulus,
            classification=result['class'],
            confidence=result['confidence'],
            entropy=result['entropy'],
            is_certain=result['is_certain'],
            should_fallback=result['should_fallback'],
            distribution_type=result.get('distribution_type', 'unknown'),
            method=result.get('method', 'quantum'),
            response_time_ms=response_time_ms
        )

        return result

    def calculate_ucb_scores(self, stimulus_class: str) -> dict[str, float]:
        """🎰 CALCUL UCB SCORES POUR SÉLECTION SYNAPSE"""
        scores = {}

        for synapse_name, synapse in self.synapses.items():
            if not hasattr(synapse, "can_execute") or not synapse.can_execute():
                scores[synapse_name] = -float("inf")  # Synapse indisponible
                continue

            stats = synapse.get_bandit_stats()
            trials = stats["trials"]
            avg_reward = stats["avg_reward"]

            # Force exploration si pas assez de trials
            if trials < self.min_trials_per_synapse:
                scores[synapse_name] = float("inf")
            elif self.global_trial_count == 0:
                scores[synapse_name] = float("inf")
            else:
                # UCB = r̄ᵢ + c√(ln(N)/(nᵢ+1))
                exploration_term = self.ucb_exploration_factor * math.sqrt(
                    math.log(self.global_trial_count) / (trials + 1)
                )
                scores[synapse_name] = avg_reward + exploration_term

        return scores

    def select_best_synapse(self, stimulus_class: str) -> tuple[str | None, SynapseProtocol | None]:
        """🏆 SÉLECTION OPTIMALE SYNAPSE VIA UCB"""
        
        # 🎯 OPTIMISATION: ping force TOUJOURS reflex (templates > LLM pour réflexes)
        if stimulus_class == "ping":
            self.logger.debug(f"🎯 Classe ping → Force reflex (templates)")
            return "reflex", self.synapses["reflex"]
        
        ucb_scores = self.calculate_ucb_scores(stimulus_class)

        # Tri par score UCB décroissant
        sorted_synapses = sorted(ucb_scores.items(), key=lambda x: x[1], reverse=True)

        for synapse_name, score in sorted_synapses:
            if score > -float("inf"):  # Synapse disponible
                selected_synapse = self.synapses[synapse_name]
                self.logger.debug(f"🎯 Synapse sélectionnée: {synapse_name} (UCB: {score:.3f})")
                return synapse_name, selected_synapse

        # Aucune synapse disponible
        self.logger.warning("⚠️ Aucune synapse disponible")
        return None, None

    async def process_stimulus(self, stimulus: str, context: str = "general") -> str | None:
        """
        🔥 TRAITEMENT STIMULUS PRINCIPAL V2.0

        Pipeline neuronal complet avec UCB bandit et observabilité
        """
        correlation_id = str(uuid.uuid4())[:8]
        stimulus_class = self.classify_stimulus(stimulus, context)

        self.logger.info(f"🧠 [{correlation_id}] Stimulus: {stimulus_class} | Context: {context}")

        # Métriques Prometheus - Début requête
        neural_prometheus_metrics.record_neural_request(stimulus_class)
        neural_prometheus_metrics.update_global_metrics(
            total_requests=self.total_requests,
            successful_requests=self.successful_requests,
            active_correlations=len(self.active_correlations),
            ucb_exploration_factor=self.ucb_exploration_factor,
        )
        # Enregistrement corrélation
        correlation_data = {
            "correlation_id": correlation_id,
            "stimulus": stimulus[:100],  # Truncate pour logs
            "context": context,
            "stimulus_class": stimulus_class,
            "start_time": time.time(),
            "selected_synapse": None,
            "response": None,
            "success": False,
            "latency": 0.0,
        }
        self.active_correlations[correlation_id] = correlation_data

        try:
            # Sélection synapse via UCB
            synapse_name, selected_synapse = self.select_best_synapse(stimulus_class)

            if not selected_synapse:
                self.logger.error(f"🚫 [{correlation_id}] Aucune synapse disponible")
                return self._fallback_response(stimulus, context)

            correlation_data["selected_synapse"] = synapse_name
            self.global_trial_count += 1

            # Transmission synaptique avec SynapseProtocol
            start_time = time.time()
            response = await selected_synapse.fire(
                stimulus=stimulus,
                context=context,
                stimulus_class=stimulus_class,
                correlation_id=correlation_id,
            )

            latency = time.time() - start_time
            correlation_data["latency"] = latency
            correlation_data["response"] = response[:100] if response else None
            correlation_data["success"] = bool(response)

            # Métriques globales avec Prometheus
            self.total_requests += 1
            if response:
                self.successful_requests += 1
                self.avg_response_time = (
                    self.avg_response_time * (self.successful_requests - 1) + latency
                ) / self.successful_requests

                # Enregistrer succès Prometheus
                neural_prometheus_metrics.record_neural_success(
                    latency, synapse_name or "unknown", stimulus_class
                )

                self.logger.info(f"🧠✅ [{correlation_id}] {synapse_name} Success - {latency:.2f}s")
                return response
            else:
                # Enregistrer échec Prometheus
                neural_prometheus_metrics.record_neural_failure(
                    synapse_name or "unknown", "no_response"
                )

                self.logger.warning(f"🧠❌ [{correlation_id}] {synapse_name} Failed")

                # Fallback avec métriques
                neural_prometheus_metrics.record_neural_fallback("synapse_failure")
                return self._fallback_response(stimulus, context)

        except Exception as e:
            correlation_data["error"] = str(e)
            self.logger.error(f"🧠💥 [{correlation_id}] Erreur pipeline: {e}")
            return self._fallback_response(stimulus, context)
        finally:
            # Archivage corrélation
            self._archive_correlation(correlation_id)

    def _fallback_response(self, stimulus: str, context: str) -> str:
        """🛡️ RÉPONSE FALLBACK INTELLIGENTE (3 classes)"""
        fallback_responses = {
            "ping": "🤖 Je suis là !",
            "gen_short": "😊 Désolé, petit souci technique !",
            "gen_long": "🤔 Je réfléchis encore... Pose ta question plus tard !",
        }

        stimulus_class = self.classify_stimulus(stimulus, context)
        return fallback_responses.get(stimulus_class, "🤖 Système en cours de recalibrage...")

    def _archive_correlation(self, correlation_id: str):
        """📦 ARCHIVAGE CORRÉLATION POUR ANALYTICS"""
        if correlation_id in self.active_correlations:
            correlation_data = self.active_correlations.pop(correlation_id)
            correlation_data["end_time"] = time.time()
            correlation_data["duration"] = (
                correlation_data["end_time"] - correlation_data["start_time"]
            )

            self.correlation_history.append(correlation_data)

            # Rotation historique
            if len(self.correlation_history) > self.max_correlation_history:
                self.correlation_history.pop(0)

    def get_neural_metrics(self) -> dict[str, Any]:
        """📊 MÉTRIQUES NEURONALES COMPLÈTES V2.0"""
        current_time = time.time()
        uptime = current_time - self.last_performance_reset

        # Métriques par synapse
        synapse_metrics = {}
        for name, synapse in self.synapses.items():
            synapse_metrics[name] = synapse.get_neural_metrics()

        # UCB scores actuels avec export Prometheus
        ucb_scores = self.calculate_ucb_scores("gen_short")  # Test avec gen_short
        neural_prometheus_metrics.record_ucb_scores(ucb_scores)

        # Mise à jour métriques synapses dans Prometheus
        for name, synapse in self.synapses.items():
            synapse_data = synapse.get_neural_metrics()
            neural_prometheus_metrics.update_synapse_metrics(name, synapse_data)

        # Analyse corrélations récentes
        recent_correlations = [
            c for c in self.correlation_history if current_time - c["start_time"] < 300
        ]  # 5 min
        recent_success_rate = (
            len([c for c in recent_correlations if c["success"]]) / len(recent_correlations)
            if recent_correlations
            else 0
        )

        return {
            "manager_type": "neural_pathway_v2",
            "uptime_seconds": round(uptime, 1),
            # Global performance
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "global_success_rate": (
                round(self.successful_requests / self.total_requests, 3)
                if self.total_requests > 0
                else 0
            ),
            "avg_response_time_seconds": round(self.avg_response_time, 3),
            # UCB bandit
            "global_trial_count": self.global_trial_count,
            "ucb_exploration_factor": self.ucb_exploration_factor,
            "current_ucb_scores": {name: round(score, 3) for name, score in ucb_scores.items()},
            # Corrélations
            "active_correlations": len(self.active_correlations),
            "correlation_history_size": len(self.correlation_history),
            "recent_success_rate_5min": round(recent_success_rate, 3),
            # 🌌 Quantum Metrics V3.0
            "quantum_stats": self.quantum_metrics.get_current_stats().__dict__,
            "quantum_pattern_hits": self.quantum_metrics.get_pattern_hit_stats(),
            # Synapses individuelles
            "synapses": synapse_metrics,
            # Santé globale
            "healthy_synapses": len(
                [s for s in synapse_metrics.values() if s.get("can_execute", False)]
            ),
            "total_synapses": len(self.synapses),
        }

    def get_correlation_analytics(self, minutes: int = 60) -> dict[str, Any]:
        """📈 ANALYTICS CORRÉLATIONS DÉTAILLÉES"""
        current_time = time.time()
        cutoff_time = current_time - (minutes * 60)

        relevant_correlations = [
            c for c in self.correlation_history if c["start_time"] >= cutoff_time
        ]

        if not relevant_correlations:
            return {"period_minutes": minutes, "total_correlations": 0}

        # Analyse par synapse
        synapse_stats = {}
        for correlation in relevant_correlations:
            synapse = correlation.get("selected_synapse", "unknown")
            if synapse not in synapse_stats:
                synapse_stats[synapse] = {"count": 0, "successes": 0, "total_latency": 0.0}

            synapse_stats[synapse]["count"] += 1
            if correlation["success"]:
                synapse_stats[synapse]["successes"] += 1
            synapse_stats[synapse]["total_latency"] += correlation["latency"]

        # Calcul métriques finales
        for synapse, stats in synapse_stats.items():
            stats["success_rate"] = stats["successes"] / stats["count"]
            stats["avg_latency"] = stats["total_latency"] / stats["count"]

        return {
            "period_minutes": minutes,
            "total_correlations": len(relevant_correlations),
            "synapse_performance": synapse_stats,
            "overall_success_rate": len([c for c in relevant_correlations if c["success"]])
            / len(relevant_correlations),
        }

    def get_quantum_analytics(self) -> dict[str, Any]:
        """🌌 ANALYTICS QUANTUM METRICS AVANCÉES"""
        return {
            "quantum_stats": self.quantum_metrics.get_current_stats().__dict__,
            "pattern_hit_distribution": self.quantum_metrics.get_pattern_hit_stats(),
            "recent_metrics": [
                {
                    "timestamp": m["timestamp"],
                    "classification": m["classification"],
                    "confidence": m["confidence"],
                    "entropy": m["entropy"],
                    "is_certain": m["is_certain"],
                    "should_fallback": m["should_fallback"],
                    "response_time_ms": m["response_time_ms"]
                }
                for m in self.quantum_metrics.get_recent_metrics(20)
            ],
            "quantum_json_report": self.quantum_metrics.export_json_report()
        }

    def reset_performance_metrics(self):
        """🔄 RESET MÉTRIQUES PERFORMANCE"""
        self.total_requests = 0
        self.successful_requests = 0
        self.avg_response_time = 0.0
        self.last_performance_reset = time.time()
        self.logger.info("🔄 Métriques performance réinitialisées")
