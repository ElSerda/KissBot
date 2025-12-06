"""
Tests unitaires pour !kbupdate
"""
import pytest
import asyncio
import yaml
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

from core.message_types import ChatMessage
from core.message_bus import MessageBus
from modules.classic_commands.broadcaster_commands.broadcast import cmd_kbupdate


@pytest.fixture
def mock_config_yaml():
    """Mock config.yaml avec liste de channels"""
    return """
twitch:
  channels:
    - el_serda
    - pelerin_
    - test_channel
"""


@pytest.fixture
def mock_message():
    """Mock ChatMessage d'el_serda"""
    msg = MagicMock(spec=ChatMessage)
    msg.user_id = "44456636"  # el_serda
    msg.user_login = "el_serda"
    msg.channel = "#el_serda"
    msg.channel_id = "44456636"
    return msg


@pytest.fixture
def mock_twitch_client():
    """Mock Twitch API client"""
    client = AsyncMock()
    
    # Mock get_users pour retourner des IDs
    async def mock_get_users(logins=None):
        channel_ids = {
            "el_serda": "44456636",
            "pelerin_": "135500767",
            "test_channel": "999999999"
        }
        for login in logins:
            user = MagicMock()
            user.id = channel_ids.get(login, "000000000")
            user.login = login
            yield user
    
    client.get_users = mock_get_users
    client.send_chat_announcement = AsyncMock()
    
    return client


@pytest.mark.asyncio
async def test_kbupdate_owner_only(mock_message, mock_twitch_client):
    """Test que seul el_serda peut utiliser !kbupdate"""
    bus = MessageBus()
    
    # Test avec un non-owner
    mock_message.user_id = "123456789"  # Pas el_serda
    mock_message.user_login = "random_user"
    
    with patch("builtins.open", mock_open(read_data="twitch:\n  channels:\n    - el_serda")):
        with patch("pathlib.Path.exists", return_value=True):
            result = await cmd_kbupdate(
                msg=mock_message,
                args=["Test", "message"],
                bus=bus,
                twitch_client=mock_twitch_client
            )
    
    assert "❌" in result
    assert "el_serda" in result.lower()


@pytest.mark.asyncio
async def test_kbupdate_no_args(mock_message, mock_twitch_client):
    """Test refus si pas d'arguments"""
    bus = MessageBus()
    
    with patch("builtins.open", mock_open(read_data="twitch:\n  channels:\n    - el_serda")):
        with patch("pathlib.Path.exists", return_value=True):
            result = await cmd_kbupdate(
                msg=mock_message,
                args=[],
                bus=bus,
                twitch_client=mock_twitch_client
            )
    
    assert "❌" in result
    assert "Usage" in result


@pytest.mark.asyncio
async def test_kbupdate_message_too_long(mock_message, mock_twitch_client):
    """Test refus si message > 300 chars"""
    bus = MessageBus()
    long_message = ["x" * 350]
    
    with patch("builtins.open", mock_open(read_data="twitch:\n  channels:\n    - el_serda")):
        with patch("pathlib.Path.exists", return_value=True):
            result = await cmd_kbupdate(
                msg=mock_message,
                args=long_message,
                bus=bus,
                twitch_client=mock_twitch_client
            )
    
    assert "❌" in result
    assert "trop long" in result.lower()


@pytest.mark.asyncio
async def test_kbupdate_success_multi_channel(mock_message, mock_twitch_client, mock_config_yaml):
    """Test envoi réussi sur plusieurs channels"""
    bus = MessageBus()
    
    with patch("builtins.open", mock_open(read_data=mock_config_yaml)):
        with patch("pathlib.Path.exists", return_value=True):
            result = await cmd_kbupdate(
                msg=mock_message,
                args=["Test", "update", "!"],
                bus=bus,
                twitch_client=mock_twitch_client
            )
    
    # Vérifier le résultat
    assert "📢" in result
    assert "3/3" in result  # 3 channels configurés
    
    # Vérifier que send_chat_announcement a été appelé 3 fois
    assert mock_twitch_client.send_chat_announcement.call_count == 3
    
    # Vérifier les paramètres de chaque appel
    calls = mock_twitch_client.send_chat_announcement.call_args_list
    for call in calls:
        kwargs = call.kwargs
        assert kwargs["moderator_id"] == "1209350837"  # serda_bot
        assert kwargs["color"] == "purple"
        assert "🤖 KissBot Update:" in kwargs["message"]


@pytest.mark.asyncio
async def test_kbupdate_partial_failure(mock_message, mock_twitch_client, mock_config_yaml):
    """Test avec échec partiel sur certains channels"""
    bus = MessageBus()
    
    # Simuler un échec sur le 2e channel
    call_count = 0
    original_announce = mock_twitch_client.send_chat_announcement
    
    async def failing_announce(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:  # Échoue sur le 2e appel
            raise Exception("API Error 403")
        return await original_announce(*args, **kwargs)
    
    mock_twitch_client.send_chat_announcement = failing_announce
    
    with patch("builtins.open", mock_open(read_data=mock_config_yaml)):
        with patch("pathlib.Path.exists", return_value=True):
            result = await cmd_kbupdate(
                msg=mock_message,
                args=["Test"],
                bus=bus,
                twitch_client=mock_twitch_client
            )
    
    # Devrait indiquer 2/3 (1 échec)
    assert "2/3" in result
    assert "⚠️" in result or "Échecs" in result


@pytest.mark.asyncio
async def test_kbupdate_no_twitch_client(mock_message):
    """Test erreur si pas de Twitch client"""
    bus = MessageBus()
    
    with patch("builtins.open", mock_open(read_data="twitch:\n  channels:\n    - el_serda")):
        with patch("pathlib.Path.exists", return_value=True):
            result = await cmd_kbupdate(
                msg=mock_message,
                args=["Test"],
                bus=bus,
                twitch_client=None  # Pas de client
            )
    
    assert "❌" in result
    assert "Twitch API" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
