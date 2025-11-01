"""
🔥 TEST RÉEL avec le modèle LLM local (LM Studio)
On va voir comment le LLM réagit aux prompts PARTIEL vs STRICT
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


async def test_real_llm_adaptive_prompts():
    """Test le système d'enrichissement adaptatif avec le VRAI LLM local."""
    
    print("\n" + "="*80)
    print("🔥 TEST RÉEL : LLM local avec prompts adaptatifs")
    print("="*80)
    
    # Load config
    config_path = "config/config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Setup LLM handler (REAL Neural Pathway Manager)
    print("\n🚀 Initialisation du Neural Pathway Manager (LM Studio)...")
    llm_handler = NeuralPathwayManager(config)
    
    # Setup cache
    import tempfile
    temp_dir = tempfile.mkdtemp()
    cache_file = os.path.join(temp_dir, "test_games.json")
    cache = GameCache(config={"cache": {"duration_hours": 1}}, cache_file=cache_file)
    
    print(f"✅ LLM connecté : {config['llm']['model_endpoint']}")
    print(f"✅ Modèle : {config['llm']['model_name']}")
    
    # ========================================
    # TEST 1 : Données PAUVRES (juste nom)
    # ========================================
    print("\n" + "="*80)
    print("📦 TEST 1 : Données PAUVRES (juste nom 'Brotato')")
    print("-" * 80)
    
    cache.set("brotato", {"name": "Brotato"})
    
    print("\n💬 Question : 'C'est quoi le gameplay de Brotato?'")
    print("📝 Prompt envoyé : ORIGINAL (pas assez de données)")
    print("\n⏳ Attente réponse LLM...\n")
    
    response1 = await process_llm_request(
        llm_handler=llm_handler,
        prompt="C'est quoi le gameplay de Brotato?",
        context="ask",
        user_name="testuser",
        game_cache=cache
    )
    
    print("🤖 Réponse LLM :")
    print(f"   {response1}")
    print("\n💡 Observation : Le LLM utilise ses connaissances générales")
    
    # ========================================
    # TEST 2 : Données MOYENNES (nom + année)
    # ========================================
    print("\n" + "="*80)
    print("📊 TEST 2 : Données MOYENNES (nom + année 'Hollow Knight')")
    print("-" * 80)
    
    cache.set("hollow_knight", {
        "name": "Hollow Knight",
        "year": "2017",
        "platforms": ["PC", "Switch"]
    })
    
    print("\n💬 Question : 'Parle-moi de Hollow Knight'")
    print("📝 Prompt envoyé : CONTEXTE PARTIEL (année + plateformes)")
    print("🎯 Directive : 'Suggère !gameinfo si besoin de plus d'infos'")
    print("\n⏳ Attente réponse LLM...\n")
    
    response2 = await process_llm_request(
        llm_handler=llm_handler,
        prompt="Parle-moi de Hollow Knight",
        context="ask",
        user_name="testuser",
        game_cache=cache
    )
    
    print("🤖 Réponse LLM :")
    print(f"   {response2}")
    print("\n💡 Observation : Le LLM devrait mentionner 2017 et suggérer !gameinfo")
    
    # ========================================
    # TEST 3 : Données RICHES (genres + description)
    # ========================================
    print("\n" + "="*80)
    print("💎 TEST 3 : Données RICHES (genres + description 'Celeste')")
    print("-" * 80)
    
    cache.set("celeste", {
        "name": "Celeste",
        "year": "2018",
        "platforms": ["PC", "Switch", "PS4", "Xbox"],
        "genres": ["Platformer", "Indie", "Adventure"],
        "description": "A challenging platformer about climbing a mountain while battling anxiety and self-doubt"
    })
    
    print("\n💬 Question : 'C'est quoi Celeste?'")
    print("📝 Prompt envoyé : CONTEXTE STRICT (toutes les infos)")
    print("🎯 Directive : 'OBLIGATOIRE : Utilise TOUTES ces infos'")
    print("\n⏳ Attente réponse LLM...\n")
    
    response3 = await process_llm_request(
        llm_handler=llm_handler,
        prompt="C'est quoi Celeste?",
        context="ask",
        user_name="testuser",
        game_cache=cache
    )
    
    print("🤖 Réponse LLM :")
    print(f"   {response3}")
    print("\n💡 Observation : Le LLM devrait mentionner 2018, plateformes, genres, thème anxiété")
    
    # ========================================
    # TEST 4 : Jeu INCONNU (pas en cache)
    # ========================================
    print("\n" + "="*80)
    print("❌ TEST 4 : Jeu INCONNU (pas en cache 'Factorio')")
    print("-" * 80)
    
    print("\n💬 Question : 'C'est quoi Factorio?'")
    print("📝 Prompt envoyé : ORIGINAL (jeu non détecté)")
    print("\n⏳ Attente réponse LLM...\n")
    
    response4 = await process_llm_request(
        llm_handler=llm_handler,
        prompt="C'est quoi Factorio?",
        context="ask",
        user_name="testuser",
        game_cache=cache
    )
    
    print("🤖 Réponse LLM :")
    print(f"   {response4}")
    print("\n💡 Observation : Le LLM utilise ses connaissances générales (pas de contexte)")
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)
    
    print("\n" + "="*80)
    print("✅ Test terminé ! Analyse les différences de réponses selon l'enrichissement")
    print("="*80 + "\n")
    
    print("\n📊 RÉSUMÉ DES STRATÉGIES :")
    print("=" * 80)
    print("1️⃣  Données PAUVRES (juste nom) → ORIGINAL → LLM libre")
    print("2️⃣  Données MOYENNES (nom+année) → PARTIEL → LLM guidé + suggère !gameinfo")
    print("3️⃣  Données RICHES (genres+desc) → STRICT → LLM contraint (UTILISE TOUT)")
    print("4️⃣  Jeu INCONNU → ORIGINAL → LLM libre")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    print("\n🎮 Assurez-vous que LM Studio tourne sur http://127.0.0.1:1234\n")
    asyncio.run(test_real_llm_adaptive_prompts())
