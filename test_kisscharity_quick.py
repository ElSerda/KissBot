#!/usr/bin/env python3
"""
Test rapide de la commande !kisscharity
Vérifie la logique sans démarrer le bot complet
"""
import asyncio
import logging
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from core.message_types import ChatMessage
from core.message_bus import MessageBus
from commands.bot_commands.broadcast import cmd_kisscharity, BROADCAST_COOLDOWN

logging.basicConfig(level=logging.INFO, format='%(levelname)s | %(message)s')
LOGGER = logging.getLogger(__name__)


def create_test_message(is_broadcaster: bool = True, channel: str = "el_serda") -> ChatMessage:
    """Créer un message de test"""
    return ChatMessage(
        channel=channel,
        channel_id="123456",
        user_login="test_user",
        user_id="789",
        text="!kisscharity Test broadcast",
        is_mod=False,
        is_broadcaster=is_broadcaster,
        is_vip=False,
        transport="irc",
        badges={}
    )


async def test_1_broadcaster_success():
    """Test 1: Broadcaster envoie un broadcast avec succès"""
    print("\n" + "="*70)
    print("TEST 1: Broadcaster success")
    print("="*70)
    
    # Setup
    msg = create_test_message(is_broadcaster=True)
    args = ["🎮", "Event", "charity", "ce", "soir", "!"]
    bus = Mock()
    
    # Mock IRC client
    irc_client = Mock()
    irc_client.broadcast_message = AsyncMock(return_value=(3, 3))  # 3/3 success
    
    # Reset cooldown pour ce test
    import commands.bot_commands.broadcast as broadcast_module
    broadcast_module._last_broadcast_time = None
    
    # Execute
    response = await cmd_kisscharity(msg, args, bus, irc_client)
    
    # Verify
    assert irc_client.broadcast_message.called
    # Vérifier que source_channel est passé
    call_args = irc_client.broadcast_message.call_args
    assert call_args.kwargs.get('source_channel') == 'el_serda'
    assert call_args.kwargs.get('exclude_channel') == 'el_serda'
    assert "3 channels" in response
    assert "🎉" in response or "succès" in response
    
    print(f"✅ Response: {response}")
    print(f"✅ Source channel passed: {call_args.kwargs.get('source_channel')}")
    print("✅ Test 1 PASSED")


async def test_2_non_broadcaster_rejected():
    """Test 2: Non-broadcaster est rejeté"""
    print("\n" + "="*70)
    print("TEST 2: Non-broadcaster rejected")
    print("="*70)
    
    # Setup
    msg = create_test_message(is_broadcaster=False)
    args = ["Test", "message"]
    bus = Mock()
    irc_client = Mock()
    
    # Execute
    response = await cmd_kisscharity(msg, args, bus, irc_client)
    
    # Verify
    assert "broadcaster" in response.lower() or "❌" in response
    assert not hasattr(irc_client.broadcast_message, 'called') or not irc_client.broadcast_message.called
    
    print(f"✅ Response: {response}")
    print("✅ Test 2 PASSED")


async def test_3_empty_message_rejected():
    """Test 3: Message vide est rejeté"""
    print("\n" + "="*70)
    print("TEST 3: Empty message rejected")
    print("="*70)
    
    # Setup
    msg = create_test_message(is_broadcaster=True)
    args = []  # Vide
    bus = Mock()
    irc_client = Mock()
    
    # Reset cooldown pour ce test
    import commands.bot_commands.broadcast as broadcast_module
    broadcast_module._last_broadcast_time = None
    
    # Execute
    response = await cmd_kisscharity(msg, args, bus, irc_client)
    
    # Verify
    assert "Usage" in response or "❌" in response
    
    print(f"✅ Response: {response}")
    print("✅ Test 3 PASSED")


async def test_4_message_too_long():
    """Test 4: Message trop long (>500 chars) est rejeté"""
    print("\n" + "="*70)
    print("TEST 4: Message too long rejected")
    print("="*70)
    
    # Setup
    msg = create_test_message(is_broadcaster=True)
    args = ["X"] * 501  # 501 mots = trop long
    bus = Mock()
    irc_client = Mock()
    
    # Reset cooldown
    import commands.bot_commands.broadcast as broadcast_module
    broadcast_module._last_broadcast_time = None
    
    # Execute
    response = await cmd_kisscharity(msg, args, bus, irc_client)
    
    # Verify
    assert "trop long" in response.lower() or "500" in response
    
    print(f"✅ Response: {response}")
    print("✅ Test 4 PASSED")


