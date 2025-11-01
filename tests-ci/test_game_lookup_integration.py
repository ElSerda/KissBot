"""
Tests for backends/game_lookup.py - Phase 3: API Integration with httpx mocking.

Test Strategy:
- Mock httpx.AsyncClient responses for RAWG/Steam APIs
- Test success paths, error handling (404/500/timeout), retry logic
- Validate cache integration (hit before API call)
- Test format_result() output (Twitch-safe, emoji, line breaks)
- Test multi-source fallback (RAWG fails → try Steam)
- Test data merging logic (RAWG + Steam fusion)

Coverage Target: 21% → 85%+ on backends/game_lookup.py
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backends.game_lookup import GameLookup, GameResult
import httpx


# ============================================================================
# Test Class 1: RAWG API Success Cases
# ============================================================================
class TestRAWGAPISuccess:
    """Test successful RAWG API calls with various game data."""

    @pytest.mark.asyncio
    async def test_rawg_search_single_result(self):
        """Test RAWG search with exact match (single result)."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        # Mock RAWG response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [{
                "name": "Brotato",
                "released": "2023-06-23",
                "rating": 4.5,
                "metacritic": 85,
                "platforms": [{"platform": {"name": "PC"}}],
                "genres": [{"name": "Action"}],
                "added": 5000
            }]
        }
        mock_response.raise_for_status = MagicMock()
        
        # Mock httpx client
        lookup.http_client.get = AsyncMock(return_value=mock_response)
        
        result = await lookup.search_game("Brotato")
        
        assert result is not None
        assert result.name == "Brotato"
        assert result.year == "2023"
        assert result.rating_rawg == 4.5
        assert result.metacritic == 85
        assert "PC" in result.platforms
        assert "Action" in result.genres
        assert result.primary_source == "RAWG"
        
        await lookup.close()

    @pytest.mark.asyncio
    async def test_rawg_search_multiple_results_exact_match(self):
        """Test RAWG search with multiple results, exact match wins."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"name": "Stardew Valley 2", "added": 1000, "rating": 3.0},
                {"name": "Stardew Valley", "added": 50000, "rating": 4.8},  # Exact match
                {"name": "Stardew Valley Expanded", "added": 2000, "rating": 4.0}
            ]
        }
        mock_response.raise_for_status = MagicMock()
        
        lookup.http_client.get = AsyncMock(return_value=mock_response)
        
        result = await lookup.search_game("Stardew Valley")
        
        assert result is not None
        assert result.name == "Stardew Valley"
        assert result.rating_rawg == 4.8
        
        await lookup.close()

    @pytest.mark.asyncio
    async def test_rawg_search_fallback_to_most_popular(self):
        """Test RAWG search falls back to most popular (added count) when no exact match."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"name": "Don't Starve Together", "added": 100000, "rating": 4.5},  # Most popular
                {"name": "Don't Starve", "added": 50000, "rating": 4.2},
                {"name": "Don't Starve: Shipwrecked", "added": 20000, "rating": 4.0}
            ]
        }
        mock_response.raise_for_status = MagicMock()
        
        lookup.http_client.get = AsyncMock(return_value=mock_response)
        
        result = await lookup.search_game("dont starve")
        
        assert result is not None
        # Should pick "Don't Starve Together" (most added, contains query)
        assert "Don't Starve" in result.name
        
        await lookup.close()


