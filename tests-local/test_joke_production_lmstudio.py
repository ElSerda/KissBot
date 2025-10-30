"""
🚀 TEST PRODUCTION: !joke avec LM Studio + Solution Mistral AI

Test réel avec:
- Vrai LM Studio (Mistral 7B)
- Multiple appels !joke
- Vérification variété réelle
- Mesure cache hit rate
- Streaming debug mode
"""

import asyncio
import sys
import time
import yaml
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from intelligence.joke_cache import JokeCache, get_dynamic_prompt
from intelligence.neural_pathway_manager import NeuralPathwayManager
from intelligence.core import process_llm_request


def load_config():
    """Load configuration from YAML file."""
    with open('config/config.yaml', 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


async def test_joke_production():
    """Test production avec vrai LM Studio"""
    print("=" * 70)
    print("🚀 TEST PRODUCTION: !joke avec Solution Mistral AI")
    print("=" * 70 + "\n")
    
    # Load config
    try:
        config = load_config()
        print("✅ Config loaded")
    except Exception as e:
        print(f"❌ Config load failed: {e}")
        return
    
    # Initialize LLM handler
    try:
        llm_handler = NeuralPathwayManager(config)
        print("✅ LLM handler initialized")
    except Exception as e:
        print(f"❌ LLM handler failed: {e}")
        return
    
    # Initialize cache (5 min TTL)
    joke_cache = JokeCache(ttl_seconds=300, max_size=100)
    print("✅ JokeCache initialized (TTL=5min)\n")
    
    # Base prompt
    base_prompt = "Réponds EN 1 PHRASE MAX EN FRANÇAIS, SANS TE PRÉSENTER, style humoristique : raconte une blague courte"
    user_id = "el_serda_test"
    
    # Test 5 appels !joke
    print("🎭 Simulation 5 appels !joke:\n")
    
    jokes = []
    for i in range(5):
        print(f"📢 !joke #{i+1}")
        
        # 🎲 Prompt dynamique
        dynamic_prompt = get_dynamic_prompt(base_prompt)
        print(f"   Prompt variant: ...{dynamic_prompt[-50:]}")
        
        # 🔑 Cache key
        cache_key = joke_cache.get_key(user_id, dynamic_prompt)
        print(f"   Cache key: {cache_key[-50:]}")
        
        # 💾 Check cache
        cached_joke = joke_cache.get(cache_key)
        if cached_joke:
            print(f"   💾 CACHE HIT!")
            print(f"   🎭 Blague: {cached_joke}\n")
            jokes.append(cached_joke)
            continue
        
        print(f"   💔 Cache MISS - Appel LLM...")
        
        # 🧠 Call LLM
        start_time = time.time()
        response = await process_llm_request(
            llm_handler=llm_handler,
            prompt=dynamic_prompt,
            context="ask",
            user_name=user_id,
            game_cache=None,
            pre_optimized=True,
            stimulus_class="gen_short"
        )
        latency = time.time() - start_time
        
        if response:
            print(f"   ⏱️ Latency: {latency:.2f}s")
            print(f"   🎭 Blague: {response}")
            
            # 💾 Store in cache
            joke_cache.set(cache_key, response)
            print(f"   💾 Stored in cache")
            
            jokes.append(response)
        else:
            print(f"   ❌ LLM failed")
            jokes.append(None)
        
        print()
        
        # Petit délai entre appels
        await asyncio.sleep(0.5)
    
    # Analyse résultats
    print("=" * 70)
    print("📊 ANALYSE RÉSULTATS")
    print("=" * 70 + "\n")
    
    # Vérifier variété
    valid_jokes = [j for j in jokes if j]
    unique_jokes = set(valid_jokes)
    
    print(f"✅ Blagues générées: {len(valid_jokes)}/5")
    print(f"✅ Blagues uniques: {len(unique_jokes)}/{len(valid_jokes)}")
    
    if len(unique_jokes) >= 3:
        print(f"🎉 VARIÉTÉ VALIDÉE (≥3 blagues différentes)")
    else:
        print(f"⚠️ Variété faible ({len(unique_jokes)} blagues différentes)")
    
    # Stats cache
    stats = joke_cache.get_stats()
    print(f"\n📊 Cache Stats:")
    print(f"   Total entries: {stats['total_entries']}")
    print(f"   Total users: {stats['total_users']}")
    print(f"   Cache hits: {stats['hits']}")
    print(f"   Cache misses: {stats['misses']}")
    print(f"   Hit rate: {stats['hit_rate']:.1f}%")
    
    # Afficher blagues
    print(f"\n🎭 Blagues obtenues:")
    for i, joke in enumerate(valid_jokes, 1):
        print(f"   {i}. {joke}")
    
    # Vérifier rotation variant
    print(f"\n🔄 User sessions:")
    print(f"   {user_id}: {joke_cache.user_sessions[user_id]} appels")
    print(f"   Expected variants: v0 (calls 1-3), v1 (calls 4-6)")
    
    print("\n" + "=" * 70)
    print("✅ TEST PRODUCTION TERMINÉ")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_joke_production())
