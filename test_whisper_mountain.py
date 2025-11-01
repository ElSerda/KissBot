#!/usr/bin/env python3
"""
Test spécifique pour Whisper Mountain Outbreak - Debug enrichissement
"""
import asyncio
import yaml
from backends.game_lookup import GameLookup


async def test_whisper_mountain():
    """Test détaillé de Whisper Mountain Outbreak"""
    
    # Load config
    with open("config/config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    # Init GameLookup
    lookup = GameLookup(config)
    
    game_name = "Whisper Mountain Outbreak"
    
    print("=" * 80)
    print(f"TEST DÉTAILLÉ: {game_name}")
    print("=" * 80)
    
    # 1. Enrichissement IGDB
    print("\n🔍 Étape 1: Enrichissement depuis IGDB name...")
    game = await lookup.enrich_game_from_igdb_name(game_name)
    
    if not game:
        print("❌ Jeu non trouvé")
        return
    
    print(f"✅ Jeu trouvé: {game.name}")
    print(f"   Year: {game.year}")
    print(f"   Platforms: {', '.join(game.platforms) if game.platforms else 'N/A'}")
    print(f"   Rating RAWG: {game.rating_rawg}")
    print(f"   Metacritic: {game.metacritic}")
    print(f"   Confidence: {game.confidence}")
    print(f"   Sources: {game.source_count}")
    
    # 2. Description
    print(f"\n📝 Étape 2: Description (summary)")
    if game.summary:
        print(f"   Length: {len(game.summary)} chars")
        print(f"   Content: {game.summary}")
    else:
        print("   ❌ Pas de description")
    
    # 3. Format standard (!gi)
    print(f"\n🎮 Étape 3: Format standard (!gi)")
    standard_format = lookup.format_result(game, compact=False)
    print(f"   Length: {len(standard_format)} chars")
    print(f"   Output: {standard_format}")
    
    # 4. Format compact (!gc)
    print(f"\n🎯 Étape 4: Format compact (!gc)")
    compact_format = lookup.format_result(game, compact=True)
    print(f"   Length: {len(compact_format)} chars")
    print(f"   Output: {compact_format}")
    
    # 5. Simulation message Twitch complet
    print(f"\n💬 Étape 5: Simulation message Twitch (!gc)")
    user_login = "el_serda"
    channel = "pelerin_"
    
    if game.summary:
        # Calculer l'espace disponible
        prefix = f"@{user_login} 🎮 {channel} joue actuellement à {compact_format} | "
        max_summary_len = 450 - len(prefix)
        
        print(f"   Prefix: '{prefix}'")
        print(f"   Prefix length: {len(prefix)} chars")
        print(f"   Max summary: {max_summary_len} chars")
        print(f"   Original summary: {len(game.summary)} chars")
        
        # Tronquer intelligemment
        summary = game.summary[:max_summary_len]
        if len(game.summary) > max_summary_len:
            last_dot = summary.rfind('. ')
            last_space = summary.rfind(' ')
            print(f"   Last dot at: {last_dot}")
            print(f"   Last space at: {last_space}")
            print(f"   Threshold 70%: {max_summary_len * 0.7}")
            print(f"   Threshold 80%: {max_summary_len * 0.8}")
            
            if last_dot > max_summary_len * 0.7:
                summary = summary[:last_dot + 1]
                print(f"   ✂️ Cut at last dot")
            elif last_space > max_summary_len * 0.8:
                summary = summary[:last_space] + "..."
                print(f"   ✂️ Cut at last space")
            else:
                summary += "..."
                print(f"   ✂️ Hard cut with ...")
        
        response_text = f"{prefix}{summary}"
    else:
        response_text = f"@{user_login} 🎮 {channel} joue actuellement à {compact_format} (5 viewers)"
    
    print(f"\n📤 MESSAGE FINAL:")
    print(f"   Length: {len(response_text)} chars")
    print(f"   Limite Twitch: 500 chars")
    print(f"   Marge: {500 - len(response_text)} chars")
    print()
    print(response_text)
    
    # Vérification limite Twitch
    if len(response_text) > 500:
        print(f"\n⚠️ ATTENTION: Message trop long ! ({len(response_text)} > 500)")
    else:
        print(f"\n✅ Message OK (< 500 chars)")
    
    print("\n" + "=" * 80)
    
    await lookup.close()


if __name__ == "__main__":
    asyncio.run(test_whisper_mountain())
