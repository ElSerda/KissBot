#!/usr/bin/env python3
"""Helix Read-Only Transport - Phase 2.6: avec timeout handling

Requêtes Helix publiques (sans User Token) :
- get_streams() : Informations sur les streams actifs
- get_users() : Données publiques des utilisateurs
- get_games() : Informations sur les jeux/catégories
- search_channels() : Recherche de chaînes
- search_categories() : Recherche de catégories

Toutes les réponses sont publiées sur le MessageBus.
Phase 2.6 : Ajout timeout pour éviter blocages.
"""

import asyncio
import logging
from typing import List, Optional

from twitchAPI.twitch import Twitch

from core.message_bus import MessageBus
from core.message_types import SystemEvent

LOGGER = logging.getLogger(__name__)


class HelixReadOnlyClient:
    """
    Client Helix pour requêtes publiques (App Token)
    
    Phase 2.6 : Ajout timeout handling pour éviter blocages LLM.
    """
    
    def __init__(self, twitch: Twitch, bus: MessageBus, helix_timeout: float = 8.0):
        """Initialise le client Helix read-only.
        
        Args:
            twitch: Instance Twitch API (avec App Token)
            bus: MessageBus pour publier les événements
            helix_timeout: Timeout requêtes Helix en secondes (Phase 2.6)
        """
        self.twitch = twitch
        self.bus = bus
        self.helix_timeout = helix_timeout
        LOGGER.debug(f"HelixReadOnlyClient init (timeout={helix_timeout}s)")

    async def get_stream(self, user_login: str) -> Optional[dict]:
        """Récupère les informations d'un stream actif.
        
        Args:
            user_login: Login du broadcaster
            
        Returns:
            Dict avec les infos du stream ou None si offline
        """
        try:
            LOGGER.debug(f"[HELIX] get_stream({user_login})")
            
            # Phase 2.6: Wrap avec timeout
            async def _fetch():
                streams = []
                async for stream in self.twitch.get_streams(user_login=[user_login]):
                    streams.append(stream)
                return streams
            
            streams = await asyncio.wait_for(_fetch(), timeout=self.helix_timeout)
            
            if not streams:
                LOGGER.debug(f"Stream {user_login} offline")
                return None
            
            stream = streams[0]
            data = {
                "id": stream.id,
                "user_id": stream.user_id,
                "user_login": stream.user_login,
                "user_name": stream.user_name,
                "game_id": stream.game_id,
                "game_name": stream.game_name,
                "title": stream.title,
                "viewer_count": stream.viewer_count,
                "started_at": stream.started_at.isoformat(),
                "language": stream.language,
                "thumbnail_url": stream.thumbnail_url,
                "is_mature": stream.is_mature,
            }
            
            # Log en DEBUG pour éviter spam (StreamMonitor log déjà proprement)
            LOGGER.debug(f"Stream {user_login}: {stream.title} ({stream.viewer_count} viewers)")
            
            # Publier sur le bus
            event = SystemEvent(kind="helix.stream.info", payload=data)
            await self.bus.publish("system.event", event)
            
            return data
            
        except asyncio.TimeoutError:
            LOGGER.error(f"⏱️ Timeout get_stream({user_login}) après {self.helix_timeout}s")
            return None
        except Exception as e:
            LOGGER.error(f"Erreur get_stream({user_login}): {e}")
            return None

    async def get_user(self, user_login: str) -> Optional[dict]:
        """Récupère les informations publiques d'un utilisateur.
        
        Args:
            user_login: Login de l'utilisateur
            
        Returns:
            Dict avec les infos de l'utilisateur ou None si introuvable
        """
        try:
            LOGGER.debug(f"[HELIX] get_user({user_login})")
            
            users = []
            async for user in self.twitch.get_users(logins=[user_login]):
                users.append(user)
            
            if not users:
                LOGGER.debug(f"User {user_login} introuvable")
                return None
            
            user = users[0]
            data = {
                "id": user.id,
                "login": user.login,
                "display_name": user.display_name,
                "type": user.type,
                "broadcaster_type": user.broadcaster_type,
                "description": user.description,
                "profile_image_url": user.profile_image_url,
                "offline_image_url": user.offline_image_url,
                "created_at": user.created_at.isoformat(),
            }
            
            LOGGER.info(f"User {user_login}: {user.display_name} (ID: {user.id})")
            
            # Publier sur le bus
            event = SystemEvent(kind="helix.user.info", payload=data)
            await self.bus.publish("system.event", event)
            
            return data
            
        except Exception as e:
            LOGGER.error(f"Erreur get_user({user_login}): {e}")
            return None

    async def get_game(self, game_name: str) -> Optional[dict]:
        """Récupère les informations d'un jeu/catégorie.
        
        Args:
            game_name: Nom du jeu
            
        Returns:
            Dict avec les infos du jeu ou None si introuvable
        """
        try:
            LOGGER.debug(f"[HELIX] get_game({game_name})")
            
            games = []
            async for game in self.twitch.get_games(names=[game_name]):
                games.append(game)
            
            if not games:
                LOGGER.debug(f"Game {game_name} introuvable")
                return None
            
            game = games[0]
            data = {
                "id": game.id,
                "name": game.name,
                "box_art_url": game.box_art_url,
                "igdb_id": game.igdb_id,
            }
            
            LOGGER.info(f"Game {game_name}: ID {game.id}")
            
            # Publier sur le bus
            event = SystemEvent(kind="helix.game.info", payload=data)
            await self.bus.publish("system.event", event)
            
            return data
            
        except Exception as e:
            LOGGER.error(f"Erreur get_game({game_name}): {e}")
            return None

    async def get_top_games(self, limit: int = 10) -> List[dict]:
        """Récupère les jeux les plus populaires.
        
        Args:
            limit: Nombre de jeux à récupérer (max 100)
            
        Returns:
            Liste de dicts avec les infos des jeux
        """
        try:
            LOGGER.info(f"[HELIX] get_top_games(limit={limit})")
            
            games = []
            count = 0
            async for game in self.twitch.get_top_games(first=limit):
                games.append({
                    "id": game.id,
                    "name": game.name,
                    "box_art_url": game.box_art_url,
                    "igdb_id": game.igdb_id,
                })
                count += 1
                if count >= limit:
                    break
            
            LOGGER.info(f"Top games: {len(games)} récupérés")
            
            # Publier sur le bus
            event = SystemEvent(kind="helix.top_games", payload={"games": games})
            await self.bus.publish("system.event", event)
            
            return games
            
        except Exception as e:
            LOGGER.error(f"Erreur get_top_games: {e}")
            return []
