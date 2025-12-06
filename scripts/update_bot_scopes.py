#!/usr/bin/env python3
"""
🔑 Update Bot Token Scopes via OAuth Flow

Ce script permet de mettre à jour les scopes du token bot (serda_bot)
en lançant un flow OAuth avec les nouvelles scopes requises.

Usage:
    python scripts/update_bot_scopes.py [--bot serda_bot]

Le script va:
1. Ouvrir un navigateur pour l'authentification Twitch
2. Demander les nouvelles scopes
3. Sauvegarder le token mis à jour dans la DB
"""

import asyncio
import json
import os
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.type import AuthScope

from database.manager import DatabaseManager

# ═══════════════════════════════════════════════════════════════════════════
# Configuration - Scopes requises pour le bot
# ═══════════════════════════════════════════════════════════════════════════
BOT_SCOPES = [
    # Modération (pour !kbupdate /announcements)
    AuthScope.MODERATOR_MANAGE_ANNOUNCEMENTS,
    AuthScope.MODERATOR_MANAGE_BANNED_USERS,
    AuthScope.MODERATOR_MANAGE_BLOCKED_TERMS,
    AuthScope.MODERATOR_MANAGE_CHAT_MESSAGES,
    AuthScope.MODERATOR_READ_CHATTERS,
    # Channel
    AuthScope.CHANNEL_READ_SUBSCRIPTIONS,
    AuthScope.CHANNEL_MANAGE_BROADCAST,
    AuthScope.CHANNEL_READ_REDEMPTIONS,
    AuthScope.CHANNEL_BOT,
    # Chat (EventSub + IRC)
    AuthScope.CHAT_READ,
    AuthScope.CHAT_EDIT,
    AuthScope.USER_READ_CHAT,
    AuthScope.USER_WRITE_CHAT,
    AuthScope.USER_BOT,
    # User
    AuthScope.USER_READ_EMAIL,
    AuthScope.USER_READ_MODERATED_CHANNELS,
]


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler to capture OAuth callback"""
    
    auth_code = None
    
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/callback':
            params = parse_qs(parsed.query)
            if 'code' in params:
                OAuthCallbackHandler.auth_code = params['code'][0]
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"""
                    <html><body style="font-family: sans-serif; text-align: center; padding: 50px;">
                    <h1>&#x2705; Authentification reussie!</h1>
                    <p>Vous pouvez fermer cette fenetre et retourner au terminal.</p>
                    </body></html>
                """)
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Error: No code received")
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress logs


async def update_bot_scopes(bot_name: str = "serda_bot"):
    """
    Met à jour les scopes du token bot via OAuth flow.
    """
    print(f"\n🔑 Mise à jour des scopes pour: {bot_name}")
    print(f"📋 Scopes demandées: {len(BOT_SCOPES)}")
    for scope in BOT_SCOPES:
        print(f"   - {scope.value}")
    
    # Load config
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    client_id = config['twitch']['client_id']
    client_secret = config['twitch']['client_secret']
    
    # Initialize Twitch
    twitch = await Twitch(client_id, client_secret)
    
    # Use UserAuthenticator for OAuth flow
    auth = UserAuthenticator(twitch, BOT_SCOPES, url='http://localhost:17563/callback')
    
    # Get auth URL
    auth_url = auth.return_auth_url()
    
    print(f"\n🌐 Ouvre ton navigateur et connecte-toi avec le compte {bot_name}:")
    print(f"\n   {auth_url}\n")
    
    # Open browser
    webbrowser.open(auth_url)
    
    # Start local server to capture callback
    print("⏳ En attente de l'authentification...")
    
    # Use UserAuthenticator's built-in flow
    try:
        token, refresh_token = await auth.authenticate()
    except Exception as e:
        print(f"❌ Erreur d'authentification: {e}")
        await twitch.close()
        return False
    
    print(f"✅ Token obtenu!")
    
    # Set user auth to get user info
    await twitch.set_user_authentication(token, BOT_SCOPES, refresh_token)
    
    # Get user info
    users = []
    async for user in twitch.get_users():
        users.append(user)
    
    if not users:
        print("❌ Impossible de récupérer les infos utilisateur")
        await twitch.close()
        return False
    
    user = users[0]
    print(f"👤 Utilisateur authentifié: {user.login} (ID: {user.id})")
    
    if user.login.lower() != bot_name.lower():
        print(f"⚠️  ATTENTION: Tu t'es connecté avec {user.login}, pas {bot_name}!")
        confirm = input("Continuer quand même? (y/n): ")
        if confirm.lower() != 'y':
            await twitch.close()
            return False
    
    # Save to database
    db_path = Path(__file__).parent.parent / "kissbot.db"
    key_path = Path(__file__).parent.parent / ".kissbot.key"
    
    db = DatabaseManager(str(db_path), str(key_path))
    
    # Check if user exists
    db_user = db.get_user_by_login(user.login)
    if not db_user:
        # Create user
        db.create_user(
            twitch_user_id=user.id,
            twitch_login=user.login,
            display_name=user.display_name,
            is_bot=True
        )
        db_user = db.get_user_by_login(user.login)
        print(f"✅ Utilisateur créé en DB: {user.login}")
    
    # Store tokens with new scopes
    scopes_list = [s.value for s in BOT_SCOPES]
    
    db.store_tokens(
        user_id=db_user['id'],
        access_token=token,
        refresh_token=refresh_token,
        expires_in=14400,  # 4 hours
        scopes=scopes_list,
        token_type='bot',
        status='valid'
    )
    
    print(f"\n✅ Token sauvegardé en DB avec {len(scopes_list)} scopes!")
    print(f"   Dont: moderator:manage:announcements ✅")
    
    # Verify
    print("\n📊 Vérification:")
    tokens = db.get_tokens(db_user['id'], token_type='bot')
    if tokens:
        saved_scopes = json.loads(tokens['scopes']) if tokens.get('scopes') else []
        print(f"   Scopes en DB: {len(saved_scopes)}")
        if 'moderator:manage:announcements' in saved_scopes:
            print(f"   ✅ moderator:manage:announcements présent!")
        else:
            print(f"   ❌ moderator:manage:announcements MANQUANT!")
    
    await twitch.close()
    
    print(f"\n🚀 Prochaine étape:")
    print(f"   ./kissbot.sh restart --use-db")
    
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Update bot token scopes")
    parser.add_argument("--bot", default="serda_bot", help="Bot account name")
    args = parser.parse_args()
    
    asyncio.run(update_bot_scopes(args.bot))
