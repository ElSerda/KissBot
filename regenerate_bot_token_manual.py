#!/usr/bin/env python3
"""
Régénérer le token serda_bot - MANUEL
Colle l'URL de callback complète quand demandé
"""

import asyncio
import json
import logging
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import yaml
from twitchAPI.twitch import Twitch
from twitchAPI.type import AuthScope

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


async def main():
    """Générer token manuellement"""
    print("=" * 70)
    print("Régénération token serda_bot - MANUEL")
    print("=" * 70)
    
    # Load config
    config_file = Path("config/config.yaml")
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    app_id = config["twitch"]["client_id"]
    app_secret = config["twitch"]["client_secret"]
    
    # Scopes requis pour IRC
    scopes = [
        AuthScope.USER_READ_CHAT,
        AuthScope.USER_WRITE_CHAT,
        AuthScope.USER_BOT,
        AuthScope.CHAT_READ,
        AuthScope.CHAT_EDIT
    ]
    
    scope_str = " ".join([str(s) for s in scopes])
    
    # Générer l'URL d'autorisation
    auth_url = (
        f"https://id.twitch.tv/oauth2/authorize"
        f"?client_id={app_id}"
        f"&redirect_uri=http://localhost:3000"
        f"&response_type=code"
        f"&scope={scope_str.replace(' ', '%20')}"
    )
    
    print(f"\n📋 URL d'autorisation:")
    print(f"\n{auth_url}\n")
    print(f"1️⃣  Ouvre cette URL dans ton navigateur")
    print(f"2️⃣  Connecte-toi avec le compte serda_bot")
    print(f"3️⃣  Autorise l'application")
    print(f"4️⃣  Copie l'URL complète de callback (commence par http://localhost:3000/?code=...)")
    
    callback_url = input("\n📥 Colle l'URL de callback ici: ").strip()
    
    # Parser l'URL pour extraire le code
    parsed = urlparse(callback_url)
    params = parse_qs(parsed.query)
    
    if 'code' not in params:
        print("\n❌ Pas de code dans l'URL !")
        return
    
    code = params['code'][0]
    print(f"\n✅ Code extrait: {code[:20]}...")
    
    # Échanger le code contre un token
    print("\n🔄 Échange du code contre un token...")
    
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://id.twitch.tv/oauth2/token",
            data={
                "client_id": app_id,
                "client_secret": app_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": "http://localhost:3000"
            }
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                access_token = data["access_token"]
                refresh_token = data["refresh_token"]
                
                print(f"✅ Token obtenu: {access_token[:20]}...")
                print(f"✅ Refresh: {refresh_token[:20]}...")
                
                # Valider le token pour obtenir l'user_id
                print("\n🔍 Validation du token...")
                async with session.get(
                    "https://id.twitch.tv/oauth2/validate",
                    headers={"Authorization": f"OAuth {access_token}"}
                ) as val_resp:
                    if val_resp.status == 200:
                        val_data = await val_resp.json()
                        user_id = str(val_data["user_id"])
                        user_login = val_data["login"]
                        
                        print(f"✅ User: {user_login} (ID: {user_id})")
                        print(f"🔑 Scopes: {val_data['scopes']}")
                        
                        # Sauvegarder dans .tio.tokens.json
                        token_file = Path(".tio.tokens.json")
                        tokens_data = {}
                        
                        if token_file.exists():
                            with open(token_file, 'r') as f:
                                tokens_data = json.load(f)
                        
                        tokens_data[user_id] = {
                            "user_id": user_id,
                            "user_login": user_login,
                            "token": access_token,
                            "refresh": refresh_token,
                            "last_validated": "2025-10-31T20:30:00.000000"
                        }
                        
                        with open(token_file, 'w') as f:
                            json.dump(tokens_data, f, indent=4)
                        
                        print(f"\n✅ Token sauvegardé dans {token_file}")
                        print("\n🎉 Terminé ! Le bot peut maintenant se connecter à IRC.")
                    else:
                        error_text = await val_resp.text()
                        print(f"\n❌ Erreur validation: {val_resp.status} - {error_text}")
            else:
                error_text = await resp.text()
                print(f"\n❌ Erreur échange code: {resp.status} - {error_text}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Annulé")
    except Exception as e:
        LOGGER.error(f"Erreur: {e}", exc_info=True)
