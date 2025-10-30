"""
Tests unitaires pour la commande !joke
Test du pipeline process_llm_request avec prompt "raconte une blague courte"
"""

import pytest
from unittest.mock import AsyncMock, patch
from intelligence.core import process_llm_request


@pytest.mark.asyncio
async def test_joke_pipeline_success():
    """Test pipeline !joke: process_llm_request avec prompt 'raconte une blague courte'"""
    # Mock LLM handler
    llm_handler = AsyncMock()
    llm_handler.process_stimulus = AsyncMock(
        return_value="Un développeur a dit à un testeur : 'Ça marche sur ma machine !'"
    )

    # Execute pipeline
    response = await process_llm_request(
        llm_handler=llm_handler,
        prompt="raconte une blague courte",
        context="ask",
        user_name="TestUser",
        game_cache=None,
    )

    # Verify
    assert response is not None
    assert "développeur" in response or "testeur" in response or len(response) > 0
    llm_handler.process_stimulus.assert_called_once_with(
        stimulus="raconte une blague courte",
        context="ask",
    )


@pytest.mark.asyncio
async def test_joke_pipeline_truncation():
    """Test pipeline !joke: troncature si réponse > 450 chars"""
    # Mock LLM handler avec réponse longue
    long_joke = "A" * 500  # 500 caractères
    llm_handler = AsyncMock()
    llm_handler.process_stimulus = AsyncMock(return_value=long_joke)

    # Execute pipeline
    response = await process_llm_request(
        llm_handler=llm_handler,
        prompt="raconte une blague courte",
        context="ask",
        user_name="TestUser",
        game_cache=None,
    )

    # Verify truncation
    assert response is not None
    assert len(response) <= 450
    assert response.endswith("...")


@pytest.mark.asyncio
async def test_joke_pipeline_empty_response():
    """Test pipeline !joke: gestion réponse vide"""
    # Mock LLM handler avec réponse vide
    llm_handler = AsyncMock()
    llm_handler.process_stimulus = AsyncMock(return_value=None)

    # Execute pipeline
    response = await process_llm_request(
        llm_handler=llm_handler,
        prompt="raconte une blague courte",
        context="ask",
        user_name="TestUser",
        game_cache=None,
    )

    # Verify
    assert response is None


@pytest.mark.asyncio
async def test_joke_pipeline_exception():
    """Test pipeline !joke: gestion exception LLM"""
    # Mock LLM handler qui raise exception
    llm_handler = AsyncMock()
    llm_handler.process_stimulus = AsyncMock(side_effect=Exception("LLM Error"))

    # Execute pipeline
    response = await process_llm_request(
        llm_handler=llm_handler,
        prompt="raconte une blague courte",
        context="ask",
        user_name="TestUser",
        game_cache=None,
    )

    # Verify exception handled gracefully
    assert response is None


@pytest.mark.asyncio
async def test_joke_pipeline_no_game_context():
    """Test pipeline !joke: pas d'enrichissement Smart Context (game_cache=None)"""
    # Mock LLM handler
    llm_handler = AsyncMock()
    llm_handler.process_stimulus = AsyncMock(return_value="Une blague courte !")

    # Execute pipeline avec game_cache=None
    response = await process_llm_request(
        llm_handler=llm_handler,
        prompt="raconte une blague courte",
        context="ask",
        user_name="TestUser",
        game_cache=None,  # Important: pas d'enrichissement jeu
    )

    # Verify: prompt passé tel quel sans enrichissement
    llm_handler.process_stimulus.assert_called_once_with(
        stimulus="raconte une blague courte",  # Pas de contexte jeu ajouté
        context="ask",
    )
    assert response == "Une blague courte !"

