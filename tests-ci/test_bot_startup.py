"""
Tests de démarrage du bot KissBot
Vérifie que le bot peut être initialisé et configuré correctement
"""
import pytest
import yaml
from pathlib import Path


class TestBotConfiguration:
    """Tests de configuration du bot"""
    
    @pytest.mark.skipif(not Path("config/config.yaml").exists(), reason="config.yaml requis")
    def test_config_file_exists(self):
        """Vérifie que config.yaml existe"""
        config_path = Path("config/config.yaml")
        assert config_path.exists(), "config/config.yaml doit exister"
    
    @pytest.mark.skipif(not Path("config/config.yaml").exists(), reason="config.yaml requis")
    def test_config_is_valid_yaml(self):
        """Vérifie que config.yaml est un YAML valide"""
        with open("config/config.yaml", "r") as f:
            config = yaml.safe_load(f)
        
        assert config is not None
        assert isinstance(config, dict)
    
    @pytest.mark.skipif(not Path("config/config.yaml").exists(), reason="config.yaml requis")
    def test_config_has_required_sections(self):
        """Vérifie que config.yaml contient les sections essentielles"""
        with open("config/config.yaml", "r") as f:
            config = yaml.safe_load(f)
        # Sections minimales requises (présentes dans tous les configs)
        required_sections = ['bot', 'twitch', 'llm']
        for section in required_sections:
            assert section in config, f"Section '{section}' manquante dans config.yaml"


class TestBotImports:
    """Tests d'imports du bot"""
    
    def test_import_bot_module(self):
        """Vérifie que le module bot peut être importé"""
        from bot import KissBotV3Working
        assert KissBotV3Working is not None
    
    def test_import_config_loader(self):
        """Vérifie que config_loader fonctionne"""
        from bot import load_config
        config = load_config()
        assert config is not None
        assert isinstance(config, dict)
    
    def test_import_all_components(self):
        """Vérifie que tous les components peuvent être importés"""
        from commands.utils_commands import UtilsCommands
        from commands.game_commands import GameCommands
        from commands.intelligence_commands import IntelligenceCommands
        from commands.translation import TranslationCommands
        from commands.quantum_commands import QuantumCommands
        
        assert all([
            UtilsCommands,
            GameCommands,
            IntelligenceCommands,
            TranslationCommands,
            QuantumCommands
        ])


@pytest.mark.bot
@pytest.mark.asyncio
async def test_bot_can_be_instantiated():
    """Test que le bot peut être instancié (sans se connecter)"""
    from bot import KissBotV3Working
    
    try:
        bot = KissBotV3Working()
        assert bot is not None
        assert hasattr(bot, 'config')
        assert hasattr(bot, 'bot_id')
    except Exception as e:
        pytest.fail(f"Bot instantiation failed: {e}")
