"""
🔥 TEST ÉTENDU avec le modèle LLM local - Plus de jeux, plus de scénarios
On va stresser le système d'enrichissement adaptatif !
"""
import sys
import os
import asyncio
import yaml

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backends.game_cache import GameCache
from intelligence.core import process_llm_request
from intelligence.neural_pathway_manager import NeuralPathwayManager


async def test_extended_adaptive_prompts():
    """Test étendu avec plusieurs jeux et scénarios variés."""
    
    print("\n" + "="*80)
    print("🔥 TEST ÉTENDU : LLM local avec 8+ jeux différents")
    print("="*80)
    
    # Load config
    config_path = "config/config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Setup LLM handler
    print("\n🚀 Initialisation du Neural Pathway Manager...")
    llm_handler = NeuralPathwayManager(config)
    
    # Setup cache
    import tempfile
    temp_dir = tempfile.mkdtemp()
    cache_file = os.path.join(temp_dir, "test_games.json")
    cache = GameCache(config={"cache": {"duration_hours": 1}}, cache_file=cache_file)
    
    print(f"✅ LLM connecté : {config['llm']['model_endpoint']}")
    print(f"✅ Modèle : {config['llm']['model_name']}\n")
    
    # ========================================
    # BATCH 1 : Jeux indie populaires
    # ========================================
    print("="*80)
    print("🎮 BATCH 1 : Jeux indie avec données variables")
    print("="*80)
    
    # Test 1 : Stardew Valley (données riches)
    cache.set("stardew_valley", {
        "name": "Stardew Valley",
        "year": "2016",
        "platforms": ["PC", "Switch", "PS4", "Xbox", "Mobile"],
        "genres": ["Simulation", "RPG", "Indie"],
        "description": "A farming simulation game where you inherit your grandfather's old farm and build a new life in the countryside"
    })
    
    print("\n💎 TEST 1 : Stardew Valley (DONNÉES RICHES)")
    print("-" * 80)
    print("💬 Question : 'C'est quoi Stardew Valley?'")
    response1 = await process_llm_request(
        llm_handler=llm_handler,
        prompt="C'est quoi Stardew Valley?",
        context="ask",
        user_name="testuser",
        game_cache=cache
    )
    print(f"🤖 {response1}\n")
    
    # Test 2 : Hades (données moyennes - pas de description)
    cache.set("hades", {
        "name": "Hades",
        "year": "2020",
        "platforms": ["PC", "Switch", "PS4", "PS5", "Xbox"],
        "genres": ["Action", "Roguelike", "Indie"]
    })
    
    print("\n📊 TEST 2 : Hades (DONNÉES MOYENNES - pas de description)")
    print("-" * 80)
    print("💬 Question : 'Parle-moi de Hades'")
    response2 = await process_llm_request(
        llm_handler=llm_handler,
        prompt="Parle-moi de Hades",
        context="ask",
        user_name="testuser",
        game_cache=cache
    )
    print(f"🤖 {response2}\n")
    
    # Test 3 : Undertale (juste nom + année)
    cache.set("undertale", {
        "name": "Undertale",
        "year": "2015"
    })
    
    print("\n📦 TEST 3 : Undertale (DONNÉES PAUVRES - juste année)")
    print("-" * 80)
    print("💬 Question : 'Undertale c'est bien?'")
    response3 = await process_llm_request(
        llm_handler=llm_handler,
        prompt="Undertale c'est bien?",
        context="ask",
        user_name="testuser",
        game_cache=cache
    )
    print(f"🤖 {response3}\n")
    
    # ========================================
    # BATCH 2 : AAA Games
    # ========================================
    print("="*80)
    print("🎮 BATCH 2 : Jeux AAA avec contexte riche")
    print("="*80)
    
    # Test 4 : Elden Ring (données complètes)
    cache.set("elden_ring", {
        "name": "Elden Ring",
        "year": "2022",
        "platforms": ["PC", "PS4", "PS5", "Xbox One", "Xbox Series X/S"],
        "genres": ["Action", "RPG", "Adventure"],
        "description": "An open-world action RPG developed by FromSoftware in collaboration with George R.R. Martin, featuring challenging combat and vast exploration"
    })
    
    print("\n💎 TEST 4 : Elden Ring (DONNÉES COMPLÈTES)")
    print("-" * 80)
    print("💬 Question : 'Elden Ring c'est difficile?'")
    response4 = await process_llm_request(
        llm_handler=llm_handler,
        prompt="Elden Ring c'est difficile?",
        context="ask",
        user_name="testuser",
        game_cache=cache
    )
    print(f"🤖 {response4}\n")
    
    # Test 5 : The Witcher 3 (données riches)
    cache.set("witcher_3", {
        "name": "The Witcher 3: Wild Hunt",
        "year": "2015",
        "platforms": ["PC", "PS4", "Xbox One", "Switch"],
        "genres": ["RPG", "Action", "Adventure"],
        "description": "A story-driven open world RPG set in a visually stunning fantasy universe full of meaningful choices and impactful consequences"
    })
    
    print("\n💎 TEST 5 : The Witcher 3 (DONNÉES RICHES)")
    print("-" * 80)
    print("💬 Question : 'The Witcher 3 ça parle de quoi?'")
    response5 = await process_llm_request(
        llm_handler=llm_handler,
        prompt="The Witcher 3 ça parle de quoi?",
        context="ask",
        user_name="testuser",
        game_cache=cache
    )
    print(f"🤖 {response5}\n")
    
    # ========================================
    # BATCH 3 : Edge cases
    # ========================================
    print("="*80)
    print("🎮 BATCH 3 : Cas limites et edge cases")
    print("="*80)
    
    # Test 6 : Jeu avec juste le nom (très pauvre)
    cache.set("terraria", {
        "name": "Terraria"
    })
    
    print("\n📦 TEST 6 : Terraria (ULTRA PAUVRE - juste nom)")
    print("-" * 80)
    print("💬 Question : 'C'est quoi Terraria?'")
    response6 = await process_llm_request(
        llm_handler=llm_handler,
        prompt="C'est quoi Terraria?",
        context="ask",
        user_name="testuser",
        game_cache=cache
    )
    print(f"🤖 {response6}\n")
    
    # Test 7 : Jeu pas en cache
    print("\n❌ TEST 7 : Minecraft (PAS EN CACHE)")
    print("-" * 80)
    print("💬 Question : 'Minecraft c'est quoi?'")
    response7 = await process_llm_request(
        llm_handler=llm_handler,
        prompt="Minecraft c'est quoi?",
        context="ask",
        user_name="testuser",
        game_cache=cache
    )
    print(f"🤖 {response7}\n")
    
    # Test 8 : Jeu avec genres multiples et description longue
    cache.set("cyberpunk_2077", {
        "name": "Cyberpunk 2077",
        "year": "2020",
        "platforms": ["PC", "PS4", "PS5", "Xbox One", "Xbox Series X/S"],
        "genres": ["RPG", "Action", "Shooter", "Adventure"],
        "description": "An open-world action-adventure RPG set in Night City, a megalopolis obsessed with power, glamour and body modification where you play as V, a mercenary outlaw"
    })
    
    print("\n💎 TEST 8 : Cyberpunk 2077 (DONNÉES TRÈS RICHES)")
    print("-" * 80)
    print("💬 Question : 'Cyberpunk 2077 ça se passe où?'")
    response8 = await process_llm_request(
        llm_handler=llm_handler,
        prompt="Cyberpunk 2077 ça se passe où?",
        context="ask",
        user_name="testuser",
        game_cache=cache
    )
    print(f"🤖 {response8}\n")
    
    # ========================================
    # BATCH 4 : Questions contextuelles
    # ========================================
    print("="*80)
    print("🎮 BATCH 4 : Questions avec contexte implicite")
    print("="*80)
    
    # Test 9 : Question sur gameplay (devrait trigger enrichissement)
    print("\n🎯 TEST 9 : Question gameplay sur Stardew Valley (déjà en cache)")
    print("-" * 80)
    print("💬 Question : 'Le gameplay de Stardew est comment?'")
    response9 = await process_llm_request(
        llm_handler=llm_handler,
        prompt="Le gameplay de Stardew est comment?",
        context="ask",
        user_name="testuser",
        game_cache=cache
    )
    print(f"🤖 {response9}\n")
    
    # Test 10 : Question comparative (2 jeux en cache)
    print("\n🎯 TEST 10 : Comparaison Hades vs Celeste")
    print("-" * 80)
    print("💬 Question : 'Hades ou Celeste, lequel est le plus dur?'")
    response10 = await process_llm_request(
        llm_handler=llm_handler,
        prompt="Hades ou Celeste, lequel est le plus dur?",
        context="ask",
        user_name="testuser",
        game_cache=cache
    )
    print(f"🤖 {response10}\n")
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)
    
    print("\n" + "="*80)
    print("✅ TEST ÉTENDU TERMINÉ !")
    print("="*80 + "\n")
    
    print("\n📊 RÉSUMÉ DES TESTS :")
    print("=" * 80)
    print("✅ TEST 1 : Stardew Valley (RICHE) → STRICT attendu")
    print("✅ TEST 2 : Hades (MOYEN, pas de desc) → PARTIEL attendu")
    print("✅ TEST 3 : Undertale (PAUVRE, juste année) → PARTIEL attendu")
    print("✅ TEST 4 : Elden Ring (COMPLET) → STRICT attendu")
    print("✅ TEST 5 : Witcher 3 (RICHE) → STRICT attendu")
    print("✅ TEST 6 : Terraria (ULTRA PAUVRE) → ORIGINAL attendu")
    print("✅ TEST 7 : Minecraft (PAS EN CACHE) → ORIGINAL attendu")
    print("✅ TEST 8 : Cyberpunk 2077 (TRÈS RICHE) → STRICT attendu")
    print("✅ TEST 9 : Gameplay Stardew (contexte) → STRICT attendu")
    print("✅ TEST 10 : Comparaison (2 jeux) → Fusion intelligente ?")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    print("\n🎮 LM Studio doit être lancé sur http://127.0.0.1:1234\n")
    asyncio.run(test_extended_adaptive_prompts())
