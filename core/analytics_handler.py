#!/usr/bin/env python3
"""
Analytics Handler - Phase 1.3
Subscribe aux événements du MessageBus et les traite
"""

import logging
from typing import Any

from core.message_bus import MessageBus
from core.message_types import SystemEvent

LOGGER = logging.getLogger(__name__)


class AnalyticsHandler:
    """
    Subscriber qui écoute tous les événements système
    et les traite pour analytics/logging
    """
    
    def __init__(self, bus: MessageBus):
        self.bus = bus
        self.event_count = 0
        
        # Subscribe à tous les topics système
        self.bus.subscribe("system.event", self._handle_system_event)
        
        LOGGER.info("AnalyticsHandler initialisé")
    
    async def _handle_system_event(self, event: SystemEvent) -> None:
        """
        Traite un événement système (Helix, EventSub, etc.)
        
        Args:
            event: SystemEvent avec kind et payload
        """
        self.event_count += 1
        
        kind = event.kind
        payload = event.payload
        
        # Router selon le type d'événement
        if kind == "helix.stream.info":
            await self._handle_stream_info(payload)
        elif kind == "helix.user.info":
            await self._handle_user_info(payload)
        elif kind == "helix.game.info":
            await self._handle_game_info(payload)
        elif kind == "helix.top_games":
            await self._handle_top_games(payload)
        else:
            LOGGER.debug(f"[Analytics] Event inconnu: {kind}")
    
    async def _handle_stream_info(self, payload: dict[str, Any]) -> None:
        """Traite les infos de stream"""
        if payload:
            user_login = payload.get("user_login", "?")
            title = payload.get("title", "")
            viewers = payload.get("viewer_count", 0)
            game = payload.get("game_name", "?")
            
            LOGGER.debug(
                f"📊 [Stream] {user_login} | {viewers} viewers | {game} | {title[:50]}"
            )
        else:
            LOGGER.debug("[Stream] Offline ou non trouvé")
    
    async def _handle_user_info(self, payload: dict[str, Any]) -> None:
        """Traite les infos utilisateur"""
        display_name = payload.get("display_name", "?")
        user_id = payload.get("id", "?")
        created_at = payload.get("created_at", "?")
        
        LOGGER.debug(
            f"📊 [User] {display_name} (ID: {user_id}) | Créé: {created_at}"
        )
    
    async def _handle_game_info(self, payload: dict[str, Any]) -> None:
        """Traite les infos de jeu"""
        name = payload.get("name", "?")
        game_id = payload.get("id", "?")
        
        LOGGER.debug(f"📊 [Game] {name} (ID: {game_id})")
    
    async def _handle_top_games(self, payload: dict[str, Any]) -> None:
        """Traite le top des jeux"""
        games = payload.get("games", [])
        LOGGER.debug(f"📊 [TopGames] {len(games)} jeux récupérés")
        
        for i, game in enumerate(games[:3], 1):
            LOGGER.debug(f"   {i}. {game.get('name', '?')}")
    
    def get_stats(self) -> dict[str, int]:
        """Retourne les stats d'événements traités"""
        return {
            "total_events": self.event_count
        }
