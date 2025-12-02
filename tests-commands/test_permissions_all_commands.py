"""
Tests de permissions - Toutes les commandes
===========================================
Vérifie que chaque commande respecte les niveaux de permission.

Niveaux:
- USER: Tout le monde peut utiliser
- MOD: Mods et broadcasters uniquement
- BROADCASTER: Broadcasters uniquement
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass
from typing import List, Tuple
from enum import Enum


class PermLevel(Enum):
    USER = "user"
    MOD = "mod"
    BROADCASTER = "broadcaster"


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
    
    @classmethod
    def as_user(cls):
        """Message d'un viewer normal"""
        return cls(is_mod=False, is_broadcaster=False, user_id="11111", channel_id="99999")
    
    @classmethod
    def as_mod(cls):
        """Message d'un modérateur"""
        return cls(is_mod=True, is_broadcaster=False, user_id="22222", channel_id="99999")
    
    @classmethod
    def as_broadcaster(cls):
        """Message du broadcaster (user_id == channel_id)"""
        return cls(is_mod=False, is_broadcaster=True, user_id="99999", channel_id="99999")


class MockBus:
    """Mock MessageBus"""
    def __init__(self):
        self.published: List[Tuple[str, any]] = []
    
    async def publish(self, topic: str, message):
        self.published.append((topic, message))
    
    def clear(self):
        self.published.clear()
    
    def get_last_response(self) -> str:
        """Retourne le texte de la dernière réponse"""
        if self.published:
            return self.published[-1][1].text
        return ""
    
    def has_response(self) -> bool:
        return len(self.published) > 0


class MockHandler:
    """Mock MessageHandler avec tous les attributs nécessaires"""
    def __init__(self):
        self.bus = MockBus()
        self.game_lookup = MagicMock()
        self.game_lookup.db = MagicMock()
        self.game_lookup.db.get_cache_stats.return_value = {
            'hit_rate': 85.0, 'count': 100, 'top_game': 'Hades', 'top_hits': 50
        }
        self.game_lookup.perf = MagicMock()
        self.game_lookup.perf.clear = MagicMock()
        self.game_lookup.perf.get_report.return_value = "Mock report"
        self.game_lookup.perf.get_summary.return_value = {
            'total_us': 1500.0, 'operation_count': 5, 'avg_us_per_operation': 300.0
        }
        self.game_lookup.search_game = AsyncMock(return_value=MagicMock(name="Hades"))
        self.helix = MagicMock()
        self.helix.get_stream = AsyncMock(return_value=None)
        self.music_cache = MagicMock()
        self.music_cache.cleanup_expired.return_value = 5
        self.dev_whitelist = MagicMock()
        self.dev_whitelist.add_dev.return_value = True
        self.dev_whitelist.remove_dev.return_value = True
        self.dev_whitelist.list_devs.return_value = ["dev1", "dev2"]
        self.banword_manager = MagicMock()
        self.banword_manager.add_banword.return_value = True
        self.banword_manager.remove_banword.return_value = True
        self.banword_manager.list_banwords.return_value = ["word1", "word2"]
        self.start_time = 0
        self.command_count = 42
        self.system_monitor = MagicMock()
        self.system_monitor.get_stats.return_value = {
            'cpu_percent': 25.0, 'memory_mb': 150.0, 'thread_count': 10
        }
        # Attributs additionnels
        self.llm_handler = MagicMock()
        self.llm_handler.is_available.return_value = True
        self.irc_client = MagicMock()
        self.irc_client.joined_channels = ["#test_channel"]
        self.config = {}
    
    def reset(self):
        self.bus.clear()


# ════════════════════════════════════════════════════════════════════════
# DÉFINITION DES COMMANDES ET LEURS PERMISSIONS
# ════════════════════════════════════════════════════════════════════════

