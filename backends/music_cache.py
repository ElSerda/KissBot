"""
🎵 Quantum Music Cache - KissBot Phase 3.4 (POC)

Cache quantique pour musiques avec apprentissage crowdsourced.
Proof of Concept pour multi-domain quantum system.

FONCTIONNALITÉS QUANTUM :
├── Superposition de résultats (multiple suggestions)
├── Collapse par mods (ancrage vérité terrain)
├── Apprentissage par confirmations users
├── Stats temps réel (observabilité)
└── Cleanup décohérence (nettoyage intelligent)

WORKFLOW :
1. !qmusic artist song → Superposition (liste 1-2-3)
2. !collapse music 1 → Mod ancre la vraie track
3. Bot apprend → Futures recherches améliorées

NOTE: Phase 3.4 POC - Pas d'API externe pour l'instant (mock data OK)
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any

from core.cache_interface import BaseCacheInterface, CacheStats


class MusicCache(BaseCacheInterface):
    """
    🔬 Quantum Music Cache - Phase 3.4 POC

    QUANTUM FEATURES :
    - Superposition : Multiple track suggestions (1-2-3)
    - Collapse : Mods anchor truth (crowdsourced curation)
    - Learning : Bot improves from confirmations
    - Stats : Real-time observability
    """

    def __init__(self, config: dict[str, Any], cache_file: str = "cache/quantum_music.json"):
        super().__init__(config)
        self.cache_file = cache_file

        # Configuration cache
        cache_config = config.get("cache", {})
        self.cache_duration = timedelta(hours=cache_config.get("duration_hours", 24))

        # Configuration quantum
        quantum_config = config.get("quantum_music", {})
        self.max_superpositions = quantum_config.get("max_suggestions", 3)
        self.confirmation_boost = quantum_config.get("confirmation_confidence_boost", 0.2)

        # Quantum storage
        # Structure: {
        #   "music:artist-song": {
        #       "superpositions": [
        #           {"track": {...}, "confidence": 0.9, "verified": 0, "confirmations": 0},
        #           {"track": {...}, "confidence": 0.7, "verified": 0, "confirmations": 0}
        #       ],
        #       "collapsed": False,
        #       "created_at": "ISO timestamp",
        #       "last_search": "ISO timestamp"
        #   }
        # }
        self.quantum_states: dict[str, dict[str, Any]] = {}

        self.logger = logging.getLogger(__name__)

        self._ensure_cache_dir()
        self._load_cache()

    def _ensure_cache_dir(self):
        """Créer le dossier cache si nécessaire."""
        cache_dir = os.path.dirname(self.cache_file)
        if cache_dir and not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

    def _load_cache(self):
        """Charger le cache quantique depuis le fichier."""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, encoding="utf-8") as f:
                    data = json.load(f)

                # Nettoyer les entrées expirées
                now = datetime.now()
                valid_cache = {}

                for key, quantum_state in data.items():
                    created_time = datetime.fromisoformat(quantum_state["created_at"])
                    if now - created_time < self.cache_duration:
                        valid_cache[key] = quantum_state

                self.quantum_states = valid_cache
                self.logger.info(f"🎵 Quantum music cache chargé: {len(self.quantum_states)} états quantiques")
            else:
                self.logger.info("🎵 Nouveau quantum music cache créé")

        except Exception as e:
            self.logger.error(f"Erreur chargement quantum music cache: {e}")
            self.quantum_states = {}

    def _save_cache(self):
        """Sauvegarder le cache quantique."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.quantum_states, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Erreur sauvegarde quantum music cache: {e}")

    async def search_quantum_music(
        self, query: str, observer: str = "user"
    ) -> list[dict[str, Any]]:
        """
        🔬 Recherche quantique avec superposition

        Returns list of superposition states (1-2-3):
        [
            {
                "index": 1,
                "track": {...TrackData...},
                "confidence": 0.9,
                "verified": 0,
                "confirmations": 0,
                "collapsed": False
            },
            ...
        ]
        """
        cache_key = f"music:{query.lower().strip()}"

        # Check existing quantum state
        if cache_key in self.quantum_states:
            quantum_state = self.quantum_states[cache_key]

            # Update last search timestamp
            quantum_state["last_search"] = datetime.now().isoformat()
            self._save_cache()

            # Return existing superpositions
            superpositions = quantum_state.get("superpositions", [])
            result = []
            for idx, sup in enumerate(superpositions[:self.max_superpositions], start=1):
                result.append({
                    "index": idx,
                    "track": sup.get("track"),
                    "confidence": sup.get("confidence", 0.5),
                    "verified": sup.get("verified", 0),
                    "confirmations": sup.get("confirmations", 0),
                    "collapsed": quantum_state.get("collapsed", False)
                })

            self.logger.info(f"🎯 Quantum music state trouvé: {query} ({len(result)} superpositions)")
            return result

        # Create new quantum superposition (POC - mock data)
        return await self._create_quantum_superposition(query, observer)

    async def _create_quantum_superposition(
        self, query: str, observer: str
    ) -> list[dict[str, Any]]:
        """Crée une nouvelle superposition quantique (POC - mock data)."""
        cache_key = f"music:{query.lower().strip()}"

        try:
            # POC: Mock music data (TODO: Add real API in future)
            mock_track = {
                "artist": "Artist Name",
                "title": query.title(),
                "album": "Unknown Album",
                "year": 2024,
                "duration": "3:45",
                "genres": ["Rock", "Alternative"],
                "source": "mock"
            }

            confidence = 0.5  # Lower confidence for mock data

            # Create quantum state
            quantum_state = {
                "superpositions": [
                    {
                        "track": mock_track,
                        "confidence": confidence,
                        "verified": 0,
                        "confirmations": 0,
                        "created_by": observer
                    }
                ],
                "collapsed": False,
                "created_at": datetime.now().isoformat(),
                "last_search": datetime.now().isoformat(),
                "search_count": 1
            }

            self.quantum_states[cache_key] = quantum_state
            self._save_cache()

            self.logger.info(f"⚛️ Music superposition créée: {query} (POC mock data)")

            # Return formatted result
            return [{
                "index": 1,
                "track": mock_track,
                "confidence": confidence,
                "verified": 0,
                "confirmations": 0,
                "collapsed": False
            }]

        except Exception as e:
            self.logger.error(f"Erreur création music superposition {query}: {e}")
            return []

    def collapse_music(self, query: str, observer: str, state_index: int = 1) -> dict[str, Any] | None:
        """
        💥 Collapse quantum music state (Mod anchors truth)

        Args:
            query: Track query
            observer: Username (mod/admin)
            state_index: Superposition index (1-2-3)

        Returns:
            Collapsed track data or None if failed
        """
        cache_key = f"music:{query.lower().strip()}"

        if cache_key not in self.quantum_states:
            self.logger.warning(f"❌ État quantique music inexistant: {query}")
            return None

        quantum_state = self.quantum_states[cache_key]
        superpositions = quantum_state.get("superpositions", [])

        # Convert 1-based to 0-based index
        idx = state_index - 1

        if idx < 0 or idx >= len(superpositions):
            self.logger.warning(f"❌ Index invalide: {state_index} pour {query}")
            return None

        # Collapse to selected superposition
        selected = superpositions[idx]
        selected["verified"] = 1
        selected["confirmations"] += 1
        selected["last_confirmed_by"] = observer
        selected["last_confirmed_at"] = datetime.now().isoformat()

        quantum_state["collapsed"] = True
        quantum_state["collapsed_at"] = datetime.now().isoformat()
        quantum_state["collapsed_by"] = observer

        # Move collapsed state to first position
        if idx != 0:
            superpositions[0], superpositions[idx] = superpositions[idx], superpositions[0]

        self._save_cache()

        self.logger.info(
            f"💥 Music collapse quantique: {query} par {observer} → {selected['track']['title']} "
            f"(confirmations: {selected['confirmations']})"
        )

        return selected["track"]

    def get_quantum_stats(self) -> dict[str, Any]:
        """
        📊 Stats système quantique music (pour !quantum command)

        Returns:
            {
                "total_tracks": int,
                "superpositions_active": int,
                "collapsed_states": int,
                "verified_percentage": float,
                "total_confirmations": int
            }
        """
        total_tracks = len(self.quantum_states)
        superpositions_active = 0
        collapsed_states = 0
        total_confirmations = 0

        for quantum_state in self.quantum_states.values():
            if quantum_state.get("collapsed"):
                collapsed_states += 1
            else:
                # Count non-collapsed superpositions
                sup_count = len(quantum_state.get("superpositions", []))
                if sup_count > 1:
                    superpositions_active += 1

            # Count confirmations
            for sup in quantum_state.get("superpositions", []):
                total_confirmations += sup.get("confirmations", 0)

        verified_pct = (collapsed_states / total_tracks * 100) if total_tracks > 0 else 0.0

        return {
            "total_tracks": total_tracks,
            "superpositions_active": superpositions_active,
            "collapsed_states": collapsed_states,
            "verified_percentage": verified_pct,
            "total_confirmations": total_confirmations
        }

    def cleanup_expired(self) -> int:
        """
        💨 Décohérence quantique music (cleanup expired states)

        Returns:
            Number of states evaporated
        """
        now = datetime.now()
        expired_keys = []

        for key, quantum_state in self.quantum_states.items():
            created_time = datetime.fromisoformat(quantum_state["created_at"])

            # Expired if beyond cache duration
            if now - created_time >= self.cache_duration:
                expired_keys.append(key)
                continue

            # Also expire non-verified states with no recent searches
            last_search = datetime.fromisoformat(quantum_state.get("last_search", quantum_state["created_at"]))
            if not quantum_state.get("collapsed") and (now - last_search) >= timedelta(hours=48):
                expired_keys.append(key)

        # Evaporate expired states
        for key in expired_keys:
            del self.quantum_states[key]

        if expired_keys:
            self._save_cache()
            self.logger.info(f"💨 Music décohérence: {len(expired_keys)} états évaporés")

        return len(expired_keys)

    # ============================================================
    # BaseCacheInterface Implementation
    # ============================================================

    def get(self, query: str) -> dict[Any, Any] | None:
        """Get collapsed/verified track (interface compatibility)."""
        cache_key = f"music:{query.lower().strip()}"

        if cache_key in self.quantum_states:
            quantum_state = self.quantum_states[cache_key]

            # Return first (collapsed) superposition if exists
            superpositions = quantum_state.get("superpositions", [])
            if superpositions:
                return superpositions[0].get("track")

        return None

    def set(self, key: str, value: dict[str, Any], **kwargs) -> bool:
        """Set track in cache (interface compatibility)."""
        try:
            cache_key = f"music:{key.lower().strip()}"
            confidence = kwargs.get("confidence", 0.8)
            observer = kwargs.get("observer", "system")
            verified = 1 if kwargs.get("verified", False) else 0

            quantum_state = {
                "superpositions": [
                    {
                        "track": value,
                        "confidence": confidence,
                        "verified": verified,
                        "confirmations": 0,
                        "created_by": observer
                    }
                ],
                "collapsed": verified == 1,
                "created_at": datetime.now().isoformat(),
                "last_search": datetime.now().isoformat(),
                "search_count": 1
            }

            self.quantum_states[cache_key] = quantum_state
            self._save_cache()

            self.logger.info(f"💾 Quantum music set: {key} (verified: {verified})")
            return True

        except Exception as e:
            self.logger.error(f"❌ Erreur quantum music set: {e}")
            return False

    async def search(self, query: str, **kwargs) -> dict[str, Any] | None:
        """Search track (interface compatibility - returns first result)."""
        results = await self.search_quantum_music(query, kwargs.get("observer", "user"))
        if results:
            return results[0].get("track")
        return None

    def get_stats(self) -> CacheStats:
        """Get stats (interface compatibility)."""
        quantum_stats = self.get_quantum_stats()

        return CacheStats(
            total_keys=quantum_stats["total_tracks"],
            confirmed_keys=quantum_stats["collapsed_states"],
            cache_hits=0,
            cache_misses=0,
            hit_rate=0.0,
            total_size_mb=0.0,
            avg_confidence=quantum_stats["verified_percentage"] / 100.0,
            quantum_enabled=True,
        )

    def clear(self) -> bool:
        """Clear all quantum music states (interface compatibility)."""
        try:
            count = len(self.quantum_states)
            self.quantum_states = {}
            self._save_cache()
            self.logger.info(f"🗑️ Quantum music cache vidé: {count} états")
            return True
        except Exception as e:
            self.logger.error(f"❌ Erreur clear quantum music: {e}")
            return False

    async def close(self):
        """Cleanup on shutdown."""
        pass  # No external API to close for POC
