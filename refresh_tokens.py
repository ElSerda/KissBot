#!/usr/bin/env python3
"""
Script pour refresh les tokens expirés avec les refresh_tokens
"""
import asyncio
import yaml
from pathlib import Path
import aiohttp


async def refresh_token(client_id: str, client_secret: str, refresh_token: str):
    """Refresh un access token avec le refresh token"""
    url = "https://id.twitch.tv/oauth2/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data) as response:
            if response.status == 200:
                return await response.json()
            else:
                error = await response.text()
                print(f"❌ Erreur HTTP {response.status}: {error}")
                return None


async def validate_token(access_token: str):
    """Valide un token et retourne ses infos"""
    url = "https://id.twitch.tv/oauth2/validate"
    headers = {"Authorization": f"OAuth {access_token}"}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            else:
                return None


async def refresh_all_tokens():
    """Refresh tous les tokens dans la config"""
    config_file = Path("config/config.yaml")
    
    # Charger config
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    twitch_config = config.get("twitch", {})
    tokens = twitch_config.get("tokens", {})
    client_id = twitch_config.get("client_id")
    client_secret = twitch_config.get("client_secret")
    
    print("=" * 70)
    print("🔄 Refresh des tokens Twitch")
    print("=" * 70)
    
    updated = False
    
    for account_name, token_info in tokens.items():
        print(f"\n📋 {account_name} (ID: {token_info['user_id']})")
        print("-" * 70)
        
        old_access = token_info.get("access_token")
        old_refresh = token_info.get("refresh_token")
        
        # Vérifier si le token actuel est valide
        validation = await validate_token(old_access)
        
        if validation:
            print("✅ Token actuel encore valide")
            expires = validation.get('expires_in', 0)
            print(f"   Expire dans: {expires} secondes ({expires // 3600}h {(expires % 3600) // 60}m)")
            
            scopes = validation.get('scopes', [])
            print(f"\n   Scopes actuels ({len(scopes)}):")
            for scope in sorted(scopes):
                print(f"     • {scope}")
            
            # Vérifier si on a tous les scopes requis
            required = ["chat:read", "chat:edit", "user:read:chat", "user:write:chat", "user:bot"]
            missing = [s for s in required if s not in scopes]
            
            if missing:
                print(f"\n   ⚠️  Scopes manquants: {', '.join(missing)}")
                print(f"   💡 Il faut re-autoriser l'app avec les bons scopes")
            else:
                print(f"\n   ✅ Tous les scopes requis sont présents!")
            
            continue
        
        # Token expiré, on refresh
        print("⏳ Token expiré, refresh en cours...")
        
        result = await refresh_token(client_id, client_secret, old_refresh)
        
        if result:
            new_access = result.get("access_token")
            new_refresh = result.get("refresh_token")
            
            # Valider le nouveau token
            validation = await validate_token(new_access)
            
            if validation:
                print("✅ Token refreshé avec succès!")
                print(f"   Login: {validation.get('login')}")
                print(f"   User ID: {validation.get('user_id')}")
                print(f"   Expire dans: {validation.get('expires_in')} secondes")
                
                scopes = validation.get('scopes', [])
                print(f"\n   Scopes ({len(scopes)}):")
                for scope in sorted(scopes):
                    print(f"     • {scope}")
                
                # Mettre à jour dans le dict
                token_info["access_token"] = new_access
                token_info["refresh_token"] = new_refresh
                updated = True
                
                # Vérifier les scopes requis
                required = ["chat:read", "chat:edit", "user:read:chat", "user:write:chat", "user:bot"]
                missing = [s for s in required if s not in scopes]
                
                if missing:
                    print(f"\n   ⚠️  Scopes manquants: {', '.join(missing)}")
                else:
                    print(f"\n   ✅ Tous les scopes requis sont présents!")
            else:
                print("❌ Impossible de valider le nouveau token")
        else:
            print("❌ Échec du refresh")
    
    # Sauvegarder la config mise à jour
    if updated:
        print("\n" + "=" * 70)
        print("💾 Sauvegarde des nouveaux tokens dans config.yaml...")
        
        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        print("✅ Configuration mise à jour !")
    else:
        print("\n" + "=" * 70)
        print("ℹ️  Aucune mise à jour nécessaire")
    
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(refresh_all_tokens())
