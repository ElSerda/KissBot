"""Game cache with quantum-inspired behavior. See: docs/api/quantum_game_cache.md"""

import time
from dataclasses import dataclass
from typing import Any

from backends.game_lookup import GameLookup, GameResult
from core.cache_interface import BaseCacheInterface, CacheStats
from core.quantum_cache import QuantumCache, QuantumState


@dataclass
class QuantumGameResult:
    """Game result with quantum properties → docs/api/quantum_game_cache.md#quantumgameresult"""

    game_result: GameResult
    quantum_confidence: float = 0.5
    user_confirmations: int = 0
    search_frequency: int = 1
    last_confirmed_by: str | None = None
    related_games: list[str] | None = None

    def __post_init__(self):
        if self.related_games is None:
            self.related_games = []


class QuantumGameCache(BaseCacheInterface):
    """Quantum game cache → docs/api/quantum_game_cache.md"""

    def __init__(self, config: dict, cache_file: str = "cache/quantum_games.json"):
        super().__init__(config)
        self.cache_file = cache_file

        self.quantum_cache = QuantumCache(config)

        self.game_lookup = GameLookup(config)

        game_config = config.get("quantum_games", {})
        self.auto_entangle_threshold = game_config.get("auto_entangle_threshold", 0.8)
        self.confirmation_boost = game_config.get("confirmation_confidence_boost", 0.3)
        self.max_suggestions = game_config.get("max_suggestions", 3)

        self.logger.info("🎮🔬 QuantumGameCache initialisé - Jeux quantiques actifs")

    async def search_quantum_game(
        self, query: str, observer: str = "user"
    ) -> dict[str, Any] | None:
        cache_key = f"game:{query.lower()}"

        existing_state = self.quantum_cache.get(cache_key, observer=observer)

        if existing_state and isinstance(existing_state, dict):
            result = existing_state.get("game_result")
            if result:
                self.logger.info(
                    f"🎯 Jeu quantique trouvé: {query} "
                    f"(vérifié: {existing_state.get('verified', 0)})"
                )
                return existing_state

        return await self._create_quantum_superposition(query, observer)

    async def _create_quantum_superposition(
        self, query: str, observer: str
    ) -> dict[str, Any] | None:
        """See docs/api/quantum_game_cache.md"""
        cache_key = f"game:{query.lower()}"

        try:
            primary_result = await self.game_lookup.search_game(query)

            if not primary_result:
                self.logger.warning(f"❌ Aucun résultat quantique pour: {query}")
                return None

            confidence = self._calculate_quantum_confidence(primary_result, query)

            quantum_game = {
                "game_result": {
                    "name": primary_result.name,
                    "year": primary_result.year,
                    "rating_rawg": primary_result.rating_rawg,
                    "metacritic": primary_result.metacritic,
                    "platforms": (primary_result.platforms or [])[:3],
                    "genres": (primary_result.genres or [])[:2],
                    "confidence": primary_result.confidence,
                    "source_count": primary_result.source_count,
                    "api_sources": primary_result.api_sources or [],
                },
                "quantum_confidence": confidence,
                "search_frequency": 1,
                "user_confirmations": 0,
                "created_by": observer,
                "verified": 0,
                "possible_typo": primary_result.possible_typo,
            }

            self.quantum_cache.set(
                key=cache_key,
                value=quantum_game,
                source=f"api:{'+'.join(primary_result.api_sources) if primary_result.api_sources else 'unknown'}",
                creator=observer,
                confidence=confidence,
            )

            await self._auto_entangle_similar_games(cache_key, primary_result)

            self.logger.info(
                f"⚛️ Superposition créée: {query} → {primary_result.name} "
                f"(confiance: {confidence:.2f})"
            )

            return quantum_game

        except Exception as e:
            self.logger.error(f"Erreur création superposition {query}: {e}")
            return None

    def _calculate_quantum_confidence(self, game_result: GameResult, query: str) -> float:
        """See docs/api/quantum_game_cache.md"""
        confidence = 0.3

        if hasattr(game_result, "source_count") and game_result.source_count >= 2:
            confidence += 0.3

        query_lower = query.lower().strip()
        name_lower = game_result.name.lower().strip()
        if query_lower == name_lower:
            confidence += 0.3
        elif query_lower in name_lower or name_lower in query_lower:
            confidence += 0.2

        if hasattr(game_result, "metacritic") and game_result.metacritic:
            confidence += 0.1
        if hasattr(game_result, "rating_rawg") and game_result.rating_rawg > 0:
            confidence += 0.1

        if hasattr(game_result, "possible_typo") and game_result.possible_typo:
            confidence *= 0.8

        return min(confidence, 0.9)

    async def _auto_entangle_similar_games(self, primary_key: str, game_result: GameResult) -> None:
        """See docs/api/quantum_game_cache.md"""
        if not hasattr(game_result, "genres") or not game_result.genres:
            return

        for existing_key in self.quantum_cache.quantum_states.keys():
            if existing_key.startswith("game:") and existing_key != primary_key:
                existing_states = self.quantum_cache.quantum_states[existing_key]

                for state in existing_states:
                    if not isinstance(state.data, dict):
                        continue

                    existing_game = state.data.get("game_result", {})
                    existing_genres = existing_game.get("genres", [])

                    common_genres = set(game_result.genres) & set(existing_genres)
                    if len(common_genres) >= 1:
                        self.quantum_cache.entangle(primary_key, existing_key)
                        self.logger.debug(
                            f"🔗 Auto-intrication: {primary_key} ↔ {existing_key} "
                            f"(genres: {list(common_genres)})"
                        )
                        break

    def confirm_game(self, query: str, observer: str, state_index: int = 0) -> bool:
        """See docs/api/quantum_game_cache.md"""
        cache_key = f"game:{query.lower()}"

        success = self.quantum_cache.collapse_state(
            key=cache_key, observer=observer, state_index=state_index
        )

        if success:
            collapsed_state = self.quantum_cache.get(cache_key, observer="system")
            if collapsed_state and isinstance(collapsed_state, dict):
                collapsed_state["user_confirmations"] = (
                    collapsed_state.get("user_confirmations", 0) + 1
                )
                collapsed_state["last_confirmed_by"] = observer
                collapsed_state["verified"] = 1

                self.logger.info(
                    f"💥 Jeu confirmé: {query} par {observer} "
                    f"→ État permanent (confirmations: {collapsed_state['user_confirmations']})"
                )

        return success

    def get_quantum_suggestions(self, query: str) -> list[dict[str, Any]]:
        """See docs/api/quantum_game_cache.md"""
        cache_key = f"game:{query.lower()}"
        states = self.quantum_cache.quantum_states.get(cache_key, [])

        suggestions = []
        for i, state in enumerate(states):
            if isinstance(state.data, dict):
                game_data = state.data.get("game_result", {})
                suggestions.append(
                    {
                        "index": i,
                        "name": game_data.get("name", "Unknown"),
                        "year": game_data.get("year", "?"),
                        "confidence": state.confidence,
                        "verified": state.verified,
                        "source": state.source,
                        "observer_count": state.observer_count,
                    }
                )

        suggestions.sort(key=lambda x: x["confidence"], reverse=True)
        return suggestions[: self.max_suggestions]

    def _generate_confidence_bar(self, confidence: float, width: int = 10) -> str:
        """Génère barre de progression visuelle pour confiance quantique."""
        filled = int(confidence * width)
        empty = width - filled
        return "█" * filled + "░" * empty

    def _get_quantum_status_symbol(self, verified: int, confidence: float) -> tuple[str, str]:
        """Retourne symbole et statut selon état quantique."""
        if verified == 1:
            return "🔒", "COLLAPSED"
        elif confidence >= 0.8:
            return "⚛️", "SUPERPOSITION"
        elif confidence >= 0.6:
            return "❓", "SUPERPOSITION"
        else:
            return "💫", "QUANTUM"

    def format_quantum_visual(self, quantum_game: dict[str, Any]) -> str:
        """Formate affichage visuel quantique magique."""
        game_data = quantum_game.get("game_result", {})
        name = game_data.get("name", "Unknown")
        confidence = quantum_game.get("quantum_confidence", 0.5)
        verified = quantum_game.get("verified", 0)

        symbol, status = self._get_quantum_status_symbol(verified, confidence)
        confidence_bar = self._generate_confidence_bar(confidence)
        confidence_value = f"{confidence:.1f}"

        return f"{symbol} {name} | {confidence_bar} {confidence_value} | {status}"

    def format_quantum_game_result(self, quantum_game: dict[str, Any]) -> str:
        """Formate un résultat quantique pour affichage Twitch."""
        game_data = quantum_game.get("game_result", {})
        name = game_data.get("name", "Unknown")
        year = game_data.get("year", "?")

        if quantum_game.get("verified") == 1:
            symbol = "🔒"
            status = "CONFIRMÉ"
        else:
            symbol = "⚛️"
            status = "SUGGESTION"

        details = []
        if game_data.get("metacritic"):
            details.append(f"🏆 {game_data['metacritic']}/100")
        elif game_data.get("rating_rawg", 0) > 0:
            details.append(f"⭐ {game_data['rating_rawg']:.1f}/5")

        if game_data.get("platforms"):
            platforms = ", ".join(game_data["platforms"][:2])
            details.append(f"🕹️ {platforms}")

        confidence = quantum_game.get("quantum_confidence", 0)
        conf_text = f"{confidence:.1f}"

        result = f"{symbol} {name}"
        if year != "?":
            result += f" ({year})"
        if details:
            result += f" - {' | '.join(details)}"
        result += f" - {status} ({conf_text})"

        if quantum_game.get("verified") != 1:
            result += " • !collapse pour confirmer"

        return result

    def format_quantum_dashboard(self, query: str | None = None) -> str:
        """Génère tableau de bord quantique visuel pour affichage."""
        lines = ["🔬 [SERDA_BOT]"]

        if query:
            cache_key = f"game:{query.lower()}"
            states = self.quantum_cache.quantum_states.get(cache_key, [])

            for state in states[:3]:
                if isinstance(state.data, dict):
                    visual = self.format_quantum_visual(state.data)
                    lines.append(visual)
        else:
            count = 0
            for key, states in self.quantum_cache.quantum_states.items():
                if count >= 5:
                    break

                if key.startswith("game:") and states:
                    state = states[0]
                    if isinstance(state.data, dict):
                        visual = self.format_quantum_visual(state.data)
                        lines.append(visual)
                        count += 1

        return "\n".join(lines)

    def get_quantum_game_stats(self) -> dict[str, Any]:
        """Statistiques du cache quantique des jeux."""
        base_stats = self.quantum_cache.get_quantum_stats()

        game_keys = [k for k in self.quantum_cache.quantum_states.keys() if k.startswith("game:")]
        confirmed_games = 0
        pending_games = 0

        for key in game_keys:
            states = self.quantum_cache.quantum_states[key]
            for state in states:
                if state.verified == 1:
                    confirmed_games += 1
                else:
                    pending_games += 1

        return {
            **base_stats,
            "game_keys": len(game_keys),
            "confirmed_games": confirmed_games,
            "pending_games": pending_games,
            "learning_rate": confirmed_games / max(len(game_keys), 1),
        }

    def get(self, key: str) -> dict[str, Any] | None:
        """Interface get() : recherche directe quantum."""
        quantum_key = f"game:{key.lower()}"

        if quantum_key in self.quantum_cache.quantum_states:
            states = self.quantum_cache.quantum_states[quantum_key]
            if states:
                verified_state = next((s for s in states if s.verified == 1), None)
                if verified_state:
                    return verified_state.data
                elif states:
                    return states[0].data

        return None

    def set(self, key: str, value: dict[str, Any], **kwargs) -> bool:
        """Interface set() : stockage quantum avec options."""
        quantum_key = f"game:{key.lower()}"

        confidence = kwargs.get("confidence", 0.8)
        observer = kwargs.get("observer", "system")
        confirmed = kwargs.get("confirmed", False)

        try:
            new_state = QuantumState(
                data=value,
                confidence=confidence,
                verified=1 if confirmed else 0,
                observer_count=1,
                timestamp=time.time(),
                created_by=observer,
            )

            if quantum_key not in self.quantum_cache.quantum_states:
                self.quantum_cache.quantum_states[quantum_key] = []

            self.quantum_cache.quantum_states[quantum_key].append(new_state)

            if confirmed:
                self.quantum_cache.collapse_state(quantum_key, observer)

            self.logger.info(f"💾 Quantum set: {key} (confirmed: {confirmed})")
            return True

        except Exception as e:
            self.logger.error(f"❌ Erreur quantum set: {e}")
            return False

    async def search(self, query: str, **kwargs) -> dict[str, Any] | None:
        """Interface search() : délègue vers search_quantum_game()."""
        observer = kwargs.get("observer", "user")
        return await self.search_quantum_game(query, observer)

    def get_stats(self) -> CacheStats:
        """Interface get_stats() : stats compatibles."""
        quantum_stats = self.get_quantum_game_stats()

        return CacheStats(
            total_keys=quantum_stats.get("game_keys", 0),
            confirmed_keys=quantum_stats.get("confirmed_games", 0),
            cache_hits=0,
            cache_misses=0,
            hit_rate=0.0,
            total_size_mb=0.0,
            avg_confidence=quantum_stats.get("learning_rate", 0.0),
            quantum_enabled=True,
        )

    def clear(self) -> bool:
        """Interface clear() : vide le cache quantum."""
        try:
            game_keys = [
                k for k in self.quantum_cache.quantum_states.keys() if k.startswith("game:")
            ]
            for key in game_keys:
                del self.quantum_cache.quantum_states[key]

            self.logger.info(f"🗑️ Quantum cache vidé: {len(game_keys)} jeux")
            return True
        except Exception as e:
            self.logger.error(f"❌ Erreur clear quantum: {e}")
            return False

    def cleanup_expired(self) -> int:
        """Interface cleanup_expired() : nettoyage quantum."""
        return self.quantum_cache.cleanup_expired()

    async def cleanup_quantum_games(self) -> int:
        """Nettoyage quantique spécialisé pour les jeux."""
        cleaned = self.quantum_cache.cleanup_expired()
        return cleaned

    async def learn_from_api_result(self, query: str, api_result: dict, observer: str) -> bool:
        """Apprentissage automatique à partir d'un résultat d'API."""
        if not api_result:
            return False
            
        try:
            # Créer une clé quantique normalisée
            quantum_key = f"game:{query.lower().strip()}"
            
            # Confiance élevée pour résultats API directs
            confidence = 0.9
            
            # Stocker avec métadonnées d'apprentissage
            enriched_result = {
                "game_result": api_result,
                "api_source": True,
                "learning_source": "api_direct",
                "original_query": query,
                "observer": observer
            }
            
            # Enregistrer dans le cache quantique
            self.quantum_cache.set(
                quantum_key, 
                enriched_result, 
                confidence=confidence,
                source="api_learning"
            )
            
            self.logger.info(f"📚 Apprentissage automatique: {query} → confiance {confidence}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur apprentissage automatique {query}: {e}")
            return False

    async def close(self):
        """Nettoyage à la fermeture."""
        if hasattr(self, "game_lookup"):
            await self.game_lookup.close()
