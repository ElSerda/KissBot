#!/usr/bin/env python3
"""
API Routes - Endpoints pour le dashboard
"""

import logging
import re
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Cookie, Depends, Request
from pydantic import BaseModel, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address

# Ajouter le path parent pour importer les modules KissBot
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from modules.moderation import get_banword_manager

logger = logging.getLogger(__name__)
router = APIRouter()

# Rate limiter (récupéré depuis app.state)
limiter = Limiter(key_func=get_remote_address)


# ============================================================
# PYDANTIC MODELS - Validation des entrées
# ============================================================

class BanwordCreate(BaseModel):
    """Validation pour création de banword."""
    word: str
    
    @field_validator('word')
    @classmethod
    def validate_word(cls, v: str) -> str:
        # Strip et lowercase
        v = v.strip().lower()
        
        # Longueur
        if len(v) < 3:
            raise ValueError('Le mot doit faire au moins 3 caractères')
        if len(v) > 50:
            raise ValueError('Le mot ne peut pas dépasser 50 caractères')
        
        # Caractères autorisés (alphanumériques + quelques spéciaux)
        if not re.match(r'^[a-z0-9àâäéèêëïîôùûüç_.\-]+$', v):
            raise ValueError('Caractères non autorisés dans le mot')
        
        return v


def get_current_user(session: Optional[str] = Cookie(None)) -> dict:
    """Dépendance pour vérifier l'authentification."""
    if not session:
        raise HTTPException(401, "Not authenticated")
    
    try:
        parts = session.split(":")
        if len(parts) >= 2:
            return {"id": parts[0], "login": parts[1]}
        raise HTTPException(401, "Invalid session format")
    except ValueError:
        raise HTTPException(401, "Invalid session")


# ============================================================
# BANWORDS API
# ============================================================

@router.get("/banwords/{channel}")
@limiter.limit("30/minute")
async def list_banwords(
    request: Request,
    channel: str,
    user: dict = Depends(get_current_user)
):
    """
    Liste les banwords d'un channel.
    Le user doit être broadcaster du channel.
    """
    if user["login"].lower() != channel.lower():
        raise HTTPException(403, "You can only view your own channel's banwords")
    
    manager = get_banword_manager()
    words = manager.list_banwords(channel)
    
    return {
        "channel": channel,
        "banwords": words,
        "count": len(words)
    }


@router.post("/banwords/{channel}")
@limiter.limit("10/minute")
async def add_banword(
    request: Request,
    channel: str,
    payload: BanwordCreate,
    user: dict = Depends(get_current_user)
):
    """
    Ajoute un banword à un channel.
    Body JSON: {"word": "mot_a_bannir"}
    """
    if user["login"].lower() != channel.lower():
        raise HTTPException(403, "You can only modify your own channel's banwords")
    
    # Le word est déjà validé et nettoyé par Pydantic
    word = payload.word
    
    manager = get_banword_manager()
    added = manager.add_banword(channel, word, user["login"])
    
    if added:
        logger.info(f"🚫 API: {user['login']} added banword '{word}' to #{channel}")
        return {"status": "added", "word": word}
    else:
        return {"status": "exists", "word": word}


@router.delete("/banwords/{channel}/{word}")
@limiter.limit("10/minute")
async def remove_banword(
    request: Request,
    channel: str,
    word: str,
    user: dict = Depends(get_current_user)
):
    """
    Supprime un banword d'un channel.
    """
    if user["login"].lower() != channel.lower():
        raise HTTPException(403, "You can only modify your own channel's banwords")
    
    manager = get_banword_manager()
    removed = manager.remove_banword(channel, word)
    
    if removed:
        logger.info(f"✅ API: {user['login']} removed banword '{word}' from #{channel}")
        return {"status": "removed", "word": word}
    else:
        raise HTTPException(404, f"Banword '{word}' not found")


# ============================================================
# CHANNEL STATUS
# ============================================================

@router.get("/channel/{channel}/status")
async def channel_status(
    channel: str,
    user: dict = Depends(get_current_user)
):
    """
    Statut du bot sur un channel.
    """
    # TODO: Vérifier si le bot est actif sur ce channel
    return {
        "channel": channel,
        "bot_active": True,  # TODO: Vérifier vraiment
        "bot_is_mod": False,  # TODO: Vérifier via API Twitch
        "features": {
            "banwords": True,
            "auto_translate": False,
            "llm_responses": True,
        }
    }


# ============================================================
# STATS
# ============================================================

@router.get("/stats")
async def get_stats(user: dict = Depends(get_current_user)):
    """
    Stats globales pour le dashboard.
    """
    manager = get_banword_manager()
    banword_stats = manager.get_stats()
    
    return {
        "banwords": banword_stats,
        # TODO: Ajouter plus de stats
    }
