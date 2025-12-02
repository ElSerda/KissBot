"""
Tests unitaires pour Session 1 - system.py et promo.py
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock


class TestSystemCommands:
    """Tests pour modules/classic_commands/user_commands/system.py"""
    
    def test_import_system(self):
        """Test que system.py s'importe correctement"""
        from modules.classic_commands.user_commands.system import (
            handle_ping, handle_uptime, handle_stats, handle_help
        )
        assert callable(handle_ping)
        assert callable(handle_uptime)
        assert callable(handle_stats)
        assert callable(handle_help)
    
    @pytest.mark.asyncio
    async def test_handle_ping(self):
        """Test !ping retourne Pong"""
        from modules.classic_commands.user_commands.system import handle_ping
        
        handler = MagicMock()
        handler.bus = MagicMock()
        handler.bus.publish = AsyncMock()
        
        msg = MagicMock()
        msg.channel = "test_channel"
        msg.channel_id = "12345"
        msg.user_login = "test_user"
        
        await handle_ping(handler, msg)
        
        handler.bus.publish.assert_called_once()
        call_args = handler.bus.publish.call_args
        assert call_args[0][0] == "chat.outbound"
        assert "Pong!" in call_args[0][1].text
        assert "🏓" in call_args[0][1].text
    
    @pytest.mark.asyncio
    async def test_handle_uptime(self):
        """Test !uptime retourne le temps"""
        from modules.classic_commands.user_commands.system import handle_uptime
        import time
        
        handler = MagicMock()
        handler.bus = MagicMock()
        handler.bus.publish = AsyncMock()
        handler.start_time = time.time() - 3661  # 1h 1m 1s
        
        msg = MagicMock()
        msg.channel = "test_channel"
        msg.channel_id = "12345"
        msg.user_login = "test_user"
        
        await handle_uptime(handler, msg)
        
        handler.bus.publish.assert_called_once()
        call_args = handler.bus.publish.call_args
        text = call_args[0][1].text
        assert "uptime:" in text.lower()
        assert "1h" in text
    
    @pytest.mark.asyncio
    async def test_handle_stats_no_monitor(self):
        """Test !stats sans SystemMonitor"""
        from modules.classic_commands.user_commands.system import handle_stats
        
        handler = MagicMock()
        handler.bus = MagicMock()
        handler.bus.publish = AsyncMock()
        handler.system_monitor = None
        
        msg = MagicMock()
        msg.channel = "test_channel"
        msg.channel_id = "12345"
        msg.user_login = "test_user"
        
        await handle_stats(handler, msg)
        
        handler.bus.publish.assert_called_once()
        call_args = handler.bus.publish.call_args
        assert "not available" in call_args[0][1].text
    
    @pytest.mark.asyncio
    async def test_handle_help(self):
        """Test !help liste les commandes"""
        from modules.classic_commands.user_commands.system import handle_help
        
        handler = MagicMock()
        handler.bus = MagicMock()
        handler.bus.publish = AsyncMock()
        handler.game_lookup = None
        handler.llm_handler = None
        
        msg = MagicMock()
        msg.channel = "test_channel"
        msg.channel_id = "12345"
        msg.user_login = "test_user"
        msg.is_broadcaster = False
        
        await handle_help(handler, msg)
        
        handler.bus.publish.assert_called_once()
        call_args = handler.bus.publish.call_args
        text = call_args[0][1].text
        assert "!ping" in text
        assert "!uptime" in text
        assert "!stats" in text
        assert "!help" in text


class TestPromoCommands:
    """Tests pour modules/classic_commands/user_commands/promo.py"""
    
    def test_import_promo(self):
        """Test que promo.py s'importe correctement"""
        from modules.classic_commands.user_commands.promo import (
            handle_kbkofi, handle_kisscharity
        )
        assert callable(handle_kbkofi)
        assert callable(handle_kisscharity)
    
    @pytest.mark.asyncio
    async def test_handle_kbkofi(self):
        """Test !kbkofi retourne le lien Ko-fi"""
        from modules.classic_commands.user_commands.promo import handle_kbkofi
        
        handler = MagicMock()
        handler.bus = MagicMock()
        handler.bus.publish = AsyncMock()
        
        msg = MagicMock()
        msg.channel = "test_channel"
        msg.channel_id = "12345"
        msg.user_login = "test_user"
        
        await handle_kbkofi(handler, msg)
        
        handler.bus.publish.assert_called_once()
        call_args = handler.bus.publish.call_args
        text = call_args[0][1].text
        assert "ko-fi.com/el_serda" in text
        assert "☕" in text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
