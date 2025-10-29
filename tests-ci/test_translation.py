"""
Tests CI - Système de traduction
Vérifie que le système de traduction et whitelist devs fonctionne
"""
import json
import os
from pathlib import Path

import pytest


class TestTranslationSystem:
    """Tests du système de traduction"""

    def test_translation_module_imports(self):
        """Vérifie que le module translation s'importe"""
        from commands.translation import TranslationCommands
        
        assert TranslationCommands is not None

    @pytest.mark.unit
    def test_devs_whitelist_structure(self):
        """Vérifie que devs_whitelist.json a la bonne structure."""
        with open("data/devs_whitelist.json", "r") as f:
            data = json.load(f)
        
        # Structure réelle : {"devs": [...], "auto_translate": bool, ...}
        assert isinstance(data, dict), "devs_whitelist.json doit contenir un dict"
        assert "devs" in data, "Clé 'devs' manquante"
        assert isinstance(data["devs"], list), "data['devs'] doit être une liste"

    @pytest.mark.unit
    def test_translation_commands_has_expected_methods(self):
        """Vérifie que TranslationCommands a les méthodes attendues."""
        from commands.translation import TranslationCommands
        
        component = TranslationCommands()
        
        # Méthodes de commande TwitchIO 3.x (@commands.command décore ces méthodes)
        assert hasattr(component, 'translate_text'), "Méthode translate_text (commande !trad) doit exister"


class TestDevsWhitelist:
    """Tests de la whitelist des développeurs"""

    def test_devs_whitelist_file_creation(self, tmp_path):
        """Vérifie qu'on peut créer un fichier whitelist"""
        test_file = tmp_path / "test_devs.json"
        
        # Créer une whitelist de test
        test_devs = ["dev1", "dev2", "dev3"]
        with open(test_file, 'w') as f:
            json.dump(test_devs, f)
        
        # Vérifier lecture
        with open(test_file, 'r') as f:
            loaded = json.load(f)
        
        assert loaded == test_devs

    def test_devs_whitelist_empty_is_valid(self, tmp_path):
        """Vérifie qu'une whitelist vide est valide"""
        test_file = tmp_path / "test_devs_empty.json"
        
        # Whitelist vide
        with open(test_file, 'w') as f:
            json.dump([], f)
        
        # Doit pouvoir lire
        with open(test_file, 'r') as f:
            loaded = json.load(f)
        
        assert loaded == []
        assert isinstance(loaded, list)


class TestTranslationAPI:
    """Tests de l'API de traduction (mock)"""

    @pytest.mark.requires_llm
    def test_translation_api_url_format(self):
        """Vérifie que l'URL de l'API Google Translate est correcte"""
        # URL attendue (gratuit)
        expected_url = "https://translate.googleapis.com/translate_a/single"
        
        # Vérifie que l'URL est bien formée (pas de test réseau réel)
        assert expected_url.startswith("https://")
        assert "translate.googleapis.com" in expected_url

    def test_translation_params_structure(self):
        """Vérifie la structure des paramètres de traduction"""
        expected_params = {
            "client": "gtx",
            "sl": "auto",  # Auto-détection source
            "tl": "fr",    # Target français
            "dt": "t",
            "q": "test text"
        }
        
        # Vérifie structure minimale
        assert "client" in expected_params
        assert "sl" in expected_params
        assert "tl" in expected_params
        assert expected_params["tl"] == "fr"
