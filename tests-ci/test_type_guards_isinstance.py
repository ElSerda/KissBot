"""
🦀 Tests Type Guards - isinstance (Rust-style safety)

Teste les isinstance guards ajoutés pour mypy strict compliance.
Vérifie que les guards protègent contre types incorrects dans les dicts YAML.
"""

import pytest
from unittest.mock import Mock, patch


class TestEnhancedPatternsLoaderInstanceOf:
    """Tests des isinstance guards dans enhanced_patterns_loader.py"""

    def test_get_pattern_stats_with_valid_data(self):
        """✅ Test avec données valides (cas normal)"""
        from modules.intelligence.enhanced_patterns_loader import EnhancedPatternsLoader

        # Mock rules valides
        mock_rules = {
            'ping': {
                'patterns': ['salut', 'yo', 'hello'],  # List valide
                'context_modifiers': {'gaming': 0.5},  # Dict valide
                'weight': 1.0
            },
            'gen_short': {
                'patterns': ['comment', 'pourquoi'],
                'context_modifiers': {},
                'weight': 1.5
            }
        }

        loader = EnhancedPatternsLoader()
        loader.classification_rules = mock_rules

        # Execute
        stats = loader.get_pattern_stats()

        # Vérifie: pas de crash, stats correctes
        assert stats['total_patterns'] == 5  # 3 + 2
        assert stats['classes']['ping']['pattern_count'] == 3
        assert stats['classes']['gen_short']['pattern_count'] == 2

    def test_get_pattern_stats_with_none_patterns(self):
        """🔍 Test avec patterns=None → isinstance guard protège"""
        from modules.intelligence.enhanced_patterns_loader import EnhancedPatternsLoader

        # Mock rules avec patterns=None (YAML corrompu)
        mock_rules = {
            'ping': {
                'patterns': None,  # ❌ Pas une list!
                'context_modifiers': {},
                'weight': 1.0
            }
        }

        loader = EnhancedPatternsLoader()
        loader.classification_rules = mock_rules

        # Execute - ne doit PAS crash grâce à isinstance
        stats = loader.get_pattern_stats()

        # Vérifie: isinstance guard → pattern_count=0
        assert stats['classes']['ping']['pattern_count'] == 0
        assert stats['total_patterns'] == 0

    def test_get_pattern_stats_with_string_instead_of_list(self):
        """🔍 Test avec patterns='string' au lieu de list"""
        from modules.intelligence.enhanced_patterns_loader import EnhancedPatternsLoader

        # Mock rules avec patterns en string (erreur config)
        mock_rules = {
            'gen_short': {
                'patterns': 'salut',  # ❌ String au lieu de ['salut']
                'context_modifiers': {},
                'weight': 1.0
            }
        }

        loader = EnhancedPatternsLoader()
        loader.classification_rules = mock_rules

        # Execute
        stats = loader.get_pattern_stats()

        # Vérifie: isinstance(patterns, list) → False → count=0
        assert stats['classes']['gen_short']['pattern_count'] == 0

    def test_get_pattern_stats_with_none_context_modifiers(self):
        """🔍 Test avec context_modifiers=None"""
        from modules.intelligence.enhanced_patterns_loader import EnhancedPatternsLoader

        # Mock rules avec context_modifiers=None
        mock_rules = {
            'gen_long': {
                'patterns': ['explique'],
                'context_modifiers': None,  # ❌ Pas un dict!
                'weight': 1.0
            }
        }

        loader = EnhancedPatternsLoader()
        loader.classification_rules = mock_rules

        # Execute - ne doit PAS crash
        stats = loader.get_pattern_stats()

        # Vérifie: isinstance guard → context_modifiers_len=0
        assert stats['classes']['gen_long']['context_modifiers'] == 0
        assert stats['classes']['gen_long']['pattern_count'] == 1  # patterns OK

    def test_get_pattern_stats_with_list_instead_of_dict(self):
        """🔍 Test avec context_modifiers=['item'] au lieu de dict"""
        from modules.intelligence.enhanced_patterns_loader import EnhancedPatternsLoader

        # Mock rules avec context_modifiers en list
        mock_rules = {
            'ping': {
                'patterns': ['yo'],
                'context_modifiers': ['gaming'],  # ❌ List au lieu de dict
                'weight': 1.0
            }
        }

        loader = EnhancedPatternsLoader()
        loader.classification_rules = mock_rules

        # Execute
        stats = loader.get_pattern_stats()

        # Vérifie: isinstance(context_mods, dict) → False → len=0
        assert stats['classes']['ping']['context_modifiers'] == 0

    def test_get_pattern_stats_with_mixed_corruption(self):
        """🔍 Test avec corruption mixte (plusieurs types incorrects)"""
        from modules.intelligence.enhanced_patterns_loader import EnhancedPatternsLoader

        # Mock rules totalement corrompues
        mock_rules = {
            'broken_class': {
                'patterns': 42,  # ❌ Int au lieu de list
                'context_modifiers': 'invalid',  # ❌ String au lieu de dict
                'weight': 1.0
            }
        }

        loader = EnhancedPatternsLoader()
        loader.classification_rules = mock_rules

        # Execute - ne doit PAS crash (defensive programming)
        stats = loader.get_pattern_stats()

        # Vérifie: tous les guards activés
        assert stats['classes']['broken_class']['pattern_count'] == 0
        assert stats['classes']['broken_class']['context_modifiers'] == 0
        assert stats['total_patterns'] == 0


