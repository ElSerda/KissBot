#!/usr/bin/env python3
"""
Test du rate limiting pour mentions
Phase 3.2 - Bot Mention Feature
"""
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock
from core.message_handler import MessageHandler
from core.message_types import ChatMessage


async def test_mention_rate_limiting():
    """Test le cooldown de 15s pour les mentions"""
    
    print("🧪 Test Mention Rate Limiting (15s cooldown)\n")
    
    # Mock MessageBus
    mock_bus = MagicMock()
    mock_bus.publish = AsyncMock()
    mock_bus.subscribe = MagicMock()
    
    # Config avec LLM et cooldown
    config = {
        "apis": {
            "openai_key": "test_key"  # Fake key pour init
        },
        "commands": {
            "cooldowns": {
                "mention": 3.0  # 3s pour test rapide (au lieu de 15s)
            }
        }
    }
    
    # Create handler
    handler = MessageHandler(mock_bus, config)
    
    # Mock LLM handler
    handler.llm_handler = MagicMock()
    handler.llm_handler.is_available = MagicMock(return_value=True)
    handler.llm_handler.neural_pathway = MagicMock()
    
    # Mock process_llm_request
    async def mock_llm_response(*args, **kwargs):
        return "Réponse du bot"
    
    import intelligence.core
    original_process = intelligence.core.process_llm_request
    intelligence.core.process_llm_request = mock_llm_response
    
    # Create fake message
    msg = ChatMessage(
        user_id="user_456",
        user_login="test_user",
        channel="test_channel",
        channel_id="channel_789",
        text="@serda_bot hello"
    )
    
    try:
        # Premier message: devrait passer
        print("📨 Message 1: @serda_bot hello")
        await handler._handle_mention(msg, "hello")
        
        if mock_bus.publish.called:
            print("✅ Message 1 processed (LLM called)\n")
        else:
            print("❌ Message 1 NOT processed\n")
        
        mock_bus.publish.reset_mock()
        
        # Deuxième message immédiat: devrait être bloqué (cooldown)
        print("📨 Message 2 (immediately after): @serda_bot bonjour")
        await handler._handle_mention(msg, "bonjour")
        
        if not mock_bus.publish.called:
            print("✅ Message 2 BLOCKED (cooldown active)\n")
        else:
            print("❌ Message 2 processed (should be blocked!)\n")
        
        # Attendre cooldown + marge
        print(f"⏳ Waiting {config['commands']['cooldowns']['mention'] + 0.5}s for cooldown...")
        await asyncio.sleep(config['commands']['cooldowns']['mention'] + 0.5)
        
        mock_bus.publish.reset_mock()
        
        # Troisième message: devrait passer (cooldown expiré)
        print("📨 Message 3 (after cooldown): @serda_bot ça va?")
        await handler._handle_mention(msg, "ça va?")
        
        if mock_bus.publish.called:
            print("✅ Message 3 processed (cooldown expired)\n")
        else:
            print("❌ Message 3 NOT processed (cooldown should be expired!)\n")
        
        print("✅ Rate limiting test complete!")
        
    finally:
        # Restore original function
        intelligence.core.process_llm_request = original_process


if __name__ == "__main__":
    asyncio.run(test_mention_rate_limiting())
