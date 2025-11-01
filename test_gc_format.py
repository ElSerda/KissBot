#!/usr/bin/env python3
"""
Test local pour !gc - Simulation de différents jeux avec descriptions
"""
import asyncio
import sys
from backends.game_lookup import GameLookup
from core.message_types import ChatMessage


async def test_gc_format():
    """Teste le formatage de !gc avec différents jeux"""
    
    # Load config
    import yaml
    with open("config/config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    # Init GameLookup
    lookup = GameLookup(config)
    
    # Liste de jeux à tester (catégories Twitch IGDB)
    test_games = [
        "Whisper Mountain Outbreak",  # Jeu avec description longue
        "Elden Ring",                 # Jeu populaire
        "Baldur's Gate 3",            # Jeu avec description moyenne
        "Hades",                      # Jeu avec description courte
        "Stardew Valley",             # Jeu indie
    ]
    
    print("=" * 80)
    print("TEST !gc FORMAT - Simulation de réponses Twitch")
    print("=" * 80)
    
    for game_name in test_games:
        print(f"\n📺 Testing: {game_name}")
        print("-" * 80)
        
        try:
            # Enrichir depuis IGDB name (comme !gc)
            game = await lookup.enrich_game_from_igdb_name(game_name)
            
            if game:
                # Format COMPACT (sans confidence/sources)
                game_info = lookup.format_result(game, compact=True)
                
                # Simuler le message !gc
                user_login = "el_serda"
                channel = "test_channel"
                
                if game.summary:
                    # Calculer l'espace disponible
                    prefix = f"@{user_login} 🎮 {channel} joue actuellement à {game_info} | "
                    max_summary_len = 450 - len(prefix)
                    
                    # Tronquer intelligemment
                    summary = game.summary[:max_summary_len]
                    if len(game.summary) > max_summary_len:
                        last_dot = summary.rfind('. ')
                        last_space = summary.rfind(' ')
                        if last_dot > max_summary_len * 0.7:
                            summary = summary[:last_dot + 1]
                        elif last_space > max_summary_len * 0.8:
                            summary = summary[:last_space] + "..."
                        else:
                            summary += "..."
                    
                    response_text = f"{prefix}{summary}"
                else:
                    response_text = f"@{user_login} 🎮 {channel} joue actuellement à {game_info} (5 viewers)"
                
                print(f"✅ Response ({len(response_text)} chars):")
                print(response_text)
                
                if game.summary:
                    print(f"\n📝 Original summary length: {len(game.summary)} chars")
                    print(f"📏 Truncated to: {len(summary)} chars")
                
            else:
                print(f"❌ Jeu non trouvé: {game_name}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("Tests terminés")
    print("=" * 80)
    
    await lookup.close()


if __name__ == "__main__":
    asyncio.run(test_gc_format())
