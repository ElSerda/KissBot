#!/usr/bin/env python3
"""
Test détaillé d'un jeu pour voir la langue de description
"""
import asyncio
import yaml
from backends.game_lookup import GameLookup


async def test_description_language():
    """Teste la langue des descriptions"""
    
    with open("config/config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    lookup = GameLookup(config)
    
    game_name = "Stardew Valley"
    
    print(f"Testing: {game_name}")
    print("=" * 80)
    
    game = await lookup.enrich_game_from_igdb_name(game_name)
    
    if game and game.summary:
        print(f"\n📝 Description complète:")
        print(game.summary)
        print(f"\nLength: {len(game.summary)} chars")
        
        # Détecter la langue approximativement
        french_keywords = ["vous", "votre", "est", "des", "les", "un", "une"]
        english_keywords = ["you", "your", "the", "a", "an", "is", "are"]
        
        summary_lower = game.summary.lower()
        fr_count = sum(1 for word in french_keywords if word in summary_lower)
        en_count = sum(1 for word in english_keywords if word in summary_lower)
        
        print(f"\n🔍 Détection langue:")
        print(f"   Mots français: {fr_count}")
        print(f"   Mots anglais: {en_count}")
        
        if fr_count > en_count:
            print("   ➡️ Probablement FRANÇAIS 🇫🇷")
        elif en_count > fr_count:
            print("   ➡️ Probablement ANGLAIS 🇬🇧")
        else:
            print("   ➡️ Indéterminé")
    
    await lookup.close()


if __name__ == "__main__":
    asyncio.run(test_description_language())
