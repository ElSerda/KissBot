"""
Tests de la commande !gamecategory / !gc
Auto-détection du jeu du stream actuel

Tests de STRUCTURE uniquement (pas de tests d'intégration TwitchIO)
→ Les wrappers TwitchIO sont complexes à mocker correctement
→ Utiliser debug/test_gamecategory.py pour les tests manuels avec vraie API
"""
import pytest


class TestGameCategoryCommand:
    """Tests de structure de la commande !gamecategory"""
    
    def test_game_category_command_exists(self):
        """Vérifie que la commande game_category_command existe"""
        from commands.game_commands import GameCommands
        game_commands = GameCommands()
        assert hasattr(game_commands, 'game_category_command')
    
    def test_game_category_has_gc_alias(self):
        """Vérifie que !gc est un alias de !gamecategory"""
        from commands.game_commands import GameCommands
        
        # Vérifier que le décorateur command contient l'alias
        # On lit directement le fichier source
        import pathlib
        source_file = pathlib.Path(__file__).parent.parent / "commands" / "game_commands.py"
        source_code = source_file.read_text()
        
        # Chercher la définition de gamecategory avec alias gc
        assert '@commands.command(name="gamecategory"' in source_code
        assert 'aliases=["gc"]' in source_code
    
    def test_game_category_is_component_method(self):
        """Vérifie que game_category_command est bien une méthode du Component"""
        from commands.game_commands import GameCommands
        
        game_commands = GameCommands()
        # La méthode existe et est callable
        assert hasattr(game_commands, 'game_category_command')
        assert game_commands.game_category_command is not None
