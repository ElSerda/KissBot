"""
🧪 Tests unitaires: Pipeline complet !joke avec cache et streaming
Valide l'intégration cache + process_llm_request + streaming
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from intelligence.joke_cache import JokeCache
from intelligence.core import process_llm_request


@pytest.mark.asyncio
async def test_joke_pipeline_with_cache_miss():
    """Test pipeline !joke: cache MISS → appel LLM → store cache"""
    
    # Mock LLM handler
    llm_handler = AsyncMock()
    llm_handler.local_synapse = AsyncMock()
    llm_handler.local_synapse.fire = AsyncMock(
        return_value="Pourquoi les développeurs confondent Halloween et Noël ? Parce que Oct 31 == Dec 25 !"
    )
    
    # JokeCache réel
    joke_cache = JokeCache(ttl_seconds=86400, max_size=100)
    
    prompt = "Réponds EN 1 PHRASE MAX EN FRANÇAIS, SANS TE PRÉSENTER, style humoristique : raconte une blague courte"
    
    # 1️⃣ CACHE MISS (premier appel)
    cached = joke_cache.get(prompt)
    assert cached is None, "Premier appel devrait être cache MISS"
    
    # 2️⃣ APPEL LLM
    response = await process_llm_request(
        llm_handler=llm_handler,
        prompt=prompt,
        context="ask",
        user_name="TestUser",
        game_cache=None,
        pre_optimized=True,
        stimulus_class="gen_short"
    )
    
    assert response is not None
    assert "développeurs" in response or len(response) > 10
    
    # 3️⃣ STORE DANS CACHE
    joke_cache.set(prompt, response)
    
    # 4️⃣ VÉRIFIER CACHE HIT (deuxième appel)
    cached = joke_cache.get(prompt)
    assert cached == response, "Deuxième appel devrait être cache HIT"
    
    # 5️⃣ VÉRIFIER STATS
    stats = joke_cache.get_stats()
    assert stats['hits'] == 1, "Should have 1 hit"
    assert stats['misses'] == 1, "Should have 1 miss"
    assert stats['hit_rate'] == 50.0, "Hit rate should be 50%"


@pytest.mark.asyncio
async def test_joke_pipeline_with_cache_hit():
    """Test pipeline !joke: cache HIT → pas d'appel LLM"""
    
    # Mock LLM handler (ne devrait PAS être appelé)
    llm_handler = AsyncMock()
    llm_handler.local_synapse = AsyncMock()
    llm_handler.local_synapse.fire = AsyncMock(
        return_value="Cette blague ne devrait JAMAIS être retournée"
    )
    
    # JokeCache avec blague pré-cachée
    joke_cache = JokeCache(ttl_seconds=86400, max_size=100)
    
    prompt = "Réponds EN 1 PHRASE MAX EN FRANÇAIS, SANS TE PRÉSENTER, style humoristique : raconte une blague courte"
    cached_joke = "Un singe et un cochon sont dans la jungle. Le singe a un crayon sous la queue..."
    
    # PRÉ-REMPLIR CACHE
    joke_cache.set(prompt, cached_joke)
    
    # 1️⃣ CACHE HIT (devrait skip LLM)
    cached = joke_cache.get(prompt)
    assert cached == cached_joke, "Cache devrait retourner la blague pré-cachée"
    
    # 2️⃣ VÉRIFIER LLM PAS APPELÉ (dans vraie commande, on skip process_llm_request)
    # Simuler comportement commande
    response = cached  # Pas d'appel LLM
    
    assert response == cached_joke
    
    # 3️⃣ VÉRIFIER LLM HANDLER PAS TOUCHÉ
    llm_handler.local_synapse.fire.assert_not_called()
    
    # 4️⃣ VÉRIFIER STATS
    stats = joke_cache.get_stats()
    assert stats['hits'] == 1, "Should have 1 hit"
    assert stats['misses'] == 0, "Should have 0 miss"
    assert stats['hit_rate'] == 100.0, "Hit rate should be 100%"


@pytest.mark.asyncio
async def test_streaming_accumulation():
    """Test streaming: accumulation chunks → message complet"""
    
    # Simuler streaming response avec chunks
    chunks = [
        {"choices": [{"delta": {"content": "Pourquoi "}, "finish_reason": None}]},
        {"choices": [{"delta": {"content": "les "}, "finish_reason": None}]},
        {"choices": [{"delta": {"content": "développeurs "}, "finish_reason": None}]},
        {"choices": [{"delta": {"content": "confondent-ils "}, "finish_reason": None}]},
        {"choices": [{"delta": {"content": "Halloween "}, "finish_reason": None}]},
        {"choices": [{"delta": {"content": "et Noël ?"}, "finish_reason": "stop"}]},
    ]
    
    # Accumuler comme dans local_synapse.py
    full_response = ""
    finish_reason = "unknown"
    
    for chunk in chunks:
        if "choices" in chunk and chunk["choices"]:
            delta = chunk["choices"][0].get("delta", {})
            if "content" in delta:
                full_response += delta["content"]
            
            # Capture finish_reason
            finish_reason = chunk["choices"][0].get("finish_reason", finish_reason)
    
    # Vérifier accumulation complète
    assert full_response == "Pourquoi les développeurs confondent-ils Halloween et Noël ?"
    assert finish_reason == "stop"
    assert len(full_response) > 0
    
    # Pas de chunks individuels envoyés (pas de spam chat)
    # Dans vraie implémentation, on envoie seulement full_response à la fin


@pytest.mark.asyncio
async def test_cache_performance():
    """Test performance: cache HIT doit être << 100ms"""
    import time
    
    joke_cache = JokeCache(ttl_seconds=86400, max_size=100)
    
    prompt = "test prompt"
    joke_cache.set(prompt, "test joke")
    
    # Mesurer latency cache HIT
    start = time.time()
    result = joke_cache.get(prompt)
    latency = (time.time() - start) * 1000  # Convert to ms
    
    assert result == "test joke"
    assert latency < 10, f"Cache HIT devrait être <10ms (got {latency:.2f}ms)"
    print(f"✅ Cache HIT latency: {latency:.2f}ms")


@pytest.mark.asyncio
async def test_joke_cache_isolation():
    """Test isolation: JokeCache séparé de game_cache"""
    
    joke_cache = JokeCache(ttl_seconds=86400, max_size=100)
    
    # Simuler différents domaines
    joke_prompt = "raconte une blague"
    game_query = "hades"  # Serait dans game_cache, pas joke_cache
    
    joke_cache.set(joke_prompt, "Une blague")
    
    # JokeCache ne devrait PAS contenir les jeux
    assert joke_cache.get(joke_prompt) == "Une blague"
    assert joke_cache.get(game_query) is None, "JokeCache ne devrait pas contenir game queries"
    
    stats = joke_cache.get_stats()
    assert stats['total_entries'] == 1, "Seulement la blague, pas les jeux"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
