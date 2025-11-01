"""
Phase 2: Cache System Tests - Memory Management & TTL

WHY THESE TESTS EXIST:
GameCache is the foundation of the game system. It manages in-memory storage,
TTL expiration, serialization, and provides fast lookups. Without a reliable cache,
every game query would hit APIs (slow, expensive, rate-limited).

CURRENT STATE:
- Coverage: 50% (basic operations tested, TTL/cleanup not tested)
- No tests for expiration logic
- No tests for serialization edge cases
- No tests for cache stats

TARGET:
- Coverage: 90%+ on backends/game_cache.py
- 12-15 comprehensive tests
- Light mocking (time for TTL tests)
- Validate cache persistence and cleanup

PHILOSOPHY:
Cache is the performance backbone. If cache fails, the entire bot slows down.
Test every edge case: expiration, serialization, concurrent writes, cleanup.
"""

import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backends.game_cache import GameCache


class TestGameCacheBasicOperations:
    """Test basic set/get operations"""
    
    def test_set_and_get_game(self):
        """Basic set/get operation should work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "test_cache.json")
            cache = GameCache(config={"cache": {}}, cache_file=cache_file)
            
            # Set a game
            success = cache.set("brotato_123", {"name": "Brotato", "id": 123})
            assert success is True
            
            # Get the game
            result = cache.get("brotato_123")
            assert result is not None
            assert result["name"] == "Brotato"
            assert result["id"] == 123
    
    def test_get_nonexistent_game(self):
        """Getting nonexistent game should return None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "test_cache.json")
            cache = GameCache(config={"cache": {}}, cache_file=cache_file)
            
            result = cache.get("nonexistent_game")
            assert result is None
    
    def test_cache_key_normalization(self):
        """Cache keys should be normalized (lowercase, stripped)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "test_cache.json")
            cache = GameCache(config={"cache": {}}, cache_file=cache_file)
            
            # Set with mixed case and spaces
            cache.set("  Brotato Game  ", {"name": "Brotato", "id": 123})
            
            # Get with different case/spacing should work
            result = cache.get("brotato game")
            assert result is not None
            assert result["name"] == "Brotato"


class TestGameCacheTTLExpiration:
    """Test TTL (Time To Live) expiration logic"""
    
    def test_entry_expires_after_duration(self):
        """Cache entry should expire after configured duration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "test_cache.json")
            # Configure 1-hour TTL
            cache = GameCache(
                config={"cache": {"duration_hours": 1}}, 
                cache_file=cache_file
            )
            
            # Set a game
            cache.set("brotato_123", {"name": "Brotato", "id": 123})
            
            # Mock time 2 hours in the future
            future_time = datetime.now() + timedelta(hours=2)
            with patch('backends.game_cache.datetime') as mock_datetime:
                mock_datetime.now.return_value = future_time
                mock_datetime.fromisoformat = datetime.fromisoformat
                
                # Should be expired
                result = cache.get("brotato_123")
                assert result is None
    
    def test_entry_valid_before_expiration(self):
        """Cache entry should be valid before expiration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "test_cache.json")
            # Configure 24-hour TTL
            cache = GameCache(
                config={"cache": {"duration_hours": 24}}, 
                cache_file=cache_file
            )
            
            # Set a game
            cache.set("brotato_123", {"name": "Brotato", "id": 123})
            
            # Mock time 1 hour in the future (still valid)
            future_time = datetime.now() + timedelta(hours=1)
            with patch('backends.game_cache.datetime') as mock_datetime:
                mock_datetime.now.return_value = future_time
                mock_datetime.fromisoformat = datetime.fromisoformat
                
                # Should still be valid
                result = cache.get("brotato_123")
                assert result is not None
                assert result["name"] == "Brotato"
    
    def test_default_ttl_24_hours(self):
        """Default TTL should be 24 hours if not configured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "test_cache.json")
            cache = GameCache(config={"cache": {}}, cache_file=cache_file)
            
            # Default should be 24 hours
            assert cache.cache_duration == timedelta(hours=24)


