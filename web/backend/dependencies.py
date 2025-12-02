#!/usr/bin/env python3
"""
Dépendances FastAPI partagées
"""

from typing import Optional
from fastapi import Cookie, HTTPException


def get_current_user(session: Optional[str] = Cookie(None)) -> dict:
    """
    Dépendance pour vérifier l'authentification.
    
    Extrait les infos utilisateur du cookie de session.
    Format session: "user_id:user_login:display_name"
    
    Returns:
        dict: {"id": str, "login": str, "display_name": str}
    
    Raises:
        HTTPException 401: Si non authentifié ou session invalide
    """
    if not session:
        raise HTTPException(401, "Not authenticated")
    
    try:
        parts = session.split(":")
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
        parts = session.split(":")
        if len(parts) >= 2:
            return {
                "id": parts[0],
                "login": parts[1],
                "display_name": parts[2] if len(parts) >= 3 else parts[1]
            }
    except ValueError:
        pass
    
    return None
