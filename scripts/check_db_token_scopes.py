#!/usr/bin/env python3
"""
Vérifier les scopes réels des tokens stockés dans la database.
Compare les scopes enregistrés avec les scopes réels sur Twitch.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.manager import DatabaseManager
from twitchAPI.oauth import validate_token
import yaml


async def check_token_scopes():
    """Vérifie les scopes de tous les tokens en DB"""
    
    # Load config for client_id/secret
    with open('config/config.yaml') as f:
        config = yaml.safe_load(f)
    
    client_id = config['twitch']['client_id']
    client_secret = config['twitch']['client_secret']
    
    # Connect to DB
    db = DatabaseManager('kissbot.db')
    
    print("=" * 70)
    print("🔍 Vérification des scopes OAuth (Database)")
    print("=" * 70)
    
    # Get all users (includes bot + broadcasters)
    users = db.get_all_users()
    
    for user in users:
        print(f"\n📋 {user['twitch_login']} (ID: {user['twitch_user_id']})")
        print("-" * 70)
        
        # Get tokens for this user
        for token_type in ['bot', 'broadcaster']:
            try:
                token_data = db.get_tokens(user['id'], token_type=token_type)
                if not token_data:
                    continue
                
                # Tokens are already decrypted by DatabaseManager
                access_token = token_data['access_token']
                
                # Set token and validate
                try:
                    from twitchAPI.type import AuthScope
                    import json
                    
                    # Get stored scopes
                    stored_scopes = []
                    if token_data.get('scopes'):
                        stored_scopes = json.loads(token_data['scopes'])
                    
                    # Validate token directly via Twitch OAuth endpoint
                    validation = await validate_token(access_token)
                    raw_scopes = validation.get('scopes', []) or []
                    actual_scopes = [s.value if hasattr(s, 'value') else str(s) for s in raw_scopes]
                    login = validation.get('login')
                    user_id = validation.get('user_id')
                    expires_in = validation.get('expires_in')
                    
                    print(f"\n  🔑 {token_type.upper()} token:")
                    print(f"    Expires (DB): {token_data['expires_at']}")
                    if expires_in is not None:
                        print(f"    Expires (Twitch): {expires_in}s")
                    print(f"    Status: {token_data['status']}")
                    print(f"    Stored scopes ({len(stored_scopes)}):")
                    for scope in stored_scopes:
                        print(f"      - {scope}")
                    print(f"    Actual scopes ({len(actual_scopes)}):")
                    for scope in actual_scopes:
                        print(f"      - {scope}")
                    if login:
                        print(f"    Twitch login: {login} (ID: {user_id})")
                    
                    # Compare stored vs actual scopes
                    missing = set(stored_scopes) - set(actual_scopes)
                    extra = set(actual_scopes) - set(stored_scopes)
                    if missing:
                        print(f"    ⚠️  Missing scopes in Twitch: {sorted(missing)}")
                    if extra:
                        print(f"    ℹ️  Extra scopes on Twitch: {sorted(extra)}")
                    print(f"    ✅ Token is valid")
                    
                except Exception as e:
                    print(f"  ❌ {token_type.upper()} token: {e}")
                    
            except Exception as e:
                print(f"  ⚠️ Error checking {token_type}: {e}")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(check_token_scopes())
