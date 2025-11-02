#!/usr/bin/env python3
"""
Régénérer le token serda_bot avec les scopes IRC + permissions
Scopes requis:
- user:read:chat (lire le chat)
- user:write:chat (écrire dans le chat)
- user:bot (agir en tant que bot)
- chat:read (ancien scope, peut-être requis aussi)
- chat:edit (ancien scope, peut-être requis aussi)
- user:read:moderated_channels (⭐ lister où bot est mod - LA solution!)
"""

import asyncio
import json
import logging
from pathlib import Path

import yaml
from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.type import AuthScope

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


async def main():
    """Générer token avec OAuth flow"""
    print("=" * 70)
    print("Régénération token serda_bot avec scopes IRC")
    print("=" * 70)
    
    # Load config
    config_file = Path("config/config.yaml")
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    app_id = config["twitch"]["client_id"]
    app_secret = config["twitch"]["client_secret"]
    
    # Scopes requis pour IRC + détection permissions
    scopes = [
        AuthScope.USER_READ_CHAT,   # Lire le chat
        AuthScope.USER_WRITE_CHAT,  # Écrire dans le chat
        AuthScope.USER_BOT,         # Agir en tant que bot
        AuthScope.CHAT_READ,        # Ancien scope (legacy)
        AuthScope.CHAT_EDIT,        # Ancien scope (legacy)
        AuthScope.USER_READ_MODERATED_CHANNELS  # ⭐ Lister où bot est mod (LA solution!)
    ]
    
    print(f"\n🔑 Scopes requis:")
    for scope in scopes:
        print(f"  - {scope}")
    
    print(f"\n⚠️  Un navigateur va s'ouvrir pour autoriser l'application.")
    print(f"    Connectez-vous avec le compte serda_bot !")
    input("\nAppuyez sur ENTRÉE pour continuer...")
    
    # Init Twitch
    twitch = await Twitch(app_id, app_secret)
    
    # OAuth flow avec port 3000 (configuré dans l'app Twitch)
    auth = UserAuthenticator(
        twitch, 
        scopes, 
        force_verify=False,
        url='http://localhost:3000'
    )
    token, refresh_token = await auth.authenticate()
    
    print(f"\n✅ Token obtenu !")
    print(f"   Token: {token[:20]}...")
    print(f"   Refresh: {refresh_token[:20]}...")
    
    # Valider pour obtenir user_id
    await twitch.set_user_authentication(token, scopes, refresh_token)
    users = []
    async for user in twitch.get_users():
        users.append(user)
    
    if users:
        user = users[0]
        user_id = user.id
        user_login = user.login
        print(f"   User: {user_login} (ID: {user_id})")
        
        # Sauvegarder dans .tio.tokens.json
        token_file = Path(".tio.tokens.json")
        tokens_data = {}
        
        if token_file.exists():
            with open(token_file, 'r') as f:
                tokens_data = json.load(f)
        
        tokens_data[user_id] = {
            "user_id": user_id,
            "user_login": user_login,
            "token": token,
            "refresh": refresh_token,
            "last_validated": "2025-10-31T20:10:00.000000"
        }
        
        with open(token_file, 'w') as f:
            json.dump(tokens_data, f, indent=4)
        
        print(f"\n✅ Token sauvegardé dans {token_file}")
    else:
        print("\n❌ Impossible de récupérer l'user_id")
    
    await twitch.close()
    print("\n✅ Terminé !")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Annulé")
    except Exception as e:
        LOGGER.error(f"Erreur: {e}", exc_info=True)
