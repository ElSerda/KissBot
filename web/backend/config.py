#!/usr/bin/env python3
"""
Configuration centralisée pour le backend.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Configuration via variables d'environnement."""
    
    # Twitch OAuth
    twitch_client_id: str = os.getenv("TWITCH_CLIENT_ID", "")
    twitch_client_secret: str = os.getenv("TWITCH_CLIENT_SECRET", "")
    twitch_redirect_uri: str = os.getenv(
        "TWITCH_REDIRECT_URI", 
        "http://localhost:8080/auth/callback"
    )
    
    # Scopes OAuth requis
    twitch_scopes: str = " ".join([
        # Modération
        "moderator:manage:banned_users",
        "moderator:manage:blocked_terms",
        "moderator:manage:chat_messages",
        "moderator:read:chatters",
        # Channel
        "channel:read:subscriptions",
        "channel:manage:broadcast",
        "channel:read:redemptions",
        "channel:bot",                      # Bot chat identity
        # Chat (EventSub + IRC)
        "chat:read",
        "chat:edit",
        "user:read:chat",                   # EventSub chat receive
        "user:write:chat",                  # Helix API send message
        "user:bot",                         # Bot chat identity
        # User
        "user:read:email",
        "user:read:moderated_channels",     # Check if bot is mod (rate limits)
    ])
    
    # Database (réutilise kissbot.db)
    database_path: str = os.getenv(
        "DATABASE_PATH",
        str(Path(__file__).parent.parent.parent / "kissbot.db")
    )
    encryption_key_file: str = os.getenv(
        "ENCRYPTION_KEY_FILE",
        str(Path(__file__).parent.parent.parent / ".kissbot.key")
    )
    
    # Frontend
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    
    # Session
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-change-in-prod")
    session_expire_hours: int = 24 * 7  # 1 semaine
    
    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Singleton settings."""
    return Settings()
