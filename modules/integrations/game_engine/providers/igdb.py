#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
IGDB Provider

Recherche et enrichissement de jeux via IGDB (Internet Game Database) API.
"""

import logging
import time
from datetime import datetime
from typing import List, Optional
import httpx

from modules.integrations.game_engine.providers.base import GameProvider, GameResult

logger = logging.getLogger(__name__)


class IGDBProvider(GameProvider):
    """Provider pour IGDB API (Twitch OAuth)."""
    
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        client_id: str,
        client_secret: str
    ):
        """
        Initialise le provider IGDB.
        
        Args:
            http_client: Client HTTP partagé
            client_id: Twitch Client ID
            client_secret: Twitch Client Secret
        """
        self.http_client = http_client
        self.client_id = client_id
        self.client_secret = client_secret
        
        # OAuth token cache
        self._token: Optional[str] = None
        self._token_expires: float = 0.0
    
    @property
    def name(self) -> str:
        return "igdb"
    
    @property
    def weight(self) -> float:
        """IGDB = 35% (métadonnées riches, canonical)."""
        return 0.35
    
    def is_available(self) -> bool:
        """IGDB nécessite Client ID + Secret."""
        return bool(self.client_id and self.client_secret)
    
    async def _get_token(self) -> Optional[str]:
        """
        Récupère OAuth token IGDB (cached, auto-refresh).
        
        Returns:
            Token OAuth ou None si erreur
        """
        # Check cache
        if self._token and time.time() < self._token_expires:
            return self._token
        
        # Fetch new token
        try:
            resp = await self.http_client.post(
                "https://id.twitch.tv/oauth2/token",
                params={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials"
                }
            )
            
            if resp.status_code == 200:
                data = resp.json()
                self._token = data.get("access_token")
                expires_in = data.get("expires_in", 5184000)  # 60 days default
                self._token_expires = time.time() + expires_in - 3600  # 1h margin
                logger.info(f"IGDB token obtained (expires in {expires_in}s)")
                return self._token
            else:
                logger.error(f"IGDB token fetch failed: {resp.status_code}")
                return None
        
        except Exception as e:
            logger.error(f"IGDB token error: {e}")
            return None
    
    async def search(self, query: str, limit: int = 20) -> List[dict]:
        """
        Recherche de candidats dans IGDB.
        
        Args:
            query: Requête de recherche
            limit: Nombre max de résultats
        
        Returns:
            Liste de dicts avec name, id, year, source, api_data
        """
        token = await self._get_token()
        if not token:
            return []
        
        try:
            resp = await self.http_client.post(
                "https://api.igdb.com/v4/games",
                headers={
                    "Client-ID": self.client_id,
                    "Authorization": f"Bearer {token}",
                },
                data=f'search "{query}"; fields name,first_release_date,rating,aggregated_rating,genres.name,platforms.name; limit {limit};'
            )
            
            if resp.status_code == 200:
                games = resp.json()
                candidates = []
                
                for game in games:
                    # Extract year
                    year = "?"
                    release_date = game.get("first_release_date")
                    if release_date:
                        year = str(datetime.fromtimestamp(release_date).year)
                    
                    candidates.append({
                        "name": game.get("name", ""),
                        "id": str(game.get("id", "")),
                        "year": year,
                        "api_data": game,
                        "source": "igdb"
                    })
                
                logger.debug(f"IGDB returned {len(candidates)} candidates for '{query}'")
                return candidates
        
        except Exception as e:
            logger.warning(f"IGDB search failed for '{query}': {e}")
        
        return []
    
    async def enrich(self, game_id: str) -> Optional[GameResult]:
        """
        Enrichissement depuis IGDB ID exact.
        
        Cette méthode utilise l'ID IGDB exact (ex: fourni par Twitch category)
        pour récupérer la version précise du jeu.
        
        Args:
            game_id: ID IGDB du jeu
        
        Returns:
            GameResult avec métadonnées complètes
        """
        token = await self._get_token()
        if not token:
            logger.error("No IGDB token available")
            return None
        
        try:
            resp = await self.http_client.post(
                "https://api.igdb.com/v4/games",
                headers={
                    "Client-ID": self.client_id,
                    "Authorization": f"Bearer {token}",
                },
                data=f'''where id = {game_id};
                fields name,first_release_date,rating,aggregated_rating,
                       genres.name,platforms.name,involved_companies.company.name,
                       involved_companies.developer,involved_companies.publisher,
                       summary,aggregated_rating_count;
                limit 1;'''
            )
            
            if resp.status_code != 200:
                logger.warning(f"IGDB API error: {resp.status_code}")
                return None
            
            games = resp.json()
            if not games:
                logger.warning(f"IGDB: No game found for ID {game_id}")
                return None
            
            game = games[0]
            result = self._parse_igdb_game(game)
            result.confidence = "IGDB_ID_EXACT"
            result.reliability_score = 1.0  # Maximum (ID exact)
            
            logger.info(f"IGDB ID {game_id}: {result.name} ({result.year})")
            return result
        
        except Exception as e:
            logger.error(f"IGDB enrich error (ID={game_id}): {e}", exc_info=True)
            return None
    
    async def enrich_by_name(self, game_name: str) -> Optional[GameResult]:
        """
        Enrichissement depuis nom de jeu.
        
        Args:
            game_name: Nom du jeu
        
        Returns:
            GameResult avec métadonnées IGDB
        """
        token = await self._get_token()
        if not token:
            return None
        
        try:
            resp = await self.http_client.post(
                "https://api.igdb.com/v4/games",
                headers={
                    "Client-ID": self.client_id,
                    "Authorization": f"Bearer {token}",
                },
                data=f'''search "{game_name}";
                fields name,first_release_date,rating,aggregated_rating,
                       genres.name,platforms.name,involved_companies.company.name,
                       involved_companies.developer,involved_companies.publisher,
                       summary,aggregated_rating_count;
                limit 1;'''
            )
            
            if resp.status_code != 200:
                logger.warning(f"IGDB API error: {resp.status_code}")
                return None
            
            games = resp.json()
            if not games:
                logger.warning(f"IGDB: No metadata found for '{game_name}'")
                return None
            
            game = games[0]
            result = self._parse_igdb_game(game)
            result.confidence = "IGDB_VERIFIED"
            result.reliability_score = 0.95
            
            return result
        
        except Exception as e:
            logger.error(f"IGDB enrich_by_name error for '{game_name}': {e}", exc_info=True)
            return None
    
    def _parse_igdb_game(self, game: dict) -> GameResult:
        """Parse réponse IGDB vers GameResult."""
        
        # Extract release year
        release_date = game.get("first_release_date")
        year = "?"
        if release_date:
            year = str(datetime.fromtimestamp(release_date).year)
        
        # Extract companies
        developers = []
        publishers = []
        for company_data in game.get("involved_companies", []):
            company_name = company_data.get("company", {}).get("name")
            if company_name:
                if company_data.get("developer"):
                    developers.append(company_name)
                if company_data.get("publisher"):
                    publishers.append(company_name)
        
        # Extract platforms
        platforms = [p.get("name", "") for p in game.get("platforms", [])]
        
        # Extract genres
        genres = [g.get("name", "") for g in game.get("genres", [])]
        
        # Rating (normalize 0-100 to 0-5)
        rating = game.get("aggregated_rating", 0.0)
        rating_normalized = round(rating / 20.0, 1) if rating else 0.0
        
        # Summary
        summary = game.get("summary", "")
        summary = summary[:500] if summary else None
        
        return GameResult(
            name=game.get("name", "Unknown"),
            year=year,
            rating_rawg=rating_normalized,
            ratings_count=game.get("aggregated_rating_count", 0),
            metacritic=None,  # IGDB doesn't provide Metacritic directly
            platforms=platforms[:3],
            genres=genres[:3],
            developers=developers[:2],
            publishers=publishers[:2],
            playtime=0,  # IGDB doesn't track playtime
            popularity=game.get("aggregated_rating_count", 0),
            esrb_rating="",
            summary=summary,
            reliability_score=0.95,
            confidence="IGDB_VERIFIED",
            source_count=1,
            primary_source="igdb",
            api_sources=["igdb"]
        )