COMMANDS = [
    # (module_path, function_name, required_level, args, description)
    
    # USER COMMANDS - Tout le monde
    ("modules.classic_commands.user_commands.system", "handle_ping", PermLevel.USER, "", "!ping"),
    ("modules.classic_commands.user_commands.system", "handle_uptime", PermLevel.USER, "", "!uptime"),
    ("modules.classic_commands.user_commands.system", "handle_stats", PermLevel.USER, "", "!stats"),
    ("modules.classic_commands.user_commands.system", "handle_help", PermLevel.USER, "", "!help"),
    ("modules.classic_commands.user_commands.promo", "handle_kbkofi", PermLevel.USER, "", "!kbkofi"),
    ("modules.classic_commands.user_commands.promo", "handle_kisscharity", PermLevel.USER, "Test message", "!kisscharity"),
    ("modules.classic_commands.user_commands.game", "handle_gi", PermLevel.USER, "hades", "!gi"),
    ("modules.classic_commands.user_commands.game", "handle_gs", PermLevel.USER, "hades", "!gs"),
    ("modules.classic_commands.user_commands.game", "handle_gc", PermLevel.USER, "", "!gc"),
    ("modules.classic_commands.user_commands.kbanniv", "handle_kbanniv", PermLevel.USER, "someone", "!kbanniv"),
    
    # MOD COMMANDS - Mods et broadcasters
    ("modules.classic_commands.mod_commands.performance", "handle_perf", PermLevel.MOD, "", "!perf"),
    ("modules.classic_commands.mod_commands.performance", "handle_perftrace", PermLevel.MOD, "hades", "!perftrace"),
    ("modules.classic_commands.mod_commands.devlist", "handle_adddev", PermLevel.MOD, "newdev", "!adddev"),
    ("modules.classic_commands.mod_commands.devlist", "handle_rmdev", PermLevel.MOD, "olddev", "!rmdev"),
    ("modules.classic_commands.mod_commands.devlist", "handle_listdevs", PermLevel.MOD, "", "!listdevs"),
    ("modules.classic_commands.mod_commands.banwords", "handle_kbbanword", PermLevel.MOD, "badword", "!kbbanword"),
    ("modules.classic_commands.mod_commands.banwords", "handle_kbunbanword", PermLevel.MOD, "badword", "!kbunbanword"),
    ("modules.classic_commands.mod_commands.banwords", "handle_kbbanwords", PermLevel.MOD, "", "!kbbanwords"),
    ("modules.classic_commands.broadcaster_commands.decoherence", "handle_decoherence", PermLevel.MOD, "", "!decoherence"),
    
    # BROADCASTER COMMANDS - Broadcasters uniquement
    ("modules.classic_commands.broadcaster_commands.personality", "handle_kbpersona", PermLevel.BROADCASTER, "", "!kbpersona"),
    ("modules.classic_commands.broadcaster_commands.personality", "handle_kbnsfw", PermLevel.BROADCASTER, "on", "!kbnsfw"),
]


# ════════════════════════════════════════════════════════════════════════
# TESTS DE PERMISSIONS
# ════════════════════════════════════════════════════════════════════════

