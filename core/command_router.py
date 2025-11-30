"""
Command router for KissBot V2.

Routes incoming commands to appropriate handlers (core commands, custom commands, modules).
"""

from typing import Dict, Callable, Optional, List, Any
import logging
from core.types import BotEvent, BotResponse, CommandContext

logger = logging.getLogger(__name__)


class CommandRouter:
    """
    Central command dispatcher.
    
    Routes commands in this order:
    1. Core commands (!ping, !help, !kbadd, etc.)
    2. Custom commands (per-channel !roast, !hype, etc.)
    3. Module commands (!gc, !gi, !persona, etc.)
    """
    
    def __init__(self):
        self.core_commands: Dict[str, Callable] = {}
        self.module_handlers: List[Callable] = []
        self.custom_command_engine: Optional[Any] = None  # Set by CustomCommandModule
    
    def register_core_command(
        self, 
        name: str, 
        handler: Callable, 
        permissions: Optional[List[str]] = None
    ) -> None:
        """
        Register a core command (e.g., !ping, !help).
        
        Args:
            name: Command name (without !)
            handler: Async callable that takes CommandContext and returns BotResponse
            permissions: List of required permissions: ["mod", "vip", "broadcaster"]
        """
        self.core_commands[name] = {
            "handler": handler,
            "permissions": permissions or []
        }
        logger.info(f"Registered core command: !{name}")
    
    def register_module_handler(self, handler: Callable) -> None:
        """
        Register a module's handle() method.
        
        Args:
            handler: Module's handle() method
        """
        self.module_handlers.append(handler)
        logger.debug(f"Registered module handler: {handler.__self__.__class__.__name__}")
    
    def set_custom_command_engine(self, engine: Any) -> None:
        """
        Set the custom command engine (from modules/custom_commands).
        
        Args:
            engine: CustomCommandEngine instance
        """
        self.custom_command_engine = engine
        logger.info("Custom command engine registered")
    
    async def route(self, event: BotEvent) -> Optional[BotResponse]:
        """
        Route an event to appropriate handler.
        
        Args:
            event: BotEvent (typically chat_message)
            
        Returns:
            BotResponse if handled, None if no handler found
        """
        # Only process chat messages for commands
        if event.type != "chat_message" or not event.message:
            return None
        
        message = event.message.strip()
        
        # Must start with !
        if not message.startswith("!"):
            return None
        
        # Parse command
        parts = message[1:].split(maxsplit=1)
        command_name = parts[0].lower()
        raw_args = parts[1] if len(parts) > 1 else ""
        args = raw_args.split() if raw_args else []
        
        # Build context
        ctx = CommandContext(
            event=event,
            command_name=command_name,
            args=args,
            raw_args=raw_args
        )
        
        # 1. Try core commands
        if command_name in self.core_commands:
            cmd_info = self.core_commands[command_name]
            
            # Check permissions
            if not self._check_permissions(event, cmd_info["permissions"]):
                return BotResponse(
                    text=f"@{event.user_name} Permission denied.",
                    targets=["chat"]
                )
            
            logger.info(f"Routing to core command: !{command_name}")
            return await cmd_info["handler"](ctx)
        
        # 2. Try custom commands (per-channel)
        if self.custom_command_engine:
            response = await self.custom_command_engine.handle(ctx)
            if response:
                logger.info(f"Routing to custom command: !{command_name}")
                return response
        
        # 3. Try module handlers
        for handler in self.module_handlers:
            response = await handler(event)
            if response:
                logger.info(f"Routing to module: {handler.__self__.__class__.__name__}")
                return response
        
        # No handler found
        logger.debug(f"No handler for command: !{command_name}")
        return None
    
    def _check_permissions(self, event: BotEvent, required: List[str]) -> bool:
        """
        Check if user has required permissions.
        
        Args:
            event: BotEvent with user context
            required: List of required permissions
            
        Returns:
            True if user has all required permissions
        """
        if not required:
            return True
        
        # Broadcaster always has all permissions
        if event.is_broadcaster:
            return True
        
        # Check each required permission
        for perm in required:
            if perm == "mod" and not event.is_mod:
                return False
            if perm == "vip" and not event.is_vip:
                return False
            if perm == "broadcaster" and not event.is_broadcaster:
                return False
        
        return True
