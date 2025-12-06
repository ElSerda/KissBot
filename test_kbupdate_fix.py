#!/usr/bin/env python3
"""
Test script pour vérifier que !kbupdate fonctionne maintenant avec moderator_id=serda_bot
"""

import asyncio
import sys
from pathlib import Path

# Ajoute le répertoire root au path
sys.path.insert(0, str(Path(__file__).parent))

from core.message_types import ChatMessage
from modules.classic_commands.broadcaster_commands.broadcast import cmd_kbupdate


async def test_kbupdate():
    """Test la commande !kbupdate"""
    
    # Créer un message d'origine en tant que broadcaster (el_serda, ID 44456636)
    msg = ChatMessage(
        raw_message="",
        user_login="el_serda",
        user_id=44456636,  # el_serda broadcaster
        channel="el_serda",
        channel_id=44456636,
        is_mod=False,
        is_broadcaster=True,  # C'est le broadcaster
        is_owner=False,
        message_text="!kbupdate test update message 🎉",
        tags={},
        timestamp=""
    )
    
    # Mock twitch_client avec la vraie API
    # On va utiliser le vrai twitch_client du bot
    from main import main as get_twitch_client
    
    # Créer un faux twitch_client pour le test
    class FakeTwitchClient:
        async def send_chat_announcement(self, broadcaster_id, moderator_id, message, color):
            print(f"✅ send_chat_announcement appelé avec:")
            print(f"   - broadcaster_id={broadcaster_id}")
            print(f"   - moderator_id={moderator_id}")
            print(f"   - message={message}")
            print(f"   - color={color}")
            return True
    
    twitch_client = FakeTwitchClient()
    
    # Tester la commande
    result = await cmd_kbupdate(
        msg=msg,
        args=["test", "update", "message", "🎉"],
        bus=None,
        irc_client=None,
        twitch_client=twitch_client
    )
    
    print(f"\nRésultat de la commande: {result}")
    return result


if __name__ == "__main__":
    result = asyncio.run(test_kbupdate())
    if result:
        print("\n✅ Test réussi !")
    else:
        print("\n❌ Test échoué !")
