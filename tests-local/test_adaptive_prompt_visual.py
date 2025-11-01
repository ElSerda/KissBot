"""
🔍 Test visuel pour voir les prompts PARTIEL vs STRICT générés
Ce n'est PAS un vrai test - juste pour observer le comportement
"""
import sys
import os
import asyncio

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backends.game_cache import GameCache
from intelligence.core import enrich_prompt_with_game_context


async def visual_test_adaptive_prompts():
    """Affiche les prompts générés selon la richesse des données."""
    
    # Setup temp cache
    import tempfile
    temp_dir = tempfile.mkdtemp()
    cache_file = os.path.join(temp_dir, "test_games.json")
    cache = GameCache(config={"cache": {"duration_hours": 1}}, cache_file=cache_file)
    
    print("\n" + "="*80)
    print("🔍 TEST VISUEL : Prompts adaptatifs selon richesse des données")
    print("="*80)
    
    # ========================================
    # SCENARIO 1 : Données PAUVRES (juste nom)
    # ========================================
    print("\n📦 SCENARIO 1 : Données PAUVRES (juste nom)")
    print("-" * 80)
    
    cache.set("brotato", {"name": "Brotato"})
    prompt_poor = await enrich_prompt_with_game_context(
        "C'est quoi le gameplay de Brotato?",
        cache
    )
    
    print("💬 Prompt généré (PARTIEL attendu) :")
    print(prompt_poor)
    print("\n✅ Devrait contenir : 'CONTEXTE PARTIEL', '!gameinfo'")
    
    # ========================================
    # SCENARIO 2 : Données MOYENNES (nom + année)
    # ========================================
    print("\n" + "="*80)
    print("\n📊 SCENARIO 2 : Données MOYENNES (nom + année)")
    print("-" * 80)
    
    cache.set("hollow_knight", {
        "name": "Hollow Knight",
        "year": "2017"
    })
    prompt_medium = await enrich_prompt_with_game_context(
        "Hollow Knight est sorti quand?",
        cache
    )
    
    print("💬 Prompt généré (PARTIEL attendu) :")
    print(prompt_medium)
    print("\n✅ Devrait contenir : 'CONTEXTE PARTIEL', '!gameinfo', année 2017")
    
    # ========================================
    # SCENARIO 3 : Données RICHES (genres + description)
    # ========================================
    print("\n" + "="*80)
    print("\n💎 SCENARIO 3 : Données RICHES (genres + description)")
    print("-" * 80)
    
    cache.set("celeste", {
        "name": "Celeste",
        "year": "2018",
        "platforms": ["PC", "Switch", "PS4"],
        "genres": ["Platformer", "Indie", "Adventure"],
        "description": "A challenging platformer about climbing a mountain and overcoming anxiety"
    })
    prompt_rich = await enrich_prompt_with_game_context(
        "Parle-moi de Celeste",
        cache
    )
    
    print("💬 Prompt généré (STRICT attendu) :")
    print(prompt_rich)
    print("\n✅ Devrait contenir : 'CONTEXTE STRICT', 'OBLIGATOIRE', genres traduits")
    
    # ========================================
    # SCENARIO 4 : Jeu inconnu (pas en cache)
    # ========================================
    print("\n" + "="*80)
    print("\n❌ SCENARIO 4 : Jeu INCONNU (pas en cache)")
    print("-" * 80)
    
    prompt_unknown = await enrich_prompt_with_game_context(
        "C'est quoi Factorio?",
        cache
    )
    
    print("💬 Prompt généré (ORIGINAL attendu) :")
    print(prompt_unknown)
    print("\n✅ Devrait être identique à la question originale (pas d'enrichissement)")
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)
    
    print("\n" + "="*80)
    print("✅ Test visuel terminé ! Vérifie que les prompts correspondent aux attentes")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(visual_test_adaptive_prompts())
