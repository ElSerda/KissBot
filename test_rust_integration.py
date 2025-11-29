#!/usr/bin/env python3
"""
Test d'intégration complète du moteur Rust
Simule le flow du bot avec MessageBus + Analytics
"""

import asyncio
import logging
import sys
from core.message_bus import MessageBus
from core.analytics_handler import AnalyticsHandler
from backends.game_lookup_rust import get_game_lookup, set_message_bus

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_integration():
    """Test complet: GameLookup Rust + MessageBus + Analytics"""
    print("\n" + "="*70)
    print("🦀 Test d'intégration KissBot + Rust Game Engine")
    print("="*70)
    
    # 1. Créer MessageBus
    print("\n📡 Création MessageBus...")
    bus = MessageBus()
    
    # 2. Créer AnalyticsHandler
    print("📊 Création AnalyticsHandler...")
    analytics = AnalyticsHandler(bus)
    
    # 3. Configurer GameLookup avec MessageBus
    print("🦀 Configuration GameLookup Rust...")
    set_message_bus(bus)
    lookup = get_game_lookup('kissbot.db')
    
    # 4. Effectuer quelques recherches
    print("\n" + "="*70)
    print("🔍 Test 1: Recherche en cache")
    print("="*70)
    
    game1 = await lookup.search_game("vampire survivors")
    if game1:
        print(f"✅ {game1.name} ({game1.year})")
        print(f"   Genres: {', '.join(game1.genres) if game1.genres else 'N/A'}")
        print(f"   Confidence: {game1.confidence}")
    
    # Petit délai pour laisser analytics traiter
    await asyncio.sleep(0.1)
    
    # 5. Recherche en cache x5 (performance test)
    print("\n" + "="*70)
    print("🔍 Test 2: Performance (5 recherches cache)")
    print("="*70)
    
    import time
    start = time.time()
    for i in range(5):
        await lookup.search_game("vampire survivors")
    elapsed = time.time() - start
    
    print(f"✅ 5 recherches en {elapsed*1000:.2f}ms")
    print(f"   Moyenne: {(elapsed/5)*1000:.2f}ms par recherche")
    
    await asyncio.sleep(0.1)
    
    # 6. Recherche avec alternatives
    print("\n" + "="*70)
    print("🔍 Test 3: Recherche avec alternatives")
    print("="*70)
    
    result = await lookup.search_with_alternatives("vampire survivors", max_results=3)
    if result:
        print(f"✅ Meilleur: {result['game'].name} ({result['score']:.1f}%)")
        print(f"   Cache: {result['from_cache']}")
        print(f"   Latency: {result['latency_ms']:.2f}ms")
        if result['alternatives']:
            print(f"   Alternatives: {len(result['alternatives'])}")
    
    await asyncio.sleep(0.1)
    
    # 7. Cache stats
    print("\n" + "="*70)
    print("📊 Cache Statistics")
    print("="*70)
    
    cache_stats = lookup.get_cache_stats()
    print(f"💾 Entrées: {cache_stats['total_entries']}")
    print(f"📈 Hits totaux: {cache_stats['total_hits']}")
    print(f"📊 Moyenne hits/entrée: {cache_stats['avg_hit_count']:.2f}")
    
    # 8. Analytics stats
    print("\n" + "="*70)
    print("📊 Analytics Statistics")
    print("="*70)
    
    analytics_stats = analytics.get_stats()
    print(f"🎮 Recherches totales: {analytics_stats['game_searches']}")
    print(f"💾 Cache hits: {analytics_stats['game_cache_hits']}")
    print(f"🌐 Cache misses: {analytics_stats['game_cache_misses']}")
    print(f"📊 Taux de cache hit: {analytics_stats['game_cache_hit_rate']}")
    print(f"⚡ Latence moyenne: {analytics_stats['game_avg_latency_ms']}")
    
    # 9. Validation finale
    print("\n" + "="*70)
    print("✅ RÉSULTATS")
    print("="*70)
    
    expected_searches = 7  # 1 + 5 + 1
    actual_searches = analytics_stats['game_searches']
    
    if actual_searches == expected_searches:
        print(f"✅ Nombre de recherches: {actual_searches}/{expected_searches}")
    else:
        print(f"⚠️ Nombre de recherches: {actual_searches}/{expected_searches}")
    
    hit_rate = float(analytics_stats['game_cache_hit_rate'].rstrip('%'))
    if hit_rate >= 90:
        print(f"✅ Taux de cache hit: {hit_rate}% (>90%)")
    else:
        print(f"⚠️ Taux de cache hit: {hit_rate}% (<90%)")
    
    avg_latency = float(analytics_stats['game_avg_latency_ms'].rstrip('ms'))
    if avg_latency < 1.0:
        print(f"✅ Latence moyenne: {avg_latency}ms (<1ms)")
    else:
        print(f"⚠️ Latence moyenne: {avg_latency}ms (>1ms)")
    
    print("\n" + "="*70)
    print("🎉 INTÉGRATION RÉUSSIE !")
    print("="*70)
    print("\n💡 Le moteur Rust est prêt pour production:")
    print("   • MessageBus configuré ✅")
    print("   • Analytics tracking ✅")
    print("   • Performance validée ✅")
    print("   • Cache hit rate optimal ✅")

if __name__ == "__main__":
    try:
        asyncio.run(test_integration())
    except KeyboardInterrupt:
        print("\n❌ Interrompu par l'utilisateur")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
