#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Steam Provider

Recherche et enrichissement de jeux via Steam Store API.
"""

import logging
import re
from typing import List, Optional
import httpx

from modules.integrations.game_engine.providers.base import GameProvider, GameResult

logger = logging.getLogger(__name__)


class SteamProvider(GameProvider):
    """Provider pour Steam Store API."""
    
    def __init__(self, http_client: httpx.AsyncClient, api_key: Optional[str] = None):
        """
        Initialise le provider Steam.
        
        Args:
            http_client: Client HTTP partagé
            api_key: Clé API Steam (optionnelle, pas utilisée pour store search)
        """
        self.http_client = http_client
        self.api_key = api_key
    
    @property
    def name(self) -> str:
        return "steam"
    
    @property
    def weight(self) -> float:
        """Steam = 40% (très fiable pour PC games)."""
        return 0.40
    
    def is_available(self) -> bool:
        """Steam store search ne nécessite pas de clé API."""
        return True
    
    async def search(self, query: str, limit: int = 20) -> List[dict]:
        """
        Recherche de candidats dans Steam Store.
        
        Args:
            query: Requête de recherche
            limit: Nombre max de résultats
        
        Returns:
            Liste de dicts avec name, source, api_data
        """
        try:
            resp = await self.http_client.get(
                "https://store.steampowered.com/api/storesearch/",
                params={"term": query, "l": "french", "cc": "FR"}
            )
            
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                candidates = [{
                    "name": item.get("name", ""),
                    "id": str(item.get("id", "")),
                    "year": self._extract_year_from_item(item),
                    "api_data": item,
                    "source": "steam"
                } for item in items[:limit]]
                
                logger.debug(f"Steam returned {len(candidates)} candidates for '{query}'")
                return candidates
        
        except Exception as e:
            logger.warning(f"Steam search failed for '{query}': {e}")
        
        return []
    
    async def enrich(self, app_id: str) -> Optional[GameResult]:
        """
        Enrichissement depuis App ID Steam.
        
        Args:
            app_id: Steam App ID
        
        Returns:
            GameResult avec métadonnées complètes
        """
        try:
            # Fetch detailed info from appdetails
            details_resp = await self.http_client.get(
                "https://store.steampowered.com/api/appdetails",
                params={"appids": app_id, "l": "french", "cc": "fr"}
            )
            
            if details_resp.status_code != 200:
                return None
            
            details_data = details_resp.json()
            game_details = details_data.get(str(app_id), {}).get("data", {})
            
            if not game_details:
                return None
            
            return self._parse_steam_details(game_details, app_id)
        
        except Exception as e:
            logger.error(f"Steam enrich error (app_id={app_id}): {e}")
            return None
    
    async def enrich_by_name(self, game_name: str, language: str = "french") -> Optional[GameResult]:
        """
        Enrichissement depuis nom de jeu.
        
        Args:
            game_name: Nom exact du jeu
            language: Langue ("french" ou "english")
        
        Returns:
            GameResult avec métadonnées Steam
        """
        try:
            # Search Steam Store
            lang_code = "french" if language == "french" else "english"
            country_code = "FR" if language == "french" else "US"
            
            search_resp = await self.http_client.get(
                "https://store.steampowered.com/api/storesearch/",
                params={"term": game_name, "l": lang_code, "cc": country_code}
            )
            
            if search_resp.status_code != 200:
                return None
            
            items = search_resp.json().get("items", [])
            if not items:
                return None
            
            # Find best match (prefer exact title)
            game = self._find_best_match(items, game_name)
            app_id = game.get("id")
            
            if not app_id:
                return None
            
            # Fetch detailed info
            details_resp = await self.http_client.get(
                "https://store.steampowered.com/api/appdetails",
                params={"appids": app_id, "l": lang_code, "cc": country_code.lower()}
            )
            
            if details_resp.status_code != 200:
                return None
            
            details_data = details_resp.json()
            game_details = details_data.get(str(app_id), {}).get("data", {})
            
            if not game_details:
                return None
            
            # Fallback to English if French description too short
            summary = game_details.get("short_description", "")
            if language == "french" and (not summary or len(summary.strip()) < 10):
                logger.debug(f"Steam FR description too short, trying EN for {game_name}")
                details_resp_en = await self.http_client.get(
                    "https://store.steampowered.com/api/appdetails",
                    params={"appids": app_id, "l": "english", "cc": "us"}
                )
                if details_resp_en.status_code == 200:
                    details_data_en = details_resp_en.json()
                    game_details_en = details_data_en.get(str(app_id), {}).get("data", {})
                    summary_en = game_details_en.get("short_description", "")
                    if summary_en:
                        game_details["short_description"] = summary_en
                        logger.debug(f"Using Steam EN description for {game_name}")
            
            return self._parse_steam_details(game_details, app_id)
        
        except Exception as e:
            logger.error(f"Steam enrich_by_name error for '{game_name}': {e}")
            return None
    
    def _find_best_match(self, items: List[dict], game_name: str) -> dict:
        """Trouve le meilleur match parmi les résultats (exact > first)."""
        game_name_lower = game_name.lower().strip()
        
        # Exact match
        for item in items[:5]:
            item_name = item.get("name", "").lower().strip()
            if item_name == game_name_lower:
                logger.debug(f"Steam exact match: {item.get('name')}")
                return item
        
        # Fallback: first result
        logger.debug(f"Steam: No exact match, using first result: {items[0].get('name')}")
        return items[0]
    
    def _parse_steam_details(self, game_details: dict, app_id: str) -> GameResult:
        """Parse Steam appdetails response vers GameResult."""
        
        # Extract platforms
        platforms = []
        for platform, available in game_details.get("platforms", {}).items():
            if available:
                platforms.append(platform.capitalize())
        
        # Extract metacritic
        metacritic = None
        metacritic_data = game_details.get("metacritic", {})
        if isinstance(metacritic_data, dict):
            score = metacritic_data.get("score")
            if score is not None:
                try:
                    metacritic = int(score)
                except (ValueError, TypeError):
                    pass
        
        # Extract genres
        genres = game_details.get("genres", [])
        genre_names = [g.get("description", "") for g in genres[:3]]
        
        # Extract release year
        release_info = game_details.get("release_date", {})
        release_date = release_info.get("date", "")
        year = "?"
        if release_date:
            year_match = re.search(r'\b(19|20)\d{2}\b', release_date)
            if year_match:
                year = year_match.group(0)
        
        # Extract developers/publishers
        developers = game_details.get("developers", [])[:2]
        publishers = game_details.get("publishers", [])[:2]
        
        # Summary
        summary = game_details.get("short_description", "")
        summary = summary[:500] if summary else None
        
        return GameResult(
            name=game_details.get("name", "Unknown"),
            year=year,
            metacritic=metacritic,
            platforms=platforms[:3],
            genres=genre_names,
            developers=developers,
            publishers=publishers,
            summary=summary,
            reliability_score=0.95,
            confidence="STEAM_VERIFIED",
            source_count=1,
            primary_source="steam",
            api_sources=["steam"]
        )
    
    def _extract_year_from_item(self, item: dict) -> str:
        """Extrait l'année depuis un item de recherche Steam (si disponible)."""
        # Steam search ne retourne pas toujours l'année, fallback à "?"
        return "?"
