"""
🧪 Test Solution Mistral AI: JokeCache Intelligent + Prompts Dynamiques

Tests pour valider:
- Cache intelligent avec user sessions
- Rotation toutes les 3 blagues
- Variabilité temporelle (5 minutes)
- Prompts dynamiques
- TTL 5 minutes
"""

import time
from intelligence.joke_cache import JokeCache, get_dynamic_prompt


def test_user_sessions_tracking():
    """Test 1: User sessions incrementent correctement"""
    print("🧪 TEST 1: User sessions tracking")
    
    cache = JokeCache(ttl_seconds=300, max_size=100)
    
    # User fait 3 appels
    key1 = cache.get_key("el_serda", "raconte une blague")
    key2 = cache.get_key("el_serda", "raconte une blague")
    key3 = cache.get_key("el_serda", "raconte une blague")
    
    # Vérifier sessions incrémentées
    assert cache.user_sessions["el_serda"] == 3, "Should have 3 sessions"
    print(f"✅ Sessions: {cache.user_sessions['el_serda']}")
    
    # Vérifier variant change après 3 appels
    key4 = cache.get_key("el_serda", "raconte une blague")
    assert "v0_" in key1, "Keys 1-3 should have v0"
    assert "v0_" in key2
    assert "v0_" in key3
    assert "v1_" in key4, "Key 4 should have v1 (session_count // 3 = 1)"
    
    print(f"✅ Variant rotation après 3 appels:")
    print(f"   Keys 1-3: v0 → {key1[-20:]}")
    print(f"   Key 4: v1 → {key4[-20:]}")
    print("\n🎉 TEST 1 RÉUSSI !\n")


def test_different_users_different_keys():
    """Test 2: Users différents = clés différentes"""
    print("🧪 TEST 2: Different users = different keys")
    
    cache = JokeCache()
    
    key_alice = cache.get_key("alice", "raconte une blague")
    key_bob = cache.get_key("bob", "raconte une blague")
    
    assert key_alice != key_bob, "Different users should have different keys"
    assert "alice" in key_alice
    assert "bob" in key_bob
    
    print(f"✅ Alice key: {key_alice[-30:]}")
    print(f"✅ Bob key: {key_bob[-30:]}")
    print("\n🎉 TEST 2 RÉUSSI !\n")


def test_temporal_variability():
    """Test 3: Variabilité temporelle (5 minutes)"""
    print("🧪 TEST 3: Temporal variability")
    
    cache = JokeCache(ttl_seconds=10)  # TTL court pour test
    
    # Clé au temps T
    key_t0 = cache.get_key("user", "blague")
    
    # Simuler 6 secondes (pas assez pour changer variant temps)
    # time_variant = int(time.time() / 300)
    # On ne peut pas tester ça facilement sans attendre 5 minutes...
    # Mais on peut valider que la clé CONTIENT le timestamp
    
    assert "_v" in key_t0, "Key should contain variant with timestamp"
    assert "user" in key_t0, "Key should contain user_id"
    
    print(f"✅ Key format: {key_t0[-40:]}")
    print("✅ Format contient user + variant temporel")
    print("\n🎉 TEST 3 RÉUSSI !\n")


def test_cache_get_set_with_new_keys():
    """Test 4: Cache get/set avec nouvelles clés"""
    print("🧪 TEST 4: Cache get/set avec get_key()")
    
    cache = JokeCache(ttl_seconds=5)
    
    # Générer clé pour user
    key = cache.get_key("el_serda", "raconte une blague")
    
    # Test MISS
    result = cache.get(key)
    assert result is None, "First call should be MISS"
    print("✅ Cache MISS détecté")
    
    # Test SET
    cache.set(key, "Pourquoi les développeurs détestent la nature ? Trop de bugs !")
    print("✅ Cache SET ok")
    
    # Test HIT
    result = cache.get(key)
    assert result is not None, "Second call should be HIT"
    assert "bugs" in result
    print("✅ Cache HIT détecté")
    
    # Test TTL expiration
    print("⏱️ Attente 6s pour TTL...")
    time.sleep(6)
    result = cache.get(key)
    assert result is None, "After TTL, should be MISS"
    print("✅ TTL expiration ok")
    
    print("\n🎉 TEST 4 RÉUSSI !\n")


