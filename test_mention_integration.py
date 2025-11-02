#!/usr/bin/env python3
"""
Test d'intégration mention → LLM
- Bot Mention Feature
"""
import asyncio
import sys
import logging
from unittest.mock import MagicMock, AsyncMock
from core.message_handler import MessageHandler
from core.message_types import ChatMessage

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")


async def test_mention_integration():
    """Test l'intégration complète: mention détectée → LLM appelé → réponse envoyée"""
    
    print("\n🧪 Test Mention Integration\n")
    print("=" * 60)
    
    # Mock MessageBus
    mock_bus = MagicMock()
    mock_bus.publish = AsyncMock()
    mock_bus.subscribe = MagicMock()
    
    # Config avec LLM et bot name
    config = {
        "bot_login_name": "serda_bot",  # Bot name pour mentions
        "apis": {
            "openai_key": "test_key"
        },
        "commands": {
            "cooldowns": {
                "mention": 1.0  # 1s pour test rapide
            }
        }
    }
    
    # Create handler
    print("📦 Creating MessageHandler...")
    handler = MessageHandler(mock_bus, config)
    
    # Mock LLM (simuler réponse)
    handler.llm_handler = MagicMock()
    handler.llm_handler.is_available = MagicMock(return_value=True)
    handler.llm_handler.neural_pathway = MagicMock()
    
    async def mock_llm_response(*args, **kwargs):
        prompt = kwargs.get("prompt", "")
        context = kwargs.get("context", "unknown")
        print(f"   🧠 LLM called with context='{context}', prompt='{prompt[:30]}...'")
        return f"Réponse test pour: {prompt[:20]}"
    
    import intelligence.core
    original_process = intelligence.core.process_llm_request
    intelligence.core.process_llm_request = mock_llm_response
    
    test_cases = [
        ("@serda_bot tu penses quoi de python?", True, "mention"),
        ("serda_bot ça va?", True, "mention"),
        ("!ask python", False, None),  # Pas une mention
        ("hello world", False, None),  # Pas une mention
        ("@other_bot salut", False, None),  # Mauvais bot
    ]
    
    print("\n" + "=" * 60)
    print("Test Cases:\n")
    
    try:
        for i, (text, should_trigger, expected_context) in enumerate(test_cases, 1):
            print(f"\n{i}. Message: '{text}'")
            
            # Reset mock
            mock_bus.publish.reset_mock()
            
            # Create message
            msg = ChatMessage(
                user_id=f"user_{i}",
                user_login=f"test_user_{i}",
                channel="test_channel",
                channel_id="channel_123",
                text=text
            )
            
            # Process via handler
            await handler._handle_chat_message(msg)
            
            # Check result
            if should_trigger:
                if mock_bus.publish.called:
                    print(f"   ✅ Mention triggered LLM (context: {expected_context})")
                    
                    # Verify response
                    call_args = mock_bus.publish.call_args
                    if call_args:
                        topic = call_args[0][0]
                        message_obj = call_args[0][1]
                        response_text = message_obj.text
                        print(f"   📤 Response: '{response_text[:50]}...'")
                else:
                    print(f"   ❌ Mention NOT triggered (expected LLM call)")
            else:
                if not mock_bus.publish.called:
                    print(f"   ✅ Correctly ignored (not a mention)")
                else:
                    print(f"   ⚠️ Unexpectedly triggered (should ignore)")
            
            # Wait a bit for cooldown
            if should_trigger:
                await asyncio.sleep(1.2)
        
        print("\n" + "=" * 60)
        print("✅ Integration test complete!\n")
        
    finally:
        # Restore
        intelligence.core.process_llm_request = original_process


if __name__ == "__main__":
    asyncio.run(test_mention_integration())
