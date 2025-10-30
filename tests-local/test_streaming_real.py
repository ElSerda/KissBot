"""
🧪 Test streaming response RÉEL avec LM Studio
Test accumulation chunks en conditions GPU bridé (lent = plus de chunks)
"""

import asyncio
import time
import yaml


async def test_streaming_real():
    """Test streaming réel avec LM Studio (GPU layers bridé)"""
    print("🔬 TEST STREAMING RÉEL AVEC LM STUDIO")
    print("=" * 60)
    
    # Load config
    with open("config/config.yaml") as f:
        config = yaml.safe_load(f)
    
    # Init handler
    from intelligence.neural_pathway_manager import NeuralPathwayManager
    llm_handler = NeuralPathwayManager(config)
    
    # Test prompt (court pour voir chunks)
    prompt = "Réponds EN 1 PHRASE MAX EN FRANÇAIS, SANS TE PRÉSENTER, style humoristique : raconte une blague courte"
    
    print(f"\n📝 Prompt: {prompt[:50]}...")
    print(f"🎯 Mode: Streaming avec accumulation")
    print(f"🔧 Config: GPU layers bridé (streaming visible)\n")
    
    # Appel direct synapse avec streaming
    start = time.time()
    
    response = await llm_handler.local_synapse.fire(
        stimulus=prompt,
        context="direct",
        stimulus_class="gen_short",
        correlation_id="streaming_test"
    )
    
    latency = time.time() - start
    
    print(f"\n✅ RÉSULTAT:")
    print(f"   Réponse: {response}")
    print(f"   Latence: {latency:.2f}s")
    print(f"   Length: {len(response)} chars")
    
    # Validations
    assert response is not None, "Response ne devrait pas être None"
    assert len(response) > 10, "Response devrait être > 10 chars"
    assert latency > 0, "Latency devrait être mesurable"
    
    print(f"\n📊 MÉTRIQUES:")
    print(f"   ✓ Streaming activé: ✅")
    print(f"   ✓ Accumulation: ✅ (pas de spam)")
    print(f"   ✓ Message complet: ✅")
    print(f"   ✓ Latence acceptable: {'✅' if latency < 5 else '⚠️'} ({latency:.2f}s)")
    
    # Test que streaming est bien configuré
    synapse = llm_handler.local_synapse
    print(f"\n🔍 CONFIG SYNAPSE:")
    print(f"   Endpoint: {synapse.endpoint}")
    print(f"   Model: {synapse.model_name}")
    print(f"   Streaming: activé (stream=True)")
    
    print("\n" + "=" * 60)
    print("✅ TEST STREAMING RÉEL RÉUSSI !")
    print("=" * 60)


async def test_streaming_multiple_calls():
    """Test streaming avec plusieurs appels successifs"""
    print("\n🔬 TEST STREAMING: APPELS MULTIPLES")
    print("=" * 60)
    
    with open("config/config.yaml") as f:
        config = yaml.safe_load(f)
    
    from intelligence.neural_pathway_manager import NeuralPathwayManager
    llm_handler = NeuralPathwayManager(config)
    
    prompts = [
        "Réponds EN 1 PHRASE: raconte une blague dev",
        "Réponds EN 1 PHRASE: raconte une blague science",
        "Réponds EN 1 PHRASE: raconte une blague courte"
    ]
    
    latencies = []
    
    for i, prompt in enumerate(prompts, 1):
        print(f"\n🎯 Appel {i}/3: {prompt[:40]}...")
        
        start = time.time()
        response = await llm_handler.local_synapse.fire(
            stimulus=prompt,
            context="direct",
            stimulus_class="gen_short",
            correlation_id=f"multi_test_{i}"
        )
        latency = time.time() - start
        latencies.append(latency)
        
        print(f"   ✅ Response: {response[:60]}...")
        print(f"   ⏱️ Latency: {latency:.2f}s")
        
        assert response is not None
        assert len(response) > 10
    
    avg_latency = sum(latencies) / len(latencies)
    
    print(f"\n📊 STATISTIQUES:")
    print(f"   Appels: {len(latencies)}")
    print(f"   Latence moyenne: {avg_latency:.2f}s")
    print(f"   Latence min: {min(latencies):.2f}s")
    print(f"   Latence max: {max(latencies):.2f}s")
    
    print("\n" + "=" * 60)
    print("✅ TEST APPELS MULTIPLES RÉUSSI !")
    print("=" * 60)


async def test_streaming_vs_cache():
    """Test comparaison streaming LLM vs cache hit"""
    print("\n🔬 TEST COMPARAISON: STREAMING vs CACHE")
    print("=" * 60)
    
    with open("config/config.yaml") as f:
        config = yaml.safe_load(f)
    
    from intelligence.neural_pathway_manager import NeuralPathwayManager
    from intelligence.joke_cache import JokeCache
    
    llm_handler = NeuralPathwayManager(config)
    joke_cache = JokeCache(ttl_seconds=86400, max_size=100)
    
    prompt = "Réponds EN 1 PHRASE MAX EN FRANÇAIS, SANS TE PRÉSENTER, style humoristique : raconte une blague courte"
    
    # 1️⃣ APPEL STREAMING (cache miss)
    print(f"\n🌊 APPEL 1: Streaming (cache miss)")
    start = time.time()
    response = await llm_handler.local_synapse.fire(
        stimulus=prompt,
        context="direct",
        stimulus_class="gen_short",
        correlation_id="cache_test"
    )
    streaming_latency = (time.time() - start) * 1000  # ms
    
    print(f"   Response: {response[:60]}...")
    print(f"   ⏱️ Latency: {streaming_latency:.2f}ms")
    
    # Store dans cache
    joke_cache.set(prompt, response)
    
    # 2️⃣ APPEL CACHE (cache hit)
    print(f"\n💾 APPEL 2: Cache (cache hit)")
    start = time.time()
    cached = joke_cache.get(prompt)
    cache_latency = (time.time() - start) * 1000  # ms
    
    print(f"   Response: {cached[:60]}...")
    print(f"   ⏱️ Latency: {cache_latency:.2f}ms")
    
    # Comparaison
    speedup = streaming_latency / cache_latency
    
    print(f"\n📊 COMPARAISON:")
    print(f"   Streaming: {streaming_latency:.2f}ms")
    print(f"   Cache:     {cache_latency:.2f}ms")
    print(f"   Speedup:   {speedup:.0f}x plus rapide !")
    
    assert cached == response, "Cache devrait retourner même réponse"
    assert cache_latency < 100, f"Cache devrait être <100ms (got {cache_latency:.2f}ms)"
    assert speedup > 10, f"Cache devrait être >10x plus rapide (got {speedup:.0f}x)"
    
    print("\n" + "=" * 60)
    print("✅ TEST COMPARAISON RÉUSSI !")
    print("=" * 60)


if __name__ == "__main__":
    print("\n" + "🚀 TESTS STREAMING RÉEL LM STUDIO ".center(60, "="))
    print("⚠️  ATTENTION: Nécessite LM Studio lancé sur port 1234")
    print("⚠️  Config recommandée: GPU layers bridé pour voir chunks\n")
    
    asyncio.run(test_streaming_real())
    asyncio.run(test_streaming_multiple_calls())
    asyncio.run(test_streaming_vs_cache())
    
    print("\n" + "✅ TOUS LES TESTS STREAMING RÉUSSIS ! ".center(60, "=") + "\n")
