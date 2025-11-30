"""
Base module interface for KissBot V2.

All feature modules inherit from BaseModule to ensure consistent behavior.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from core.types import BotEvent, BotResponse


class BaseModule(ABC):
    """
    Abstract base class for all KissBot modules.
    
    Modules can:
    - Handle events (chat messages, subscriptions, etc.)
    - Register commands
    - Be enabled/disabled per channel
    - Clean up resources on shutdown
    
    Example:
        class MyModule(BaseModule):
            async def handle(self, event: BotEvent) -> Optional[BotResponse]:
                if event.type == "chat_message" and "!hello" in event.message:
                    return BotResponse(text="Hello!", targets=["chat"])
                return None
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize module with configuration.
        
        Args:
            config: Module-specific config dict (from YAML or DB)
        """
        self.enabled = config.get("enabled", False)
        self.config = config
        self.name = self.__class__.__name__
    
    @abstractmethod
    async def handle(self, event: BotEvent) -> Optional[BotResponse]:
        """
        Handle a bot event.
        
        Args:
            event: Normalized BotEvent
            
        Returns:
            BotResponse if module handles event, None otherwise
            
        Note:
            Return None quickly if module doesn't handle this event type.
            This allows other modules to process it.
        """
        pass
    
    async def on_load(self) -> None:
        """
        Hook called when module is loaded.
        
        Use for:
        - DB connections
        - External API clients
        - Cache initialization
        - Background tasks
        """
        pass
    
    async def on_unload(self) -> None:
        """
        Hook called when module is unloaded (bot shutdown).
        
        Use for:
        - Closing connections
        - Saving state
        - Cleanup resources
        - Stopping background tasks
        """
        pass
    
    def is_enabled_for_channel(self, channel_id: str) -> bool:
        """
        Check if module is enabled for specific channel.
        
        Args:
            channel_id: Twitch channel ID
            
        Returns:
            True if enabled, False otherwise
            
        Note:
            Override this for per-channel enable/disable logic.
        """
        return self.enabled
    
    def __repr__(self) -> str:
        status = "enabled" if self.enabled else "disabled"
        return f"{self.name}({status})"