async def test_5_cooldown_enforcement():
    """Test 5: Cooldown de 5 minutes est appliqué"""
    print("\n" + "="*70)
    print("TEST 5: Cooldown enforcement")
    print("="*70)
    
    # Setup
    msg = create_test_message(is_broadcaster=True)
    args = ["Test", "broadcast"]
    bus = Mock()
    irc_client = Mock()
    irc_client.broadcast_message = AsyncMock(return_value=(2, 2))
    
    # Reset et set cooldown à maintenant - 2 minutes (il reste 3 minutes)
    import commands.bot_commands.broadcast as broadcast_module
    broadcast_module._last_broadcast_time = datetime.now() - timedelta(minutes=2)
    
    # Execute
    response = await cmd_kisscharity(msg, args, bus, irc_client)
    
    # Verify
    assert "Cooldown" in response or "⏱️" in response or "Attends" in response
    assert "3m" in response or "2m" in response  # Il reste environ 3 minutes
    
    print(f"✅ Response: {response}")
    print("✅ Test 5 PASSED")


async def test_6_partial_success():
    """Test 6: Succès partiel (3/5 channels)"""
    print("\n" + "="*70)
    print("TEST 6: Partial success (3/5)")
    print("="*70)
    
    # Setup
    msg = create_test_message(is_broadcaster=True)
    args = ["Test", "partial"]
    bus = Mock()
    
    # Mock IRC client avec échec partiel
    irc_client = Mock()
    irc_client.broadcast_message = AsyncMock(return_value=(3, 5))  # 3/5 success
    
    # Reset cooldown
    import commands.bot_commands.broadcast as broadcast_module
    broadcast_module._last_broadcast_time = None
    
    # Execute
    response = await cmd_kisscharity(msg, args, bus, irc_client)
    
    # Verify
    assert "3/5" in response
    assert "échecs" in response or "2" in response  # 2 échecs
    
    print(f"✅ Response: {response}")
    print("✅ Test 6 PASSED")


async def test_7_complete_failure():
    """Test 7: Échec complet (0/3)"""
    print("\n" + "="*70)
    print("TEST 7: Complete failure (0/3)")
    print("="*70)
    
    # Setup
    msg = create_test_message(is_broadcaster=True)
    args = ["Test", "failure"]
    bus = Mock()
    
    # Mock IRC client avec échec total
    irc_client = Mock()
    irc_client.broadcast_message = AsyncMock(return_value=(0, 3))  # 0/3 success
    
    # Reset cooldown
    import commands.bot_commands.broadcast as broadcast_module
    broadcast_module._last_broadcast_time = None
    
    # Execute
    response = await cmd_kisscharity(msg, args, bus, irc_client)
    
    # Verify
    assert "❌" in response
    assert "impossible" in response.lower() or "erreur" in response.lower()
    
    print(f"✅ Response: {response}")
    print("✅ Test 7 PASSED")


async def main():
    """Lancer tous les tests"""
    print("\n" + "="*70)
    print("🧪 TESTS UNITAIRES !kisscharity")
    print("="*70)
    
    tests = [
        ("Broadcaster success", test_1_broadcaster_success),
        ("Non-broadcaster rejected", test_2_non_broadcaster_rejected),
        ("Empty message rejected", test_3_empty_message_rejected),
        ("Message too long", test_4_message_too_long),
        ("Cooldown enforcement", test_5_cooldown_enforcement),
        ("Partial success (3/5)", test_6_partial_success),
        ("Complete failure (0/3)", test_7_complete_failure),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            await test_func()
            passed += 1
        except AssertionError as e:
            print(f"❌ Test FAILED: {name}")
            print(f"   Error: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ Test ERROR: {name}")
            print(f"   Exception: {e}")
            failed += 1
    
    # Résumé
    print("\n" + "="*70)
    print("📊 RÉSUMÉ DES TESTS")
    print("="*70)
    print(f"✅ Tests réussis: {passed}/{len(tests)}")
    print(f"❌ Tests échoués: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 TOUS LES TESTS PASSENT ! Ready pour test live !")
        print("="*70)
        return 0
    else:
        print("\n⚠️  Certains tests ont échoué, vérifier avant test live")
        print("="*70)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
