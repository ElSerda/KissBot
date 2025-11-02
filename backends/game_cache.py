"""
🎮 Quantum Game Cache - KissBot

Cache quantique pour jeux avec apprentissage crowdsourced.

FONCTIONNALITÉS QUANTUM :
├── Superposition de résultats (multiple suggestions)
├── Collapse par mods (ancrage vérité terrain)
├── Apprentissage par confirmations users
├── Stats temps réel (observabilité)
└── Cleanup décohérence (nettoyage intelligent)

WORKFLOW :
1. !qgame hades → Superposition (liste 1-2-3)
2. !collapse hades 1 → Mod ancre le vrai jeu
3. Bot apprend → Futures recherches améliorées
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Any

from backends.game_lookup import GameLookup, GameResult
from core.cache_interface import BaseCacheInterface, CacheStats


class GameCache(BaseCacheInterface):
    """
    🔬 Quantum Game Cache - Phase 3.4

    QUANTUM FEATURES :
    - Superposition : Multiple game suggestions (1-2-3)
    - Collapse : Mods anchor truth (crowdsourced curation)
    - Learning : Bot improves from confirmations
    - Stats : Real-time observability
    """

    def __init__(self, config: dict[str, Any], cache_file: str = "cache/quantum_games.json"):
        super().__init__(config)
        self.cache_file = cache_file

        # Configuration cache
        cache_config = config.get("cache", {})
        self.cache_duration = timedelta(hours=cache_config.get("duration_hours", 24))

        # Configuration quantum
        quantum_config = config.get("quantum_games", {})
        self.max_superpositions = quantum_config.get("max_suggestions", 3)
        self.confirmation_boost = quantum_config.get("confirmation_confidence_boost", 0.2)
        self.auto_entangle = quantum_config.get("auto_entangle", True)

        # Quantum storage
        # Structure: {
        #   "game:hades": {
        #       "superpositions": [
        #           {"game": {...}, "confidence": 0.9, "verified": 0, "confirmations": 0},
        #           {"game": {...}, "confidence": 0.7, "verified": 0, "confirmations": 0}
        #       ],
        #       "collapsed": False,
        #       "created_at": "ISO timestamp",
        #       "last_search": "ISO timestamp"
        #   }
        # }
        self.quantum_states: dict[str, dict[str, Any]] = {}

        # Game API
        self.game_lookup = GameLookup(config)

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
                self.logger.info(f"� Quantum cache chargé: {len(self.quantum_states)} états quantiques")
            else:
                self.logger.info("� Nouveau quantum cache créé")

        except Exception as e:
            self.logger.error(f"Erreur chargement quantum cache: {e}")
            self.quantum_states = {}

    def _save_cache(self):
        """Sauvegarder le cache quantique."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.quantum_states, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Erreur sauvegarde quantum cache: {e}")

    async def search_quantum_game(
        self, query: str, observer: str = "user"
    ) -> list[dict[str, Any]]:
        """
        🔬 Recherche quantique avec superposition

        Returns list of superposition states (1-2-3):
        [
            {
                "index": 1,
                "game": {...GameResult...},
                "confidence": 0.9,
                "verified": 0,
                "confirmations": 0,
                "collapsed": False
            },
            ...
        ]
        """
        cache_key = f"game:{query.lower().strip()}"

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
                    "game": sup.get("game"),
                    "confidence": sup.get("confidence", 0.5),
                    "verified": sup.get("verified", 0),
                    "confirmations": sup.get("confirmations", 0),
                    "collapsed": quantum_state.get("collapsed", False)
                })

            self.logger.info(f"🎯 Quantum state trouvé: {query} ({len(result)} superpositions)")
            return result

        # Create new quantum superposition
        return await self._create_quantum_superposition(query, observer)

    async def _create_quantum_superposition(
        self, query: str, observer: str
    ) -> list[dict[str, Any]]:
        """Crée une nouvelle superposition quantique."""
        cache_key = f"game:{query.lower().strip()}"

        try:
            # Search via API
            primary_result = await self.game_lookup.search_game(query)

            if not primary_result:
                self.logger.warning(f"❌ Aucun résultat pour: {query}")
                return []

            # Calculate quantum confidence
            confidence = self._calculate_confidence(primary_result, query)

            # Create quantum state with single superposition (for now)
            quantum_state = {
                "superpositions": [
                    {
                        "game": {
                            "name": primary_result.name,
                            "year": primary_result.year,
                            "rating_rawg": primary_result.rating_rawg,
                            "metacritic": primary_result.metacritic,
                            "platforms": (primary_result.platforms or [])[:3],
                            "genres": (primary_result.genres or [])[:2],
                            "source_count": primary_result.source_count,
                            "api_sources": primary_result.api_sources or [],
                        },
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

            self.logger.info(f"⚛️ Superposition créée: {query} → {primary_result.name} (conf: {confidence:.2f})")

            # Return formatted result
            return [{
                "index": 1,
                "game": quantum_state["superpositions"][0]["game"],
                "confidence": confidence,
                "verified": 0,
                "confirmations": 0,
                "collapsed": False
            }]

        except Exception as e:
            self.logger.error(f"Erreur création superposition {query}: {e}")
            return []

    def _calculate_confidence(self, game_result: GameResult, query: str) -> float:
        """Calcule la confiance quantique."""
        confidence = 0.3

        # Multiple API sources boost
        if hasattr(game_result, "source_count") and game_result.source_count >= 2:
            confidence += 0.3

        # Name match boost
        query_lower = query.lower().strip()
        name_lower = game_result.name.lower().strip()
        if query_lower == name_lower:
            confidence += 0.3
        elif query_lower in name_lower or name_lower in query_lower:
            confidence += 0.2

        # Quality indicators
        if hasattr(game_result, "metacritic") and game_result.metacritic:
            confidence += 0.1
        if hasattr(game_result, "rating_rawg") and game_result.rating_rawg > 0:
            confidence += 0.1

        return min(confidence, 0.95)

    def collapse_game(self, query: str, observer: str, state_index: int = 1) -> dict[str, Any] | None:
        """
        💥 Collapse quantum state (Mod anchors truth)

        Args:
            query: Game name
            observer: Username (mod/admin)
            state_index: Superposition index (1-2-3)

        Returns:
            Collapsed game data or None if failed
        """
        cache_key = f"game:{query.lower().strip()}"

        if cache_key not in self.quantum_states:
            self.logger.warning(f"❌ État quantique inexistant: {query}")
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
            f"💥 Collapse quantique: {query} par {observer} → {selected['game']['name']} "
            f"(confirmations: {selected['confirmations']})"
        )

        return selected["game"]

    def get_quantum_stats(self) -> dict[str, Any]:
        """
        📊 Stats système quantique (pour !quantum command)

        Returns:
            {
                "total_games": int,
                "superpositions_active": int,
                "collapsed_states": int,
                "verified_percentage": float,
                "total_confirmations": int
            }
        """
        total_games = len(self.quantum_states)
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

        verified_pct = (collapsed_states / total_games * 100) if total_games > 0 else 0.0

        return {
            "total_games": total_games,
            "superpositions_active": superpositions_active,
            "collapsed_states": collapsed_states,
            "verified_percentage": verified_pct,
            "total_confirmations": total_confirmations
        }

    def cleanup_expired(self) -> int:
        """
        💨 Décohérence quantique (cleanup expired states)

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
            self.logger.info(f"💨 Décohérence: {len(expired_keys)} états évaporés")

        return len(expired_keys)

    # ============================================================
    # BaseCacheInterface Implementation
    # ============================================================

    def get(self, game_query: str) -> dict[Any, Any] | None:
        """Get collapsed/verified game (interface compatibility)."""
        cache_key = f"game:{game_query.lower().strip()}"

        if cache_key in self.quantum_states:
            quantum_state = self.quantum_states[cache_key]

            # Return first (collapsed) superposition if exists
            superpositions = quantum_state.get("superpositions", [])
            if superpositions:
                return superpositions[0].get("game")

        return None

    def set(self, key: str, value: dict[str, Any], **kwargs) -> bool:
        """Set game in cache (interface compatibility)."""
        try:
            cache_key = f"game:{key.lower().strip()}"
            confidence = kwargs.get("confidence", 0.8)
            observer = kwargs.get("observer", "system")
            verified = 1 if kwargs.get("verified", False) else 0

            quantum_state = {
                "superpositions": [
                    {
                        "game": value,
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

            self.logger.info(f"💾 Quantum set: {key} (verified: {verified})")
            return True

        except Exception as e:
            self.logger.error(f"❌ Erreur quantum set: {e}")
            return False

    async def search(self, query: str, **kwargs) -> dict[str, Any] | None:
        """Search game (interface compatibility - returns first result)."""
        results = await self.search_quantum_game(query, kwargs.get("observer", "user"))
        if results:
            return results[0].get("game")
        return None

    def get_stats(self) -> CacheStats:
        """Get stats (interface compatibility)."""
        quantum_stats = self.get_quantum_stats()

        return CacheStats(
            total_keys=quantum_stats["total_games"],
            confirmed_keys=quantum_stats["collapsed_states"],
            cache_hits=0,
            cache_misses=0,
            hit_rate=0.0,
            total_size_mb=0.0,
            avg_confidence=quantum_stats["verified_percentage"] / 100.0,
            quantum_enabled=True,
        )

    def clear(self) -> bool:
        """Clear all quantum states (interface compatibility)."""
        try:
            count = len(self.quantum_states)
            self.quantum_states = {}
            self._save_cache()
            self.logger.info(f"🗑️ Quantum cache vidé: {count} états")
            return True
        except Exception as e:
            self.logger.error(f"❌ Erreur clear quantum: {e}")
            return False

    async def close(self):
        """Cleanup on shutdown."""
        if hasattr(self, "game_lookup"):
            await self.game_lookup.close()


# Legacy methods for backwards compatibility (not needed but kept for safety)

    def clear_expired(self):
        """Legacy: nettoyer les entrées expirées."""
        return self.cleanup_expired()

    def clear_game(self, game_query: str) -> bool:
        """Supprimer un jeu spécifique du cache."""
        cache_key = f"game:{game_query.lower().strip()}"

        if cache_key in self.quantum_states:
            del self.quantum_states[cache_key]
            self._save_cache()
            self.logger.info(f"🗑️ Quantum state supprimé: {game_query}")
            return True

        self.logger.warning(f"🤷 État quantique non trouvé: {game_query}")
        return False

    def clear_all(self):
        """Vider complètement le cache."""
        self.clear()
