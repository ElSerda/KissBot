"""
🧪 Test validation: stream_response_debug="on" config
"""

import yaml
from intelligence.synapses.local_synapse import LocalSynapse


def test_debug_streaming_bool():
    """Test avec debug_streaming: true (bool)"""
    config = {
        "llm": {
            "debug_streaming": True,
            "model_endpoint": "http://127.0.0.1:1234/v1/chat/completions",
            "model_name": "test-model",
            "local_llm": True,
            "language": "fr"
        },
        "neural_llm": {}
    }
    
    synapse = LocalSynapse(config)
    assert synapse.debug_streaming == True, "debug_streaming=True devrait activer debug"
    print("✅ debug_streaming: true → debug activé")


def test_stream_response_debug_on():
    """Test avec stream_response_debug: "on" (string)"""
    config = {
        "llm": {
            "stream_response_debug": "on",
            "model_endpoint": "http://127.0.0.1:1234/v1/chat/completions",
            "model_name": "test-model",
            "local_llm": True,
            "language": "fr"
        },
        "neural_llm": {}
    }
    
    synapse = LocalSynapse(config)
    assert synapse.debug_streaming == True, "stream_response_debug='on' devrait activer debug"
    print("✅ stream_response_debug: 'on' → debug activé")


def test_stream_response_debug_off():
    """Test avec stream_response_debug: "off" (désactivé)"""
    config = {
        "llm": {
            "stream_response_debug": "off",
            "model_endpoint": "http://127.0.0.1:1234/v1/chat/completions",
            "model_name": "test-model",
            "local_llm": True,
            "language": "fr"
        },
        "neural_llm": {}
    }
    
    synapse = LocalSynapse(config)
    assert synapse.debug_streaming == False, "stream_response_debug='off' devrait désactiver debug"
    print("✅ stream_response_debug: 'off' → debug désactivé")


def test_no_config():
    """Test sans config debug (défaut désactivé)"""
    config = {
        "llm": {
            "model_endpoint": "http://127.0.0.1:1234/v1/chat/completions",
            "model_name": "test-model",
            "local_llm": True,
            "language": "fr"
        },
        "neural_llm": {}
    }
    
    synapse = LocalSynapse(config)
    assert synapse.debug_streaming == False, "Sans config, debug devrait être désactivé"
    print("✅ Aucune config debug → debug désactivé (défaut)")


def test_both_configs():
    """Test avec les deux configs (priorité OR)"""
    config = {
        "llm": {
            "debug_streaming": False,  # False
            "stream_response_debug": "on",  # Mais "on" ici
            "model_endpoint": "http://127.0.0.1:1234/v1/chat/completions",
            "model_name": "test-model",
            "local_llm": True,
            "language": "fr"
        },
        "neural_llm": {}
    }
    
    synapse = LocalSynapse(config)
    assert synapse.debug_streaming == True, "OR logic: l'un des deux à True devrait activer"
    print("✅ debug_streaming=False OR stream_response_debug='on' → debug activé")


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 TEST CONFIG: stream_response_debug")
    print("=" * 60 + "\n")
    
    test_debug_streaming_bool()
    test_stream_response_debug_on()
    test_stream_response_debug_off()
    test_no_config()
    test_both_configs()
    
    print("\n" + "=" * 60)
    print("✅ TOUS LES TESTS CONFIG RÉUSSIS !")
    print("=" * 60)
    print("\n💡 Utilisation recommandée en production:")
    print('   stream_response_debug: "on"  # Voir chunks en live')
    print('   stream_response_debug: "off" # Production propre')
