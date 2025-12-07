#!/usr/bin/env python3
"""
Test direct de _log_send_result() pour vérifier qu'il logue correctement.

Simule une réponse SendMessageResponse avec drop_reason
et vérife que les logs s'affichent.
"""

import logging
import sys
from pathlib import Path

# Setup logging to see output
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Setup path
sys.path.insert(0, str(Path(__file__).parent))

# Importer les classes nécessaires
from twitchapi.transports.eventsub_chat_client import EventSubChatClient
from core.message_bus import MessageBus

# Mock d'une SendMessageResponse avec drop_reason
from dataclasses import dataclass
from typing import Optional

@dataclass
class MockDropReason:
    code: str
    message: str

@dataclass
class MockSendMessageResponse:
    is_sent: bool
    message_id: str = ""
    drop_reason: Optional[MockDropReason] = None

# Créer une instance du client avec un vrai MessageBus
bus = MessageBus()
client = EventSubChatClient(
    twitch=None,
    bus=bus,
    bot_user_id="1209350837",
    bot_login="serda_bot",
    channels=["el_serda"],
    broadcaster_ids={"el_serda": "44456636"}
)

print("\n" + "="*70)
print("Testing _log_send_result() with different drop_reason codes")
print("="*70 + "\n")

# Test 1: msg_rejected (AutoMod)
print("\n[TEST 1] msg_rejected (AutoMod blocked)")
response = MockSendMessageResponse(
    is_sent=False,
    drop_reason=MockDropReason(
        code="msg_rejected",
        message="Your message is being checked by mods and has not been sent."
    )
)
client._log_send_result("el_serda", response, "Test message from AutoMod")

# Test 2: automod_held (Moderator review)
print("\n[TEST 2] automod_held (Awaiting mod review)")
response = MockSendMessageResponse(
    is_sent=False,
    drop_reason=MockDropReason(
        code="automod_held",
        message="Your message was held for moderator review"
    )
)
client._log_send_result("el_serda", response, "Test message awaiting review")

# Test 3: msg_blocked (Explicit block)
print("\n[TEST 3] msg_blocked (Explicitly blocked)")
response = MockSendMessageResponse(
    is_sent=False,
    drop_reason=MockDropReason(
        code="msg_blocked",
        message="Message content blocked"
    )
)
client._log_send_result("el_serda", response, "Blocked message test")

# Test 4: Success
print("\n[TEST 4] Success (is_sent=True)")
response = MockSendMessageResponse(
    is_sent=True,
    message_id="abc123",
    drop_reason=None
)
client._log_send_result("el_serda", response, "Success test message")

# Test 5: Unknown code
print("\n[TEST 5] Unknown drop_reason code")
response = MockSendMessageResponse(
    is_sent=False,
    drop_reason=MockDropReason(
        code="unknown_error_code",
        message="Some unknown error"
    )
)
client._log_send_result("el_serda", response, "Unknown error test")

print("\n" + "="*70)
print("✅ All tests completed - check logs above for _log_send_result() output")
print("="*70 + "\n")


print("\n" + "="*70)
print("Testing _log_send_result() with different drop_reason codes")
print("="*70 + "\n")

# Test 1: msg_rejected (AutoMod)
print("\n[TEST 1] msg_rejected (AutoMod blocked)")
response = MockSendMessageResponse(
    is_sent=False,
    drop_reason=MockDropReason(
        code="msg_rejected",
        message="Your message is being checked by mods and has not been sent."
    )
)
client._log_send_result("el_serda", response, "Test message from AutoMod")

# Test 2: automod_held (Moderator review)
print("\n[TEST 2] automod_held (Awaiting mod review)")
response = MockSendMessageResponse(
    is_sent=False,
    drop_reason=MockDropReason(
        code="automod_held",
        message="Your message was held for moderator review"
    )
)
client._log_send_result("el_serda", response, "Test message awaiting review")

# Test 3: msg_blocked (Explicit block)
print("\n[TEST 3] msg_blocked (Explicitly blocked)")
response = MockSendMessageResponse(
    is_sent=False,
    drop_reason=MockDropReason(
        code="msg_blocked",
        message="Message content blocked"
    )
)
client._log_send_result("el_serda", response, "Blocked message test")

# Test 4: Success
print("\n[TEST 4] Success (is_sent=True)")
response = MockSendMessageResponse(
    is_sent=True,
    message_id="abc123",
    drop_reason=None
)
client._log_send_result("el_serda", response, "Success test message")

# Test 5: Unknown code
print("\n[TEST 5] Unknown drop_reason code")
response = MockSendMessageResponse(
    is_sent=False,
    drop_reason=MockDropReason(
        code="unknown_error_code",
        message="Some unknown error"
    )
)
client._log_send_result("el_serda", response, "Unknown error test")

print("\n" + "="*70)
print("✅ All tests completed - check logs above for _log_send_result() output")
print("="*70 + "\n")
