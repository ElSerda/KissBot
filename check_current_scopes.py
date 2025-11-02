#!/usr/bin/env python3
"""
Vérifie les scopes des tokens actuels depuis config.yaml
"""
import asyncio
import aiohttp
import yaml


async def validate_token(access_token: str):
    """Valide un token et retourne les infos"""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://id.twitch.tv/oauth2/validate",
            headers={"Authorization": f"OAuth {access_token}"}
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                return None


async def main():
    # Charger tokens depuis .tio.tokens.json (utilisé par le bot)
    import json
    with open(".tio.tokens.json", "r") as f:
        tokens = json.load(f)
    
    print("=" * 70)
    print("🔍 Vérification des scopes OAuth actuels (.tio.tokens.json)")
    print("=" * 70)
    
    user_names = {
        "1209350837": "serda_bot",
        "44456636": "el_serda"
    }
    
    for user_id, token_data in tokens.items():
        user_name = user_names.get(user_id, user_id)
        print(f"\n📋 {user_name} (ID: {user_id})")
        print("-" * 70)
        
        access_token = token_data["token"]
        validation = await validate_token(access_token)
        
        if validation:
            scopes = validation.get("scopes", [])
            expires_in = validation.get("expires_in", 0)
            
            print(f"✅ Token valide (expire dans {expires_in // 3600}h {(expires_in % 3600) // 60}m)")
            print(f"📜 Scopes actuels:")
            for scope in sorted(scopes):
                print(f"   - {scope}")
            
            # Vérifier scopes requis pour permissions
            required_for_perms = ["moderation:read", "channel:read:vips"]
            missing = [s for s in required_for_perms if s not in scopes]
            
            if missing:
                print(f"\n⚠️  Scopes manquants pour détection permissions:")
                for scope in missing:
                    print(f"   - {scope}")
            else:
                print(f"\n✅ Tous les scopes requis sont présents!")
        else:
            print("❌ Token invalide ou expiré")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
