"""
🔥 TEST REAL LLM STREAMING - Debug pour trouver le bug
Lance le VRAI Mistral 7B via LM Studio pour voir où ça plante
"""

import pytest
import yaml
from intelligence.synapses.local_synapse import LocalSynapse


@pytest.mark.asyncio
async def test_real_streaming_simple():
    """Test le plus simple possible avec VRAI LLM"""
    config = yaml.safe_load(open('config/config.yaml'))
    
    synapse = LocalSynapse(config)
    
    # Vérifications de base
    assert synapse.is_enabled, "LocalSynapse devrait être enabled"
    assert synapse.can_execute(), "LocalSynapse devrait pouvoir s'exécuter"
    
    print("\n🔥 TEST REAL STREAMING")
    print(f"   Endpoint: {synapse.endpoint}")
    print(f"   Model: {synapse.model_name}")
    print(f"   Debug streaming: {synapse.debug_streaming}")
    print(f"   Timeouts: {synapse.timeouts}")
    print()
    
    # Test avec prompt ULTRA simple
    response = await synapse.fire(
        stimulus="Dis juste le mot 'Bonjour'",
        context="ask",
        stimulus_class="gen_short",
        correlation_id="test_real_streaming"
    )
    
    print(f"\n✅ Response reçue: '{response}'")
    print(f"   Type: {type(response)}")
    print(f"   Length: {len(response) if response else 0}")
    
    # Assertions
    assert response is not None, "❌ Response ne devrait PAS être None !"
    assert len(response) > 0, "❌ Response ne devrait PAS être vide !"
    assert isinstance(response, str), "❌ Response devrait être un string !"
    
    print("\n✅ TEST PASSED ! Le streaming fonctionne !")


@pytest.mark.asyncio
async def test_real_streaming_with_config():
    """Test que la config centralisée est bien utilisée"""
    config = yaml.safe_load(open('config/config.yaml'))
    
    synapse = LocalSynapse(config)
    
    print("\n📋 CONFIG INFERENCE CHARGÉE:")
    inference = config['llm']['inference']
    ask_config = inference['ask']
    print(f"   ask.max_tokens: {ask_config['max_tokens']}")
    print(f"   ask.temperature: {ask_config['temperature']}")
    print(f"   ask.repeat_penalty: {ask_config['repeat_penalty']}")
    print()
    
    # Test avec context ASK (devrait utiliser max_tokens=200, temp=0.3)
    response = await synapse.fire(
        stimulus="Explique Python en 1 phrase",
        context="ask",
        correlation_id="test_config"
    )
    
    print(f"\n✅ Response: '{response}'")
    
    assert response is not None, "Config centralisée cassée ?"
    assert len(response) > 10, "Response trop courte ?"


@pytest.mark.asyncio
async def test_real_streaming_mention_context():
    """Test context mention avec paramètres différents"""
    config = yaml.safe_load(open('config/config.yaml'))
    
    synapse = LocalSynapse(config)
    
    print("\n📋 CONFIG MENTION:")
    mention_config = config['llm']['inference']['mention']
    print(f"   mention.max_tokens: {mention_config['max_tokens']}")
    print(f"   mention.temperature: {mention_config['temperature']}")
    print()
    
    # Test avec context MENTION (devrait utiliser max_tokens=200, temp=0.7)
    response = await synapse.fire(
        stimulus="Salut ! Ça va ?",
        context="mention",
        correlation_id="test_mention"
    )
    
    print(f"\n✅ Response mention: '{response}'")
    
    assert response is not None, "Mention context cassé ?"