class TestGameCacheCleanup:
    """Test cache cleanup operations"""
    
    def test_cleanup_expired_removes_old_entries(self):
        """cleanup_expired() should remove expired entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "test_cache.json")
            cache = GameCache(
                config={"cache": {"duration_hours": 1}}, 
                cache_file=cache_file
            )
            
            # Add multiple games
            cache.set("brotato_123", {"name": "Brotato", "id": 123})
            cache.set("stardew_456", {"name": "Stardew Valley", "id": 456})
            
            # Mock time 2 hours in the future
            future_time = datetime.now() + timedelta(hours=2)
            with patch('backends.game_cache.datetime') as mock_datetime:
                mock_datetime.now.return_value = future_time
                mock_datetime.fromisoformat = datetime.fromisoformat
                
                # Cleanup should remove both
                removed_count = cache.cleanup_expired()
                assert removed_count == 2
                assert len(cache.cache) == 0
    
    def test_cleanup_expired_keeps_valid_entries(self):
        """cleanup_expired() should keep valid entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "test_cache.json")
            cache = GameCache(
                config={"cache": {"duration_hours": 24}}, 
                cache_file=cache_file
            )
            
            # Add games
            cache.set("brotato_123", {"name": "Brotato", "id": 123})
            cache.set("stardew_456", {"name": "Stardew Valley", "id": 456})
            
            # Mock time 1 hour in the future (still valid)
            future_time = datetime.now() + timedelta(hours=1)
            with patch('backends.game_cache.datetime') as mock_datetime:
                mock_datetime.now.return_value = future_time
                mock_datetime.fromisoformat = datetime.fromisoformat
                
                # Cleanup should remove nothing
                removed_count = cache.cleanup_expired()
                assert removed_count == 0
                assert len(cache.cache) == 2
    
    def test_clear_all_empties_cache(self):
        """clear_all() should empty the entire cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "test_cache.json")
            cache = GameCache(config={"cache": {}}, cache_file=cache_file)
            
            # Add games
            cache.set("brotato_123", {"name": "Brotato", "id": 123})
            cache.set("stardew_456", {"name": "Stardew Valley", "id": 456})
            
            # Clear all
            cache.clear_all()
            
            assert len(cache.cache) == 0
            assert cache.get("brotato_123") is None
    
    def test_clear_game_removes_specific_entry(self):
        """clear_game() should remove a specific game."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "test_cache.json")
            cache = GameCache(config={"cache": {}}, cache_file=cache_file)
            
            # Add games
            cache.set("brotato_123", {"name": "Brotato", "id": 123})
            cache.set("stardew_456", {"name": "Stardew Valley", "id": 456})
            
            # Clear one game
            success = cache.clear_game("brotato_123")
            
            assert success is True
            assert cache.get("brotato_123") is None
            assert cache.get("stardew_456") is not None  # Other still exists


