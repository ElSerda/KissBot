#!/usr/bin/env python3
"""
Example usage of KissBot Game Engine Python bindings
"""

import kissbot_game_engine

def main():
    print(f"🎮 KissBot Game Engine v{kissbot_game_engine.__version__}")
    print()
    
    # Create engine
    engine = kissbot_game_engine.GameEngine("../kissbot.db")
    
    # Search for a game
    print("🔍 Searching for 'vampire survivors'...")
    result = engine.search("vampire survivors", max_results=5, use_cache=True)
    
    print(f"\n✅ Found: {result['game']['name']}")
    print(f"   Score: {result['score']:.1f}%")
    print(f"   Provider: {result['provider']}")
    print(f"   From cache: {result['from_cache']}")
    print(f"   Latency: {result['latency_ms']:.2f}ms")
    print(f"   Ranking: {result['ranking_method']}")
    
    if result['alternatives']:
        print(f"\n📋 Alternatives ({len(result['alternatives'])}):")
        for i, alt in enumerate(result['alternatives'][:3], 1):
            print(f"   {i}. {alt['name']}")
    
    # Cache stats
    print("\n📊 Cache Statistics:")
    stats = engine.cache_stats()
    print(f"   Total entries: {stats['total_entries']}")
    print(f"   Total hits: {stats['total_hits']}")
    print(f"   Avg hits/entry: {stats['avg_hit_count']:.2f}")

if __name__ == "__main__":
    main()