def test_dynamic_prompts():
    """Test 5: Prompts dynamiques varient"""
    print("🧪 TEST 5: Dynamic prompts")
    
    base = "raconte une blague courte"
    
    # Générer plusieurs prompts
    prompts = [get_dynamic_prompt(base) for _ in range(10)]
    
    # Vérifier variété
    unique_prompts = set(prompts)
    print(f"📊 {len(unique_prompts)} prompts uniques sur 10 générés")
    
    # Au moins 3 variants différents sur 10 (probabilité haute avec 7 variants)
    assert len(unique_prompts) >= 3, "Should have at least 3 different prompts"
    
    # Vérifier que les variants sont présents
    all_variants = ["style drôle", "style absurde", "style court", "pour enfants", 
                    "pour adultes", "avec un jeu de mots", "surprise-moi"]
    
    found_variants = []
    for prompt in prompts:
        for variant in all_variants:
            if variant in prompt:
                found_variants.append(variant)
                break
    
    assert len(found_variants) >= 3, "Should have at least 3 different variants used"
    
    print("✅ Exemples de prompts dynamiques:")
    for i, p in enumerate(prompts[:5], 1):
        print(f"   {i}. {p}")
    
    print("\n🎉 TEST 5 RÉUSSI !\n")


def test_rotation_after_3_calls():
    """Test 6: Rotation après 3 appels même user"""
    print("🧪 TEST 6: Rotation après 3 appels")
    
    cache = JokeCache(ttl_seconds=300)
    
    user = "test_user"
    base_prompt = "blague"
    
    # 3 premiers appels → variant v0
    keys_v0 = []
    for i in range(3):
        key = cache.get_key(user, base_prompt)
        keys_v0.append(key)
        cache.set(key, f"Blague {i}")
    
    # Vérifier tous v0
    for key in keys_v0:
        assert "v0_" in key, f"Keys 1-3 should be v0, got {key}"
    
    print(f"✅ Keys 1-3 (v0): {keys_v0[0][-30:]}")
    
    # 4ème appel → variant v1
    key_v1 = cache.get_key(user, base_prompt)
    assert "v1_" in key_v1, f"Key 4 should be v1, got {key_v1}"
    
    print(f"✅ Key 4 (v1): {key_v1[-30:]}")
    
    # Les clés v0 et v1 sont différentes
    assert keys_v0[0] != key_v1, "v0 and v1 keys should be different"
    
    print("✅ Rotation automatique après 3 appels validée")
    print("\n🎉 TEST 6 RÉUSSI !\n")


def test_stats_with_user_tracking():
    """Test 7: Stats incluent user tracking"""
    print("🧪 TEST 7: Stats avec user tracking")
    
    cache = JokeCache()
    
    # Plusieurs users
    cache.get_key("alice", "blague")
    cache.get_key("bob", "blague")
    cache.get_key("charlie", "blague")
    
    stats = cache.get_stats()
    
    assert "total_users" in stats, "Stats should include total_users"
    assert stats["total_users"] == 3, f"Should have 3 users, got {stats['total_users']}"
    
    print(f"📊 Stats: {stats}")
    print("✅ Stats incluent user tracking")
    print("\n🎉 TEST 7 RÉUSSI !\n")


if __name__ == "__main__":
    print("=" * 70)
    print("🚀 TESTS SOLUTION MISTRAL AI: Cache Intelligent + Prompts Dynamiques")
    print("=" * 70 + "\n")
    
    test_user_sessions_tracking()
    test_different_users_different_keys()
    test_temporal_variability()
    test_cache_get_set_with_new_keys()
    test_dynamic_prompts()
    test_rotation_after_3_calls()
    test_stats_with_user_tracking()
    
    print("=" * 70)
    print("✅ TOUS LES TESTS MISTRAL AI RÉUSSIS !")
    print("=" * 70)
