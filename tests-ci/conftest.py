"""
Pytest configuration for CI tests
Provides common fixtures and test config
"""
import pytest


@pytest.fixture
def mock_config():
    """Mock configuration for tests (no real API keys needed)"""
    return {
        'apis': {
            'rawg_key': 'test_rawg_key_mock',
            'openai_key': 'test_openai_key_mock',
            'timeout': 10.0
        },
        'cache': {
            'max_size': 100,
            'ttl_seconds': 3600,
            'duration_hours': 24
        },
        'quantum_games': {
            'max_suggestions': 3,
            'confirmation_confidence_boost': 0.2,
            'auto_entangle': True
        },
        'bot': {
            'name': 'test_bot',
            'debug': False
        }
    }


@pytest.fixture
def game_cache_config():
    """Specific config for GameCache tests"""
    return {
        'apis': {
            'rawg_key': 'mock_rawg_api_key_for_testing'
        },
        'cache': {
            'max_size': 100
        }
    }
