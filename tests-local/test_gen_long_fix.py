"""
🧪 Test Fix gen_long: Prompt adapté pour explications détaillées
"""

import asyncio
import yaml
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from intelligence.neural_pathway_manager import NeuralPathwayManager
from intelligence.core import process_llm_request


def load_config():
    with open('config/config.yaml', 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


async def test_gen_long_fix():
    print("=" * 70)
    print("🧪 TEST FIX GEN_LONG: Prompt adapté pour explications")
    print("=" * 70 + "\n")
    
    config = load_config()
    llm_handler = NeuralPathwayManager(config)
    print("✅ LLM handler initialized\n")
    
    # Test question qui nécessite explication
    question = "explique moi la causalité"
    
    print(f"📢 Question: {question}")
    print("🎯 Classification attendue: gen_long")
    print("📝 Prompt adapté: 2-4 phrases autorisées\n")
    
    response = await process_llm_request(
        llm_handler=llm_handler,
        prompt=question,
        context="mention",
        user_name="el_serda_test",
        game_cache=None,
    )
    
    print(f"🤖 Réponse: {response}")
    print(f"📏 Longueur: {len(response)} caractères")
    
    # Compter les phrases
    phrase_count = response.count('.') + response.count('!') + response.count('?')
    print(f"📊 Phrases détectées: ~{phrase_count}")
    
    if phrase_count >= 2:
        print("✅ Explication détaillée générée (≥2 phrases)")
    else:
        print("⚠️ Réponse trop courte pour gen_long")
    
    print("\n" + "=" * 70)
    print("✅ TEST TERMINÉ")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_gen_long_fix())
