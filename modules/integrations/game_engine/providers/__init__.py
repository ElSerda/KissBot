#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Game Providers - Modular API backends

Chaque provider implémente l'interface GameProvider pour :
- Recherche de candidats (search)
- Enrichissement métadonnées (enrich)
- Poids de fiabilité (weight)
"""

from modules.integrations.game_engine.providers.base import GameProvider, GameResult
from modules.integrations.game_engine.providers.steam import SteamProvider
from modules.integrations.game_engine.providers.igdb import IGDBProvider
from modules.integrations.game_engine.providers.rawg import RAWGProvider

__all__ = [
    'GameProvider',
    'GameResult',
    'SteamProvider',
    'IGDBProvider',
    'RAWGProvider',
]
