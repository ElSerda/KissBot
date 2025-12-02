"""
Tests unitaires - Sessions 2, 3, 4 (Migration Commands)
=======================================================
Vérifie que toutes les commandes migrées fonctionnent correctement.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass


@dataclass
class MockChatMessage:
    """Mock ChatMessage pour tests"""
    user_login: str = "test_user"
    user_id: str = "12345"
    channel: str = "test_channel"
    channel_id: str = "67890"
    text: str = "!test"
    is_mod: bool = False
    is_broadcaster: bool = False


class MockBus:
    """Mock MessageBus"""
    def __init__(self):
        self.published = []
    
    async def publish(self, topic: str, message):
        self.published.append((topic, message))


class MockHandler:
    """Mock MessageHandler avec tous les attributs nécessaires"""
    def __init__(self):
        self.bus = MockBus()
        self.game_lookup = None
        self.helix = None
        self.music_cache = None
        self.dev_whitelist = MagicMock()
        self.banword_manager = MagicMock()
        self.start_time = 0
        self.command_count = 42


# ════════════════════════════════════════════════════════════════════════
# SESSION 2 - GAME COMMANDS
# ════════════════════════════════════════════════════════════════════════

class TestGameCommands:
    """Tests pour !gi, !gs, !gc"""
    
    @pytest.mark.asyncio
    async def test_gi_no_game_lookup(self):
        """!gi sans game_lookup configuré"""
        from modules.classic_commands.user_commands.game import handle_gi
        
        handler = MockHandler()
        msg = MockChatMessage()
        
        await handle_gi(handler, msg, "hades")
        
        assert len(handler.bus.published) == 1
        assert "Game lookup not available" in handler.bus.published[0][1].text
    
    @pytest.mark.asyncio
    async def test_gi_no_args(self):
        """!gi sans argument"""
        from modules.classic_commands.user_commands.game import handle_gi
        
        handler = MockHandler()
        handler.game_lookup = MagicMock()
        msg = MockChatMessage()
        
        await handle_gi(handler, msg, "")
        
        assert len(handler.bus.published) == 1
        assert "Usage: !gi" in handler.bus.published[0][1].text
    
    @pytest.mark.asyncio
    async def test_gs_no_args(self):
        """!gs sans argument"""
        from modules.classic_commands.user_commands.game import handle_gs
        
        handler = MockHandler()
        handler.game_lookup = MagicMock()
        msg = MockChatMessage()
        
        await handle_gs(handler, msg, "")
        
        assert len(handler.bus.published) == 1
        assert "Usage: !gs" in handler.bus.published[0][1].text
    
    @pytest.mark.asyncio
    async def test_gc_no_helix(self):
        """!gc sans helix configuré"""
        from modules.classic_commands.user_commands.game import handle_gc
        
        handler = MockHandler()
        msg = MockChatMessage()
        
        await handle_gc(handler, msg)
        
        assert len(handler.bus.published) == 1
        assert "Helix client not available" in handler.bus.published[0][1].text


# ════════════════════════════════════════════════════════════════════════
# SESSION 3 - MOD COMMANDS
# ════════════════════════════════════════════════════════════════════════

class TestPerformanceCommands:
    """Tests pour !perf, !perftrace"""
    
    @pytest.mark.asyncio
    async def test_perf_non_mod_ignored(self):
        """!perf ignoré pour non-mods"""
        from modules.classic_commands.mod_commands.performance import handle_perf
        
        handler = MockHandler()
        msg = MockChatMessage(is_mod=False, is_broadcaster=False)
        
        await handle_perf(handler, msg)
        
        # Silently ignored = no response
        assert len(handler.bus.published) == 0
    
    @pytest.mark.asyncio
    async def test_perf_mod_no_db(self):
        """!perf par mod mais pas de DB"""
        from modules.classic_commands.mod_commands.performance import handle_perf
        
        handler = MockHandler()
        handler.game_lookup = MagicMock()
        handler.game_lookup.db = None
        msg = MockChatMessage(is_mod=True)
        
        await handle_perf(handler, msg)
        
        assert len(handler.bus.published) == 1
        assert "Database not available" in handler.bus.published[0][1].text
    
    @pytest.mark.asyncio
    async def test_perftrace_no_args(self):
        """!perftrace sans argument"""
        from modules.classic_commands.mod_commands.performance import handle_perftrace
        
        handler = MockHandler()
        handler.game_lookup = MagicMock()
        msg = MockChatMessage(is_mod=True)
        
        await handle_perftrace(handler, msg, "")
        
        assert len(handler.bus.published) == 1
        assert "Usage: !perftrace" in handler.bus.published[0][1].text


class TestDevlistCommands:
    """Tests pour !adddev, !rmdev, !listdevs"""
    
    @pytest.mark.asyncio
    async def test_adddev_non_mod_ignored(self):
        """!adddev ignoré pour non-mods"""
        from modules.classic_commands.mod_commands.devlist import handle_adddev
        
        handler = MockHandler()
        msg = MockChatMessage(is_mod=False)
        
        await handle_adddev(handler, msg, "someone")
        
        assert len(handler.bus.published) == 0
    
    @pytest.mark.asyncio
    async def test_adddev_no_args(self):
        """!adddev sans argument"""
        from modules.classic_commands.mod_commands.devlist import handle_adddev
        
        handler = MockHandler()
        msg = MockChatMessage(is_mod=True)
        
        await handle_adddev(handler, msg, "")
        
        assert len(handler.bus.published) == 1
        assert "Usage: !adddev" in handler.bus.published[0][1].text
    
    @pytest.mark.asyncio
    async def test_adddev_success(self):
        """!adddev avec succès"""
        from modules.classic_commands.mod_commands.devlist import handle_adddev
        
        handler = MockHandler()
        handler.dev_whitelist.add_dev.return_value = True
        msg = MockChatMessage(is_mod=True)
        
        await handle_adddev(handler, msg, "newdev")
        
        assert len(handler.bus.published) == 1
        assert "added to dev whitelist" in handler.bus.published[0][1].text
    
    @pytest.mark.asyncio
    async def test_listdevs_empty(self):
        """!listdevs sans devs (MOD only)"""
        from modules.classic_commands.mod_commands.devlist import handle_listdevs
        
        handler = MockHandler()
        handler.dev_whitelist.list_devs.return_value = []
        msg = MockChatMessage(is_mod=True)  # MOD required
        
        await handle_listdevs(handler, msg)
        
        assert len(handler.bus.published) == 1
        assert "No devs in whitelist" in handler.bus.published[0][1].text


class TestBanwordCommands:
    """Tests pour !kbbanword, !kbunbanword, !kbbanwords"""
    
    @pytest.mark.asyncio
    async def test_kbbanword_non_mod_ignored(self):
        """!kbbanword ignoré pour non-mods"""
        from modules.classic_commands.mod_commands.banwords import handle_kbbanword
        
        handler = MockHandler()
        msg = MockChatMessage(is_mod=False)
        
        await handle_kbbanword(handler, msg, "badword")
        
        assert len(handler.bus.published) == 0
    
    @pytest.mark.asyncio
    async def test_kbbanword_too_short(self):
        """!kbbanword mot trop court"""
        from modules.classic_commands.mod_commands.banwords import handle_kbbanword
        
        handler = MockHandler()
        msg = MockChatMessage(is_mod=True)
        
        await handle_kbbanword(handler, msg, "ab")
        
        assert len(handler.bus.published) == 1
        assert "au moins 3 caractères" in handler.bus.published[0][1].text
    
    @pytest.mark.asyncio
    async def test_kbbanword_success(self):
        """!kbbanword avec succès"""
        from modules.classic_commands.mod_commands.banwords import handle_kbbanword
        
        handler = MockHandler()
        handler.banword_manager.add_banword.return_value = True
        msg = MockChatMessage(is_mod=True)
        
        await handle_kbbanword(handler, msg, "badword")
        
        assert len(handler.bus.published) == 1
        assert "Banword ajouté" in handler.bus.published[0][1].text
    
    @pytest.mark.asyncio
    async def test_kbbanwords_empty(self):
        """!kbbanwords sans mots"""
        from modules.classic_commands.mod_commands.banwords import handle_kbbanwords
        
        handler = MockHandler()
        handler.banword_manager.list_banwords.return_value = []
        msg = MockChatMessage(is_mod=True)
        
        await handle_kbbanwords(handler, msg)
        
        assert len(handler.bus.published) == 1
        assert "Aucun banword configuré" in handler.bus.published[0][1].text


# ════════════════════════════════════════════════════════════════════════
# SESSION 4 - BROADCASTER COMMANDS
# ════════════════════════════════════════════════════════════════════════

class TestDecoherenceCommand:
    """Tests pour !decoherence"""
    
    @pytest.mark.asyncio
    async def test_decoherence_non_mod_rejected(self):
        """!decoherence refusé pour non-mods"""
        from modules.classic_commands.broadcaster_commands.decoherence import handle_decoherence
        
        handler = MockHandler()
        msg = MockChatMessage(is_mod=False, is_broadcaster=False)
        
        await handle_decoherence(handler, msg)
        
        assert len(handler.bus.published) == 1
        assert "réservé aux mods" in handler.bus.published[0][1].text
    
    @pytest.mark.asyncio
    async def test_decoherence_global_mod(self):
        """!decoherence global par mod"""
        from modules.classic_commands.broadcaster_commands.decoherence import handle_decoherence
        
        handler = MockHandler()
        msg = MockChatMessage(is_mod=True)
        
        await handle_decoherence(handler, msg, "")
        
        assert len(handler.bus.published) == 1
        assert "Décohérence globale" in handler.bus.published[0][1].text


class TestPersonalityCommands:
    """Tests pour !kbpersona, !kbnsfw"""
    
    @pytest.mark.asyncio
    async def test_kbpersona_non_broadcaster_rejected(self):
        """!kbpersona refusé pour non-broadcasters"""
        from modules.classic_commands.broadcaster_commands.personality import handle_kbpersona
        
        handler = MockHandler()
        # user_id != channel_id = not broadcaster
        msg = MockChatMessage(user_id="111", channel_id="222")
        
        await handle_kbpersona(handler, msg, "")
        
        assert len(handler.bus.published) == 1
        assert "réservée au broadcaster" in handler.bus.published[0][1].text
    
    @pytest.mark.asyncio
    async def test_kbnsfw_non_broadcaster_rejected(self):
        """!kbnsfw refusé pour non-broadcasters"""
        from modules.classic_commands.broadcaster_commands.personality import handle_kbnsfw
        
        handler = MockHandler()
        msg = MockChatMessage(user_id="111", channel_id="222")
        
        await handle_kbnsfw(handler, msg, "on")
        
        assert len(handler.bus.published) == 1
        assert "réservée au broadcaster" in handler.bus.published[0][1].text


# ════════════════════════════════════════════════════════════════════════
# IMPORT VALIDATION
# ════════════════════════════════════════════════════════════════════════

class TestImports:
    """Vérifie que tous les imports fonctionnent"""
    
    def test_import_game_commands(self):
        """Import game commands"""
        from modules.classic_commands.user_commands.game import (
            handle_gi, handle_gs, handle_gc
        )
        assert callable(handle_gi)
        assert callable(handle_gs)
        assert callable(handle_gc)
    
    def test_import_kbanniv(self):
        """Import kbanniv command"""
        from modules.classic_commands.user_commands.kbanniv import handle_kbanniv
        assert callable(handle_kbanniv)
    
    def test_import_mod_commands(self):
        """Import mod commands"""
        from modules.classic_commands.mod_commands import (
            handle_perf, handle_perftrace,
            handle_adddev, handle_rmdev, handle_listdevs,
            handle_kbbanword, handle_kbunbanword, handle_kbbanwords
        )
        assert callable(handle_perf)
        assert callable(handle_perftrace)
        assert callable(handle_adddev)
        assert callable(handle_rmdev)
        assert callable(handle_listdevs)
        assert callable(handle_kbbanword)
        assert callable(handle_kbunbanword)
        assert callable(handle_kbbanwords)
    
    def test_import_broadcaster_commands(self):
        """Import broadcaster commands"""
        from modules.classic_commands.broadcaster_commands import (
            handle_decoherence,
            handle_kbpersona,
            handle_kbnsfw
        )
        assert callable(handle_decoherence)
        assert callable(handle_kbpersona)
        assert callable(handle_kbnsfw)
    
    def test_message_handler_import(self):
        """Import MessageHandler"""
        from core.message_handler import MessageHandler
        assert MessageHandler is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
