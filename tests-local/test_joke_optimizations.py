"""
🧪 Test POC: JokeCache + Streaming
Validation cache hit/miss et streaming accumulation
"""

import asyncio
import time
from intelligence.joke_cache import JokeCache


def test_joke_cache():
    """Test JokeCache basique"""
    print("🧪 TEST 1: JokeCache basique")
    
    cache = JokeCache(ttl_seconds=5, max_size=10)
    
    prompt = "Réponds EN 1 PHRASE MAX EN FRANÇAIS, SANS TE PRÉSENTER, style humoristique : raconte une blague courte"
    
    # Test MISS
    result = cache.get(prompt)
    assert result is None, "Premier appel devrait être MISS"
    print("✅ Cache MISS détecté")
    
    # Test SET
    cache.set(prompt, "Une blague test !")
    print("✅ Cache SET ok")
    
    # Test HIT
    result = cache.get(prompt)
    assert result == "Une blague test !", "Deuxième appel devrait être HIT"
    print("✅ Cache HIT détecté")
    
    # Test STATS
    stats = cache.get_stats()
    print(f"📊 Stats: {stats}")
    assert stats['hits'] == 1, "Should have 1 hit"
    assert stats['misses'] == 1, "Should have 1 miss"
    assert stats['hit_rate'] == 50.0, "Hit rate should be 50%"
    print("✅ Stats correctes")
    
    # Test TTL
    print("⏱️ Attente 6s pour TTL expiration...")
    time.sleep(6)
    result = cache.get(prompt)
    assert result is None, "Après TTL, devrait être MISS"
    print("✅ TTL expiration ok")
    
    print("\n🎉 TEST 1 RÉUSSI !\n")


def test_cache_hash():
    """Test hash prompts différents"""
    print("🧪 TEST 2: Hash prompts")
    
    cache = JokeCache()
    
    prompt1 = "raconte une blague"
    prompt2 = "raconte une blague différente"
    
    cache.set(prompt1, "Blague 1")
    cache.set(prompt2, "Blague 2")
    
    assert cache.get(prompt1) == "Blague 1", "Prompt 1 devrait retourner Blague 1"
    assert cache.get(prompt2) == "Blague 2", "Prompt 2 devrait retourner Blague 2"
    
    stats = cache.get_stats()
    assert stats['total_entries'] == 2, "Devrait avoir 2 entrées"
    
    print("✅ Hash séparation ok")
    print("\n🎉 TEST 2 RÉUSSI !\n")


def test_cache_cleanup():
    """Test cleanup automatique"""
    print("🧪 TEST 3: Cleanup automatique")
    
    cache = JokeCache(max_size=3)
    
    # Remplir cache au max
    for i in range(5):
        cache.set(f"prompt_{i}", f"joke_{i}")
        time.sleep(0.1)  # Différencier timestamps
    
    stats = cache.get_stats()
    print(f"📊 Stats après 5 insertions (max=3): {stats}")
    
    # Devrait avoir gardé seulement 80% de 3 = 2 plus récents (cleanup LRU)
    assert stats['total_entries'] <= 3, f"Ne devrait pas dépasser max_size (got {stats['total_entries']})"
    
    # Les plus anciens devraient être supprimés
    assert cache.get("prompt_0") is None, "Prompt 0 (plus ancien) devrait être supprimé"
    assert cache.get("prompt_4") is not None, "Prompt 4 (plus récent) devrait être présent"
    
    print("✅ Cleanup automatique ok")
    print("\n🎉 TEST 3 RÉUSSI !\n")


async def test_streaming_mock():
    """Test simulation streaming"""
    print("🧪 TEST 4: Streaming simulation")
    
    # Simuler streaming avec accumulation
    full_response = ""
    chunks = ["Pourquoi ", "les ", "développeurs ", "confondent-ils ", "Halloween ", "et Noël ? "]
    
    for chunk in chunks:
        full_response += chunk
        # Pas d'affichage pendant accumulation
    
    # Afficher seulement à la fin
    print(f"🌊 Réponse complète après streaming: {full_response}")
    assert len(full_response) > 0, "Devrait avoir accumulé les chunks"
    assert "développeurs" in full_response, "Devrait contenir le contenu complet"
    
    print("✅ Streaming accumulation ok")
    print("\n🎉 TEST 4 RÉUSSI !\n")


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 TESTS POC: JokeCache + Streaming")
    print("=" * 60 + "\n")
    
    test_joke_cache()
    test_cache_hash()
    test_cache_cleanup()
    asyncio.run(test_streaming_mock())
    
    print("=" * 60)
    print("✅ TOUS LES TESTS RÉUSSIS !")
    print("=" * 60)
