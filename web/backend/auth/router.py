#!/usr/bin/env python3
"""
OAuth Twitch - Routes d'authentification
"""

import sys
import logging
import secrets
from pathlib import Path
from urllib.parse import urlencode
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Response, Cookie
from fastapi.responses import RedirectResponse
import httpx

# Ajouter le path parent pour importer les modules KissBot
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Store temporaire pour les states OAuth (en prod: Redis)
_oauth_states: dict[str, bool] = {}


@router.get("/twitch")
async def login_twitch():
    """
    Initie le flow OAuth Twitch.
    Redirige l'utilisateur vers la page de login Twitch.
    """
    settings = get_settings()
    
    if not settings.twitch_client_id:
        raise HTTPException(500, "TWITCH_CLIENT_ID not configured")
    
    # Générer un state unique pour éviter CSRF
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = True
    
    # Construire l'URL OAuth
    params = {
        "client_id": settings.twitch_client_id,
        "redirect_uri": settings.twitch_redirect_uri,
        "response_type": "code",
        "scope": settings.twitch_scopes,
        "state": state,
        "force_verify": "true",  # Force re-auth pour tester les scopes
    }
    
    auth_url = f"https://id.twitch.tv/oauth2/authorize?{urlencode(params)}"
    logger.info(f"🔐 OAuth redirect to Twitch (state={state[:8]}...)")
    logger.info(f"🔗 Redirect URI used: {settings.twitch_redirect_uri}")
    
    return RedirectResponse(url=auth_url)


async def handle_oauth_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
):
    """
    Handle OAuth callback logic - appelable depuis /auth/callback ou /
    """
    settings = get_settings()
    
    # Erreur de Twitch
    if error:
        logger.error(f"❌ OAuth error: {error} - {error_description}")
        return RedirectResponse(
            url=f"/?error={error}"
        )
    
    # Vérifier state (anti-CSRF)
    if not state or state not in _oauth_states:
        logger.error("❌ Invalid OAuth state")
        return RedirectResponse(url="/?error=invalid_state")
    
    del _oauth_states[state]  # One-time use
    
    if not code:
        return RedirectResponse(url="/?error=missing_code")
    
    # Échanger code contre tokens
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://id.twitch.tv/oauth2/token",
            data={
                "client_id": settings.twitch_client_id,
                "client_secret": settings.twitch_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.twitch_redirect_uri,
            }
        )
    
    if token_response.status_code != 200:
        logger.error(f"❌ Token exchange failed: {token_response.text}")
        return RedirectResponse(url="/?error=token_exchange_failed")
    
    tokens = token_response.json()
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    expires_in = tokens.get("expires_in", 3600)
    
    logger.info(f"✅ Got tokens (expires in {expires_in}s)")
    
    # Récupérer les infos utilisateur
    async with httpx.AsyncClient() as client:
        user_response = await client.get(
            "https://api.twitch.tv/helix/users",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Client-Id": settings.twitch_client_id,
            }
        )
    
    if user_response.status_code != 200:
        logger.error(f"❌ User info failed: {user_response.text}")
        return RedirectResponse(url="/?error=user_info_failed")
    
    user_data = user_response.json().get("data", [{}])[0]
    user_id = user_data.get("id")
    user_login = user_data.get("login")
    user_display = user_data.get("display_name")
    
    logger.info(f"✅ Authenticated: {user_display} (ID: {user_id})")
    
    # ═══════════════════════════════════════════════════════════════════
    # STOCKAGE TOKENS EN BDD
    # ═══════════════════════════════════════════════════════════════════
    try:
        from database.manager import DatabaseManager
        
        db = DatabaseManager(
            db_path=settings.database_path,
            key_file=settings.encryption_key_file
        )
        
        # 1. Chercher ou créer l'utilisateur
        existing_user = db.get_user(user_id)
        
        if existing_user:
            internal_user_id = existing_user['id']
            # Mettre à jour le display_name si changé
            if existing_user.get('display_name') != user_display:
                db.update_user(internal_user_id, display_name=user_display)
            logger.info(f"📝 User exists in DB: {user_login} (internal ID: {internal_user_id})")
        else:
            # Créer le nouvel utilisateur
            internal_user_id = db.create_user(
                twitch_user_id=user_id,
                twitch_login=user_login,
                display_name=user_display,
                is_bot=False  # C'est un broadcaster, pas un bot
            )
            logger.info(f"📝 User created in DB: {user_login} (internal ID: {internal_user_id})")
        
        # 2. Stocker les tokens (type='broadcaster')
        scopes = tokens.get("scope", [])
        if isinstance(scopes, str):
            scopes = scopes.split()
        
        db.store_tokens(
            user_id=internal_user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            scopes=scopes,
            token_type='broadcaster',
            status='valid'
        )
        logger.info(f"✅ Tokens stored for {user_login} (scopes: {len(scopes)})")
        
    except FileNotFoundError as e:
        # DB pas encore initialisée, on continue sans stocker
        logger.warning(f"⚠️ Database not found, tokens not stored: {e}")
    except Exception as e:
        logger.error(f"❌ Failed to store tokens: {e}", exc_info=True)
        # On continue quand même pour permettre le login
    
    # Créer session (cookie) avec id:login:display_name
    # secure=True uniquement en prod (HTTPS)
    import os
    is_prod = os.getenv("DEBUG", "false").lower() != "true"
    
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        key="session",
        value=f"{user_id}:{user_login}:{user_display}",
        httponly=True,
        secure=is_prod,  # True en prod (HTTPS), False en dev
        samesite="lax",
        max_age=settings.session_expire_hours * 3600,
    )
    
    return response


@router.get("/callback")
async def oauth_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
):
    """
    Callback OAuth Twitch (route alternative si redirect_uri = /auth/callback).
    """
    return await handle_oauth_callback(code, state, error, error_description)


@router.get("/me")
async def get_me(session: Optional[str] = Cookie(None)):
    """
    Retourne les infos de l'utilisateur connecté.
    """
    from dependencies import get_current_user as _get_user
    user = _get_user(session)
    return {
        "id": user["id"],
        "login": user["login"],
        "display_name": user.get("display_name", user["login"]),
        "authenticated": True
    }


@router.post("/logout")
async def logout_post():
    """
    Déconnexion (POST) - supprime le cookie de session.
    """
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("session")
    return response


@router.get("/logout")
async def logout_get():
    """
    Déconnexion (GET) - supprime le cookie de session.
    """
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("session")
    return response


@router.get("/status")
async def auth_status(session: Optional[str] = Cookie(None)):
    """
    Vérifie si l'utilisateur est connecté.
    """
    if session:
        try:
            user_id, user_login = session.split(":", 1)
            return {
                "authenticated": True,
                "user_id": user_id,
                "user_login": user_login
            }
        except ValueError:
            pass
    
    return {"authenticated": False}
