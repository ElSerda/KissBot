"""
Tests unitaires pour modules/classic_commands/user_commands/intelligence_v2.py

Valide que:
1. handle_ask utilise le préfixe [ASK]
2. handle_ask gère correctement les erreurs
3. handle_joke fonctionne
4. Les handlers sont importables et callable
"""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import inspect


class MockBus:
    """Mock du MessageBus"""
    def __init__(self):
        self.publish = AsyncMock()
        self.published_messages = []
    
    async def mock_publish(self, topic, message):
        self.published_messages.append((topic, message))


class MockLLMHandler:
    """Mock du LLM Handler"""
    def __init__(self, response="Test LLM Response"):
        self.response = response
        self.ask = AsyncMock(return_value=response)


class MockConfig:
    """Mock de la config"""
    def get(self, key, default=None):
        if key == "wikipedia":
            return {"lang": "fr"}
        return default


class MockHandler:
    """Mock du MessageHandler"""
    def __init__(self, llm_response="Test LLM Response", llm_available=True):
        self.bus = MockBus()
        self.bus.publish = self.bus.mock_publish
        self.config = MockConfig()
        
        if llm_available:
            self.llm_handler = MockLLMHandler(llm_response)
        else:
            self.llm_handler = None


class MockMessage:
    """Mock d'un ChatMessage"""
    def __init__(self, user="test_user", channel="test_channel", channel_id="12345"):
        self.user_login = user
        self.channel = channel
        self.channel_id = channel_id


# ═══════════════════════════════════════════════════════════════════════════
# Tests d'import et structure
# ═══════════════════════════════════════════════════════════════════════════

class TestImports:
    """Tests d'import des modules"""
    
    def test_import_intelligence_v2(self):
        """Vérifie que intelligence_v2.py est importable"""
        from modules.classic_commands.user_commands.intelligence_v2 import handle_ask, handle_joke
        assert callable(handle_ask)
        assert callable(handle_joke)
    
    def test_handle_ask_is_async(self):
        """Vérifie que handle_ask est une fonction async"""
        from modules.classic_commands.user_commands.intelligence_v2 import handle_ask
        assert asyncio.iscoroutinefunction(handle_ask)
    
    def test_handle_joke_is_async(self):
        """Vérifie que handle_joke est une fonction async"""
        from modules.classic_commands.user_commands.intelligence_v2 import handle_joke
        assert asyncio.iscoroutinefunction(handle_joke)


# ═══════════════════════════════════════════════════════════════════════════
# Tests du préfixe [ASK]
# ═══════════════════════════════════════════════════════════════════════════

class TestAskPrefix:
    """Tests du préfixe [ASK] dans handle_ask"""
    
    def test_source_contains_ask_prefix(self):
        """Vérifie que le code source contient [ASK]"""
        from modules.classic_commands.user_commands.intelligence_v2 import handle_ask
        source = inspect.getsource(handle_ask)
        assert '[ASK]' in source, "Le préfixe [ASK] doit être dans le code source"
    
    def test_source_has_correct_format(self):
        """Vérifie le format exact f'[ASK] {llm_response}'"""
        from modules.classic_commands.user_commands.intelligence_v2 import handle_ask
        source = inspect.getsource(handle_ask)
        assert 'f"[ASK] {llm_response}"' in source or "f'[ASK] {llm_response}'" in source


# ═══════════════════════════════════════════════════════════════════════════
# Tests fonctionnels handle_ask
# ═══════════════════════════════════════════════════════════════════════════