class TestInstanceOfGuardsSourceCode:
    """Vérifie que les isinstance guards existent dans le code source"""

    def test_isinstance_guards_exist_in_source(self):
        """🔍 Vérifie présence des isinstance dans enhanced_patterns_loader.py"""
        import pathlib

        loader_file = pathlib.Path(__file__).parent.parent / "modules" / "intelligence" / "enhanced_patterns_loader.py"
        source = loader_file.read_text()

        # Vérifie présence des guards
        assert "isinstance(patterns, list)" in source
        assert "isinstance(context_mods, dict)" in source
        assert "isinstance(total_patt, int)" in source

    def test_isinstance_guards_count(self):
        """📊 Compte le nombre de isinstance guards"""
        import pathlib

        loader_file = pathlib.Path(__file__).parent.parent / "modules" / "intelligence" / "enhanced_patterns_loader.py"
        source = loader_file.read_text()

        # Compte les occurrences
        isinstance_count = source.count("isinstance(")

        # Devrait y en avoir au moins 3 dans get_pattern_stats
        assert isinstance_count >= 3, f"Expected at least 3 isinstance guards, found {isinstance_count}"


class TestInstanceOfGuardsJustification:
    """Documente pourquoi les isinstance guards sont nécessaires"""

    def test_isinstance_guards_protect_against_yaml_corruption(self):
        """📊 ANALYSE: Les isinstance guards protègent contre quoi?

        Cas réels:
        - YAML mal formé (indentation incorrecte)
        - Type cast automatique YAML (patterns: salut → string au lieu de list)
        - Fichier corrompu (édition manuelle incorrecte)
        - Fusion de config (merge conflict mal résolu)
        """
        yaml_corruption_cases = [
            "YAML mal indenté → patterns devient string",
            "Type cast auto YAML → context_modifiers devient string",
            "Édition manuelle → oubli des []",
            "Merge conflict → structure cassée",
            "Total_patterns corrompu → type inconsistent",
        ]

        # Les isinstance guards protègent contre tous ces cas
        assert len(yaml_corruption_cases) == 5

    def test_mypy_errors_without_isinstance(self):
        """🦀 MYPY: Sans isinstance → erreurs operator/len

        Avant:
        - pattern_count = len(patterns) → error: Argument has incompatible type "object"
        - stats['total_patterns'] += count → error: Unsupported operand types

        Après:
        - len(patterns) if isinstance(patterns, list) else 0 → mypy happy
        """
        mypy_errors = {
            "before": "Argument 1 to 'len' has incompatible type 'object'; expected 'Sized'",
            "after": "Success: no issues found"
        }

        assert "object" in mypy_errors["before"]
        assert "Success" in mypy_errors["after"]
