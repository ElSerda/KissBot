"""
🌌 Quantum Metrics - Version Simplifiée (200L vs 454L)

Métriques essentielles pour StaticQuantumClassifier sans overhead
Buffer réduit (100 vs 10000), pas de Prometheus, stats simples
"""

import time
from typing import Dict, List, Any


class QuantumStats:
    """📊 Statistiques quantiques (simple dict-like)"""
    
    def __init__(self):
        self.total_classifications = 0
        self.accuracy_rate = 0.0
        self.avg_confidence = 0.0
        self.avg_entropy = 0.0
        self.fallback_rate = 0.0
        self.certainty_rate = 0.0
        self.avg_response_time_ms = 0.0
        self.class_distribution = {}
        self.class_confidence = {}
        self.entropy_buckets = {
            "very_low": 0,  # 0.0 - 0.5
            "low": 0,       # 0.5 - 1.0
            "medium": 0,    # 1.0 - 1.5
            "high": 0,      # 1.5 - 2.0
            "max": 0        # 2.0
        }
    
    def __dict__(self):
        """Compatibilité avec ancien code qui fait .__dict__"""
        return {
            "total_classifications": self.total_classifications,
            "accuracy_rate": self.accuracy_rate,
            "avg_confidence": self.avg_confidence,
            "avg_entropy": self.avg_entropy,
            "fallback_rate": self.fallback_rate,
            "certainty_rate": self.certainty_rate,
            "avg_response_time_ms": self.avg_response_time_ms,
            "class_distribution": self.class_distribution,
            "class_confidence": self.class_confidence,
            "entropy_buckets": self.entropy_buckets,
        }


class QuantumMetrics:
    """🌌 Métriques quantiques simplifiées (buffer 100, stats essentielles)"""
    
    def __init__(self, 
                 buffer_size: int = 100,
                 enable_prometheus: bool = False,
                 prometheus_prefix: str = "kissbot_quantum",
                 enable_structured_logging: bool = False):
        """
        Args:
            buffer_size: Réduit à 100 (vs 10000)
            enable_prometheus: Désactivé (trop complexe)
            prometheus_prefix: Ignoré
            enable_structured_logging: Ignoré
        """
        self.buffer_size = buffer_size
        
        # Buffer simple (liste circulaire)
        self.metrics_buffer: List[Dict[str, Any]] = []
        
        # Stats temps réel
        self.current_stats = QuantumStats()
        
        # Pattern hits simplifiés
        self.pattern_hits: Dict[str, Dict[str, int]] = {}
        
        # Totaux pour calculs
        self._total_confidence = 0.0
        self._total_entropy = 0.0
        self._total_response_time = 0.0
        self._total_fallbacks = 0
        self._total_certain = 0
    
    def record_classification(
        self,
        stimulus: str,
        classification: str,
        confidence: float,
        entropy: float,
        is_certain: bool,
        should_fallback: bool,
        distribution_type: str = "unknown",
        method: str = "quantum",
        response_time_ms: float = 0.0,
        quantum_result: Dict[str, Any] = None
    ):
        """📊 Enregistrer classification (API compatible)"""
        
        # Créer métrique
        metric = {
            "timestamp": time.time(),
            "stimulus": stimulus[:50],  # Tronquer pour économiser mémoire
            "classification": classification,
            "confidence": confidence,
            "entropy": entropy,
            "is_certain": is_certain,
            "should_fallback": should_fallback,
            "distribution_type": distribution_type,
            "method": method,
            "response_time_ms": response_time_ms,
        }
        
        # Buffer circulaire simple
        if len(self.metrics_buffer) >= self.buffer_size:
            self.metrics_buffer.pop(0)
        self.metrics_buffer.append(metric)
        
        # Mettre à jour stats
        self._update_stats(metric)
    
    def _update_stats(self, metric: Dict[str, Any]):
        """📈 Mise à jour statistiques"""
        stats = self.current_stats
        
        # Totaux
        stats.total_classifications += 1
        
        # Accumulateurs
        self._total_confidence += metric["confidence"]
        self._total_entropy += metric["entropy"]
        self._total_response_time += metric["response_time_ms"]
        
        if metric["should_fallback"]:
            self._total_fallbacks += 1
        
        if metric["is_certain"]:
            self._total_certain += 1
        
        # Moyennes
        n = stats.total_classifications
        stats.avg_confidence = self._total_confidence / n
        stats.avg_entropy = self._total_entropy / n
        stats.avg_response_time_ms = self._total_response_time / n
        stats.fallback_rate = self._total_fallbacks / n
        stats.certainty_rate = self._total_certain / n
        
        # Distribution par classe
        cls = metric["classification"]
        stats.class_distribution[cls] = stats.class_distribution.get(cls, 0) + 1
        
        # Confidence par classe (moyenne simple)
        if cls not in stats.class_confidence:
            stats.class_confidence[cls] = metric["confidence"]
        else:
            # Moyenne glissante simple
            stats.class_confidence[cls] = (
                stats.class_confidence[cls] * 0.9 + metric["confidence"] * 0.1
            )
        
        # Buckets entropie
        entropy = metric["entropy"]
        if entropy < 0.5:
            stats.entropy_buckets["very_low"] += 1
        elif entropy < 1.0:
            stats.entropy_buckets["low"] += 1
        elif entropy < 1.5:
            stats.entropy_buckets["medium"] += 1
        elif entropy < 2.0:
            stats.entropy_buckets["high"] += 1
        else:
            stats.entropy_buckets["max"] += 1
    
    def get_current_stats(self) -> QuantumStats:
        """📊 Obtenir stats actuelles"""
        return self.current_stats
    
    def get_pattern_hit_stats(self) -> Dict[str, Any]:
        """🎯 Stats pattern hits (simplifié)"""
        # Retourner stats basiques depuis buffer
        pattern_stats = {}
        for metric in self.metrics_buffer:
            cls = metric["classification"]
            if cls not in pattern_stats:
                pattern_stats[cls] = {"count": 0, "avg_confidence": 0.0}
            pattern_stats[cls]["count"] += 1
        
        return pattern_stats
    
    def get_recent_metrics(self, n: int = 20) -> List[Dict[str, Any]]:
        """📋 Obtenir N dernières métriques"""
        return self.metrics_buffer[-n:] if self.metrics_buffer else []
    
    def export_json_report(self) -> Dict[str, Any]:
        """📊 Export rapport JSON (simplifié)"""
        return {
            "stats": self.current_stats.__dict__(),
            "recent_classifications": [
                {
                    "class": m["classification"],
                    "confidence": m["confidence"],
                    "entropy": m["entropy"],
                    "certain": m["is_certain"],
                }
                for m in self.metrics_buffer[-10:]
            ],
            "pattern_hits": self.get_pattern_hit_stats(),
            "buffer_size": len(self.metrics_buffer),
            "max_buffer": self.buffer_size,
        }
    
    def reset_metrics(self):
        """🔄 Reset métriques (utile pour tests)"""
        self.metrics_buffer.clear()
        self.current_stats = QuantumStats()
        self.pattern_hits.clear()
        self._total_confidence = 0.0
        self._total_entropy = 0.0
        self._total_response_time = 0.0
        self._total_fallbacks = 0
        self._total_certain = 0
