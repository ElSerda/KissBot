"""
🎬 Test DEBUG: Affichage streaming en temps réel
Visualiser les chunks arriver progressivement (GPU bridé = + chunks)
"""

import asyncio
import yaml


async def test_streaming_visual_debug():
    """Test avec debug_streaming=True pour voir les chunks en temps réel"""
    print("=" * 60)
    print("🎬 TEST STREAMING VISUEL (DEBUG MODE)")
    print("=" * 60)
    print("\n⚠️  GPU layers bridé recommandé pour voir plus de chunks\n")
    
    # Load config et ACTIVER debug_streaming
    with open("config/config.yaml") as f:
        config = yaml.safe_load(f)
    
    # 🎬 ACTIVER DEBUG STREAMING
    config['llm']['debug_streaming'] = True
    
    from intelligence.neural_pathway_manager import NeuralPathwayManager
    llm_handler = NeuralPathwayManager(config)
    
    print("🔧 Config:")
    print(f"   Model: {llm_handler.local_synapse.model_name}")
    print(f"   Debug streaming: {llm_handler.local_synapse.debug_streaming}")
    print(f"   Endpoint: {llm_handler.local_synapse.endpoint}\n")
    
    # Test avec plusieurs prompts
    prompts = [
        ("Blague courte", "Réponds EN 1 PHRASE MAX EN FRANÇAIS, SANS TE PRÉSENTER, style humoristique : raconte une blague courte"),
        ("Fact science", "Réponds EN 1 PHRASE MAX EN FRANÇAIS, SANS TE PRÉSENTER : partage un fait scientifique fascinant"),
        ("Dev joke", "Réponds EN 1 PHRASE MAX EN FRANÇAIS, SANS TE PRÉSENTER : raconte une blague sur les développeurs"),
    ]
    
    for i, (title, prompt) in enumerate(prompts, 1):
        print(f"\n{'=' * 60}")
        print(f"🎯 TEST {i}/3: {title}")
        print(f"{'=' * 60}")
        print(f"📝 Prompt: {prompt[:50]}...\n")
        
        response = await llm_handler.local_synapse.fire(
            stimulus=prompt,
            context="direct",
            stimulus_class="gen_short",
            correlation_id=f"visual_test_{i}"
        )
        
        print(f"\n✅ Réponse finale: {response}\n")
        
        if i < len(prompts):
            print("⏸️  Pause 1s avant prochain test...")
            await asyncio.sleep(1)
    
    print("\n" + "=" * 60)
    print("✅ TEST STREAMING VISUEL TERMINÉ !")
    print("=" * 60)
    print("\n💡 Remarques:")
    print("   - Chunks affichés en temps réel (progressive)")
    print("   - GPU bridé = + chunks visibles")
    print("   - Accumulation = pas de spam chat")
    print("   - Message complet envoyé à stop_reason\n")


if __name__ == "__main__":
    print("\n🎬 STREAMING DEBUG MODE ".center(60, "="))
    print("Voir les chunks LLM arriver en temps réel !\n")
    
    asyncio.run(test_streaming_visual_debug())
