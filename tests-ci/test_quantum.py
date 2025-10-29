"""
Tests CI - Système Quantum Cache
Vérifie que le cache quantique fonctionne (si utilisé)
"""
import pytest


class TestQuantumCommands:
    """Tests des commandes quantum"""

    def test_quantum_commands_imports(self):
        """Vérifie que QuantumCommands s'importe"""
        from commands.quantum_commands import QuantumCommands
        
        assert QuantumCommands is not None

    def test_quantum_commands_has_expected_methods(self):
        """Vérifie que QuantumCommands a les méthodes attendues"""
        from commands.quantum_commands import QuantumCommands
        
        component = QuantumCommands()
        
        # Méthode principale
        assert hasattr(component, 'quantum_status'), "Méthode quantum_status doit exister"


class TestQuantumCache:
    """Tests du cache quantique (si présent)"""

    def test_quantum_cache_module_exists(self):
        """Vérifie que le module quantum_cache existe"""
        try:
            from core.quantum_cache import QuantumCache
            assert QuantumCache is not None
        except ImportError:
            pytest.skip("core.quantum_cache n'existe pas ou n'est pas utilisé")

    @pytest.mark.unit
    def test_quantum_cache_basic_operations(self):
        """Test les opérations de base du cache quantum."""
        from core.quantum_cache import QuantumCache
        
        # QuantumCache nécessite une config, créons-en une simple
        config = {"cache": {"max_size": 100, "ttl_seconds": 3600}}
        cache = QuantumCache(config)
        
        # Test set/get basique
        cache.set("test_key", "test_value")
        value = cache.get("test_key")
        
        assert value is not None


class TestQuantumMetrics:
    """Tests des métriques quantiques"""

    def test_quantum_metrics_imports(self):
        """Vérifie que quantum_metrics s'importe"""
        try:
            from intelligence.quantum_metrics import QuantumMetrics
            assert QuantumMetrics is not None
        except ImportError:
            pytest.skip("quantum_metrics non utilisé dans ce projet")

    @pytest.mark.slow
    def test_quantum_metrics_instantiation(self):
        """Vérifie qu'on peut instancier QuantumMetrics"""
        try:
            from intelligence.quantum_metrics import QuantumMetrics
            
            metrics = QuantumMetrics()
            assert metrics is not None
            
            # Vérifie méthodes attendues
            assert hasattr(metrics, 'record_classification')
            
        except ImportError:
            pytest.skip("QuantumMetrics non disponible")
