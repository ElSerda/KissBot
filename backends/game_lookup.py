"""SerdaBot V1 - Game Lookup API multi-sources (RAWG + Steam) - Architecture KISS."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import httpx

try:
    from core.cache import CacheManager
except ImportError:
    # Silencieux - CacheManager optionnel
    CacheManager = None  # type: ignore

# Plateformes principales (PC + Consoles, pas mobile/web)
PC_CONSOLE_PLATFORMS = "4,18,1,7,19,14,15,16,17"  # PC, PS, Xbox, Nintendo


@dataclass
class GameResult:
    """Résultat de jeu avec validation de fiabilité et données enrichies."""

    name: str
    year: str = "?"
    rating_rawg: float = 0.0
    ratings_count: int = 0
    metacritic: int | None = None
    steam_reviews: str | None = None
    platforms: list[str] | None = None
    genres: list[str] | None = None
    developers: list[str] | None = None
    publishers: list[str] | None = None
    playtime: int = 0
    popularity: int = 0  # "added" count
    esrb_rating: str = ""
    # 🎮 KISS Enhancement: Summary pour enrichissement LLM contexte
    summary: str | None = None  # Description courte du jeu (RAWG API)
    description_raw: str | None = None  # Description complète si nécessaire
    reliability_score: float = 0.0
    confidence: str = "LOW"
    source_count: int = 1
    primary_source: str = "unknown"  # API principale (rawg/steam/itch.io)
    api_sources: list[str] | None = None  # Liste de toutes les APIs ayant contribué
    possible_typo: bool = False  # Flag si input user ≠ output RAWG (faute de frappe possible)

    def __post_init__(self):
        if self.platforms is None:
            self.platforms = []
        if self.genres is None:
            self.genres = []
        if self.developers is None:
            self.developers = []
        if self.publishers is None:
            self.publishers = []
        if self.api_sources is None:
            self.api_sources = []


class GameLookup:
    """Gestionnaire principal des recherches de jeux multi-API."""

    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.http_client = httpx.AsyncClient(timeout=10.0)
        # Initialiser le cache si disponible
        if CacheManager is not None:
            self.cache = CacheManager(config)
        else:
            self.cache = None
            self.logger.warning("CacheManager non disponible - cache désactivé")

        # Configuration APIs
        apis_config = config.get("apis", {})
        self.rawg_key = apis_config.get("rawg_key")
        self.steam_key = apis_config.get("steam_key")  # Optionnel

        if not self.rawg_key:
            raise ValueError("RAWG API key manquante dans config")

    async def search_game(self, game_name: str) -> GameResult | None:
        """Point d'entrée principal pour recherche de jeu."""
        # Validation input
        if not game_name or not game_name.strip():
            self.logger.warning("❌ Nom de jeu vide ou invalide")
            return None

        game_name = game_name.strip()

        # Vérifier cache
        if self.cache is not None:
            cached = self.cache.get(f"game:{game_name.lower()}")
            if cached:
                return cached

        try:
            # Recherche parallèle RAWG + Steam
            # Note: RAWG agrège déjà itch.io, Epic, GOG → 99%+ couverture
            rawg_task = self._fetch_rawg(game_name)
            steam_task = self._fetch_steam(game_name)

            # asyncio.gather avec return_exceptions peut retourner Exception ou les vrais résultats
            results = await asyncio.gather(rawg_task, steam_task, return_exceptions=True)

            # Helper pour traiter les résultats API (Exception ou Dict)
            def process_api_result(data: Any, api_name: str) -> dict[str, Any] | None:
                if isinstance(data, Exception):
                    self.logger.warning(f"{api_name} error: {data}")
                    return None
                elif isinstance(data, dict):
                    return data
                return None

            # Traiter les résultats en une ligne chacun
            rawg_dict = process_api_result(results[0], "RAWG")
            steam_dict = process_api_result(results[1], "Steam")

            # Fusionner les données
            # S'assurer que les données sont des dicts valides
            if rawg_dict is not None or steam_dict is not None:
                result = self._merge_data(rawg_dict, steam_dict, game_name)
            else:
                result = None

            if result:
                # Calculer fiabilité
                result.reliability_score = self._calculate_reliability(result, game_name)
                result.confidence = self._get_confidence_level(result.reliability_score)

                # 🎯 Détection faute de frappe simplifiée (écart input/output)
                name_lower = result.name.lower()
                query_lower = game_name.lower()
                if query_lower not in name_lower and name_lower not in query_lower:
                    result.possible_typo = True
                    self.logger.warning(f"⚠️ Écart input/output: '{game_name}' → '{result.name}'")

                # Cache le résultat si disponible
                if self.cache is not None:
                    self.cache.set(f"game:{game_name.lower()}", result)

                sources_str = (
                    "+".join(result.api_sources) if result.api_sources else result.primary_source
                )
                typo_flag = " [TYPO?]" if result.possible_typo else ""
                self.logger.info(
                    f"✅ Jeu trouvé: {result.name} [{sources_str}] - {result.confidence}{typo_flag}"
                )
                return result

            self.logger.warning(f"❌ Aucun jeu trouvé pour: {game_name}")
            return None

        except Exception as e:
            self.logger.error(f"Erreur recherche {game_name}: {e}")
            return None

    async def _fetch_rawg(self, game_name: str) -> dict | None:
        """Récupère données depuis RAWG API."""
        try:
            params = {
                "key": self.rawg_key,
                "search": game_name,
                # "platforms": PC_CONSOLE_PLATFORMS,  # 🔍 TEST: Temporaire désactivé
                "page_size": 5,
            }

            response = await self.http_client.get("https://api.rawg.io/api/games", params=params)
            response.raise_for_status()

            games = response.json().get("results", [])
            if not games:
                return None

            best_game = self._find_best_game_lean(games, game_name)
            if not best_game:
                return None

            return {
                "name": best_game.get("name", ""),
                "released": best_game.get("released", ""),
                "tba": best_game.get("tba", False),
                "rating": best_game.get("rating", 0),
                "metacritic": best_game.get("metacritic"),
                "platforms": [
                    p.get("platform", {}).get("name", "") for p in best_game.get("platforms", [])
                ],
                # 🎮 KISS Enhancement: Récupérer genres et description pour contexte LLM
                "genres": [g.get("name", "") for g in best_game.get("genres", [])],
                "description": best_game.get("description", ""),  # Sera null dans search
                "description_raw": best_game.get("description_raw", ""),  # Sera null dans search
                "source": "rawg",
            }

        except Exception as e:
            self.logger.error(f"RAWG API error: {e}")
            return None

    async def _fetch_steam(self, game_name: str) -> dict | None:
        """Récupère données depuis Steam API."""
        try:
            params = {"term": game_name, "l": "french", "cc": "FR"}

            response = await self.http_client.get(
                "https://store.steampowered.com/api/storesearch/", params=params
            )
            response.raise_for_status()

            items = response.json().get("items", [])
            if not items:
                return None

            game = items[0]
            platforms = []
            for platform, available in game.get("platforms", {}).items():
                if available:
                    platforms.append(platform.capitalize())

            # 🎯 KISS Enhancement: Récupérer description française via Steam appdetails
            steam_description = None
            app_id = game.get("id")
            if app_id:
                try:
                    details_params = {"appids": app_id, "l": "french", "cc": "fr"}
                    details_response = await self.http_client.get(
                        "https://store.steampowered.com/api/appdetails", params=details_params
                    )
                    details_data = details_response.json()
                    game_details = details_data.get(str(app_id), {}).get("data", {})
                    steam_description = game_details.get("short_description", "")
                except Exception as e:
                    self.logger.debug(f"Steam details fetch failed: {e}")

            return {
                "name": game.get("name", ""),
                "metacritic": game.get("metascore"),
                "platforms": platforms,
                # 🇫🇷 Description en français de Steam !
                "description": steam_description,
                "description_raw": steam_description,
                "source": "steam",
            }

        except Exception as e:
            self.logger.error(f"Steam API error: {e}")
            return None

    def _find_best_game_lean(self, games: list[dict], query: str) -> dict | None:
        """Trouve le jeu le plus pertinent - Version LEAN simplifiée."""
        if not games:
            return None

        if len(games) == 1:
            return games[0]

        query_lower = query.lower()

        # 1. Chercher match exact d'abord
        for game in games:
            name = game.get("name", "").lower()
            if name == query_lower:
                return game

        # 2. Chercher inclusion (query dans nom ou nom dans query)
        for game in games:
            name = game.get("name", "").lower()
            if query_lower in name or name in query_lower:
                return game

        # 3. Fallback: le plus populaire (par "added" count)
        return max(games, key=lambda g: g.get("added", 0))

    def _merge_data(
        self, rawg_data: dict | None, steam_data: dict | None, query: str
    ) -> GameResult | None:
        """Fusionne les données RAWG + Steam - Version LEAN."""
        # Prioriser RAWG, fallback Steam
        data = rawg_data or steam_data
        if not data:
            return None

        # 🎯 FIX FUSION: Fusionner descriptions intelligemment
        # Priorité : Steam (français) > RAWG (anglais)
        summary = None
        description_raw = None

        if steam_data and steam_data.get("description"):
            # Steam a une description française - priorité !
            summary = steam_data.get("description", "").strip()[:300]
            description_raw = steam_data.get("description_raw", "").strip()[:500]
        elif rawg_data and rawg_data.get("description"):
            # Fallback RAWG anglais
            summary = rawg_data.get("description", "").strip()[:300]
            description_raw = rawg_data.get("description_raw", "").strip()[:500]

        # Créer résultat de base
        result = GameResult(
            name=data["name"],
            year=(
                self._extract_year(data.get("released", ""), data.get("tba", False))
                if rawg_data
                else "?"
            ),
            rating_rawg=data.get("rating", 0),
            metacritic=data.get("metacritic"),
            platforms=data.get("platforms", [])[:3],  # Max 3 plateformes
            # 🇫� Descriptions fusionnées avec priorité français !
            summary=summary,
            description_raw=description_raw,
            genres=data.get("genres", []),  # 🎯 FIX: Assigner les genres !
            source_count=1,
            primary_source="RAWG" if rawg_data else "Steam",
            api_sources=["RAWG"] if rawg_data else ["Steam"],
        )

        # Enrichir avec 2ème source si disponible
        if rawg_data and steam_data:
            result.source_count = 2
            result.api_sources = ["RAWG", "Steam"]
            if not result.metacritic:
                result.metacritic = steam_data.get("metacritic")

        return result

    def _extract_year(self, date_str: str, tba: bool = False) -> str:
        """Extrait l'année d'une date ISO."""
        if tba:
            return "TBA"
        if not date_str:
            return "?"
        try:
            year = date_str.split("-")[0]
            return year if year.isdigit() else "?"
        except Exception:
            return "?"

    def _validate_game_data(self, data: dict, query: str, source: str) -> bool:
        """Valide les données de jeu - Version LEAN simplifiée."""
        if not data or not isinstance(data, dict):
            return False

        # Check basique : nom présent
        name = data.get("name", "").strip()
        if not name:
            return False

        # Check scores dans les limites
        rating = data.get("rating", 0)
        if rating and isinstance(rating, (int, float)) and (rating < 0 or rating > 5):
            return False

        metacritic = data.get("metacritic")
        if (
            metacritic
            and isinstance(metacritic, (int, float))
            and (metacritic < 0 or metacritic > 100)
        ):
            return False

        return True

    def _calculate_reliability(self, result: GameResult, query: str) -> float:
        """Calcule le score de fiabilité - Version KISS avec boost précision."""
        score = 0.0

        # Base score selon sources/ratings
        if result.source_count >= 2:
            score = 80  # HIGH
        elif result.metacritic:
            score = 70  # MEDIUM-HIGH
        elif result.rating_rawg > 0:
            score = 50  # MEDIUM
        else:
            score = 30  # LOW

        # 🎯 KISS Fix: Boost score si query précise (2+ mots)
        word_count = len(query.split())
        if word_count >= 3:
            score += 20  # Bonus fort pour très précis
        elif word_count == 2:
            score += 10  # Bonus léger pour moyennement précis

        return min(score, 90)  # Cap à 90 pour éviter inflation

    def _get_confidence_level(self, score: float) -> str:
        """Détermine le niveau de confiance - Version LEAN simplifiée."""
        if score >= 70:
            return "HIGH"
        elif score >= 50:
            return "MEDIUM"
        else:
            return "LOW"

    def format_result(self, result: GameResult) -> str:
        """Formate le résultat pour affichage Twitch - Version LEAN."""
        output = f"🎮 {result.name}"
        if result.year != "?":
            output += f" ({result.year})"
        if result.metacritic:
            output += f" - 🏆 {result.metacritic}/100"
        elif result.rating_rawg > 0:
            output += f" - ⭐ {result.rating_rawg:.1f}/5"
        if result.platforms:
            output += f" - 🕹️ {', '.join(result.platforms[:3])}"
        icon = (
            "🔥" if result.confidence == "HIGH" else "✅" if result.confidence == "MEDIUM" else "⚠️"
        )
        return f"{output} - {icon} {result.confidence} ({result.source_count} sources)"

    async def close(self):
        """Nettoyage à la fermeture."""
        await self.http_client.aclose()
