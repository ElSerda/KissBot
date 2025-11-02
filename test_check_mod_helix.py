#!/usr/bin/env python3
"""
Test: Vérifier si bot est mod/VIP via Helix API
"""
import asyncio
import yaml
from twitchAPI.twitch import Twitch


async def check_permissions():
    # Load config
    with open("config/config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    client_id = config["twitch"]["client_id"]
    client_secret = config["twitch"]["client_secret"]
    bot_id = config["twitch"]["bot_id"]  # 1209350837
    
    # Load bot token from .tio.tokens.json
    import json
    with open(".tio.tokens.json", "r") as f:
        tokens = json.load(f)
    
    bot_token_data = tokens[bot_id]
    bot_token = bot_token_data["token"]
    bot_refresh = bot_token_data["refresh"]
    
    print("=" * 70)
    print("🔍 Vérification permissions bot via Helix API")
    print("=" * 70)
    print(f"Bot ID: {bot_id}")
    print(f"Token: {bot_token[:20]}...")
    
    # Init Twitch avec user auth
    from twitchAPI.type import AuthScope
    
    twitch = await Twitch(client_id, client_secret)
    scopes = [
        AuthScope.USER_READ_MODERATED_CHANNELS
    ]
    await twitch.set_user_authentication(bot_token, scopes, bot_refresh)
    
    print(f"\n🔍 Channels où le bot est modérateur:")
    print("-" * 70)
    
    try:
        # ⭐ LA solution : get_moderated_channels() avec le token du bot !
        moderated_channels = []
        async for channel in twitch.get_moderated_channels(user_id=bot_id):
            moderated_channels.append(channel.broadcaster_login)
            print(f"   ✅ {channel.broadcaster_login} (ID: {channel.broadcaster_id})")
        
        if not moderated_channels:
            print(f"   ℹ️  Bot n'est mod sur aucun channel")
        
        # Vérifier si el_serda est dans la liste
        channel_name = "el_serda"
        channel_id = "44456636"
        is_mod_on_el_serda = "el_serda" in moderated_channels
        
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        is_mod_on_el_serda = False
    
    print(f"\n📺 Channel: {channel_name} (ID: {channel_id})")
    print("-" * 70)
    
    if is_mod_on_el_serda:
        print(f"✅ Bot EST mod sur #{channel_name}")
        is_mod = True
    else:
        print(f"❌ Bot N'EST PAS mod sur #{channel_name}")
        is_mod = False
    
    # Pour VIP, on garde la détection IRC (badges) car nécessite token broadcaster
    is_vip = False
    print(f"ℹ️  VIP: Détection via IRC badges (token broadcaster requis pour Helix)")
    
    # Rate limit
    if is_mod or is_vip:
        rate = 100
        delay = 30.0 / (100 * 0.7)
        if is_mod and is_vip:
            status = "MOD + VIP 🛡️👑"
        elif is_mod:
            status = "MOD 🛡️"
        else:
            status = "VIP 👑"
    else:
        rate = 20
        delay = 30.0 / (20 * 0.7)
        status = "User 👤"
    
    print(f"\n📊 Status: {status}")
    print(f"   Rate limit: {rate} msg/30s")
    print(f"   Safe delay: {delay:.2f}s")
    
    await twitch.close()
    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(check_permissions())
