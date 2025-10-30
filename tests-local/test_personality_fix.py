"""
🧪 Test Fix Personnalité: Validation prompt amélioré pour mentions

Test les changements:
1. Personnalité simplifiée (drôle, sarcastique, direct)
2. max_tokens mention: 150 → 200
3. Prompt système amélioré avec règles claires
"""

import asyncio
import yaml
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from intelligence.neural_pathway_manager import NeuralPathwayManager
from intelligence.core import process_llm_request


def load_config():
    """Load configuration from YAML file."""
    with open('config/config.yaml', 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


async def test_personality_mentions():
    """Test réponses aux mentions avec nouvelle personnalité"""
    print("=" * 70)
    print("🧪 TEST FIX PERSONNALITÉ: Mentions avec prompt amélioré")
    print("=" * 70 + "\n")
    
    # Load config
    config = load_config()
    personality = config.get("bot", {}).get("personality", "")
    
    print("📋 Nouvelle personnalité:")
    print(f"   {personality}\n")
    
    # Initialize LLM handler
    llm_handler = NeuralPathwayManager(config)
    print("✅ LLM handler initialized\n")
    
    # Test questions typiques
    test_cases = [
        "comment ça va ?",
        "salut toi ! comment tu va ?",
        "tu fais quoi ?",
        "qui es-tu ?",
        "raconte-moi une blague",
    ]
    
    print("🎭 Test 5 questions avec nouvelle personnalité:\n")
    
    for i, question in enumerate(test_cases, 1):
        print(f"📢 Question {i}: {question}")
        
        response = await process_llm_request(
            llm_handler=llm_handler,
            prompt=question,
            context="mention",
            user_name="el_serda_test",
            game_cache=None,
        )
        
        print(f"🤖 Réponse: {response}")
        print(f"📏 Longueur: {len(response)} caractères\n")
        
        # Vérifications
        issues = []
        if "taquin" in response.lower() and "jeu" in response.lower():
            issues.append("⚠️ Interprète 'taquin' comme jeu")
        if "cash" in response.lower() and "argent" in response.lower():
            issues.append("⚠️ Interprète 'cash' comme argent")
        if len(response) > 400:
            issues.append(f"⚠️ Trop long ({len(response)} > 400 chars)")
        if response.endswith("..."):
            issues.append("⚠️ Réponse tronquée")
        
        if issues:
            print("   Issues détectées:")
            for issue in issues:
                print(f"     {issue}")
            print()
        
        await asyncio.sleep(0.5)
    
    print("=" * 70)
    print("✅ TEST TERMINÉ")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_personality_mentions())
