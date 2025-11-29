#!/usr/bin/env python3
"""
Vérifier les scopes réels du token serda_bot
"""

import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.manager import DatabaseManager
from database.crypto import TokenEncryptor
from twitchAPI.twitch import Twitch
import yaml


async def main():
    # Load config
    with open('config/config.yaml') as f:
        config = yaml.safe_load(f)
    
    client_id = config['twitch']['client_id']
    client_secret = config['twitch']['client_secret']
    
    # Connect to DB
    db = DatabaseManager('kissbot.db')
    crypto = TokenEncryptor()
    
    # Get serda_bot
    user = db.get_user_by_login('serda_bot')
    if not user:
        print("❌ User serda_bot not found")
        return
    
    print(f"User: {user['twitch_login']} (ID: {user['twitch_user_id']})")
    
    # Get bot token
    token_data = db.get_tokens(user['id'], token_type='bot')
    if not token_data:
        print("❌ No bot token found")
        return
    
    # Token is already decrypted by DatabaseManager
    access_token = token_data['access_token']
    
    print(f"\nStored scopes in DB:")
    stored_scopes = json.loads(token_data['scopes']) if token_data['scopes'] else []
    for scope in stored_scopes:
        print(f"  - {scope}")
    
    # Validate token with Twitch
    print(f"\nValidating token with Twitch...")
    twitch = await Twitch(client_id, client_secret)
    
    try:
        # Use the token to make a validate call
        # This will tell us if the token is valid and what scopes it actually has
        from twitchAPI.helper import first
        from twitchAPI.oauth import validate_token
        
        validation = await validate_token(access_token)
        
        print(f"\n✅ Token is valid!")
        print(f"Validation data: {validation}")
        print(f"\nActual scopes on Twitch:")
        for scope in validation.get('scopes', []):
            print(f"  - {scope}")
        
        # Compare
        actual_scopes = set(validation.get('scopes', []))
        stored_scopes_set = set(stored_scopes)
        
        if actual_scopes == stored_scopes_set:
            print(f"\n✅ Scopes match!")
        else:
            missing_in_db = actual_scopes - stored_scopes_set
            missing_in_token = stored_scopes_set - actual_scopes
            
            if missing_in_db:
                print(f"\n⚠️ Scopes in token but not in DB:")
                for scope in missing_in_db:
                    print(f"  - {scope}")
            
            if missing_in_token:
                print(f"\n❌ Scopes in DB but NOT in token:")
                for scope in missing_in_token:
                    print(f"  - {scope}")
        
    except Exception as e:
        print(f"❌ Token validation failed: {e}")
        import traceback
        traceback.print_exc()
    
    await twitch.close()


if __name__ == "__main__":
    asyncio.run(main())