class TestUserPermissions:
    """Test que les USER commands sont accessibles à tous"""
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("module_path,func_name,level,args,desc", [
        cmd for cmd in COMMANDS if cmd[2] == PermLevel.USER
    ])
    async def test_user_can_execute(self, module_path, func_name, level, args, desc):
        """Un USER peut exécuter les commandes USER"""
        import importlib
        module = importlib.import_module(module_path)
        handler_func = getattr(module, func_name)
        
        handler = MockHandler()
        msg = MockChatMessage.as_user()
        
        await handler_func(handler, msg, args) if args else await handler_func(handler, msg)
        
        # Les commandes USER doivent TOUJOURS répondre (pas de silent ignore)
        assert handler.bus.has_response(), f"{desc} should respond to USER"
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("module_path,func_name,level,args,desc", [
        cmd for cmd in COMMANDS if cmd[2] == PermLevel.USER
    ])
    async def test_mod_can_execute(self, module_path, func_name, level, args, desc):
        """Un MOD peut exécuter les commandes USER"""
        import importlib
        module = importlib.import_module(module_path)
        handler_func = getattr(module, func_name)
        
        handler = MockHandler()
        msg = MockChatMessage.as_mod()
        
        await handler_func(handler, msg, args) if args else await handler_func(handler, msg)
        
        assert handler.bus.has_response(), f"{desc} should respond to MOD"
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("module_path,func_name,level,args,desc", [
        cmd for cmd in COMMANDS if cmd[2] == PermLevel.USER
    ])
    async def test_broadcaster_can_execute(self, module_path, func_name, level, args, desc):
        """Un BROADCASTER peut exécuter les commandes USER"""
        import importlib
        module = importlib.import_module(module_path)
        handler_func = getattr(module, func_name)
        
        handler = MockHandler()
        msg = MockChatMessage.as_broadcaster()
        
        await handler_func(handler, msg, args) if args else await handler_func(handler, msg)
        
        assert handler.bus.has_response(), f"{desc} should respond to BROADCASTER"


class TestModPermissions:
    """Test que les MOD commands sont réservées aux mods/broadcasters"""
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("module_path,func_name,level,args,desc", [
        cmd for cmd in COMMANDS if cmd[2] == PermLevel.MOD
    ])
    async def test_user_cannot_execute(self, module_path, func_name, level, args, desc):
        """Un USER ne peut PAS exécuter les commandes MOD (silent ignore ou rejet)"""
        import importlib
        module = importlib.import_module(module_path)
        handler_func = getattr(module, func_name)
        
        handler = MockHandler()
        msg = MockChatMessage.as_user()
        
        await handler_func(handler, msg, args) if args else await handler_func(handler, msg)
        
        # Soit pas de réponse (silent), soit message de rejet
        if handler.bus.has_response():
            response = handler.bus.get_last_response()
            assert any(x in response.lower() for x in ["réservé", "mod", "permission", "❌", "⚠️"]), \
                f"{desc} should reject USER with error message"
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("module_path,func_name,level,args,desc", [
        cmd for cmd in COMMANDS if cmd[2] == PermLevel.MOD
    ])
    async def test_mod_can_execute(self, module_path, func_name, level, args, desc):
        """Un MOD peut exécuter les commandes MOD"""
        import importlib
        module = importlib.import_module(module_path)
        handler_func = getattr(module, func_name)
        
        handler = MockHandler()
        msg = MockChatMessage.as_mod()
        
        await handler_func(handler, msg, args) if args else await handler_func(handler, msg)
        
        assert handler.bus.has_response(), f"{desc} should respond to MOD"
        # Et la réponse ne doit pas être un rejet
        response = handler.bus.get_last_response()
        assert "réservé" not in response.lower(), f"{desc} should not reject MOD"
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("module_path,func_name,level,args,desc", [
        cmd for cmd in COMMANDS if cmd[2] == PermLevel.MOD
    ])
    async def test_broadcaster_can_execute(self, module_path, func_name, level, args, desc):
        """Un BROADCASTER peut exécuter les commandes MOD"""
        import importlib
        module = importlib.import_module(module_path)
        handler_func = getattr(module, func_name)
        
        handler = MockHandler()
        msg = MockChatMessage.as_broadcaster()
        
        await handler_func(handler, msg, args) if args else await handler_func(handler, msg)
        
        assert handler.bus.has_response(), f"{desc} should respond to BROADCASTER"


