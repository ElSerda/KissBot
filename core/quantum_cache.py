"""Quantum cache system → docs/api/quantum_cache.md"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class QuantumState:
    """État quantique → docs/api/quantum_cache.md#quantumstate"""

    data: Any
    timestamp: float

    verified: int = 0
    confidence: float = 0.5
    observer_count: int = 0
    entangled_keys: list[str] = field(default_factory=list)

    source: str = "unknown"
    created_by: str = "system"
    last_access: float = field(default_factory=time.time)

    def is_expired(self, ttl_verified: int = 86400, ttl_unverified: int = 1800) -> bool:
        """Expiry check → docs/api/quantum_cache.md#is-expired"""
        current_time = time.time()
        age = current_time - self.timestamp

        if self.verified == 1:
            return age > ttl_verified
        else:
            return age > ttl_unverified

    def observe(self, observer: str = "user") -> None:
        """Observer access → docs/api/quantum_cache.md#observe"""
        self.observer_count += 1
        self.last_access = time.time()

    def collapse(self, observer: str = "user") -> None:
        """Wave function collapse → docs/api/quantum_cache.md#collapse"""
        self.verified = 1
        self.confidence = 1.0
        self.observe(observer)


class QuantumCache:
    """Cache Quantique → docs/api/quantum_cache.md#quantumcache"""

    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(__name__)

        cache_config = config.get("quantum_cache", {})
        self.ttl_verified = cache_config.get("ttl_verified_seconds", 86400)
        self.ttl_unverified = cache_config.get("ttl_unverified_seconds", 1800)
        self.max_superposition = cache_config.get("max_superposition_states", 3)
        self.entanglement_enabled = cache_config.get("entanglement_enabled", True)

        self.quantum_states: dict[str, list[QuantumState]] = {}
        self.entanglement_registry: dict[str, list[str]] = {}

        self.logger.info("🔬 QuantumCache initialisé - Phénomènes quantiques actifs")

    def get(self, key: str, observer: str = "user") -> Any | None:
        """Quantum state retrieval → docs/api/quantum_cache.md#get"""
        states = self.quantum_states.get(key, [])
        if not states:
            return None

        self._trigger_decoherence(key)
        self._trigger_decoherence(key)
        states = self.quantum_states.get(key, [])
        if not states:
            return None

        best_state = max(states, key=lambda s: s.confidence)

        best_state.observe(observer)

        self.logger.debug(
            f"🔍 Observation quantique: {key} par {observer} "
            f"(confiance: {best_state.confidence:.2f}, "
            f"vérifié: {best_state.verified})"
        )

        return best_state.data

    def set(
        self,
        key: str,
        value: Any,
        source: str = "system",
        creator: str = "system",
        confidence: float = 0.5,
    ) -> None:
        """Store quantum state → docs/api/quantum_cache.md#set"""
        current_time = time.time()

        new_state = QuantumState(
            data=value,
            timestamp=current_time,
            confidence=confidence,
            source=source,
            created_by=creator,
        )

        if key not in self.quantum_states:
            self.quantum_states[key] = []

        self.quantum_states[key].append(new_state)

        self._limit_superposition(key)

        self.logger.debug(
            f"⚛️ Nouvel état quantique: {key} "
            f"(confiance: {confidence:.2f}, "
            f"total états: {len(self.quantum_states[key])})"
        )

    def collapse_state(self, key: str, observer: str = "user", state_index: int = 0) -> bool:
        """Wave function collapse → docs/api/quantum_cache.md#collapse-state"""
        states = self.quantum_states.get(key, [])
        if not states or state_index >= len(states):
            return False

        chosen_state = states[state_index]
        chosen_state.collapse(observer)

        self.quantum_states[key] = [chosen_state]

        if self.entanglement_enabled:
            self._propagate_entanglement(key, chosen_state)

        self.logger.info(
            f"💥 COLLAPSE quantique: {key} par {observer} "
            f"→ État fixé (source: {chosen_state.source})"
        )

        return True

    def entangle(self, key1: str, key2: str) -> None:
        """Quantum entanglement → docs/api/quantum_cache.md#entangle"""
        if not self.entanglement_enabled:
            return

        if key1 not in self.entanglement_registry:
            self.entanglement_registry[key1] = []
        if key2 not in self.entanglement_registry:
            self.entanglement_registry[key2] = []

        if key2 not in self.entanglement_registry[key1]:
            self.entanglement_registry[key1].append(key2)
        if key1 not in self.entanglement_registry[key2]:
            self.entanglement_registry[key2].append(key1)

        for key in [key1, key2]:
            states = self.quantum_states.get(key, [])
            for state in states:
                other_key = key2 if key == key1 else key1
                if other_key not in state.entangled_keys:
                    state.entangled_keys.append(other_key)

        self.logger.debug(f"🔗 Intrication quantique: {key1} ↔ {key2}")

    def _propagate_entanglement(self, collapsed_key: str, collapsed_state: QuantumState) -> None:
        """Propage les effets d'un collapse à travers les intrications."""
        entangled_keys = self.entanglement_registry.get(collapsed_key, [])

        for entangled_key in entangled_keys:
            entangled_states = self.quantum_states.get(entangled_key, [])

            for state in entangled_states:
                if state.source == collapsed_state.source:
                    state.confidence = min(state.confidence + 0.2, 1.0)
                    self.logger.debug(
                        f"⚡ Intrication: {entangled_key} confiance "
                        f"boosted → {state.confidence:.2f}"
                    )

    def _limit_superposition(self, key: str) -> None:
        """Limite le nombre d'états en superposition (principe d'incertitude)."""
        states = self.quantum_states.get(key, [])

        if len(states) > self.max_superposition:
            states.sort(key=lambda s: s.confidence, reverse=True)
            self.quantum_states[key] = states[: self.max_superposition]

            self.logger.debug(
                f"✂️ Superposition limitée: {key} " f"→ {self.max_superposition} états max"
            )

    def _trigger_decoherence(self, key: str) -> None:
        """
        DÉCOHÉRENCE QUANTIQUE

        États non-vérifiés s'évaporent après TTL (particules virtuelles).
        """
        states = self.quantum_states.get(key, [])
        if not states:
            return

        valid_states = []
        expired_count = 0

        for state in states:
            if state.is_expired(self.ttl_verified, self.ttl_unverified):
                expired_count += 1
            else:
                valid_states.append(state)

        if expired_count > 0:
            self.quantum_states[key] = valid_states
            if not valid_states:
                del self.quantum_states[key]
                if key in self.entanglement_registry:
                    del self.entanglement_registry[key]

            self.logger.debug(f"💨 Décohérence: {key} → {expired_count} états évaporés")

    def cleanup_expired(self) -> int:
        """Global decoherence cleanup → docs/api/quantum_cache.md#cleanup-expired"""
        cleaned_count = 0
        keys_to_remove = []

        for key in list(self.quantum_states.keys()):
            self._trigger_decoherence(key)
            if key not in self.quantum_states:
                keys_to_remove.append(key)
                cleaned_count += 1

        for removed_key in keys_to_remove:
            if removed_key in self.entanglement_registry:
                del self.entanglement_registry[removed_key]

        if cleaned_count > 0:
            self.logger.info(f"🧹 Décohérence globale: {cleaned_count} clés évaporées")

        return cleaned_count

    def get_quantum_stats(self) -> dict[str, Any]:
        """Statistiques du système quantique."""
        total_states = sum(len(states) for states in self.quantum_states.values())
        verified_states = sum(
            1 for states in self.quantum_states.values() for state in states if state.verified == 1
        )
        entangled_pairs = len(self.entanglement_registry)

        return {
            "total_keys": len(self.quantum_states),
            "total_states": total_states,
            "superposition_keys": len([k for k, v in self.quantum_states.items() if len(v) > 1]),
            "verified_states": verified_states,
            "unverified_states": total_states - verified_states,
            "entangled_pairs": entangled_pairs,
            "avg_states_per_key": total_states / max(len(self.quantum_states), 1),
            "max_superposition_allowed": self.max_superposition,
            "ttl_verified_hours": self.ttl_verified / 3600,
            "ttl_unverified_minutes": self.ttl_unverified / 60,
        }

    def visualize_quantum_state(self, key: str) -> str:
        """Visualisation ASCII d'un état quantique."""
        states = self.quantum_states.get(key, [])
        if not states:
            return f"🚫 {key}: État quantique vide"

        lines = [f"🔬 {key} - États quantiques:"]

        for i, state in enumerate(states):
            status = "🔒 COLLAPSED" if state.verified == 1 else "⚛️ SUPERPOSITION"
            confidence_bar = "█" * int(state.confidence * 10)
            entangled = f" 🔗{len(state.entangled_keys)}" if state.entangled_keys else ""

            lines.append(
                f"  [{i}] {status} - {confidence_bar} {state.confidence:.1f} "
                f"- 👁️{state.observer_count} - {state.source}{entangled}"
            )

        return "\n".join(lines)
