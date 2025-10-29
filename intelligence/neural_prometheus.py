"""
📊 Neural Prometheus Metrics - Version Simplifiée (250L vs 550L)

Métriques essentielles sans dataclasses/locks/deque complexes
Compatible API neural_pathway_manager.py
"""

import time
from typing import Any


class NeuralPrometheusMetrics:
    """📊 Métriques Neural simplifiées (dict simples)"""

    def __init__(self):
        # Compteurs globaux
        self.requests_total = 0
        self.success_total = 0
        self.failures_total = 0
        self.fallback_total = 0

        # Requests par classe
        self.requests_by_class = {"ping": 0, "lookup": 0, "gen_short": 0, "gen_long": 0}

        # Latences (liste simple dernières 100 valeurs)
        self.latencies = []
        self.max_latencies = 100

        # Métriques globales
        self.global_success_rate = 0.0
        self.active_correlations = 0
        self.ucb_exploration_factor = 1.4

        # Métriques UCB scores
        self.ucb_scores = {"local": 0.0, "cloud": 0.0, "reflex": 0.0}

        # Métriques par synapse
        self.synapse_fires = {"local": 0, "cloud": 0, "reflex": 0}
        self.synapse_success = {"local": 0, "cloud": 0, "reflex": 0}
        self.synapse_failures = {"local": 0, "cloud": 0, "reflex": 0}
        self.synapse_success_rate = {"local": 0.0, "cloud": 0.0, "reflex": 0.0}
        self.synapse_circuit_state = {"local": 0, "cloud": 0, "reflex": 0}  # 0=CLOSED, 1=OPEN
        self.synapse_ema_latency = {"local": 0.0, "cloud": 0.0, "reflex": 0.0}
        self.synapse_can_execute = {"local": 1, "cloud": 1, "reflex": 1}  # 1=True, 0=False

        # Failures par erreur
        self.failures_by_error = {}

        # Fallbacks par raison
        self.fallbacks_by_reason = {}

    def record_neural_request(self, stimulus_class: str = "gen_short"):
        """📊 Enregistrer requête Neural"""
        self.requests_total += 1
        if stimulus_class in self.requests_by_class:
            self.requests_by_class[stimulus_class] += 1

    def record_neural_success(
        self,
        latency_seconds: float,
        synapse_name: str = "local",
        stimulus_class: str = "gen_short"
    ):
        """✅ Enregistrer succès Neural"""
        self.success_total += 1

        # Latence
        if len(self.latencies) >= self.max_latencies:
            self.latencies.pop(0)
        self.latencies.append(latency_seconds)

        # Synapse stats
        if synapse_name in self.synapse_success:
            self.synapse_success[synapse_name] += 1

    def record_neural_failure(self, synapse_name: str = "local", error_type: str = "unknown"):
        """❌ Enregistrer échec Neural"""
        self.failures_total += 1

        # Par synapse
        if synapse_name in self.synapse_failures:
            self.synapse_failures[synapse_name] += 1

        # Par type d'erreur
        self.failures_by_error[error_type] = self.failures_by_error.get(error_type, 0) + 1

    def record_neural_fallback(self, reason: str = "unknown"):
        """🔄 Enregistrer fallback Neural"""
        self.fallback_total += 1
        self.fallbacks_by_reason[reason] = self.fallbacks_by_reason.get(reason, 0) + 1

    def record_ucb_scores(self, ucb_scores: dict[str, float]):
        """🎰 Enregistrer scores UCB"""
        self.ucb_scores.update(ucb_scores)

    def update_synapse_metrics(self, synapse_name: str, synapse_data: dict[str, Any]):
        """🔌 Mettre à jour métriques synapse"""
        if synapse_name not in self.synapse_success_rate:
            return

        if "success_rate" in synapse_data:
            self.synapse_success_rate[synapse_name] = synapse_data["success_rate"]

        if "circuit_state" in synapse_data:
            # CLOSED=0, OPEN=1, HALF_OPEN=0.5
            state_map = {"CLOSED": 0, "OPEN": 1, "HALF_OPEN": 0.5}
            self.synapse_circuit_state[synapse_name] = state_map.get(synapse_data["circuit_state"], 0)

        if "ema_latency" in synapse_data:
            self.synapse_ema_latency[synapse_name] = synapse_data["ema_latency"]

        if "can_execute" in synapse_data:
            self.synapse_can_execute[synapse_name] = 1 if synapse_data["can_execute"] else 0

    def update_global_metrics(
        self,
        total_requests: int = 0,
        successful_requests: int = 0,
        active_correlations: int = 0,
        ucb_exploration_factor: float = 1.4,
    ):
        """🌍 Mettre à jour métriques globales"""
        if total_requests > 0:
            self.global_success_rate = successful_requests / total_requests
        self.active_correlations = active_correlations
        self.ucb_exploration_factor = ucb_exploration_factor

    def export_prometheus_format(self) -> str:
        """🚀 Export format Prometheus (simplifié)"""
        timestamp = int(time.time() * 1000)
        lines = []

        # Compteurs principaux
        lines.append("# HELP neural_requests_total Total Neural requests")
        lines.append("# TYPE neural_requests_total counter")
        lines.append(f"neural_requests_total {self.requests_total} {timestamp}")

        lines.append("# HELP neural_success_total Total Neural successes")
        lines.append("# TYPE neural_success_total counter")
        lines.append(f"neural_success_total {self.success_total} {timestamp}")

        lines.append("# HELP neural_failures_total Total Neural failures")
        lines.append("# TYPE neural_failures_total counter")
        lines.append(f"neural_failures_total {self.failures_total} {timestamp}")

        lines.append("# HELP neural_fallback_total Total Neural fallbacks")
        lines.append("# TYPE neural_fallback_total counter")
        lines.append(f"neural_fallback_total {self.fallback_total} {timestamp}")

        # Requests par classe
        for class_name, count in self.requests_by_class.items():
            lines.append(f'neural_requests_by_class{{class="{class_name}"}} {count} {timestamp}')

        # Latences (p50, p95, p99)
        if self.latencies:
            sorted_lat = sorted(self.latencies)
            p50_idx = int(len(sorted_lat) * 0.5)
            p95_idx = int(len(sorted_lat) * 0.95)
            p99_idx = int(len(sorted_lat) * 0.99)

            lines.append("# HELP neural_latency_p50 Latency p50")
            lines.append(f"neural_latency_p50 {sorted_lat[p50_idx]:.6f} {timestamp}")
            lines.append("# HELP neural_latency_p95 Latency p95")
            lines.append(f"neural_latency_p95 {sorted_lat[p95_idx]:.6f} {timestamp}")
            lines.append("# HELP neural_latency_p99 Latency p99")
            lines.append(f"neural_latency_p99 {sorted_lat[p99_idx]:.6f} {timestamp}")

        # Métriques globales
        lines.append("# HELP neural_global_success_rate Global success rate")
        lines.append(f"neural_global_success_rate {self.global_success_rate:.4f} {timestamp}")

        lines.append("# HELP neural_active_correlations Active correlations")
        lines.append(f"neural_active_correlations {self.active_correlations} {timestamp}")

        # UCB scores
        for synapse, score in self.ucb_scores.items():
            lines.append(f'neural_ucb_score{{synapse="{synapse}"}} {score:.4f} {timestamp}')

        # Métriques par synapse
        for synapse in ["local", "cloud", "reflex"]:
            lines.append(f'neural_synapse_fires{{synapse="{synapse}"}} {self.synapse_fires[synapse]} {timestamp}')
            lines.append(f'neural_synapse_success{{synapse="{synapse}"}} {self.synapse_success[synapse]} {timestamp}')
            lines.append(f'neural_synapse_failures{{synapse="{synapse}"}} {self.synapse_failures[synapse]} {timestamp}')
            lines.append(f'neural_synapse_success_rate{{synapse="{synapse}"}} {self.synapse_success_rate[synapse]:.4f} {timestamp}')
            lines.append(f'neural_synapse_circuit_state{{synapse="{synapse}"}} {self.synapse_circuit_state[synapse]} {timestamp}')
            lines.append(f'neural_synapse_ema_latency{{synapse="{synapse}"}} {self.synapse_ema_latency[synapse]:.6f} {timestamp}')
            lines.append(f'neural_synapse_can_execute{{synapse="{synapse}"}} {self.synapse_can_execute[synapse]} {timestamp}')

        return "\n".join(lines) + "\n"

    def get_summary_stats(self) -> dict[str, Any]:
        """📈 Résumé statistiques"""
        latency_summary = {}
        if self.latencies:
            sorted_lat = sorted(self.latencies)
            latency_summary = {
                "p50": sorted_lat[int(len(sorted_lat) * 0.5)],
                "p95": sorted_lat[int(len(sorted_lat) * 0.95)],
                "p99": sorted_lat[int(len(sorted_lat) * 0.99)],
            }

        return {
            "total_requests": self.requests_total,
            "total_success": self.success_total,
            "total_failures": self.failures_total,
            "total_fallbacks": self.fallback_total,
            "global_success_rate": self.global_success_rate,
            "active_correlations": self.active_correlations,
            "latency": latency_summary,
            "ucb_scores": self.ucb_scores,
            "synapse_states": {
                name: {
                    "fires": self.synapse_fires[name],
                    "success": self.synapse_success[name],
                    "failures": self.synapse_failures[name],
                    "success_rate": self.synapse_success_rate[name],
                    "circuit_state": self.synapse_circuit_state[name],
                    "can_execute": self.synapse_can_execute[name],
                    "ema_latency": self.synapse_ema_latency[name],
                }
                for name in ["local", "cloud", "reflex"]
            },
        }


# Instance globale (API compatible)
neural_prometheus_metrics = NeuralPrometheusMetrics()


def export_neural_metrics() -> str:
    """🚀 Export métriques Prometheus"""
    return neural_prometheus_metrics.export_prometheus_format()


def get_neural_stats_summary() -> dict[str, Any]:
    """📊 Résumé stats"""
    return neural_prometheus_metrics.get_summary_stats()