class TestBroadcasterPermissions:
    """Test que les BROADCASTER commands sont réservées aux broadcasters"""
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("module_path,func_name,level,args,desc", [
        cmd for cmd in COMMANDS if cmd[2] == PermLevel.BROADCASTER
    ])
    async def test_user_cannot_execute(self, module_path, func_name, level, args, desc):
        """Un USER ne peut PAS exécuter les commandes BROADCASTER"""
        import importlib
        module = importlib.import_module(module_path)
        handler_func = getattr(module, func_name)
        
        handler = MockHandler()
        msg = MockChatMessage.as_user()
        
        await handler_func(handler, msg, args) if args else await handler_func(handler, msg)
        
        # Doit rejeter
        assert handler.bus.has_response(), f"{desc} should respond with rejection"
        response = handler.bus.get_last_response()
        assert any(x in response.lower() for x in ["broadcaster", "réservé", "❌"]), \
            f"{desc} should reject USER"
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("module_path,func_name,level,args,desc", [
        cmd for cmd in COMMANDS if cmd[2] == PermLevel.BROADCASTER
    ])
    async def test_mod_cannot_execute(self, module_path, func_name, level, args, desc):
        """Un MOD ne peut PAS exécuter les commandes BROADCASTER"""
        import importlib
        module = importlib.import_module(module_path)
        handler_func = getattr(module, func_name)
        
        handler = MockHandler()
        msg = MockChatMessage.as_mod()
        
        await handler_func(handler, msg, args) if args else await handler_func(handler, msg)
        
        # Doit rejeter
        assert handler.bus.has_response(), f"{desc} should respond with rejection"
        response = handler.bus.get_last_response()
        assert any(x in response.lower() for x in ["broadcaster", "réservé", "❌"]), \
            f"{desc} should reject MOD"
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("module_path,func_name,level,args,desc", [
        cmd for cmd in COMMANDS if cmd[2] == PermLevel.BROADCASTER
    ])
    async def test_broadcaster_can_execute(self, module_path, func_name, level, args, desc):
        """Un BROADCASTER peut exécuter les commandes BROADCASTER"""
        import importlib
        module = importlib.import_module(module_path)
        handler_func = getattr(module, func_name)
        
        handler = MockHandler()
        msg = MockChatMessage.as_broadcaster()
        
        await handler_func(handler, msg, args) if args else await handler_func(handler, msg)
        
        assert handler.bus.has_response(), f"{desc} should respond to BROADCASTER"
        response = handler.bus.get_last_response()
        # Ne doit pas être un rejet
        assert "réservée au broadcaster" not in response.lower(), f"{desc} should not reject BROADCASTER"


# ════════════════════════════════════════════════════════════════════════
# TESTS DE COUVERTURE
# ════════════════════════════════════════════════════════════════════════

class TestCommandCoverage:
    """Vérifie que toutes les commandes sont testées"""
    
    def test_all_commands_have_level(self):
        """Chaque commande dans COMMANDS a un niveau défini"""
        for cmd in COMMANDS:
            assert cmd[2] in PermLevel, f"{cmd[4]} has invalid permission level"
    
    def test_user_commands_count(self):
        """Nombre de commandes USER"""
        user_cmds = [c for c in COMMANDS if c[2] == PermLevel.USER]
        print(f"\n📊 USER commands: {len(user_cmds)}")
        for c in user_cmds:
            print(f"   - {c[4]}")
        assert len(user_cmds) >= 8, "Should have at least 8 USER commands"
    
    def test_mod_commands_count(self):
        """Nombre de commandes MOD"""
        mod_cmds = [c for c in COMMANDS if c[2] == PermLevel.MOD]
        print(f"\n📊 MOD commands: {len(mod_cmds)}")
        for c in mod_cmds:
            print(f"   - {c[4]}")
        assert len(mod_cmds) >= 8, "Should have at least 8 MOD commands"
    
    def test_broadcaster_commands_count(self):
        """Nombre de commandes BROADCASTER"""
        bc_cmds = [c for c in COMMANDS if c[2] == PermLevel.BROADCASTER]
        print(f"\n📊 BROADCASTER commands: {len(bc_cmds)}")
        for c in bc_cmds:
            print(f"   - {c[4]}")
        assert len(bc_cmds) >= 2, "Should have at least 2 BROADCASTER commands"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