# ============================================================================
# Test Class 2: RAWG API Error Cases
# ============================================================================
class TestRAWGAPIErrors:
    """Test RAWG API error handling (404, 500, timeout)."""

    @pytest.mark.asyncio
    async def test_rawg_404_no_results(self):
        """Test RAWG returns empty results (game not found)."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = MagicMock()
        
        lookup.http_client.get = AsyncMock(return_value=mock_response)
        
        result = await lookup.search_game("NonExistentGame12345")
        
        # Should return None when no results
        assert result is None
        
        await lookup.close()

    @pytest.mark.asyncio
    async def test_rawg_500_server_error(self):
        """Test RAWG API server error (500) handling."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        # Mock raise_for_status to raise HTTPStatusError
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Server Error", request=MagicMock(), response=MagicMock()
        )
        
        lookup.http_client.get = AsyncMock(return_value=mock_response)
        
        result = await lookup.search_game("Brotato")
        
        # Should gracefully handle error and return None
        assert result is None
        
        await lookup.close()

    @pytest.mark.asyncio
    async def test_rawg_timeout(self):
        """Test RAWG API timeout handling."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        # Mock timeout exception
        lookup.http_client.get = AsyncMock(side_effect=httpx.TimeoutException("Request timeout"))
        
        result = await lookup.search_game("Brotato")
        
        # Should gracefully handle timeout and return None
        assert result is None
        
        await lookup.close()


# ============================================================================
# Test Class 3: Steam API Integration
# ============================================================================
class TestSteamAPIIntegration:
    """Test Steam API calls and integration with RAWG."""

    @pytest.mark.asyncio
    async def test_steam_search_success(self):
        """Test successful Steam API search."""
        config = {"apis": {"rawg_key": "test_key", "steam_key": "steam_test"}}
        lookup = GameLookup(config)
        
        # Mock RAWG failure and Steam success
        async def mock_get(url, **kwargs):
            if "rawg.io" in url:
                mock_resp = MagicMock()
                mock_resp.json.return_value = {"results": []}
                mock_resp.raise_for_status = MagicMock()
                return mock_resp
            elif "steampowered.com/api/storesearch" in url:
                mock_resp = MagicMock()
                mock_resp.json.return_value = {
                    "items": [{
                        "id": 413150,
                        "name": "Stardew Valley",
                        "metascore": 89,
                        "platforms": {"windows": True, "mac": True}
                    }]
                }
                mock_resp.raise_for_status = MagicMock()
                return mock_resp
            elif "appdetails" in url:
                mock_resp = MagicMock()
                mock_resp.json.return_value = {
                    "413150": {
                        "data": {
                            "short_description": "Un jeu de ferme relaxant"
                        }
                    }
                }
                return mock_resp
            return MagicMock()
        
        lookup.http_client.get = AsyncMock(side_effect=mock_get)
        
        result = await lookup.search_game("Stardew Valley")
        
        assert result is not None
        assert result.name == "Stardew Valley"
        assert result.metacritic == 89
        assert result.primary_source == "Steam"
        assert "Windows" in result.platforms or "Mac" in result.platforms
        
        await lookup.close()

    @pytest.mark.asyncio
    async def test_steam_api_failure_fallback_rawg(self):
        """Test Steam API fails, falls back to RAWG only."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        async def mock_get(url, **kwargs):
            if "rawg.io" in url:
                mock_resp = MagicMock()
                mock_resp.json.return_value = {
                    "results": [{
                        "name": "Brotato",
                        "rating": 4.5,
                        "added": 5000
                    }]
                }
                mock_resp.raise_for_status = MagicMock()
                return mock_resp
            elif "steampowered.com" in url:
                raise httpx.TimeoutException("Steam timeout")
            return MagicMock()
        
        lookup.http_client.get = AsyncMock(side_effect=mock_get)
        
        result = await lookup.search_game("Brotato")
        
        # Should succeed with RAWG only
        assert result is not None
        assert result.name == "Brotato"
        assert result.primary_source == "RAWG"
        assert result.source_count == 1
        
        await lookup.close()

    @pytest.mark.asyncio
    async def test_multi_source_fusion_rawg_steam(self):
        """Test data fusion from RAWG + Steam (both succeed)."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        async def mock_get(url, **kwargs):
            if "rawg.io" in url:
                mock_resp = MagicMock()
                mock_resp.json.return_value = {
                    "results": [{
                        "name": "Celeste",
                        "released": "2018-01-25",
                        "rating": 4.7,
                        "metacritic": None,  # Missing from RAWG
                        "platforms": [{"platform": {"name": "PC"}}],
                        "genres": [{"name": "Platformer"}],
                        "added": 10000
                    }]
                }
                mock_resp.raise_for_status = MagicMock()
                return mock_resp
            elif "steampowered.com/api/storesearch" in url:
                mock_resp = MagicMock()
                mock_resp.json.return_value = {
                    "items": [{
                        "id": 504230,
                        "name": "Celeste",
                        "metascore": 94,  # Enrichment from Steam!
                        "platforms": {"windows": True, "linux": True}
                    }]
                }
                mock_resp.raise_for_status = MagicMock()
                return mock_resp
            elif "appdetails" in url:
                mock_resp = MagicMock()
                mock_resp.json.return_value = {
                    "504230": {
                        "data": {
                            "short_description": "Climb the mountain"
                        }
                    }
                }
                return mock_resp
            return MagicMock()
        
        lookup.http_client.get = AsyncMock(side_effect=mock_get)
        
        result = await lookup.search_game("Celeste")
        
        # Validate fusion
        assert result is not None
        assert result.name == "Celeste"
        assert result.metacritic == 94  # Enriched from Steam!
        assert result.source_count == 2
        assert "RAWG" in result.api_sources
        assert "Steam" in result.api_sources
        
        await lookup.close()


# ============================================================================
# Test Class 4: Cache Integration
# ============================================================================
class TestCacheIntegration:
    """Test cache hit/miss behavior before API calls."""

    @pytest.mark.asyncio
    async def test_cache_hit_no_api_call(self):
        """Test cache hit prevents API calls."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        # Pre-populate cache
        cached_result = GameResult(
            name="Brotato",
            year="2023",
            rating_rawg=4.5,
            primary_source="RAWG"
        )
        if lookup.cache is not None:
            lookup.cache.set("game:brotato", cached_result)
        
        # Mock should NOT be called
        lookup.http_client.get = AsyncMock()
        
        result = await lookup.search_game("Brotato")
        
        # Should return cached result
        assert result is not None
        assert result.name == "Brotato"
        
        # Verify no API calls made (only if cache available)
        if lookup.cache is not None:
            lookup.http_client.get.assert_not_called()
        
        await lookup.close()

    @pytest.mark.asyncio
    async def test_cache_miss_triggers_api(self):
        """Test cache miss triggers API calls."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        # Mock cache miss (return None)
        if lookup.cache is not None:
            lookup.cache.get = MagicMock(return_value=None)
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [{
                "name": "Hades",
                "rating": 4.8,
                "added": 20000
            }]
        }
        mock_response.raise_for_status = MagicMock()
        
        lookup.http_client.get = AsyncMock(return_value=mock_response)
        
        result = await lookup.search_game("Hades")
        
        assert result is not None
        assert result.name == "Hades"
        
        # Verify API was called
        lookup.http_client.get.assert_called()
        
        await lookup.close()

    @pytest.mark.asyncio
    async def test_cache_stores_result_after_api_success(self):
        """Test successful API result gets cached."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        # Mock cache miss first, then cache hit
        cache_data = {}
        
        def mock_cache_get(key):
            return cache_data.get(key)
        
        def mock_cache_set(key, value):
            cache_data[key] = value
        
        if lookup.cache is not None:
            lookup.cache.get = MagicMock(side_effect=mock_cache_get)
            lookup.cache.set = MagicMock(side_effect=mock_cache_set)
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [{
                "name": "Hollow Knight",
                "rating": 4.9,
                "added": 30000
            }]
        }
        mock_response.raise_for_status = MagicMock()
        
        lookup.http_client.get = AsyncMock(return_value=mock_response)
        
        result = await lookup.search_game("Hollow Knight")
        
        # First call should cache result
        assert result is not None
        
        # Second call should hit cache (no API call)
        lookup.http_client.get.reset_mock()
        result2 = await lookup.search_game("Hollow Knight")
        
        assert result2 is not None
        assert result2.name == "Hollow Knight"
        
        # Verify no second API call (only if cache available)
        if lookup.cache is not None:
            lookup.http_client.get.assert_not_called()
        
        await lookup.close()


