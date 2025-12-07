"""
Tests unitaires pour !kbupdate (avec broadcaster tokens)
"""
import pytest
import asyncio
import yaml
import json
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
  client_id: test_client_id
  client_secret: test_client_secret
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
def mock_db_manager():
    """Mock DatabaseManager avec tokens broadcaster"""
    db = MagicMock()
    
    # Mock get_user_by_login
    def mock_get_user(login):
        users = {
            "el_serda": {"id": 2, "twitch_user_id": 44456636, "login": "el_serda"},
            "pelerin_": {"id": 3, "twitch_user_id": 135500767, "login": "pelerin_"},
            "test_channel": {"id": 4, "twitch_user_id": 999999999, "login": "test_channel"}
        }
        return users.get(login)
    
    # Mock get_tokens - returns broadcaster tokens
    def mock_get_tokens(user_id, token_type):
        if token_type == 'broadcaster':
            return {
                'access_token': f'test_token_{user_id}',
                'refresh_token': f'test_refresh_{user_id}',
                'scopes': json.dumps([
                    "moderator:manage:announcements",
                    "channel:manage:broadcast",
                    "chat:read",
                    "chat:edit"
                ])
            }
        return None
    
    db.get_user_by_login = mock_get_user
    db.get_tokens = mock_get_tokens
    
    return db


@pytest.fixture
def mock_twitch_instance():
    """Mock instance Twitch temporaire"""
    instance = AsyncMock()
    instance.set_user_authentication = AsyncMock()
    instance.send_chat_announcement = AsyncMock()
    instance.close = AsyncMock()
    return instance


@pytest.mark.asyncio
async def test_kbupdate_owner_only(mock_message, mock_db_manager):
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
                twitch_client=None  # Not used anymore
            )
    
    assert "❌" in result
    assert "el_serda" in result.lower()


@pytest.mark.asyncio
async def test_kbupdate_no_args(mock_message, mock_db_manager):
    """Test refus si pas d'arguments"""
    bus = MessageBus()
    
    with patch("builtins.open", mock_open(read_data="twitch:\n  channels:\n    - el_serda")):
        with patch("pathlib.Path.exists", return_value=True):
            result = await cmd_kbupdate(
                msg=mock_message,
                args=[],
                bus=bus,
                twitch_client=None
            )
    
    assert "❌" in result
    assert "Usage" in result


@pytest.mark.asyncio
async def test_kbupdate_message_too_long(mock_message, mock_db_manager):
    """Test refus si message > 300 chars"""
    bus = MessageBus()
    long_message = ["x" * 350]
    
    with patch("builtins.open", mock_open(read_data="twitch:\n  channels:\n    - el_serda")):
        with patch("pathlib.Path.exists", return_value=True):
            result = await cmd_kbupdate(
                msg=mock_message,
                args=long_message,
                bus=bus,
                twitch_client=None
            )
    
    assert "❌" in result
    assert "trop long" in result.lower()


@pytest.mark.asyncio
async def test_kbupdate_success_multi_channel(mock_message, mock_config_yaml, mock_db_manager, mock_twitch_instance):
    """Test envoi réussi sur plusieurs channels avec broadcaster tokens"""
    bus = MessageBus()
    
    with patch("builtins.open", mock_open(read_data=mock_config_yaml)):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("database.manager.DatabaseManager", return_value=mock_db_manager):
                with patch("twitchAPI.twitch.Twitch", return_value=mock_twitch_instance):
                    result = await cmd_kbupdate(
                        msg=mock_message,
                        args=["Test", "update", "!"],
                        bus=bus,
                        twitch_client=None  # Not used anymore
                    )
    
    # Vérifier le résultat
    assert "📢" in result
    assert "3/3" in result  # 3 channels configurés
    
    # Vérifier que send_chat_announcement a été appelé 3 fois
    assert mock_twitch_instance.send_chat_announcement.call_count == 3
    
    # Vérifier les paramètres: moderator_id = broadcaster_id (pas 1209350837)
    calls = mock_twitch_instance.send_chat_announcement.call_args_list
    for call in calls:
        kwargs = call.kwargs
        # CRITICAL: broadcaster_id == moderator_id
        assert kwargs["broadcaster_id"] == kwargs["moderator_id"]
        assert kwargs["color"] == "purple"
        assert "🤖 KissBot Update:" in kwargs["message"]


@pytest.mark.asyncio
async def test_kbupdate_partial_failure(mock_message, mock_config_yaml, mock_db_manager, mock_twitch_instance):
    """Test avec échec partiel sur certains channels"""
    bus = MessageBus()
    
    # Simuler un échec sur le 2e channel
    call_count = 0
    original_announce = mock_twitch_instance.send_chat_announcement
    
    async def failing_announce(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:  # Échoue sur le 2e appel
            raise Exception("API Error 403")
        return await original_announce(*args, **kwargs)
    
    mock_twitch_instance.send_chat_announcement = failing_announce
    
    with patch("builtins.open", mock_open(read_data=mock_config_yaml)):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("database.manager.DatabaseManager", return_value=mock_db_manager):
                with patch("twitchAPI.twitch.Twitch", return_value=mock_twitch_instance):
                    result = await cmd_kbupdate(
                        msg=mock_message,
                        args=["Test"],
                        bus=bus,
                        twitch_client=None
                    )
    
    # Devrait indiquer 2/3 (1 échec)
    assert "2/3" in result
    assert "⚠️" in result or "Échecs" in result


@pytest.mark.asyncio
async def test_kbupdate_broadcaster_token_architecture(mock_message, mock_config_yaml, mock_db_manager, mock_twitch_instance):
    """Test critique: Vérifie que broadcaster token est utilisé (pas bot token)"""
    bus = MessageBus()
    
    with patch("builtins.open", mock_open(read_data=mock_config_yaml)):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("database.manager.DatabaseManager", return_value=mock_db_manager):
                with patch("twitchAPI.twitch.Twitch", return_value=mock_twitch_instance):
                    result = await cmd_kbupdate(
                        msg=mock_message,
                        args=["Test"],
                        bus=bus,
                        twitch_client=None
                    )
    
    # Vérifier que set_user_authentication est appelé avec broadcaster tokens
    assert mock_twitch_instance.set_user_authentication.call_count == 3
    
    # Vérifier que les tokens sont différents pour chaque channel
    auth_calls = mock_twitch_instance.set_user_authentication.call_args_list
    tokens_used = [call.kwargs['token'] for call in auth_calls]
    
    # Tokens doivent contenir user_id (test_token_2, test_token_3, test_token_4)
    assert all('test_token_' in token for token in tokens_used)
    assert len(set(tokens_used)) == 3  # 3 tokens différents


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
