#!/usr/bin/env python3
"""
Dépendances FastAPI partagées
"""

import sys
import logging
from pathlib import Path
from functools import lru_cache
from typing import Optional

from fastapi import Cookie, HTTPException

# Ajouter le path parent pour importer les modules KissBot
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.manager import DatabaseManager
from config import get_settings

logger = logging.getLogger(__name__)

# ============================================================
# DATABASE SINGLETON
# ============================================================

_db_instance: Optional[DatabaseManager] = None


def get_database() -> DatabaseManager:
    """
    Singleton DatabaseManager.
    
    Charge la clé de chiffrement et initialise la connexion une seule fois.
    """
    global _db_instance
    
    if _db_instance is None:
        settings = get_settings()
        _db_instance = DatabaseManager(
            db_path=settings.database_path,
            key_file=settings.encryption_key_file
        )
        logger.info("📦 DatabaseManager singleton initialized")
    
    return _db_instance


# ============================================================
# AUTH DEPENDENCIES
# ============================================================

def get_current_user(session: Optional[str] = Cookie(None)) -> dict:
    """
    Dépendance pour vérifier l'authentification.
    
    Extrait les infos utilisateur du cookie de session.
    Format session: "user_id:user_login:display_name" (URL-encoded)
    
    Returns:
        dict: {"id": str, "login": str, "display_name": str}
    
    Raises:
        HTTPException 401: Si non authentifié ou session invalide
    """
    if not session:
        raise HTTPException(401, "Not authenticated")
    
    try:
        from urllib.parse import unquote
        # Décoder l'URL encoding
        decoded = unquote(session)
        parts = decoded.split(":")
        if len(parts) >= 2:
            return {
                "id": parts[0],
                "login": parts[1],
                "display_name": parts[2] if len(parts) >= 3 else parts[1]
            }
        raise HTTPException(401, "Invalid session format")
    except ValueError:
        raise HTTPException(401, "Invalid session")


def get_optional_user(session: Optional[str] = Cookie(None)) -> Optional[dict]:
    """
    Dépendance pour récupérer l'utilisateur sans erreur si non connecté.
    
    Returns:
        dict ou None si pas de session
    """
    if not session:
        return None
    
    try:
        from urllib.parse import unquote
        decoded = unquote(session)
        parts = decoded.split(":")
        if len(parts) >= 2:
            return {
                "id": parts[0],
                "login": parts[1],
                "display_name": parts[2] if len(parts) >= 3 else parts[1]
            }
    except ValueError:
        pass
    
    return None
