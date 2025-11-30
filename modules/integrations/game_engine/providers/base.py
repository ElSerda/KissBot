#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Base GameProvider Interface

Définit le contrat que chaque provider doit respecter.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass, field

@dataclass
class GameResult:
    """
    Résultat de jeu unifié (tous providers).
    
    Format standardisé pour fusionner données de multiples sources.
    """
    name: str
    year: str = "?"
    rating_rawg: float = 0.0
    ratings_count: int = 0
    metacritic: Optional[int] = None
    platforms: List[str] = field(default_factory=list)
    genres: List[str] = field(default_factory=list)
    developers: List[str] = field(default_factory=list)
    publishers: List[str] = field(default_factory=list)
    playtime: int = 0
    popularity: int = 0
    esrb_rating: str = ""
    summary: Optional[str] = None
    
    # Metadata de fiabilité
    reliability_score: float = 0.0
    confidence: str = ""
    source_count: int = 1
    primary_source: str = ""
    api_sources: List[str] = field(default_factory=list)


class GameProvider(ABC):
    """
    Interface abstraite pour un provider de jeux.
    
    Chaque API (Steam, IGDB, RAWG...) implémente cette interface
    pour être utilisée par l'orchestrator GameLookup.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Nom du provider (ex: 'steam', 'igdb', 'rawg')."""
        pass
    
    @property
    @abstractmethod
    def weight(self) -> float:
        """
        Poids de fiabilité du provider (0.0 - 1.0).
        
        Utilisé pour pondérer les scores d'alignment.
        Ex: Steam = 0.40, IGDB = 0.35, RAWG = 0.25
        """
        pass
    
    @abstractmethod
    async def search(self, query: str, limit: int = 20) -> List[dict]:
        """
        Recherche de candidats dans l'API.
        
        Args:
            query: Requête de recherche
            limit: Nombre max de résultats
        
        Returns:
            Liste de dicts avec champs minimaux :
            - name: str
            - year: str (optionnel)
            - id: str (identifiant API)
            - source: str (nom du provider)
        """
        pass
    
    @abstractmethod
    async def enrich(self, game_id: str) -> Optional[GameResult]:
        """
        Enrichissement métadonnées complètes depuis ID.
        
        Args:
            game_id: Identifiant unique dans l'API du provider
        
        Returns:
            GameResult avec toutes les métadonnées ou None si erreur
        """
        pass
    
    @abstractmethod
    async def enrich_by_name(self, game_name: str) -> Optional[GameResult]:
        """
        Enrichissement métadonnées depuis nom de jeu.
        
        Args:
            game_name: Nom du jeu à enrichir
        
        Returns:
            GameResult avec métadonnées ou None si non trouvé
        """
        pass
    
    def is_available(self) -> bool:
        """
        Vérifie si le provider est disponible (API key configurée, etc.).
        
        Returns:
            True si utilisable, False sinon
        """
        return True
