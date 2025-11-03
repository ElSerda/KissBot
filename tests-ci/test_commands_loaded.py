"""
Tests de chargement des commandes
Vérifie que toutes les commandes sont correctement enregistrées
Architecture: pytwitchAPI (pas TwitchIO)
"""
import pytest


class TestCommandsRegistry:
    """Tests du registry des commandes"""
    
    def test_registry_import(self):
        """Vérifie que le registry peut être importé"""
        from commands.registry import register_all_commands
        assert callable(register_all_commands)
    
    def test_user_commands_exist(self):
        """Vérifie que les commandes utilisateur existent"""
        from commands.user_commands.intelligence import handle_ask, handle_joke
        from commands.user_commands.game import handle_gc, handle_gi
        from commands.user_commands.wiki import handle_wiki
        
        assert callable(handle_ask)
        assert callable(handle_joke)
        assert callable(handle_gc)
        assert callable(handle_gi)
        assert callable(handle_wiki)
    
    def test_bot_commands_exist(self):
        """Vérifie que les commandes bot existent"""
        from commands.bot_commands.system import handle_ping, handle_uptime
        
        assert callable(handle_ping)
        assert callable(handle_uptime)


class TestBackendHandlers:
    """Tests des backends"""
    
    def test_wikipedia_handler(self):
        """Vérifie que le Wikipedia handler existe"""
        from backends.wikipedia_handler import search_wikipedia, is_valid_wiki_query
        
        assert callable(search_wikipedia)
        assert callable(is_valid_wiki_query)
    
    def test_game_lookup(self):
        """Vérifie que le game lookup existe"""
        from backends.game_lookup import GameLookup
        
        assert GameLookup is not None


class TestCriticalCommands:
    """Tests des commandes critiques"""
    
    def test_ask_command_exists(self):
        """Vérifie que !ask existe"""
        from commands.user_commands.intelligence import handle_ask
        assert callable(handle_ask)
    
    def test_wiki_command_exists(self):
        """Vérifie que !wiki existe"""
        from commands.user_commands.wiki import handle_wiki
        assert callable(handle_wiki)
    
    def test_game_commands_exist(self):
        """Vérifie que !gi et !gc existent"""
        from commands.user_commands.game import handle_gi, handle_gc
        assert callable(handle_gi)
        assert callable(handle_gc)
    
    def test_ping_command_exists(self):
        """Vérifie que !ping existe"""
        from commands.bot_commands.system import handle_ping
        assert callable(handle_ping)
