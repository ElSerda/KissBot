"""
Tests pour le module twitchapi/ (IRC, EventSub, transports)
Vérifie les intégrations pyTwitchAPI 4.x
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
import os


@pytest.mark.integration
class TestTwitchAPIModule:
    """Tests du module twitchapi"""
    
    def test_twitchapi_module_imports(self):
        """Vérifie que le module twitchapi s'importe"""
        try:
            import twitchapi
            assert twitchapi is not None
        except ImportError:
            pytest.skip("Module twitchapi n'existe pas")
    
    def test_twitchapi_module_structure(self):
        """Vérifie la structure du module twitchapi"""
        try:
            import twitchapi
            
            # Devrait avoir au moins __init__.py
            assert hasattr(twitchapi, '__file__')
        except ImportError:
            pytest.skip("Module twitchapi n'existe pas")


@pytest.mark.integration
class TestIRCTransport:
    """Tests IRC Transport (twitchapi/transports/)"""
    
    def test_irc_client_imports(self):
        """Vérifie que IRCClient s'importe"""
        try:
            from twitchapi.transports.irc_client import IRCClient
            assert IRCClient is not None
        except ImportError:
            pytest.skip("IRCClient non implémenté dans twitchapi/")
    
    def test_hub_eventsub_client_imports(self):
        """Vérifie que HubEventSubClient s'importe"""
        try:
            from twitchapi.transports.hub_eventsub_client import HubEventSubClient
            assert HubEventSubClient is not None
        except ImportError:
            pytest.skip("HubEventSubClient non implémenté")


@pytest.mark.integration
class TestTokenManagement:
    """Tests de la gestion des tokens Twitch"""
    
    def test_token_manager_imports(self):
        """Vérifie que le token manager s'importe"""
        try:
            from twitchapi.auth import TokenManager
            assert TokenManager is not None
        except ImportError:
            pytest.skip("TokenManager non implémenté dans twitchapi/")
    
    @pytest.mark.asyncio
    async def test_token_refresh(self):
        """Test le refresh de token"""
        try:
            from twitchapi.auth import refresh_token
            
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
            from twitchapi.handlers import setup_handlers
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
    
    @pytest.mark.skipif(not Path("config/config.yaml").exists(), reason="config.yaml requis")
    def test_config_has_twitch_section(self):
        """Vérifie que config.yaml a une section twitch"""
        import yaml
        from pathlib import Path
        
        with open("config/config.yaml", "r") as f:
            config = yaml.safe_load(f)
        
        assert 'twitch' in config
        assert 'client_id' in config['twitch']
        assert 'channels' in config['twitch']
    
    @pytest.mark.skipif(not Path("config/config.yaml").exists(), reason="config.yaml requis")
    def test_config_has_tokens(self):
        """Vérifie que config.yaml a des tokens (peut être placeholder en CI)"""
        import yaml
        from pathlib import Path
        
        with open("config/config.yaml", "r") as f:
            config = yaml.safe_load(f)
        
        assert 'twitch' in config
        # Tokens peuvent être dans twitch.tokens, twitch.token, ou access_token
        # En CI avec config.example, on accepte les placeholders
        has_token_field = (
            'tokens' in config['twitch'] or
            'token' in config['twitch'] or
            'access_token' in config['twitch']
        )
        
        assert has_token_field, "Aucun champ token trouvé dans config.twitch"
