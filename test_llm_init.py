#!/usr/bin/env python3
"""
Test Phase 3.2 - Vérification LLMHandler sans vraie clé OpenAI
"""
import yaml
from backends.llm_handler import LLMHandler


def test_llm_handler_init():
    """Test si LLMHandler s'initialise correctement"""
    
    # Load config
    with open("config/config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    print("=" * 80)
    print("TEST Phase 3.2 - LLMHandler Initialization")
    print("=" * 80)
    
    # Check si clé OpenAI configurée
    openai_key = config.get("apis", {}).get("openai_key")
    print(f"\n🔑 OpenAI Key configured: {'✅ Yes' if openai_key else '❌ No'}")
    
    # Test initialization
    try:
        llm = LLMHandler(config)
        print(f"✅ LLMHandler created")
        print(f"   Available: {llm.is_available()}")
        
        if llm.neural_pathway:
            print(f"   NeuralPathwayManager: ✅ Initialized")
        else:
            print(f"   NeuralPathwayManager: ❌ None")
            
    except Exception as e:
        print(f"❌ LLMHandler init failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("Note: Si pas de clé OpenAI, c'est normal que Neural...ger soit None")
    print("=" * 80)


if __name__ == "__main__":
    test_llm_handler_init()
