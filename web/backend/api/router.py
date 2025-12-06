#!/usr/bin/env python3
"""
API Routes - Endpoints pour le dashboard
"""

import logging
import re
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Cookie, Depends, Request, Body
from pydantic import BaseModel, field_validator, ValidationError
from slowapi import Limiter
from slowapi.util import get_remote_address

# Ajouter le path parent pour importer les modules KissBot
root_path = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(root_path))

try:
    from modules.moderation import get_banword_manager
except ImportError:
    # Fallback si modules non accessible
    logger_init = logging.getLogger(__name__)
    logger_init.warning("Could not import get_banword_manager from modules.moderation")
    def get_banword_manager(db_path=None):
        # Dummy fallback
        class DummyManager:
            def list_banwords(self, channel):
                return []
            def add_banword(self, channel, word, added_by):
                return True
            def remove_banword(self, channel, word):
                return True
            def get_stats(self):
                return {}
        return DummyManager()

from dependencies import get_current_user

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
    Body JSON attendu: {"word": "mot_a_bannir"}
    
    FastAPI valide automatiquement avec BanwordCreate.
    """
    try:
        if user["login"].lower() != channel.lower():
            raise HTTPException(status_code=403, detail="You can only modify your own channel's banwords")

        word = payload.word
        logger.info(f"🚫 Adding banword '{word}' for {channel} (user: {user['login']})")
        
        manager = get_banword_manager()
        added = manager.add_banword(channel, word, user["login"])
        
        if added:
            logger.info(f"✅ API: {user['login']} added banword '{word}' to #{channel}")
            return {"status": "added", "word": word, "message": f"'{word}' ajouté aux banwords"}
        else:
            return {"status": "exists", "word": word, "message": f"'{word}' existe déjà"}
    except HTTPException:
        # Re-propagate HTTPException (403, etc.)
        raise
    except Exception as e:
        logger.error(f"Error adding banword: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur serveur")


@router.post("/banwords/{channel}/debug")
async def debug_add_banword(
    request: Request,
    channel: str,
    user: dict = Depends(get_current_user)
):
    """Debug endpoint - logs raw request body"""
    try:
        body = await request.json()
        logger.warning(f"DEBUG: Raw body = {body}")
        return {"debug": body, "user": user["login"]}
    except Exception as e:
        logger.error(f"Debug error: {e}")
        return {"error": str(e)}


@router.post("/banwords/test/validate")
async def test_validation(request: Request):
    """
    Endpoint de test SANS authentification pour tester la validation Pydantic.
    Utiliser uniquement pour debug local.
    """
    payload_json = None
    try:
        # Lire le JSON brut
        payload_json = await request.json()
        logger.warning(f"🧪 TEST RAW BODY: {payload_json}")
        
        # Tenter validation Pydantic
        payload = BanwordCreate(**payload_json)
        logger.info(f"✅ Validation OK: {payload.word}")
        
        return {
            "status": "validation_success",
            "raw_input": payload_json,
            "validated_word": payload.word,
            "message": "Validation Pydantic réussie"
        }
    except (ValueError, ValidationError) as e:
        logger.warning(f"❌ Validation error: {e}")
        raise HTTPException(
            status_code=400,
            detail={
                "status": "validation_error",
                "error_type": type(e).__name__,
                "message": str(e),
                "raw_input": payload_json
            }
        )
    except Exception as e:
        logger.error(f"❌ Exception: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "error_type": type(e).__name__,
                "message": str(e),
                "raw_input": payload_json
            }
        )


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


# ============================================================
# CURRENT USER / SCOPES
# ============================================================


@router.get("/me/scopes")
async def get_my_scopes(user: dict = Depends(get_current_user)):
    """
    Retourne la liste des scopes OAuth pour l'utilisateur connecté.
    Endpoint protégé : nécessite le cookie de session (get_current_user).
    Ne retourne jamais de tokens, uniquement la liste des scopes.
    """
    try:
        from dependencies import get_database

        db = get_database()

        db_user = db.get_user(user["id"])  # recherche par twitch_user_id
        if not db_user:
            return {"scopes": []}

        tokens = db.get_tokens(user_id=db_user['id'], token_type='broadcaster')
        if not tokens:
            return {"scopes": []}

        raw = tokens.get('scopes', [])
        # Normaliser en liste
        if isinstance(raw, str):
            try:
                import json
                scopes = json.loads(raw)
            except Exception:
                scopes = raw.split() if raw else []
        elif isinstance(raw, list):
            scopes = raw
        else:
            scopes = []

        return {"scopes": scopes}

    except Exception as e:
        logger.warning(f"Could not fetch scopes for user {user.get('login')}: {e}")
        return {"scopes": []}
