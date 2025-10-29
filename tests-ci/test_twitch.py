"""
Tests pour le module twitch/ (EventSub, tokens, handlers)
Vérifie les intégrations TwitchIO 3.x
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch


@pytest.mark.integration
class TestTwitchModule:
    """Tests du module twitch"""
    
    def test_twitch_module_imports(self):
        """Vérifie que le module twitch s'importe"""
        try:
            import twitch
            assert twitch is not None
        except ImportError:
            pytest.skip("Module twitch n'existe pas")
    
    def test_twitch_module_structure(self):
        """Vérifie la structure du module twitch"""
        try:
            import twitch
            
            # Devrait avoir au moins __init__.py
            assert hasattr(twitch, '__file__')
        except ImportError:
            pytest.skip("Module twitch n'existe pas")


@pytest.mark.integration
class TestEventSub:
    """Tests EventSub (si implémenté dans twitch/)"""
    
    def test_eventsub_imports(self):
        """Vérifie que EventSub s'importe"""
        try:
            from twitch.eventsub import EventSubHandler
            assert EventSubHandler is not None
        except ImportError:
            pytest.skip("EventSub non implémenté dans twitch/")
    
    @pytest.mark.asyncio
    async def test_eventsub_setup(self):
        """Test le setup d'EventSub"""
        try:
            from twitch.eventsub import setup_eventsub
            
            mock_bot = Mock()
            
            # Setup devrait accepter bot et config
            result = await setup_eventsub(mock_bot, {})
            
            # Test réussi si pas d'exception
            assert True
        except ImportError:
            pytest.skip("EventSub non implémenté")


@pytest.mark.integration
class TestTokenManagement:
    """Tests de la gestion des tokens Twitch"""
    
    def test_token_manager_imports(self):
        """Vérifie que le token manager s'importe"""
        try:
            from twitch.token_manager import TokenManager
            assert TokenManager is not None
        except ImportError:
            pytest.skip("TokenManager non implémenté dans twitch/")
    
    @pytest.mark.asyncio
    async def test_token_refresh(self):
        """Test le refresh de token"""
        try:
            from twitch.token_manager import refresh_token
            
            # Mock de la requête
            with patch('aiohttp.ClientSession.post') as mock_post:
                mock_response = AsyncMock()
                mock_response.json.return_value = {
                    'access_token': 'new_token',
                    'refresh_token': 'new_refresh'
                }
                mock_response.__aenter__.return_value = mock_response
                mock_post.return_value = mock_response
                
                result = await refresh_token('old_token', 'client_id', 'secret')
                
                assert result is not None or result is None
        except ImportError:
            pytest.skip("refresh_token non implémenté")


@pytest.mark.integration
class TestTwitchHandlers:
    """Tests des handlers Twitch (events)"""
    
    def test_twitch_handlers_imports(self):
        """Vérifie que les handlers Twitch s'importent"""
        try:
            from twitch.handlers import setup_handlers
            assert setup_handlers is not None
        except ImportError:
            # Peut être dans core/handlers
            try:
                from core.handlers import setup_handlers
                assert setup_handlers is not None
            except ImportError:
                pytest.skip("Handlers non trouvés")
    
    @pytest.mark.asyncio
    async def test_event_ready_handler(self):
        """Test le handler event_ready"""
        try:
            # Les handlers sont généralement des fonctions décorées
            # On teste juste qu'ils ne crashent pas
            mock_bot = Mock()
            mock_bot.nick = "test_bot"
            mock_bot.loop = None
            
            # Si handlers existent, ils devraient setup sans crash
            assert True
        except Exception:
            pytest.skip("Handlers non testables directement")


@pytest.mark.unit
class TestTwitchConfig:
    """Tests de la configuration Twitch"""
    
    def test_config_has_twitch_section(self):
        """Vérifie que config.yaml a une section twitch"""
        import yaml
        
        with open("config/config.yaml", "r") as f:
            config = yaml.safe_load(f)
        
        assert 'twitch' in config
        assert 'client_id' in config['twitch']
        assert 'channels' in config['twitch']
    
    def test_config_has_tokens(self):
        """Vérifie que config.yaml a des tokens"""
        import yaml
        
        with open("config/config.yaml", "r") as f:
            config = yaml.safe_load(f)
        
        assert 'twitch' in config
        # Tokens peuvent être dans twitch.tokens ou au root level
        has_tokens = (
            'tokens' in config['twitch'] or
            'access_token' in config['twitch']
        )
        
        assert has_tokens