class TestHandleAsk:
    """Tests fonctionnels de handle_ask"""
    
    @pytest.mark.asyncio
    async def test_ask_success_with_prefix(self):
        """Test que !ask réussit et utilise le préfixe [ASK]"""
        from modules.classic_commands.user_commands.intelligence_v2 import handle_ask
        
        handler = MockHandler(llm_response="La correspondance AdS/CFT est une conjecture...")
        msg = MockMessage()
        
        # Patch Wikipedia au bon endroit (là où il est importé)
        with patch('modules.integrations.wikipedia.wikipedia_handler.search_wikipedia', 
                   new_callable=AsyncMock, return_value=None):
            await handle_ask(handler, msg, "correspondance ADS CFT")
        
        # Vérifier qu'un message a été publié
        assert len(handler.bus.published_messages) == 1
        topic, message = handler.bus.published_messages[0]
        
        assert topic == "chat.outbound"
        assert message.text.startswith("[ASK]"), f"Message devrait commencer par [ASK], got: {message.text[:20]}"
        assert "AdS/CFT" in message.text or "correspondance" in message.text.lower()
    
    @pytest.mark.asyncio
    async def test_ask_empty_question(self):
        """Test !ask sans question affiche usage"""
        from modules.classic_commands.user_commands.intelligence_v2 import handle_ask
        
        handler = MockHandler()
        msg = MockMessage()
        
        await handle_ask(handler, msg, "")
        
        assert len(handler.bus.published_messages) == 1
        topic, message = handler.bus.published_messages[0]
        assert "Usage:" in message.text
        assert "!ask" in message.text
    
    @pytest.mark.asyncio
    async def test_ask_no_llm(self):
        """Test !ask sans LLM retourne erreur"""
        from modules.classic_commands.user_commands.intelligence_v2 import handle_ask
        
        handler = MockHandler(llm_available=False)
        msg = MockMessage()
        
        await handle_ask(handler, msg, "test question")
        
        assert len(handler.bus.published_messages) == 1
        topic, message = handler.bus.published_messages[0]
        assert "❌" in message.text
        assert "IA" in message.text or "disponible" in message.text
    
    @pytest.mark.asyncio
    async def test_ask_truncation(self):
        """Test que les réponses longues sont tronquées à 500 chars"""
        from modules.classic_commands.user_commands.intelligence_v2 import handle_ask
        
        # Réponse très longue
        long_response = "A" * 600
        handler = MockHandler(llm_response=long_response)
        msg = MockMessage()
        
        with patch('modules.integrations.wikipedia.wikipedia_handler.search_wikipedia', 
                   new_callable=AsyncMock, return_value=None):
            await handle_ask(handler, msg, "test")
        
        topic, message = handler.bus.published_messages[0]
        assert len(message.text) <= 500, f"Message trop long: {len(message.text)} chars"
        assert message.text.endswith("..."), "Message tronqué devrait finir par ..."


# ═══════════════════════════════════════════════════════════════════════════
# Tests fonctionnels handle_joke
# ═══════════════════════════════════════════════════════════════════════════

class TestHandleJoke:
    """Tests fonctionnels de handle_joke"""
    
    @pytest.mark.asyncio
    async def test_joke_success(self):
        """Test que !joke réussit"""
        from modules.classic_commands.user_commands.intelligence_v2 import handle_joke
        
        handler = MockHandler(llm_response="Pourquoi les plongeurs plongent-ils en arrière ?")
        msg = MockMessage()
        
        await handle_joke(handler, msg, "")
        
        assert len(handler.bus.published_messages) == 1
        topic, message = handler.bus.published_messages[0]
        assert topic == "chat.outbound"
        assert "😂" in message.text or "plongeurs" in message.text
    
    @pytest.mark.asyncio
    async def test_joke_no_llm(self):
        """Test !joke sans LLM retourne erreur"""
        from modules.classic_commands.user_commands.intelligence_v2 import handle_joke
        
        handler = MockHandler(llm_available=False)
        msg = MockMessage()
        
        await handle_joke(handler, msg, "")
        
        assert len(handler.bus.published_messages) == 1
        topic, message = handler.bus.published_messages[0]
        assert "❌" in message.text


# ═══════════════════════════════════════════════════════════════════════════
# Test d'intégration rapide
# ═══════════════════════════════════════════════════════════════════════════

class TestIntegration:
    """Tests d'intégration simples"""
    
    def test_message_handler_imports_correctly(self):
        """Vérifie que message_handler.py importe correctement les handlers"""
        # Simuler l'import comme le fait message_handler.py
        from modules.classic_commands.user_commands.intelligence_v2 import handle_ask, handle_joke
        
        # Vérifier les signatures
        sig_ask = inspect.signature(handle_ask)
        params = list(sig_ask.parameters.keys())
        assert 'handler' in params
        assert 'msg' in params
        assert 'question' in params
        
        sig_joke = inspect.signature(handle_joke)
        params = list(sig_joke.parameters.keys())
        assert 'handler' in params
        assert 'msg' in params


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
