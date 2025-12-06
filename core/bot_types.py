"""
Core types for KissBot V2 architecture.

Defines normalized event and response types used across core and modules.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime


@dataclass
class BotEvent:
    """
    Normalized event from Twitch (chat message, subscription, raid, etc.)
    
    All Twitch events are normalized to this structure for consistent handling.
    """
    type: str                           # "chat_message" | "subscription" | "raid" | "follow" | etc.
    channel_id: str                     # Twitch channel ID
    channel_name: str                   # Channel login name
    user_id: str                        # User Twitch ID
    user_name: str                      # User display name
    message: Optional[str] = None       # Message text (for chat messages)
    metadata: Dict[str, Any] = field(default_factory=dict)  # Event-specific data
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    
    # User context
    is_mod: bool = False
    is_vip: bool = False
    is_broadcaster: bool = False
    is_subscriber: bool = False
    
    def __repr__(self) -> str:
        """Readable representation for logging"""
        return f"BotEvent(type={self.type}, user={self.user_name}, channel={self.channel_name})"


@dataclass
class BotResponse:
    """
    Normalized response from bot (to chat, TTS, OBS, webhook, etc.)
    
    Modules return this to indicate where and what to send.
    """
    text: str                           # Response text/payload
    targets: List[str]                  # Output targets: ["chat", "tts", "obs", "webhook:URL"]
    metadata: Dict[str, Any] = field(default_factory=dict)  # Target-specific config
    
    # Optional routing hints
    reply_to_user: Optional[str] = None     # @user to reply to (for chat)
    priority: int = 0                        # Higher = send first (for queue)
    
    def __repr__(self) -> str:
        """Readable representation for logging"""
        targets_str = ",".join(self.targets)
        return f"BotResponse(targets=[{targets_str}], text_len={len(self.text)})"


@dataclass
class CommandContext:
    """
    Context passed to command handlers
    
    Contains all information needed to execute a command.
    """
    event: BotEvent                     # Original event
    command_name: str                   # Command name (without !)
    args: List[str]                     # Command arguments
    raw_args: str                       # Raw argument string
    
    # Channel-specific config
    channel_config: Dict[str, Any] = field(default_factory=dict)
    
    def __repr__(self) -> str:
        return f"CommandContext(cmd={self.command_name}, user={self.event.user_name})"
