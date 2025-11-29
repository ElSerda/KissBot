#!/usr/bin/env python3
"""
Command Logger
Logs all command executions to dedicated commands.log file
"""

import logging
from datetime import datetime

from core.message_bus import MessageBus

LOGGER = logging.getLogger(__name__)


class CommandLogger:
    """
    Logs all command executions with user, args, and results
    Separate from instance.log for command analysis and audit
    """
    
    def __init__(self, bus: MessageBus, config: dict):
        """
        Args:
            bus: MessageBus to subscribe
            config: Config dict with _log_paths
        """
        self.bus = bus
        self.command_count = 0
        
        # Setup dedicated command logger
        log_paths = config.get('_log_paths', {})
        cmd_log_file = log_paths.get('commands')
        
        if cmd_log_file:
            # Create dedicated file handler for commands
            self.cmd_file_logger = logging.getLogger('command_executions')
            self.cmd_file_logger.setLevel(logging.INFO)
            self.cmd_file_logger.propagate = False  # Don't send to root logger
            
            handler = logging.FileHandler(cmd_log_file)
            handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
            self.cmd_file_logger.addHandler(handler)
            
            LOGGER.info(f"⚡ Command logging to: {cmd_log_file}")
        else:
            self.cmd_file_logger = None
            LOGGER.info("⚡ Command logging to main log (no dedicated file)")
        
        # Subscribe to command lifecycle events
        self.bus.subscribe("command.executed", self._handle_command_executed)
        self.bus.subscribe("command.failed", self._handle_command_failed)
        LOGGER.info("CommandLogger initialized - listening to command events")
    
    async def _handle_command_executed(self, data: dict) -> None:
        """
        Handler for successful command executions
        
        Args:
            data: Dict with command, user, channel, args, result
        """
        self.command_count += 1
        
        command = data.get('command', 'unknown')
        user = data.get('user', 'anonymous')
        channel = data.get('channel', 'unknown')
        args = data.get('args', '')
        result = data.get('result', 'success')
        
        # Args peut être string ou list, on normalise
        if isinstance(args, list):
            args_str = ' '.join(args) if args else '(no args)'
        elif isinstance(args, str):
            args_str = args if args else '(no args)'
        else:
            args_str = str(args)
        
        if self.cmd_file_logger:
            self.cmd_file_logger.info(
                f"✅ [#{channel}] {user} → !{command} {args_str} | {result}"
            )
    
    async def _handle_command_failed(self, data: dict) -> None:
        """
        Handler for failed command executions
        
        Args:
            data: Dict with command, user, channel, error
        """
        command = data.get('command', 'unknown')
        user = data.get('user', 'anonymous')
        channel = data.get('channel', 'unknown')
        error = data.get('error', 'unknown error')
        
        if self.cmd_file_logger:
            self.cmd_file_logger.warning(
                f"❌ [#{channel}] {user} → !{command} | ERROR: {error}"
            )
    
    def get_command_count(self) -> int:
        """Returns number of commands logged"""
        return self.command_count