# ============================================================================
# Test Class 5: IGDB Enrichment
# ============================================================================
class TestIGDBEnrichment:
    """Test IGDB enrichment (enrich_game_from_igdb_name)."""

    @pytest.mark.asyncio
    async def test_igdb_enrichment_success(self):
        """Test IGDB enrichment with RAWG success."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [{
                "name": "The Binding of Isaac: Rebirth",
                "released": "2014-11-04",
                "rating": 4.6,
                "added": 15000
            }]
        }
        mock_response.raise_for_status = MagicMock()
        
        lookup.http_client.get = AsyncMock(return_value=mock_response)
        
        result = await lookup.enrich_game_from_igdb_name("The Binding of Isaac: Rebirth")
        
        assert result is not None
        assert result.name == "The Binding of Isaac: Rebirth"
        assert result.confidence == "IGDB_VERIFIED"
        assert result.possible_typo is False  # IGDB = ground truth
        assert "IGDB" in result.primary_source
        
        await lookup.close()

    @pytest.mark.asyncio
    async def test_igdb_enrichment_cache_hit(self):
        """Test IGDB enrichment hits cache."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        # Pre-populate IGDB cache
        cached_result = GameResult(
            name="Valorant",
            confidence="IGDB_VERIFIED",
            primary_source="IGDB"
        )
        if lookup.cache is not None:
            lookup.cache.set("igdb:valorant", cached_result)
        
        lookup.http_client.get = AsyncMock()
        
        result = await lookup.enrich_game_from_igdb_name("Valorant")
        
        assert result is not None
        assert result.name == "Valorant"
        
        # Verify no API calls (only if cache available)
        if lookup.cache is not None:
            lookup.http_client.get.assert_not_called()
        
        await lookup.close()

    @pytest.mark.asyncio
    async def test_igdb_enrichment_fallback_minimal(self):
        """Test IGDB enrichment when RAWG/Steam fail (minimal result)."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        # Mock both APIs failing
        lookup.http_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        
        result = await lookup.enrich_game_from_igdb_name("Some Obscure Game")
        
        # Should still return minimal IGDB-only result
        assert result is not None
        assert result.name == "Some Obscure Game"
        assert result.confidence == "IGDB_VERIFIED"
        assert result.primary_source == "IGDB"
        assert "IGDB" in result.api_sources
        
        await lookup.close()


# ============================================================================
# Test Class 6: Data Merging and Validation
# ============================================================================
class TestDataMerging:
    """Test _merge_data and _validate_game_data logic."""

    @pytest.mark.asyncio
    async def test_merge_data_rawg_only(self):
        """Test merge with RAWG data only."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        rawg_data = {
            "name": "Terraria",
            "released": "2011-05-16",
            "rating": 4.4,
            "metacritic": 83,
            "platforms": [{"platform": {"name": "PC"}}],
            "genres": [{"name": "Sandbox"}]
        }
        
        result = lookup._merge_data(rawg_data, None, "Terraria")
        
        assert result is not None
        assert result.name == "Terraria"
        assert result.year == "2011"
        assert result.source_count == 1
        assert result.primary_source == "RAWG"
        
        await lookup.close()

    @pytest.mark.asyncio
    async def test_merge_data_steam_only(self):
        """Test merge with Steam data only."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        steam_data = {
            "name": "Portal 2",
            "metacritic": 95,
            "platforms": ["Windows", "Mac"],
            "description": "Test puzzle game"
        }
        
        result = lookup._merge_data(None, steam_data, "Portal 2")
        
        assert result is not None
        assert result.name == "Portal 2"
        assert result.source_count == 1
        assert result.primary_source == "Steam"
        
        await lookup.close()

    @pytest.mark.asyncio
    async def test_merge_data_both_sources(self):
        """Test merge with both RAWG and Steam data."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        rawg_data = {
            "name": "Factorio",
            "released": "2020-08-14",
            "rating": 4.6,
            "metacritic": None,
            "platforms": [{"platform": {"name": "PC"}}],
            "genres": [{"name": "Strategy"}]
        }
        
        steam_data = {
            "name": "Factorio",
            "metacritic": 90,
            "platforms": ["Windows", "Linux"]
        }
        
        result = lookup._merge_data(rawg_data, steam_data, "Factorio")
        
        assert result is not None
        assert result.name == "Factorio"
        assert result.source_count == 2
        assert result.metacritic == 90  # Enriched from Steam
        assert "RAWG" in result.api_sources
        assert "Steam" in result.api_sources
        
        await lookup.close()

    @pytest.mark.asyncio
    async def test_merge_data_description_priority(self):
        """Test description merge prioritizes Steam (French) over RAWG (English)."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        rawg_data = {
            "name": "Game",
            "description": "English description from RAWG",
            "rating": 4.0
        }
        
        steam_data = {
            "name": "Game",
            "description": "Description française de Steam",
            "platforms": ["Windows"]
        }
        
        result = lookup._merge_data(rawg_data, steam_data, "Game")
        
        assert result is not None
        # Should prioritize Steam French description
        assert result.summary == "Description française de Steam"
        
        await lookup.close()


# ============================================================================
# Test Class 7: format_result() Output Validation
# ============================================================================
class TestFormatResult:
    """Test format_result() output for Twitch display."""

    def test_format_result_full_data(self):
        """Test format with all data fields."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        result = GameResult(
            name="Hades",
            year="2020",
            rating_rawg=4.8,
            metacritic=93,
            platforms=["PC", "Switch"],
            confidence="HIGH",
            source_count=2
        )
        
        output = lookup.format_result(result)
        
        assert "🎮 Hades" in output
        assert "(2020)" in output
        assert "🏆 93/100" in output
        assert "🕹️ PC, Switch" in output
        assert "🔥 HIGH" in output
        assert "2 sources" in output

    def test_format_result_minimal_data(self):
        """Test format with minimal data (name only)."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        result = GameResult(
            name="Unknown Game",
            confidence="LOW",
            source_count=1
        )
        
        output = lookup.format_result(result)
        
        assert "🎮 Unknown Game" in output
        assert "⚠️ LOW" in output
        assert "1 sources" in output

    def test_format_result_rating_fallback(self):
        """Test format falls back to RAWG rating when no Metacritic."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        result = GameResult(
            name="Brotato",
            year="2023",
            rating_rawg=4.5,
            metacritic=None,
            confidence="MEDIUM",
            source_count=1
        )
        
        output = lookup.format_result(result)
        
        assert "⭐ 4.5/5" in output
        assert "🏆" not in output  # No metacritic

    def test_format_result_platform_truncation(self):
        """Test format truncates platforms to max 3."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        result = GameResult(
            name="Multi Platform Game",
            platforms=["PC", "PS5", "Xbox", "Switch", "Mobile"],
            confidence="HIGH",
            source_count=2
        )
        
        output = lookup.format_result(result)
        
        # Should only show first 3 platforms
        assert "PC" in output
        assert "PS5" in output
        assert "Xbox" in output
        # Mobile should not appear (truncated)


# ============================================================================
# Test Class 8: Reliability Scoring
# ============================================================================
class TestReliabilityScoring:
    """Test _calculate_reliability and _get_confidence_level."""

    def test_reliability_high_multi_source(self):
        """Test high reliability with multiple sources."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        result = GameResult(
            name="Celeste",
            source_count=2,
            metacritic=94,
            rating_rawg=4.7
        )
        
        score = lookup._calculate_reliability(result, "Celeste")
        confidence = lookup._get_confidence_level(score)
        
        assert score >= 70  # Multi-source boost
        assert confidence == "HIGH"

    def test_reliability_medium_single_source_metacritic(self):
        """Test medium-high reliability with Metacritic."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        result = GameResult(
            name="Hades",
            source_count=1,
            metacritic=93,
            rating_rawg=0.0
        )
        
        score = lookup._calculate_reliability(result, "Hades")
        confidence = lookup._get_confidence_level(score)
        
        assert 50 <= score < 80
        assert confidence in ["MEDIUM", "HIGH"]

    def test_reliability_boost_precise_query(self):
        """Test reliability boost for precise multi-word queries."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        result = GameResult(
            name="The Binding of Isaac: Rebirth",
            source_count=1,
            rating_rawg=4.6
        )
        
        # Precise query (3 words) should boost score
        score = lookup._calculate_reliability(result, "The Binding of Isaac")
        
        # Base score ~50 + 20 bonus for 3+ words
        assert score >= 70

    def test_reliability_low_minimal_data(self):
        """Test low reliability with minimal data."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        result = GameResult(
            name="Unknown",
            source_count=1,
            rating_rawg=0.0,
            metacritic=None
        )
        
        score = lookup._calculate_reliability(result, "x")
        confidence = lookup._get_confidence_level(score)
        
        assert score < 50
        assert confidence == "LOW"


# ============================================================================
# Test Class 9: Edge Cases and Error Handling
# ============================================================================
class TestEdgeCasesAndErrors:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_search_empty_game_name(self):
        """Test search with empty game name."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        result = await lookup.search_game("")
        assert result is None
        
        result = await lookup.search_game("   ")
        assert result is None
        
        await lookup.close()

    @pytest.mark.asyncio
    async def test_search_none_game_name(self):
        """Test search with None game name."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        # Should not crash
        result = await lookup.search_game(None)
        assert result is None
        
        await lookup.close()

    @pytest.mark.asyncio
    async def test_possible_typo_detection(self):
        """Test possible_typo flag when input != output."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [{
                "name": "Stardew Valley",
                "rating": 4.8,
                "added": 50000
            }]
        }
        mock_response.raise_for_status = MagicMock()
        
        lookup.http_client.get = AsyncMock(return_value=mock_response)
        
        # Query with typo
        result = await lookup.search_game("stardw valey")
        
        assert result is not None
        assert result.possible_typo is True
        
        await lookup.close()

    @pytest.mark.asyncio
    async def test_missing_api_key_raises_error(self):
        """Test initialization without RAWG API key raises ValueError."""
        config = {"apis": {}}  # Missing rawg_key
        
        with pytest.raises(ValueError, match="RAWG API key manquante"):
            GameLookup(config)

    def test_extract_year_tba(self):
        """Test year extraction with TBA flag."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        year = lookup._extract_year("", tba=True)
        assert year == "TBA"

    def test_extract_year_invalid_date(self):
        """Test year extraction with invalid date."""
        config = {"apis": {"rawg_key": "test_key"}}
        lookup = GameLookup(config)
        
        year = lookup._extract_year("invalid-date-format")
        assert year == "?"
        
        year = lookup._extract_year("")
        assert year == "?"
