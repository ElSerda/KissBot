#!/usr/bin/env python3
"""
Test du wrapper Rust Game Engine
Vérifie la compatibilité avec l'API Python existante
"""

import asyncio
import logging
from backends.game_lookup_rust import GameLookup, get_game_lookup

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_basic_search():
    """Test recherche basique"""
    print("\n" + "="*60)
    print("🧪 Test 1: Recherche basique")
    print("="*60)
    
    lookup = get_game_lookup("kissbot.db")
    
    # Test avec query en cache
    game = await lookup.search_game("vampire survivors")
    
    if game:
        print(f"✅ Trouvé: {game.name}")
        print(f"   Année: {game.year}")
        print(f"   Genres: {', '.join(game.genres) if game.genres else 'N/A'}")
        print(f"   Metacritic: {game.metacritic or 'N/A'}")
        print(f"   Confidence: {game.confidence}")
    else:
        print("❌ Aucun résultat")

async def test_with_alternatives():
    """Test recherche avec alternatives"""
    print("\n" + "="*60)
    print("🧪 Test 2: Recherche avec alternatives")
    print("="*60)
    
    lookup = get_game_lookup("kissbot.db")
    
    result = await lookup.search_with_alternatives("vampire", max_results=5)
    
    if result:
        print(f"✅ Meilleur match: {result['game'].name} ({result['score']:.1f}%)")
        print(f"   From cache: {result['from_cache']}")
        print(f"   Latency: {result['latency_ms']:.2f}ms")
        print(f"   Ranking: {result['ranking_method']}")
        
        if result['alternatives']:
            print(f"\n📋 Alternatives ({len(result['alternatives'])}):")
            for i, alt in enumerate(result['alternatives'][:3], 1):
                print(f"   {i}. {alt.name}")
    else:
        print("❌ Aucun résultat")

async def test_cache_stats():
    """Test statistiques cache"""
    print("\n" + "="*60)
    print("🧪 Test 3: Statistiques du cache")
    print("="*60)
    
    lookup = get_game_lookup("kissbot.db")
    stats = lookup.get_cache_stats()
    
    print(f"📊 Cache:")
    print(f"   Entrées: {stats['total_entries']}")
    print(f"   Hits totaux: {stats['total_hits']}")
    print(f"   Moyenne hits/entrée: {stats['avg_hit_count']:.2f}")

async def test_performance():
    """Test performance"""
    print("\n" + "="*60)
    print("🧪 Test 4: Performance (10 recherches)")
    print("="*60)
    
    lookup = get_game_lookup("kissbot.db")
    
    import time
    queries = ["vampire survivors"] * 10
    
    start = time.time()
    for query in queries:
        await lookup.search_game(query)
    elapsed = time.time() - start
    
    avg_ms = (elapsed / len(queries)) * 1000
    print(f"⚡ Performance:")
    print(f"   Total: {elapsed*1000:.2f}ms")
    print(f"   Moyenne: {avg_ms:.2f}ms/recherche")
    print(f"   Throughput: {len(queries)/elapsed:.1f} req/s")

async def main():
    """Run all tests"""
    print("🎮 Test du Wrapper Rust Game Engine")
    
    try:
        await test_basic_search()
        await test_with_alternatives()
        await test_cache_stats()
        await test_performance()
        
        print("\n" + "="*60)
        print("🎉 TOUS LES TESTS RÉUSSIS !")
        print("="*60)
        print("\n💡 Pour utiliser dans le bot:")
        print("   from backends.game_lookup_rust import get_game_lookup")
        print("   lookup = get_game_lookup('kissbot.db')")
        print("   game = await lookup.search_game(query)")
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
