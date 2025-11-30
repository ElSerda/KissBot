#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RAWG Provider

Recherche et enrichissement de jeux via RAWG API.
"""

import logging
from typing import List, Optional
import httpx

from modules.integrations.game_engine.providers.base import GameProvider, GameResult

logger = logging.getLogger(__name__)


class RAWGProvider(GameProvider):
    """Provider pour RAWG API."""
    
    def __init__(self, http_client: httpx.AsyncClient, api_key: str):
        """
        Initialise le provider RAWG.
        
        Args:
            http_client: Client HTTP partagé
            api_key: Clé API RAWG
        """
        self.http_client = http_client
        self.api_key = api_key
    
    @property
    def name(self) -> str:
        return "rawg"
    
    @property
    def weight(self) -> float:
        """RAWG = 25% (communauté, tendances)."""
        return 0.25
    
    def is_available(self) -> bool:
        """RAWG nécessite une clé API."""
        return bool(self.api_key)
    
    async def search(self, query: str, limit: int = 20) -> List[dict]:
        """
        Recherche de candidats dans RAWG.
        
        Args:
            query: Requête de recherche
            limit: Nombre max de résultats
        
        Returns:
            Liste de dicts avec name, id, year, source, api_data
        """
        try:
            resp = await self.http_client.get(
                "https://api.rawg.io/api/games",
                params={
                    "key": self.api_key,
                    "search": query,
                    "page_size": limit,
                    "platforms": "4,18,1,7,19,14,15,16,17"  # PC + consoles
                }
            )
            
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                candidates = []
                
                for game in results:
                    # Extract year from released date
                    released = game.get("released", "")
                    year = released[:4] if released and len(released) >= 4 else "?"
                    
                    candidates.append({
                        "name": game.get("name", ""),
                        "id": str(game.get("id", "")),
                        "year": year,
                        "api_data": game,
                        "source": "rawg"
                    })
                
                logger.debug(f"RAWG returned {len(candidates)} candidates for '{query}'")
                return candidates
        
        except Exception as e:
            logger.warning(f"RAWG search failed for '{query}': {e}")
        
        return []
    
    async def enrich(self, game_id: str) -> Optional[GameResult]:
        """
        Enrichissement depuis RAWG ID.
        
        Args:
            game_id: ID RAWG du jeu
        
        Returns:
            GameResult avec métadonnées complètes
        """
        try:
            resp = await self.http_client.get(
                f"https://api.rawg.io/api/games/{game_id}",
                params={"key": self.api_key}
            )
            
            if resp.status_code != 200:
                logger.warning(f"RAWG API error: {resp.status_code}")
                return None
            
            game = resp.json()
            return self._parse_rawg_game(game)
        
        except Exception as e:
            logger.error(f"RAWG enrich error (ID={game_id}): {e}")
            return None
    
    async def enrich_by_name(self, game_name: str) -> Optional[GameResult]:
        """
        Enrichissement depuis nom de jeu.
        
        Args:
            game_name: Nom du jeu
        
        Returns:
            GameResult avec métadonnées RAWG
        """
        try:
            # Search RAWG for exact match
            resp = await self.http_client.get(
                "https://api.rawg.io/api/games",
                params={
                    "key": self.api_key,
                    "search": game_name,
                    "page_size": 1,
                    "platforms": "4,18,1,7,19,14,15,16,17"
                }
            )
            
            if resp.status_code != 200:
                logger.warning(f"RAWG API error: {resp.status_code}")
                return None
            
            data = resp.json()
            results = data.get("results", [])
            
            if not results:
                logger.warning(f"RAWG: No metadata found for '{game_name}'")
                return None
            
            game = results[0]
            return self._parse_rawg_game(game)
        
        except Exception as e:
            logger.error(f"RAWG enrich_by_name error for '{game_name}': {e}", exc_info=True)
            return None
    
    def _parse_rawg_game(self, game: dict) -> GameResult:
        """Parse réponse RAWG vers GameResult."""
        
        # Extract year
        released = game.get("released", "")
        year = released[:4] if released and len(released) >= 4 else "?"
        
        # Extract platforms
        platforms = [p["platform"]["name"] for p in game.get("platforms", [])[:3]]
        
        # Extract genres
        genres = [g["name"] for g in game.get("genres", [])[:3]]
        
        # Extract companies
        developers = [d["name"] for d in game.get("developers", [])[:2]]
        publishers = [p["name"] for p in game.get("publishers", [])[:2]]
        
        # ESRB rating
        esrb_rating = ""
        esrb_data = game.get("esrb_rating")
        if esrb_data:
            esrb_rating = esrb_data.get("name", "")
        
        # Summary
        summary = game.get("description_raw", "")
        summary = summary[:500] if summary else None
        
        return GameResult(
            name=game.get("name", "Unknown"),
            year=year,
            rating_rawg=round(game.get("rating", 0.0), 1),
            ratings_count=game.get("ratings_count", 0),
            metacritic=game.get("metacritic"),
            platforms=platforms,
            genres=genres,
            developers=developers,
            publishers=publishers,
            playtime=game.get("playtime", 0),
            popularity=game.get("added", 0),
            esrb_rating=esrb_rating,
            summary=summary,
            reliability_score=0.90,
            confidence="RAWG_VERIFIED",
            source_count=1,
            primary_source="rawg",
            api_sources=["rawg"]
        )
