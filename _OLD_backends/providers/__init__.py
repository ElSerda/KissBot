#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Game Providers - Modular API backends

Chaque provider implémente l'interface GameProvider pour :
- Recherche de candidats (search)
- Enrichissement métadonnées (enrich)
- Poids de fiabilité (weight)
"""

from backends.providers.base import GameProvider, GameResult
from backends.providers.steam import SteamProvider
from backends.providers.igdb import IGDBProvider
from backends.providers.rawg import RAWGProvider

__all__ = [
    'GameProvider',
    'GameResult',
    'SteamProvider',
    'IGDBProvider',
    'RAWGProvider',
]
