"""SerdaBot V1 - Game Lookup API multi-sources (RAWG + Steam + Scraping) - Architecture KISS."""

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

import httpx

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

# Import optionnel de CacheManager
CacheManager: Optional[Any] = None
try:
    from core.cache import CacheManager as _CacheManager
    CacheManager = _CacheManager
except ImportError:
    # Silencieux - CacheManager optionnel
    pass

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
    is_early_access: bool = False  # 🚧 Détecté via Steam genres ou scraping HTML
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
        
        # ⏱️ Timeout depuis config (APIs externes peuvent être lentes)
        apis_config = config.get("apis", {})
        api_timeout = apis_config.get("timeout", 10.0)
        self.http_client = httpx.AsyncClient(timeout=api_timeout)
        
        # Initialiser le cache si disponible
        if CacheManager is not None:
            self.cache = CacheManager(config)
        else:
            self.cache = None
            self.logger.warning("CacheManager non disponible - cache désactivé")

        # Configuration APIs
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

                # 🌐 ENRICHISSEMENT STEAM STORE HTML (Fallback ultime pour dates EA)
                # Scraper uniquement si on a des données Steam (sinon pas sur Steam)
                if steam_dict and steam_dict.get("app_id"):
                    app_id = steam_dict.get("app_id")
                    scrape_data = await self._scrape_steam_store(app_id)
                    
                    if scrape_data:
                        # Enrichir année si scrape plus récente (correction EA → 1.0)
                        scrape_year = scrape_data.get("year")
                        if scrape_year and result.year.isdigit() and scrape_year > result.year:
                            old_year = result.year
                            result.year = scrape_year
                            self.logger.info(f"🌐 Steam scrape: année {old_year} → {result.year}")
                        
                        # Enrichir Early Access si pas détecté par API genres
                        if scrape_data.get("is_early_access") and not result.is_early_access:
                            result.is_early_access = True
                            self.logger.info(f"🌐 Steam scrape: Early Access détecté via HTML")

                # �🎯 Détection faute de frappe simplifiée (écart input/output)
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

    async def enrich_game_from_igdb_name(self, igdb_name: str) -> GameResult | None:
        """
        Enrichit un jeu depuis son nom IGDB (catégorie Twitch = source fiable).

        Différence vs search_game():
        - search_game(): Input user incertain → fuzzy search
        - enrich_from_igdb: Input IGDB fiable → priorité match exact

        Flow:
        1. Check cache avec nom IGDB exact
        2. Enrichir avec RAWG+Steam (match exact prioritaire)
        3. Sauvegarder en cache avec metadata 'igdb_verified=True'
        4. Return GameResult enrichi
        """
        if not igdb_name or not igdb_name.strip():
            self.logger.warning("❌ Nom IGDB vide")
            return None

        igdb_name = igdb_name.strip()
        cache_key = f"igdb:{igdb_name.lower()}"

        # 1. Check cache d'abord
        if self.cache is not None:
            cached = self.cache.get(cache_key)
            if cached:
                self.logger.info(f"✅ Cache hit (IGDB): {igdb_name}")
                return cached

        try:
            # 2. Enrichissement RAWG + Steam (parallèle)
            rawg_task = self._fetch_rawg(igdb_name)
            steam_task = self._fetch_steam(igdb_name)

            results = await asyncio.gather(rawg_task, steam_task, return_exceptions=True)

            # Process results
            def process_result(data: Any, api: str) -> dict | None:
                if isinstance(data, Exception):
                    self.logger.warning(f"{api} error: {data}")
                    return None
                return data if isinstance(data, dict) else None

            rawg_dict = process_result(results[0], "RAWG")
            steam_dict = process_result(results[1], "Steam")

            # 3. Build GameResult
            if rawg_dict is not None or steam_dict is not None:
                result = self._merge_data(rawg_dict, steam_dict, igdb_name)
            else:
                # Si aucun enrichissement, créer un résultat minimal IGDB-only
                result = GameResult(
                    name=igdb_name,
                    confidence="IGDB_ONLY",
                    primary_source="IGDB",
                    api_sources=["IGDB"]
                )

            if result:
                # Override avec nom IGDB original (pas le nom RAWG/Steam)
                result.name = igdb_name

                # Calculer fiabilité
                result.reliability_score = self._calculate_reliability(result, igdb_name)
                result.confidence = "IGDB_VERIFIED"  # Flag spécial pour sources IGDB
                result.primary_source = "IGDB+RAWG" if rawg_dict else "IGDB"

                # Pas de flag typo (source IGDB = ground truth)
                result.possible_typo = False

                # 4. Cache avec metadata
                if self.cache is not None:
                    self.cache.set(cache_key, result)

                sources = "+".join(result.api_sources) if result.api_sources else result.primary_source
                self.logger.info(f"✅ IGDB enrichi: {result.name} [{sources}] - {result.confidence}")
                return result

            self.logger.warning(f"❌ Échec enrichissement IGDB: {igdb_name}")
            return None

        except Exception as e:
            self.logger.error(f"Erreur enrichissement IGDB {igdb_name}: {e}")
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

            # 🎯 Récupérer developers/publishers via /games/{id} (pas dans search)
            game_id = best_game.get("id")
            developers = []
            publishers = []
            
            if game_id:
                try:
                    details_response = await self.http_client.get(
                        f"https://api.rawg.io/api/games/{game_id}",
                        params={"key": self.rawg_key}
                    )
                    details_response.raise_for_status()
                    details = details_response.json()
                    
                    developers = [dev.get("name", "") for dev in details.get("developers", [])]
                    publishers = [pub.get("name", "") for pub in details.get("publishers", [])]
                except Exception as e:
                    self.logger.debug(f"RAWG details fetch failed for {game_id}: {e}")

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
                "developers": developers,
                "publishers": publishers,
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

            # 🎯 KISS Enhancement: Récupérer description Steam (FR puis EN en fallback)
            steam_description = None
            is_early_access = False
            steam_metacritic = None  # 🏆 Metacritic depuis appdetails
            app_id = game.get("id")
            if app_id:
                # Essayer français d'abord
                try:
                    details_params = {"appids": app_id, "l": "french", "cc": "fr"}
                    details_response = await self.http_client.get(
                        "https://store.steampowered.com/api/appdetails", params=details_params
                    )
                    details_data = details_response.json()
                    game_details = details_data.get(str(app_id), {}).get("data", {})
                    steam_description = game_details.get("short_description", "")
                    
                    # 🏆 Récupérer Metacritic score (int)
                    metacritic_data = game_details.get("metacritic", {})
                    if metacritic_data and isinstance(metacritic_data, dict):
                        score = metacritic_data.get("score")
                        if score is not None:
                            try:
                                steam_metacritic = int(score)
                            except (ValueError, TypeError):
                                steam_metacritic = None
                    
                    # 🚧 Détecter Early Access via genres Steam (FR ou EN)
                    genres = game_details.get("genres", [])
                    is_early_access = any(
                        genre.get("description", "").lower() in ["early access", "accès anticipé"]
                        for genre in genres
                    )
                    
                    # Fallback anglais si description FR vide
                    if not steam_description or len(steam_description.strip()) < 10:
                        self.logger.debug(f"Steam FR description empty/short, trying EN for app {app_id}")
                        details_params_en = {"appids": app_id, "l": "english", "cc": "us"}
                        details_response_en = await self.http_client.get(
                            "https://store.steampowered.com/api/appdetails", params=details_params_en
                        )
                        details_data_en = details_response_en.json()
                        game_details_en = details_data_en.get(str(app_id), {}).get("data", {})
                        steam_description_en = game_details_en.get("short_description", "")
                        if steam_description_en:
                            steam_description = steam_description_en
                            self.logger.debug(f"✅ Using Steam EN description for {game.get('name')}")
                    else:
                        self.logger.debug(f"✅ Using Steam FR description for {game.get('name')}")
                        
                except Exception as e:
                    self.logger.debug(f"Steam details fetch failed: {e}")

            return {
                "name": game.get("name", ""),
                "metacritic": steam_metacritic,  # 🏆 Int depuis appdetails
                "platforms": platforms,
                # 🇫🇷 Description en français de Steam !
                "description": steam_description,
                "description_raw": steam_description,
                "is_early_access": is_early_access,  # 🚧 Flag Early Access
                "app_id": app_id,  # 🌐 Pour le scraping HTML ultérieur
                "source": "steam",
            }

        except Exception as e:
            self.logger.error(f"Steam API error: {e}")
            return None

    async def _scrape_steam_store(self, app_id: int) -> dict | None:
        """
        🌐 SCRAPING STEAM STORE HTML (Enrichissement ultime)
        
        Récupère des infos additionnelles depuis la page Steam Store HTML :
        - Date de release exacte (1.0 ou EA)
        - Détection Early Access via bannière HTML
        
        Args:
            app_id: Steam App ID du jeu
        
        Note: Utilisé en dernier recours pour corriger les dates EA → 1.0
        """
        if not HAS_BS4:
            return None
            
        try:
            # Scraper la page HTML directement avec app_id
            url = f"https://store.steampowered.com/app/{app_id}/"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "en-US,en;q=0.9"
            }
            
            response = await self.http_client.get(url, headers=headers, params={"l": "english"})
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "lxml")
            
            # Extraire date de release
            release_year = None
            release_date_elem = soup.find("div", class_="release_date")
            if release_date_elem:
                date_text = release_date_elem.get_text(strip=True)
                # Extraire année depuis "Release Date:20 Jun, 2024"
                year_match = re.search(r'\d{4}', date_text)
                if year_match:
                    release_year = year_match.group(0)
            
            # Détecter Early Access via bannières HTML
            early_access_header = soup.find("div", class_="early_access_header")
            game_area_ea = soup.find("div", class_="game_area_early_access")
            is_early_access = bool(early_access_header or game_area_ea)
            
            self.logger.debug(
                f"🌐 Steam scrape (app {app_id}): year={release_year}, EA={is_early_access}"
            )
            
            return {
                "year": release_year,
                "is_early_access": is_early_access,
                "source": "steam_scrape"
            }
            
        except Exception as e:
            self.logger.debug(f"Steam Store scrape failed for app {app_id}: {e}")
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
        # Priorité : Steam (FR → EN si vide) > RAWG (EN)
        summary = None
        description_raw = None

        if steam_data and steam_data.get("description"):
            # Steam a une description (FR ou EN en fallback) - priorité !
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
            # 🇫🇷 Descriptions fusionnées avec priorité français !
            summary=summary,
            description_raw=description_raw,
            genres=data.get("genres", []),  # 🎯 FIX: Assigner les genres !
            developers=data.get("developers", []),  # 🎨 Developers depuis RAWG
            publishers=data.get("publishers", []),  # 📦 Publishers depuis RAWG
            is_early_access=steam_data.get("is_early_access", False) if steam_data else False,  # 🚧 EA depuis Steam
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

    def format_result(self, result: GameResult, compact: bool = False) -> str:
        """Formate le résultat pour affichage Twitch.
        
        Args:
            result: Résultat du jeu à formater
            compact: Si True, format ultra-compact pour !gc (sans confidence/sources)
        """
        output = f"🎮 {result.name}"
        
        # Early Access flag
        if result.is_early_access:
            output += " 🚧"
        
        if result.year != "?":
            output += f" ({result.year})"
        
        # Développeurs/Éditeurs (prioritaire)
        if result.developers:
            dev_names = ', '.join(result.developers[:2])
            output += f" - Dev: {dev_names}"
        if result.publishers:
            pub_names = ', '.join(result.publishers[:2])
            output += f" - Pub: {pub_names}"
        
        # Notes et plateformes (tout normalisé sur /5)
        if result.metacritic:
            # Convertir Metacritic /100 → /5
            rating_normalized = result.metacritic / 20.0
            output += f" - ⭐ {rating_normalized:.1f}/5"
        elif result.rating_rawg > 0:
            output += f" - ⭐ {result.rating_rawg:.1f}/5"
        if result.platforms:
            output += f" - 🕹️ {', '.join(result.platforms[:3])}"
        
        # Description (summary) si disponible - SEULEMENT en mode non-compact
        if not compact and result.summary:
            # Limiter à 150 caractères pour Twitch
            summary_short = result.summary[:150].strip()
            if len(result.summary) > 150:
                summary_short += "..."
            output += f" | {summary_short}"
        
        # Version compacte : pas de confidence/sources
        if compact:
            return output
        
        # Version complète : ajouter confidence + sources
        icon = (
            "🔥" if result.confidence == "HIGH" else "✅" if result.confidence == "MEDIUM" else "⚠️"
        )
        return f"{output} - {icon} {result.confidence} ({result.source_count} sources)"

    async def close(self):
        """Nettoyage à la fermeture."""
        await self.http_client.aclose()
