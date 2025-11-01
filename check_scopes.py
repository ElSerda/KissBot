#!/usr/bin/env python3
"""
Script pour vérifier les scopes des tokens Twitch
"""
import asyncio
import yaml
from pathlib import Path
import aiohttp


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


async def check_token_scopes():
    """Vérifie les scopes de tous les tokens dans la config"""
    # Charger config
    config_file = Path("config/config.yaml")
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    twitch_config = config.get("twitch", {})
    tokens = twitch_config.get("tokens", {})
    
    print("=" * 70)
    print("🔍 Vérification des scopes des tokens")
    print("=" * 70)
    
    for account_name, token_info in tokens.items():
        print(f"\n📋 {account_name} (ID: {token_info['user_id']})")
        print("-" * 70)
        
        access_token = token_info.get("access_token")
        
        try:
            validation = await validate_token(access_token)
            
            if validation:
                print(f"✅ Token valide")
                print(f"   Client ID: {validation.get('client_id', 'N/A')}")
                print(f"   User ID: {validation.get('user_id', 'N/A')}")
                print(f"   Login: {validation.get('login', 'N/A')}")
                print(f"   Expiration: {validation.get('expires_in', 0)} secondes")
                
                scopes = validation.get('scopes', [])
                print(f"\n   Scopes ({len(scopes)}):")
                for scope in sorted(scopes):
                    print(f"     • {scope}")
                
                # Vérifier les scopes critiques pour le bot
                print(f"\n   🎯 Scopes requis pour le bot:")
                required_scopes = {
                    "chat:read": "chat:read" in scopes,
                    "chat:edit": "chat:edit" in scopes,
                    "user:read:chat": "user:read:chat" in scopes,
                    "user:write:chat": "user:write:chat" in scopes,
                    "user:bot": "user:bot" in scopes,
                }
                
                for scope_name, has_scope in required_scopes.items():
                    status = "✅" if has_scope else "❌"
                    desc = ""
                    if scope_name == "user:write:chat":
                        desc = " (Helix send_chat_message + BADGE)"
                    elif scope_name == "user:bot":
                        desc = " (Badge bot officiel)"
                    elif scope_name == "user:read:chat":
                        desc = " (EventSub channel.chat.message)"
                    print(f"     {status} {scope_name}{desc}")
                
            else:
                print("❌ Token invalide ou expiré")
                
        except Exception as e:
            print(f"❌ Erreur: {e}")
    
    print("\n" + "=" * 70)
    print("💡 Pour ajouter des scopes manquants:")
    print("   1. Va sur https://dev.twitch.tv/console/apps")
    print("   2. Regénère le token avec les scopes requis")
    print("   3. Ou utilise un script OAuth pour re-authoriser")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(check_token_scopes())
