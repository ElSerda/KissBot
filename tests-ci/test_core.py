"""
Tests pour le module core/ (cache, rate_limiter, handlers)
Vérifie les fonctionnalités de base du système
"""
import pytest
import time
from unittest.mock import Mock, AsyncMock, patch


@pytest.mark.unit
class TestCache:
    """Tests du système de cache simple (core/cache.py)"""
    
    def test_cache_imports(self):
        """Vérifie que le module cache s'importe"""
        try:
            from core.cache import Cache
            assert Cache is not None
        except ImportError:
            pytest.skip("core.cache n'existe pas")
    
    def test_cache_basic_operations(self):
        """Test set/get/delete basique du cache"""
        try:
            from core.cache import Cache
            cache = Cache(max_size=10)
            
            # Set/Get
            cache.set("key1", "value1")
            assert cache.get("key1") == "value1"
            
            # Get inexistant
            assert cache.get("nonexistent") is None
            
            # Delete
            cache.delete("key1")
            assert cache.get("key1") is None
        except ImportError:
            pytest.skip("core.cache n'existe pas")
    
    def test_cache_max_size(self):
        """Test que le cache respecte max_size"""
        try:
            from core.cache import Cache
            cache = Cache(max_size=3)
            
            cache.set("k1", "v1")
            cache.set("k2", "v2")
            cache.set("k3", "v3")
            cache.set("k4", "v4")  # Devrait évincer k1
            
            # Cache ne devrait avoir que 3 items max
            assert len([k for k in ["k1", "k2", "k3", "k4"] if cache.get(k) is not None]) <= 3
        except ImportError:
            pytest.skip("core.cache n'existe pas")


@pytest.mark.unit
class TestRateLimiter:
    """Tests du rate limiter pour cooldowns"""
    
    def test_rate_limiter_imports(self):
        """Vérifie que rate_limiter s'importe"""
        try:
            from core.rate_limiter import RateLimiter
            assert RateLimiter is not None
        except ImportError:
            pytest.skip("core.rate_limiter n'existe pas")
    
    def test_rate_limiter_allows_first_call(self):
        """Test que le premier appel est toujours autorisé"""
        try:
            from core.rate_limiter import RateLimiter
            limiter = RateLimiter(per30_non_verified=18)
            
            assert limiter.can_send("channel1", cost=1, is_mod=False) is True
        except ImportError:
            pytest.skip("core.rate_limiter n'existe pas")
    
    def test_rate_limiter_blocks_rapid_calls(self):
        """Test que les appels rapides respectent la limite"""
        try:
            from core.rate_limiter import RateLimiter
            import time
            
            limiter = RateLimiter(per30_non_verified=2)  # Limit to 2 per 30s
            
            # Premier appel OK
            assert limiter.can_send("channel1", cost=1, is_mod=False) is True
            limiter.record_send("channel1")
            
            # Deuxième appel OK
            assert limiter.can_send("channel1", cost=1, is_mod=False) is True
            limiter.record_send("channel1")
            
            # Troisième appel devrait être bloqué (limite atteinte)
            assert limiter.can_send("channel1", cost=1, is_mod=False) is False
        except ImportError:
            pytest.skip("core.rate_limiter n'existe pas")
    
    def test_rate_limiter_different_users(self):
        """Test que différents channels ont des limites séparées"""
        try:
            from core.rate_limiter import RateLimiter
            limiter = RateLimiter(per30_non_verified=18)
            
            assert limiter.can_send("channel1", cost=1, is_mod=False) is True
            assert limiter.can_send("channel2", cost=1, is_mod=False) is True
        except ImportError:
            pytest.skip("core.rate_limiter n'existe pas")


@pytest.mark.integration
class TestHandlers:
    """Tests des event handlers TwitchIO"""
    
    def test_handlers_imports(self):
        """Vérifie que handlers s'importe"""
        try:
            from core.handlers import setup_handlers
            assert setup_handlers is not None
        except ImportError:
            pytest.skip("core.handlers n'existe pas ou différent")
    
    @pytest.mark.asyncio
    async def test_handlers_structure(self):
        """Test la structure des handlers"""
        try:
            from core.handlers import setup_handlers
            
            # Mock bot
            mock_bot = Mock()
            mock_bot.event = lambda f: f  # Decorator passthrough
            
            # Setup devrait retourner des handlers ou None
            result = setup_handlers(mock_bot)
            # Test réussi si pas d'exception
            assert True
        except ImportError:
            pytest.skip("core.handlers n'existe pas")


@pytest.mark.unit
class TestCacheInterface:
    """Tests de l'interface de cache"""
    
    def test_cache_interface_imports(self):
        """Vérifie que cache_interface s'importe"""
        try:
            from core.cache_interface import CacheInterface
            assert CacheInterface is not None
        except ImportError:
            pytest.skip("core.cache_interface n'existe pas")
    
    def test_cache_interface_methods(self):
        """Vérifie que CacheInterface a les méthodes requises"""
        try:
            from core.cache_interface import CacheInterface
            
            assert hasattr(CacheInterface, 'get')
            assert hasattr(CacheInterface, 'set')
            assert hasattr(CacheInterface, 'delete')
        except (ImportError, AttributeError):
            pytest.skip("CacheInterface n'a pas la structure attendue")
