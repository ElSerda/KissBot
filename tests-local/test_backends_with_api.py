"""
Tests backends avec VRAIE clé RAWG API (tests locaux uniquement)
"""
import pytest
import yaml


@pytest.mark.local
@pytest.mark.requires_rawg
class TestGameLookupWithRealAPI:
    """Tests GameLookup avec vraie clé RAWG"""
    
    @pytest.fixture
    def real_config(self):
        """Charge la vraie config avec clé RAWG"""
        with open("config/config.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    
    def test_game_lookup_with_real_key(self, real_config):
        """Test GameLookup avec vraie clé API"""
        from backends.game_lookup import GameLookup
        
        # Vérifie qu'on a une clé RAWG
        assert 'rawg' in real_config
        assert 'api_key' in real_config['rawg']
        assert real_config['rawg']['api_key'] != 'test_key_123'
        
        lookup = GameLookup(real_config)
        assert lookup is not None
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_game_search_real_api(self, real_config):
        """Test recherche réelle de jeu via RAWG API"""
        from backends.game_lookup import GameLookup
        
        lookup = GameLookup(real_config)
        
        # Recherche un jeu populaire
        result = await lookup.search_game("Minecraft")
        
        assert result is not None
        # Devrait trouver au moins un résultat
        print(f"\n✅ Recherche Minecraft: {result}")


@pytest.mark.local
@pytest.mark.requires_rawg
class TestQuantumGameCacheWithRealAPI:
    """Tests QuantumGameCache avec vraie clé RAWG"""
    
    @pytest.fixture
    def real_config(self):
        """Charge la vraie config"""
        with open("config/config.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    
    def test_quantum_cache_with_real_key(self, real_config):
        """Test QuantumGameCache avec vraie clé"""
        from backends.quantum_game_cache import QuantumGameCache
        
        cache = QuantumGameCache(real_config)
        assert cache is not None
        
        # Test set/get
        game_data = {'id': 1, 'name': 'Test Game', 'released': '2024-01-01'}
        cache.set('test_game', game_data, verified=True)
        
        result = cache.get('test_game')
        assert result is not None
        assert result['name'] == 'Test Game'
        print(f"\n✅ Cache quantum opérationnel: {result}")
