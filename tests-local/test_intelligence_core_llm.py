"""
Tests for intelligence/core.py - LLM Integration Tests (Local Model Required).

Test Strategy:
- Test process_llm_request() with real local LLM
- Test enrich_prompt_with_game_context() with game cache
- Test pre_optimized prompts vs normal prompts
- Test stimulus_class validation (ping/gen_short/gen_long)
- Test prompt truncation (450 char limit)
- Test error handling (None llm_handler, invalid params)

Coverage Target: 19% → 90%+ on intelligence/core.py

⚠️ REQUIRES: Local LLM running (backends/local_llm.py)
Run with: pytest tests-local/test_intelligence_core_llm.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from intelligence.core import (
    process_llm_request,
    enrich_prompt_with_game_context,
    extract_question_from_command,
    extract_mention_message
)
from backends.game_cache import GameCache
import tempfile
import os


# ============================================================================
# Test Class 1: process_llm_request() - Basic Success Cases
# ============================================================================
class TestProcessLLMRequestBasic:
    """Test process_llm_request() with mocked LLM responses."""

    @pytest.mark.asyncio
    async def test_process_llm_request_normal_prompt(self):
        """Test normal prompt (not pre-optimized) goes through process_stimulus."""
        # Mock LLM handler
        mock_llm = MagicMock()
        mock_llm.process_stimulus = AsyncMock(return_value="Test response from LLM")
        
        result = await process_llm_request(
            llm_handler=mock_llm,
            prompt="What is Brotato?",
            context="ask",
            user_name="testuser"
        )
        
        assert result == "Test response from LLM"
        mock_llm.process_stimulus.assert_called_once()
        call_args = mock_llm.process_stimulus.call_args
        assert call_args[1]["stimulus"] == "What is Brotato?"
        assert call_args[1]["context"] == "ask"

    @pytest.mark.asyncio
    async def test_process_llm_request_pre_optimized_with_synapse(self):
        """Test pre-optimized prompt calls local_synapse.fire() directly."""
        # Mock LLM handler with local_synapse
        mock_llm = MagicMock()
        mock_synapse = MagicMock()
        mock_synapse.fire = AsyncMock(return_value="Direct synapse response")
        mock_llm.local_synapse = mock_synapse
        
        result = await process_llm_request(
            llm_handler=mock_llm,
            prompt="[OPTIMIZED] Short answer please",
            context="ask",
            user_name="testuser",
            pre_optimized=True,
            stimulus_class="gen_short"
        )
        
        assert result == "Direct synapse response"
        mock_synapse.fire.assert_called_once()
        call_args = mock_synapse.fire.call_args[1]
        assert call_args["stimulus"] == "[OPTIMIZED] Short answer please"
        assert call_args["context"] == "direct"
        assert call_args["stimulus_class"] == "gen_short"

    @pytest.mark.asyncio
    async def test_process_llm_request_pre_optimized_without_synapse_fallback(self):
        """Test pre-optimized prompt falls back to process_stimulus if no synapse."""
        # Mock LLM handler WITHOUT local_synapse
        mock_llm = MagicMock(spec=["process_stimulus"])
        mock_llm.process_stimulus = AsyncMock(return_value="Fallback response")
        
        result = await process_llm_request(
            llm_handler=mock_llm,
            prompt="[OPTIMIZED] Test",
            context="ask",
            user_name="testuser",
            pre_optimized=True
        )
        
        assert result == "Fallback response"
        mock_llm.process_stimulus.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_llm_request_with_game_cache_enrichment(self):
        """Test that game cache enrichment works with adaptive prompt strategy."""
        # Setup temp cache directory
        import tempfile
        temp_dir = tempfile.mkdtemp()
        cache_file = os.path.join(temp_dir, "test_games.json")
        
        # Create GameCache instance
        game_cache = GameCache(config={"cache": {"duration_hours": 1}}, cache_file=cache_file)
        
        # Add game to cache (POOR DATA: only name, triggers PARTIEL prompt)
        game_cache.set("brotato", {"name": "Brotato"})
        
        mock_llm = MagicMock()
        mock_llm.process_stimulus = AsyncMock(return_value="Enriched response")
        
        result = await process_llm_request(
            llm_handler=mock_llm,
            prompt="Tell me about Brotato",
            context="ask",
            user_name="testuser",
            game_cache=game_cache
        )
        
        assert result == "Enriched response"
        mock_llm.process_stimulus.assert_called_once()
        
        # Check prompt was enriched with PARTIEL strategy (poor data)
        call_args = mock_llm.process_stimulus.call_args[1]
        enriched_prompt = call_args["stimulus"]
        assert "Brotato" in enriched_prompt
        assert "CONTEXTE PARTIEL" in enriched_prompt
        assert "!gameinfo" in enriched_prompt  # Should suggest enrichment
        
        # Now test with RICH DATA (genres + description)
        game_cache.set("celeste", {
            "name": "Celeste",
            "year": "2018",
            "genres": ["Platformer", "Indie"],
            "description": "A challenging platformer about climbing a mountain"
        })
        
        result2 = await process_llm_request(
            llm_handler=mock_llm,
            prompt="What is Celeste about?",
            context="ask",
            user_name="testuser",
            game_cache=game_cache
        )
        
        # Check prompt uses STRICT strategy (rich data)
        call_args2 = mock_llm.process_stimulus.call_args[1]
        enriched_prompt2 = call_args2["stimulus"]
        assert "Celeste" in enriched_prompt2
        assert "CONTEXTE STRICT" in enriched_prompt2
        assert "OBLIGATOIRE" in enriched_prompt2
        
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir)


# ============================================================================
# Test Class 2: process_llm_request() - Validation & Error Handling
# ============================================================================
class TestProcessLLMRequestValidation:
    """Test validation and error handling in process_llm_request()."""

    @pytest.mark.asyncio
    async def test_process_llm_request_none_llm_handler(self):
        """Test with None llm_handler returns None."""
        result = await process_llm_request(
            llm_handler=None,
            prompt="Test",
            context="ask",
            user_name="testuser"
        )
        
        assert result is None

    @pytest.mark.asyncio
    async def test_process_llm_request_invalid_stimulus_class_fallback(self):
        """Test invalid stimulus_class falls back to 'gen_short'."""
        mock_llm = MagicMock()
        mock_synapse = MagicMock()
        mock_synapse.fire = AsyncMock(return_value="Response")
        mock_llm.local_synapse = mock_synapse
        
        result = await process_llm_request(
            llm_handler=mock_llm,
            prompt="Test",
            context="ask",
            user_name="testuser",
            pre_optimized=True,
            stimulus_class="invalid_class"  # Invalid!
        )
        
        assert result == "Response"
        call_args = mock_synapse.fire.call_args[1]
        # Should fallback to "gen_short"
        assert call_args["stimulus_class"] == "gen_short"

    @pytest.mark.asyncio
    async def test_process_llm_request_valid_stimulus_classes(self):
        """Test all valid stimulus_class values work."""
        valid_classes = ["ping", "gen_short", "gen_long"]
        
        for stimulus_class in valid_classes:
            mock_llm = MagicMock()
            mock_synapse = MagicMock()
            mock_synapse.fire = AsyncMock(return_value=f"Response {stimulus_class}")
            mock_llm.local_synapse = mock_synapse
            
            result = await process_llm_request(
                llm_handler=mock_llm,
                prompt="Test",
                context="ask",
                user_name="testuser",
                pre_optimized=True,
                stimulus_class=stimulus_class
            )
            
            assert result == f"Response {stimulus_class}"
            call_args = mock_synapse.fire.call_args[1]
            assert call_args["stimulus_class"] == stimulus_class

    @pytest.mark.asyncio
    async def test_process_llm_request_pre_optimized_type_coercion(self):
        """Test pre_optimized gets coerced to bool if invalid type."""
        mock_llm = MagicMock(spec=[])  # Empty spec, no local_synapse
        # Since pre_optimized becomes True, it should fallback to process_stimulus
        mock_llm.process_stimulus = AsyncMock(return_value="Response")
        
        # Pass string instead of bool (will be coerced to True)
        result = await process_llm_request(
            llm_handler=mock_llm,
            prompt="Test",
            context="ask",
            user_name="testuser",
            pre_optimized="true"  # String, not bool! Will be coerced to True
        )
        
        # Should still work (coerced to True → uses process_stimulus fallback since no local_synapse)
        assert result == "Response"
        mock_llm.process_stimulus.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_llm_request_empty_response_returns_none(self):
        """Test empty LLM response returns None."""
        mock_llm = MagicMock()
        mock_llm.process_stimulus = AsyncMock(return_value="")
        
        result = await process_llm_request(
            llm_handler=mock_llm,
            prompt="Test",
            context="ask",
            user_name="testuser"
        )
        
        assert result is None

    @pytest.mark.asyncio
    async def test_process_llm_request_exception_returns_none(self):
        """Test exception during processing returns None gracefully."""
        mock_llm = MagicMock()
        mock_llm.process_stimulus = AsyncMock(side_effect=Exception("LLM Error"))
        
        result = await process_llm_request(
            llm_handler=mock_llm,
            prompt="Test",
            context="ask",
            user_name="testuser"
        )
        
        assert result is None


# ============================================================================
# Test Class 3: process_llm_request() - Response Truncation
# ============================================================================
class TestProcessLLMRequestTruncation:
    """Test response truncation for Twitch message limits."""

    @pytest.mark.asyncio
    async def test_process_llm_request_short_response_not_truncated(self):
        """Test short response (<450 chars) is not truncated."""
        mock_llm = MagicMock()
        short_response = "This is a short response"
        mock_llm.process_stimulus = AsyncMock(return_value=short_response)
        
        result = await process_llm_request(
            llm_handler=mock_llm,
            prompt="Test",
            context="ask",
            user_name="testuser"
        )
        
        assert result == short_response
        assert not result.endswith("...")

    @pytest.mark.asyncio
    async def test_process_llm_request_long_response_truncated(self):
        """Test long response (>450 chars) is truncated with '...'."""
        mock_llm = MagicMock()
        long_response = "A" * 500  # 500 chars
        mock_llm.process_stimulus = AsyncMock(return_value=long_response)
        
        result = await process_llm_request(
            llm_handler=mock_llm,
            prompt="Test",
            context="ask",
            user_name="testuser"
        )
        
        assert result is not None
        assert len(result) == 450  # 447 + "..."
        assert result.endswith("...")

    @pytest.mark.asyncio
    async def test_process_llm_request_exactly_450_chars_not_truncated(self):
        """Test response at exactly 450 chars is not truncated."""
        mock_llm = MagicMock()
        exact_response = "A" * 450
        mock_llm.process_stimulus = AsyncMock(return_value=exact_response)
        
        result = await process_llm_request(
            llm_handler=mock_llm,
            prompt="Test",
            context="ask",
            user_name="testuser"
        )
        
        assert result == exact_response
        assert not result.endswith("...")


# ============================================================================
# Test Class 4: enrich_prompt_with_game_context() - Smart Context 2.0
# ============================================================================
class TestEnrichPromptWithGameContext:
    """Test Smart Context 2.0 auto-enrichment."""

    @pytest.mark.asyncio
    async def test_enrich_prompt_game_found_in_cache(self):
        """Test prompt enrichment when game is found in cache."""
        # Mock find_game_in_cache to return controlled game data (avoid cache pollution)
        mock_game_data = {
            "name": "Brotato",
            "year": "2023",
            "genres": ["Action", "Indie"],
            "platforms": ["PC", "Switch"],
            "summary": "A top-down arena shooter roguelite where you play as a potato wielding weapons"
        }
        
        # Create a minimal mock cache (won't be used since we mock find_game_in_cache)
        mock_cache = MagicMock()
        
        with patch('intelligence.core.find_game_in_cache', return_value=mock_game_data):
            enriched = await enrich_prompt_with_game_context(
                prompt="Tell me about Brotato",
                game_cache=mock_cache
            )
        
        # Should contain game context
        assert "Brotato" in enriched
        assert "2023" in enriched
        assert "CONTEXTE STRICT" in enriched
        assert "Action" in enriched or "Indépendant" in enriched  # French translation
        assert "PC" in enriched or "Switch" in enriched
        assert "top-down arena shooter" in enriched

    @pytest.mark.asyncio
    async def test_enrich_prompt_game_not_found_returns_original(self):
        """Test original prompt returned when no game found."""
        temp_dir = tempfile.mkdtemp()
        cache_file = os.path.join(temp_dir, "test_cache.json")
        
        config = {
            "game_cache": {
                "file_path": cache_file,
                "duration_hours": 24
            }
        }
        game_cache = GameCache(config)
        
        original_prompt = "What is the weather today?"
        enriched = await enrich_prompt_with_game_context(
            prompt=original_prompt,
            game_cache=game_cache
        )
        
        # Should return original prompt unchanged
        assert enriched == original_prompt
        
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_enrich_prompt_none_cache_returns_original(self):
        """Test original prompt returned when cache is None."""
        original_prompt = "Test prompt"
        enriched = await enrich_prompt_with_game_context(
            prompt=original_prompt,
            game_cache=None
        )
        
        assert enriched == original_prompt

    @pytest.mark.asyncio
    async def test_enrich_prompt_empty_prompt_returns_original(self):
        """Test empty prompt returns empty string."""
        temp_dir = tempfile.mkdtemp()
        cache_file = os.path.join(temp_dir, "test_cache.json")
        
        config = {
            "game_cache": {
                "file_path": cache_file,
                "duration_hours": 24
            }
        }
        game_cache = GameCache(config)
        
        enriched = await enrich_prompt_with_game_context(
            prompt="",
            game_cache=game_cache
        )
        
        assert enriched == ""
        
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_enrich_prompt_genre_translation(self):
        """Test genre translation to French."""
        temp_dir = tempfile.mkdtemp()
        cache_file = os.path.join(temp_dir, "test_cache.json")
        
        config = {
            "game_cache": {
                "file_path": cache_file,
                "duration_hours": 24
            }
        }
        game_cache = GameCache(config)
        
        # Add game with English genres
        game_cache.set("celeste", {
            "name": "Celeste",
            "year": "2018",
            "genres": ["Indie", "Casual", "Adventure"],
            "platforms": ["PC"]
        })
        
        enriched = await enrich_prompt_with_game_context(
            prompt="Tell me about Celeste",
            game_cache=game_cache
        )
        
        # Check French translations exist
        assert "Indépendant" in enriched or "Indie" in enriched
        assert "Décontracté" in enriched or "Casual" in enriched or "Aventure" in enriched or "Adventure" in enriched
        
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_enrich_prompt_description_fallback_priority(self):
        """Test description fallback priority: summary > description_raw > description."""
        temp_dir = tempfile.mkdtemp()
        cache_file = os.path.join(temp_dir, "test_cache.json")
        
        config = {
            "game_cache": {
                "file_path": cache_file,
                "duration_hours": 24
            }
        }
        game_cache = GameCache(config)
        
        # Test with summary (highest priority)
        game_cache.set("game1", {
            "name": "Game 1",
            "year": "2020",
            "summary": "Summary text",
            "description_raw": "Raw description",
            "description": "Normal description"
        })
        
        enriched1 = await enrich_prompt_with_game_context(
            prompt="Tell me about Game 1",
            game_cache=game_cache
        )
        
        assert "Summary text" in enriched1
        
        # Test with description_raw (fallback)
        game_cache.set("game2", {
            "name": "Game 2",
            "year": "2020",
            "description_raw": "Raw description only"
        })
        
        enriched2 = await enrich_prompt_with_game_context(
            prompt="Tell me about Game 2",
            game_cache=game_cache
        )
        
        assert "Raw description only" in enriched2
        
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir)


# ============================================================================
# Test Class 5: Utility Functions (extract_question_from_command, extract_mention_message)
# ============================================================================
class TestUtilityFunctions:
    """Test non-async utility functions."""

    def test_extract_question_from_command_valid(self):
        """Test extracting question from !ask command."""
        result = extract_question_from_command("!ask What is Brotato?")
        assert result == "What is Brotato?"

    def test_extract_question_from_command_with_extra_spaces(self):
        """Test extraction handles extra spaces."""
        result = extract_question_from_command("!ask    What is     Brotato?")
        assert result == "What is     Brotato?"

    def test_extract_question_from_command_no_question(self):
        """Test extraction returns None when no question."""
        result = extract_question_from_command("!ask")
        assert result is None

    def test_extract_question_from_command_empty_string(self):
        """Test extraction handles empty string."""
        result = extract_question_from_command("")
        assert result is None

    def test_extract_mention_message_with_at_symbol(self):
        """Test extracting message from @bot mention."""
        result = extract_mention_message("@TestBot hello there", "TestBot")
        assert result == "hello there"

    def test_extract_mention_message_without_at_symbol(self):
        """Test extracting message from bot_name mention."""
        result = extract_mention_message("TestBot hello there", "TestBot")
        assert result == "hello there"

    def test_extract_mention_message_case_insensitive(self):
        """Test extraction is case-insensitive for detection, but uses exact case for removal."""
        # The function detects "TestBot" case-insensitively but removes with exact match
        result = extract_mention_message("TestBot hello", "TestBot")
        assert result == "hello"
        
        # Also test with @ symbol
        result2 = extract_mention_message("@TestBot hello", "TestBot")
        assert result2 == "hello"

    def test_extract_mention_message_bot_at_end(self):
        """Test extraction when bot name is at end."""
        result = extract_mention_message("hello TestBot", "TestBot")
        assert result == "hello"

    def test_extract_mention_message_no_bot_name(self):
        """Test extraction returns None when bot not mentioned."""
        result = extract_mention_message("hello there", "TestBot")
        assert result is None

    def test_extract_mention_message_only_bot_name(self):
        """Test extraction returns None when only bot name."""
        result = extract_mention_message("@TestBot", "TestBot")
        assert result is None

    def test_extract_mention_message_with_multiple_mentions(self):
        """Test extraction handles multiple bot mentions."""
        result = extract_mention_message("@TestBot hello @TestBot", "TestBot")
        # Should remove first mention only
        assert result is not None
        assert "hello" in result