class TestGameCachePersistence:
    """Test cache persistence (save/load from disk)"""
    
    def test_cache_persists_across_instances(self):
        """Cache should persist when saved and loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "test_cache.json")
            
            # First instance: set data
            cache1 = GameCache(config={"cache": {}}, cache_file=cache_file)
            cache1.set("brotato_123", {"name": "Brotato", "id": 123})
            
            # Second instance: should load data
            cache2 = GameCache(config={"cache": {}}, cache_file=cache_file)
            result = cache2.get("brotato_123")
            
            assert result is not None
            assert result["name"] == "Brotato"
    
    def test_cache_loads_valid_entries_only(self):
        """On load, only valid (non-expired) entries should be loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "test_cache.json")
            
            # Manually create cache file with one expired, one valid
            old_time = (datetime.now() - timedelta(hours=48)).isoformat()
            recent_time = datetime.now().isoformat()
            
            cache_data = {
                "old_game": {
                    "data": {"name": "Old Game", "id": 111},
                    "cached_at": old_time,
                    "query": "old_game"
                },
                "new_game": {
                    "data": {"name": "New Game", "id": 222},
                    "cached_at": recent_time,
                    "query": "new_game"
                }
            }
            
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f)
            
            # Load cache (24h TTL by default)
            cache = GameCache(config={"cache": {}}, cache_file=cache_file)
            
            # Old game should be filtered out
            assert cache.get("old_game") is None
            # New game should be loaded
            assert cache.get("new_game") is not None
    
    def test_cache_file_created_if_missing(self):
        """Cache file should be created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "new_cache.json")
            
            # File doesn't exist yet
            assert not os.path.exists(cache_file)
            
            # Create cache
            cache = GameCache(config={"cache": {}}, cache_file=cache_file)
            cache.set("brotato_123", {"name": "Brotato", "id": 123})
            
            # File should now exist
            assert os.path.exists(cache_file)


class TestGameCacheStats:
    """Test cache statistics"""
    
    def test_get_stats_returns_correct_count(self):
        """get_stats() should return correct total_keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "test_cache.json")
            cache = GameCache(config={"cache": {}}, cache_file=cache_file)
            
            # Add games
            cache.set("brotato_123", {"name": "Brotato", "id": 123})
            cache.set("stardew_456", {"name": "Stardew Valley", "id": 456})
            cache.set("isaac_789", {"name": "The Binding of Isaac", "id": 789})
            
            stats = cache.get_stats()
            
            assert stats.total_keys == 3
            assert stats.confirmed_keys == 3
    
    def test_get_stats_empty_cache(self):
        """get_stats() should work with empty cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "test_cache.json")
            cache = GameCache(config={"cache": {}}, cache_file=cache_file)
            
            stats = cache.get_stats()
            
            assert stats.total_keys == 0
            assert stats.confirmed_keys == 0


class TestGameCacheInterfaceCompatibility:
    """Test interface compatibility methods (async, clear, search)"""
    
    async def test_search_delegates_to_get(self):
        """search() should delegate to get() for interface compatibility."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "test_cache.json")
            cache = GameCache(config={"cache": {}}, cache_file=cache_file)
            
            cache.set("brotato_123", {"name": "Brotato", "id": 123})
            
            # search() should work like get()
            result = await cache.search("brotato_123")
            
            assert result is not None
            assert result["name"] == "Brotato"
    
    def test_clear_delegates_to_clear_all(self):
        """clear() should delegate to clear_all()."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "test_cache.json")
            cache = GameCache(config={"cache": {}}, cache_file=cache_file)
            
            cache.set("brotato_123", {"name": "Brotato", "id": 123})
            
            # clear() should empty cache
            success = cache.clear()
            
            assert success is True
            assert len(cache.cache) == 0


class TestGameCacheEdgeCases:
    """Test edge cases and error handling"""
    
    def test_set_with_empty_key(self):
        """Setting with empty key should handle gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "test_cache.json")
            cache = GameCache(config={"cache": {}}, cache_file=cache_file)
            
            # Empty key should still work (normalized to "")
            success = cache.set("", {"name": "Empty", "id": 999})
            assert success is True
    
    def test_get_with_empty_key(self):
        """Getting with empty key should return None or stored value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "test_cache.json")
            cache = GameCache(config={"cache": {}}, cache_file=cache_file)
            
            cache.set("", {"name": "Empty", "id": 999})
            
            result = cache.get("")
            assert result is not None
    
    def test_cache_handles_unicode_names(self):
        """Cache should handle unicode game names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "test_cache.json")
            cache = GameCache(config={"cache": {}}, cache_file=cache_file)
            
            # Unicode game name
            cache.set("persona_5", {"name": "Persona 5 ペルソナ5", "id": 555})
            
            result = cache.get("persona_5")
            assert result is not None
            assert "ペルソナ5" in result["name"]
    
    def test_cache_handles_special_chars_in_data(self):
        """Cache should handle special characters in game data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "test_cache.json")
            cache = GameCache(config={"cache": {}}, cache_file=cache_file)
            
            # Game with special chars in description
            game_data = {
                "name": "Test Game",
                "description": "A game with \"quotes\" and 'apostrophes' and newlines\n\ntab\t"
            }
            
            cache.set("test_game", game_data)
            result = cache.get("test_game")
            
            assert result is not None
            assert "quotes" in result["description"]
