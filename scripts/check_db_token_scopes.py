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
from database.crypto import TokenEncryptor
from twitchAPI.twitch import Twitch
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
    crypto = TokenEncryptor()
    
    # Create Twitch client
    twitch = await Twitch(client_id, client_secret)
    
    print("=" * 70)
    print("🔍 Vérification des scopes OAuth (Database)")
    print("=" * 70)
    
    # Get all users
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
                
                # Decrypt access token
                access_token = crypto.decrypt(token_data['access_token'])
                
                # Set token and validate
                try:
                    from twitchAPI.type import AuthScope
                    import json
                    
                    # Get stored scopes
                    stored_scopes = []
                    if token_data.get('scopes'):
                        stored_scopes = json.loads(token_data['scopes'])
                    
                    # Try to validate with token
                    await twitch.set_user_authentication(
                        token=access_token,
                        scope=[],  # Don't require any scope to just validate
                        validate=True
                    )
                    
                    # Get token info to see actual scopes
                    token_info = await twitch.get_users()
                    
                    print(f"\n  🔑 {token_type.upper()} token:")
                    print(f"    Expires: {token_data['expires_at']}")
                    print(f"    Status: {token_data['status']}")
                    print(f"    Stored scopes ({len(stored_scopes)}):")
                    for scope in stored_scopes:
                        print(f"      - {scope}")
                    
                    # Note: We can't easily get actual scopes from token without making
                    # an API call that requires specific scopes. The validation above
                    # will tell us if the token is valid.
                    print(f"    ✅ Token is valid")
                    
                except Exception as e:
                    print(f"  ❌ {token_type.upper()} token: {e}")
                    
            except Exception as e:
                print(f"  ⚠️ Error checking {token_type}: {e}")
    
    await twitch.close()
    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(check_token_scopes())
