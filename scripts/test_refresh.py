#!/usr/bin/env python3
"""Test manual token refresh"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.manager import DatabaseManager
from twitchAPI.twitch import Twitch
import yaml


async def main():
    # Load config
    with open('config/config.yaml') as f:
        config = yaml.safe_load(f)
    
    client_id = config['twitch']['client_id']
    client_secret = config['twitch']['client_secret']
    
    # Get token from DB
    db = DatabaseManager('kissbot.db')
    user = db.get_user_by_login('serda_bot')
    token_data = db.get_tokens(user['id'], token_type='bot')
    
    print(f"Current token expires: {token_data['expires_at']}")
    print(f"Refresh token: {token_data['refresh_token'][:20]}...")
    
    # Try to refresh
    twitch = await Twitch(client_id, client_secret)
    
    try:
        print("\nAttempting token refresh...")
        from twitchAPI.oauth import refresh_access_token
        
        new_access, new_refresh = await refresh_access_token(
            refresh_token=token_data['refresh_token'],
            app_id=client_id,
            app_secret=client_secret
        )
        
        print(f"\n✅ Token refreshed successfully!")
        print(f"New access token: {new_access[:20]}...")
        print(f"New refresh token: {new_refresh[:20]}...")
        
        # Save to DB
        db.store_tokens(
            user_id=user['id'],
            access_token=new_access,
            refresh_token=new_refresh,
            expires_in=14400,
            scopes=[],  # Will be validated later
            token_type='bot',
            status='valid'
        )
        print(f"\n✅ New token saved to database")
        
    except Exception as e:
        print(f"\n❌ Refresh failed: {e}")
        import traceback
        traceback.print_exc()
    
    await twitch.close()


if __name__ == "__main__":
    asyncio.run(main())
