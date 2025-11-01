#!/usr/bin/env python3
"""
Test du fallback Steam FR → EN
"""
import asyncio
import yaml
from backends.game_lookup import GameLookup


async def test_steam_fallback():
    """Teste la hiérarchie Steam FR → EN → RAWG"""
    
    with open("config/config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    lookup = GameLookup(config)
    
    # Jeux pour tester le fallback
    test_cases = [
        ("Hades", "Jeu populaire, devrait avoir FR"),
        ("Stardew Valley", "Indie, peut-être pas de FR"),
        ("Whisper Mountain Outbreak", "Jeu français"),
        ("Dwarf Fortress", "Jeu niche, probablement pas de FR"),
    ]
    
    print("=" * 80)
    print("TEST FALLBACK: Steam FR → Steam EN → RAWG EN")
    print("=" * 80)
    
    for game_name, description in test_cases:
        print(f"\n📺 Testing: {game_name} ({description})")
        print("-" * 80)
        
        try:
            game = await lookup.enrich_game_from_igdb_name(game_name)
            
            if game and game.summary:
                summary_preview = game.summary[:100] + "..." if len(game.summary) > 100 else game.summary
                print(f"✅ Description trouvée ({len(game.summary)} chars):")
                print(f"   {summary_preview}")
                print(f"   Source: {game.primary_source}")
            elif game:
                print(f"⚠️ Jeu trouvé mais pas de description")
                print(f"   Source: {game.primary_source}")
            else:
                print(f"❌ Jeu non trouvé")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print("\n" + "=" * 80)
    await lookup.close()


if __name__ == "__main__":
    asyncio.run(test_steam_fallback())
