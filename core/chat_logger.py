#!/usr/bin/env python3
"""
Chat Logger - Phase 2.2
Logs all chat messages to dedicated chat.log file
"""

import logging
import pathlib
from datetime import datetime

from core.message_bus import MessageBus
from core.message_types import ChatMessage

LOGGER = logging.getLogger(__name__)


class ChatLogger:
    """
    Subscriber that logs all chat.inbound messages to dedicated chat.log
    Separate from main instance.log for easier chat analysis
    """
    
    def __init__(self, bus: MessageBus, config: dict):
        """
        Args:
            bus: MessageBus pour subscribe
            config: Config dict with _log_paths
        """
        self.bus = bus
        self.message_count = 0
        
        # Setup dedicated chat logger
        log_paths = config.get('_log_paths', {})
        chat_log_file = log_paths.get('chat')
        
        if chat_log_file:
            # Create dedicated file handler for chat messages
            self.chat_file_logger = logging.getLogger('chat_messages')
            self.chat_file_logger.setLevel(logging.INFO)
            self.chat_file_logger.propagate = False  # Don't send to root logger
            
            handler = logging.FileHandler(chat_log_file)
            handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
            self.chat_file_logger.addHandler(handler)
            
            LOGGER.info(f"📝 Chat logging to: {chat_log_file}")
        else:
            self.chat_file_logger = None
            LOGGER.info("📝 Chat logging to main log (no dedicated file)")
        
        # Subscribe à chat.inbound
        self.bus.subscribe("chat.inbound", self._handle_chat_message)
        LOGGER.info("ChatLogger initialisé - écoute chat.inbound")
    
    async def _handle_chat_message(self, msg: ChatMessage) -> None:
        """
        Handler pour les messages IRC entrants
        
        Args:
            msg: Message chat reçu
        """
        self.message_count += 1
        
        # Badges
        badges_str = ""
        if msg.is_broadcaster:
            badges_str += "👑"
        if msg.is_mod:
            badges_str += "🛡️"
        if msg.badges.get("subscriber"):
            badges_str += "⭐"
        if msg.is_vip:
            badges_str += "💎"
        
        # Log to dedicated chat.log file
        if self.chat_file_logger:
            self.chat_file_logger.info(
                f"[#{msg.channel}] {badges_str}{msg.user_login}: {msg.text}"
            )
        
        # Affichage structuré multi-channel (console)
        separator = "─" * 60
        print(f"\n{separator}")
        print(f"📺 Channel: #{msg.channel}")
        print(separator)
        print(f"👤 {badges_str}{msg.user_login}: {msg.text}")
        print(separator)
    
    def get_message_count(self) -> int:
        """Retourne le nombre de messages reçus"""
        return self.message_count
