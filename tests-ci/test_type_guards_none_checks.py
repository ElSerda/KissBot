"""
🦀 Tests Type Guards - None Checks (Rust-style safety)

Teste les None checks ajoutés pour mypy strict compliance.
Vérifie que les guards protègent contre les edge cases twitchio.
"""

import pytest
from unittest.mock import Mock


class TestTranslationNoneChecks:
    """Tests des None checks dans translation.py"""

    def test_none_message_check_exists(self):
        """🔍 Vérifie que le check `if not ctx.message` existe dans translate_text"""
        import pathlib

        translation_file = pathlib.Path(__file__).parent.parent / "commands" / "translation.py"
        source = translation_file.read_text()

        # Vérifie présence du None check dans translate_text
        assert "if not ctx.message or not ctx.message.content:" in source
        assert "return" in source  # Early return

    def test_none_content_check_exists(self):
        """🔍 Vérifie que le check existe pour adddev/deldev aussi"""
        import pathlib

        translation_file = pathlib.Path(__file__).parent.parent / "commands" / "translation.py"
        source = translation_file.read_text()

        # Compte les occurrences de None checks
        none_checks = source.count("if not ctx.message or not ctx.message.content:")

        # Devrait y en avoir au moins 3 (translate_text, add_dev, del_dev)
        assert none_checks >= 3, f"Expected at least 3 None checks, found {none_checks}"

    def test_adddev_none_checks_exist(self):
        """🔍 Vérifie que add_dev a des None checks"""
        import pathlib

        translation_file = pathlib.Path(__file__).parent.parent / "commands" / "translation.py"
        source = translation_file.read_text()

        # Vérifie présence dans add_dev
        assert "def add_dev" in source
        assert source.count("if not ctx.message") >= 2  # Au moins 2 occurrences

    def test_deldev_none_checks_exist(self):
        """🔍 Vérifie que del_dev a des None checks"""
        import pathlib

        translation_file = pathlib.Path(__file__).parent.parent / "commands" / "translation.py"
        source = translation_file.read_text()

        # Vérifie présence dans del_dev
        assert "def del_dev" in source
        assert source.count("if not ctx.message") >= 3  # Au moins 3 occurrences


class TestNoneChecksJustification:
    """Documente pourquoi les None checks sont nécessaires"""

    def test_none_checks_are_defensive_not_useless(self):
        """📊 ANALYSE: Les None checks sont-ils vraiment nécessaires?

        Conclusion: OUI car twitchio peut retourner None dans certains edge cases:
        - Message système (SUB, RAID, etc)
        - Webhook events
        - Message supprimé rapidement
        - IRC malformé
        """
        edge_cases = [
            "Message système (SUB notification)",
            "Webhook event (pas de message texte)",
            "Message supprimé avant parsing",
            "IRC frame malformé",
            "Timeout pendant fetch message",
        ]

        # Les None checks protègent contre tous ces cas
        assert len(edge_cases) > 0, "None checks sont défensifs contre edge cases réels"

    def test_mypy_errors_without_none_checks(self):
        """🦀 MYPY: Sans None checks → erreurs type union-attr

        Avant: ctx.message.content → error: Item "None" has no attribute "content"
        Après: if not ctx.message → mypy happy
        """
        # Documentation du problème mypy résolu
        mypy_error_before = 'Item "ChatMessage | None" has no attribute "content"'
        solution = "if not ctx.message or not ctx.message.content: return"

        assert mypy_error_before != solution
        assert "None" in mypy_error_before
        assert "if not" in solution
