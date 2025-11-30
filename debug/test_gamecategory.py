"""
🔧 Debug Script - Test !gamecategory command
Teste l'auto-détection du jeu du stream actuel via Twitch API
"""
import asyncio
import yaml
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def test_gamecategory_logic():
    """Test de la logique !gamecategory sans TwitchIO"""
    print("🔧 Debug: Test !gamecategory logic\n")
    
    # 1. Load config
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    print("✅ Config chargée")
    
    # 2. Simulate Twitch API calls (mock)
    print("\n📡 Simulation Twitch API:")
    
    # Mock: User fetch
    broadcaster_name = "el_serda"  # Change ça pour tester un autre channel
    print(f"  → fetch_users(names=['{broadcaster_name}'])")
    
    # Mock: Stream fetch
    mock_user_id = "123456789"
    print(f"  → fetch_streams(user_ids=['{mock_user_id}'])")
    
    # Mock: Stream data
    mock_stream_active = True  # Change à False pour tester offline
    mock_game_name = "Hades"   # Change le jeu ici
    
    if not mock_stream_active:
        print(f"\n❌ Stream offline: '@{broadcaster_name} n'est pas sur un jeu Nullos !'")
        return
    
    if not mock_game_name:
        print(f"\n❌ Pas de jeu: '@{broadcaster_name} n'est pas sur un jeu Nullos !'")
        return
    
    print(f"\n🎮 Jeu détecté: {mock_game_name}")
    
    # 3. Test enrich_game_from_igdb_name (nouvelle méthode)
    print(f"\n🔍 Enrichissement IGDB via enrich_game_from_igdb_name()...")
    from backends.game_lookup import GameLookup
    
    lookup = GameLookup(config)
    result = await lookup.enrich_game_from_igdb_name(mock_game_name)
    
    if result:
        print(f"\n✅ Jeu trouvé:")
        print(f"  Name: {result.name}")
        print(f"  Year: {result.year}")
        print(f"  Rating RAWG: {result.rating_rawg}")
        print(f"  Metacritic: {result.metacritic}")
        print(f"  Confidence: {result.confidence}")
        print(f"  Primary Source: {result.primary_source}")
        
        # Format pour Twitch
        response = lookup.format_result(result)
        print(f"\n💬 Réponse Twitch:\n  {response}")
    else:
        print(f"\n❌ Jeu '{mock_game_name}' non trouvé dans les bases de données")


async def test_real_twitch_api():
    """Test avec vraie API Twitch (nécessite credentials)"""
    print("\n" + "="*60)
    print("🌐 Test avec VRAIE API Twitch")
    print("="*60 + "\n")
    
    try:
        import aiohttp
        
        # Load config
        config_path = Path(__file__).parent.parent / "config" / "config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        client_id = config.get('twitch', {}).get('client_id')
        client_secret = config.get('twitch', {}).get('client_secret')
        
        if not client_id or not client_secret:
            print("❌ Credentials Twitch manquants dans config.yaml")
            return
        
        print(f"✅ Client ID: {client_id[:10]}...")
        
        # 1. Get App Access Token
        print("\n📡 Récupération App Access Token...")
        async with aiohttp.ClientSession() as session:
            token_url = "https://id.twitch.tv/oauth2/token"
            token_params = {
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "client_credentials"
            }
            
            async with session.post(token_url, params=token_params) as resp:
                if resp.status != 200:
                    print(f"❌ Erreur token: {resp.status}")
                    return
                
                token_data = await resp.json()
                access_token = token_data.get("access_token")
                print(f"✅ Token obtenu: [REDACTED]")
            
            # 2. Get stream info
            broadcaster_name = "elserda"  # Change ça pour tester
            print(f"\n🔍 Recherche stream pour: {broadcaster_name}")
            
            headers = {
                "Client-ID": client_id,
                "Authorization": f"Bearer {access_token}"
            }
            
            # Get user ID
            user_url = f"https://api.twitch.tv/helix/users?login={broadcaster_name}"
            async with session.get(user_url, headers=headers) as resp:
                if resp.status != 200:
                    print(f"❌ Erreur user: {resp.status}")
                    return
                
                user_data = await resp.json()
                users = user_data.get("data", [])
                
                if not users:
                    print(f"❌ Utilisateur '{broadcaster_name}' non trouvé")
                    return
                
                user_id = users[0]["id"]
                print(f"✅ User ID: {user_id}")
            
            # Get stream
            stream_url = f"https://api.twitch.tv/helix/streams?user_id={user_id}"
            async with session.get(stream_url, headers=headers) as resp:
                if resp.status != 200:
                    print(f"❌ Erreur stream: {resp.status}")
                    return
                
                stream_data = await resp.json()
                streams = stream_data.get("data", [])
                
                if not streams:
                    print(f"\n❌ @{broadcaster_name} n'est pas sur un jeu Nullos ! (offline)")
                    return
                
                stream = streams[0]
                game_name = stream.get("game_name")
                
                if not game_name:
                    print(f"\n❌ @{broadcaster_name} n'est pas sur un jeu Nullos ! (Just Chatting?)")
                    return
                
                print(f"\n🎮 Jeu en cours: {game_name}")
                print(f"👁️  Viewers: {stream.get('viewer_count')}")
                print(f"📺 Titre: {stream.get('title')}")
                
                # Test enrich_game_from_igdb_name
                print(f"\n🔍 Enrichissement IGDB via enrich_game_from_igdb_name()...")
                from backends.game_lookup import GameLookup
                
                lookup = GameLookup(config)
                result = await lookup.enrich_game_from_igdb_name(game_name)
                
                if result:
                    response = lookup.format_result(result)
                    print(f"\n💬 Réponse finale:\n  {response}")
                else:
                    print(f"\n❌ Jeu '{game_name}' non trouvé dans RAWG/Steam")
    
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("🎮 KissBot - Debug !gamecategory\n")
    
    # Test 1: Logic avec mocks
    asyncio.run(test_gamecategory_logic())
    
    # Test 2: Vraie API Twitch (optionnel)
    print("\n" + "="*60)
    response = input("\n🌐 Tester avec la vraie API Twitch ? (y/n): ")
    if response.lower() == 'y':
        asyncio.run(test_real_twitch_api())
    else:
        print("\n✅ Tests terminés !")
