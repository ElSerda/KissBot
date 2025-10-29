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
    
    def test_quantum_commands_exist(self):
        """Vérifie que QuantumCommands existe et est un Component"""
        from commands.quantum_commands import QuantumCommands
        from twitchio.ext import commands
        
        assert issubclass(QuantumCommands, commands.Component)


class TestCommandsCount:
    """Tests du nombre de commandes"""
    
    def test_expected_commands_count(self):
        """Vérifie qu'on a bien ~26 commandes définies"""
        import re
        from pathlib import Path
        
        commands_dir = Path("commands")
        command_count = 0
        
        for py_file in commands_dir.glob("*.py"):
            if py_file.name.startswith("__"):
                continue
            
            content = py_file.read_text()
            # Compter les @commands.command decorators
            matches = re.findall(r'@commands\.command\(name="(\w+)"', content)
            command_count += len(matches)
        
        # KissBot devrait avoir ~17-26 commandes
        assert command_count >= 15, f"Seulement {command_count} commandes trouvées (attendu: ≥15)"
        assert command_count <= 30, f"Trop de commandes: {command_count} (attendu: ≤30)"


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
