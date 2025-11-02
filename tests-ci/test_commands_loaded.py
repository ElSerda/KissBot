"""
Tests de chargement des commandes
Vérifie que toutes les commandes sont correctement enregistrées
"""
import pytest


class TestCommandsStructure:
    """Tests de structure des commandes"""
    
    def test_utils_commands_exist(self):
        """Vérifie que UtilsCommands existe et est un Component"""
        from commands.utils_commands import UtilsCommands
        from twitchio.ext import commands
        
        assert issubclass(UtilsCommands, commands.Component)
    
    def test_game_commands_exist(self):
        """Vérifie que GameCommands existe et est un Component"""
        from commands.game_commands import GameCommands
        from twitchio.ext import commands
        
        assert issubclass(GameCommands, commands.Component)
    
    def test_intelligence_commands_exist(self):
        """Vérifie que IntelligenceCommands existe et est un Component"""
        from commands.intelligence_commands import IntelligenceCommands
        from twitchio.ext import commands
        
        assert issubclass(IntelligenceCommands, commands.Component)
    
    def test_translation_commands_exist(self):
        """Vérifie que TranslationCommands existe et est un Component"""
        from commands.translation import TranslationCommands
        from twitchio.ext import commands
        
        assert issubclass(TranslationCommands, commands.Component)
    
    @pytest.mark.skip(reason="Quantum commands integrated in message_handler")
    def test_quantum_commands_exist(self):
        """Vérifie que QuantumCommands existe et est un Component"""
        from commands.quantum_commands import QuantumCommands
        from twitchio.ext import commands
        
        assert issubclass(QuantumCommands, commands.Component)


class TestCommandsCount:
    """Tests du nombre de commandes"""
    
    def test_expected_commands_count(self):
        """Vérifie qu'on a bien les commandes principales dans MessageHandler"""
        from pathlib import Path
        
        # MessageBus architecture: commands handled in message_handler.py
        handler_file = Path("core/message_handler.py")
        content = handler_file.read_text()
        
        # Count command handlers (elif command == "!...")
        import re
        commands = re.findall(r'elif command == "(![\w]+)"', content)
        
        # Expected commands: !ping, !uptime, !stats, !help, !gi, !gc, !ask, 
        # !qgame, !collapse, !quantum, !decoherence, !kisscharity
        command_count = len(set(commands))  # Unique commands
        
        assert command_count >= 10, f"Seulement {command_count} commandes trouvées (attendu: ≥10)"
        assert command_count <= 20, f"Trop de commandes: {command_count} (attendu: ≤20)"


class TestCriticalCommands:
    """Tests des commandes critiques"""
    
    def test_ping_command_exists(self):
        """Vérifie que !ping existe"""
        from commands.utils_commands import UtilsCommands
        utils = UtilsCommands()
        assert hasattr(utils, 'ping_command')
    
    def test_ask_command_exists(self):
        """Vérifie que !ask existe"""
        from commands.intelligence_commands import IntelligenceCommands
        intel = IntelligenceCommands()
        assert hasattr(intel, 'ask_command')
    
    def test_trad_command_exists(self):
        """Vérifie que !trad existe"""
        from commands.translation import TranslationCommands
        trad = TranslationCommands()
        assert hasattr(trad, 'translate_text')
    
    def test_gameinfo_command_exists(self):
        """Vérifie que !gameinfo existe"""
        from commands.game_commands import GameCommands
        game = GameCommands()
        assert hasattr(game, 'game_command')
    
    def test_gamecategory_command_exists(self):
        """Vérifie que !gamecategory / !gc existe"""
        from commands.game_commands import GameCommands
        game = GameCommands()
        assert hasattr(game, 'game_category_command')
