#!/usr/bin/env python3
"""
Script pour mettre à jour tous les tests GameCache 
pour utiliser les fixtures de conftest.py
"""

import re
import sys

def fix_test_backends():
    """Fix tests-ci/test_backends.py"""
    file_path = "tests-ci/test_backends.py"
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Remplacer les configs hardcodées par mock_config fixture
    patterns = [
        # Pattern 1: config = {'rawg': {'api_key': 'test_key'}, ...}
        (r"config = \{['\"]rawg['\"]: \{['\"]api_key['\"]: ['\"]test_key['\"].*?\}",
         "mock_config"),
        # Pattern 2: config = {'rawg': {'api_key': 'test_key_123'}, ...}
        (r"config = \{['\"]rawg['\"]: \{['\"]api_key['\"]: ['\"]test_key_123['\"].*?\}",
         "mock_config"),
    ]
    
    # Ajouter mock_config parameter aux tests
    content = re.sub(
        r"def (test_\w+)\(self\):",
        r"def \1(self, mock_config):",
        content
    )
    
    # Remplacer les instantiations GameCache
    content = re.sub(
        r"config = \{['\"]rawg['\"]: \{['\"]api_key['\"]: ['\"]test_key(?:_123)?['\"].*?\}",
        "config = mock_config",
        content
    )
    
    # Remplacer les instantiations QuantumGameCache
    content = re.sub(
        r"config = \{\s*['\"]rawg['\"]: \{['\"]api_key['\"]: ['\"]test_key(?:_123)?['\"].*?\},?\s*['\"]cache['\"]: \{['\"]max_size['\"]: \d+.*?\}",
        "config = mock_config",
        content,
        flags=re.DOTALL
    )
    
    # Remplacer GameCache(config)
    content = re.sub(
        r"GameCache\(config\)",
        "GameCache(mock_config)",
        content
    )
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed {file_path}")


def fix_test_game_cache_system():
    """Fix tests-ci/test_game_cache_system.py"""
    file_path = "tests-ci/test_game_cache_system.py"
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Ajouter mock_config parameter aux méthodes de test
    content = re.sub(
        r"def (test_\w+)\(self\):",
        r"def \1(self, mock_config):",
        content
    )
    
    # Remplacer config={"cache": {}}
    content = re.sub(
        r"config=\{['\"]cache['\"]: \{\}\}",
        "config=mock_config",
        content
    )
    
    # Remplacer config={"cache": {"duration_hours": X}}
    content = re.sub(
        r"config=\{['\"]cache['\"]: \{['\"]duration_hours['\"]: \d+\}\}",
        "config=mock_config",
        content
    )
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed {file_path}")


def fix_test_game_fuzzy_matching():
    """Fix tests-ci/test_game_fuzzy_matching.py"""
    file_path = "tests-ci/test_game_fuzzy_matching.py"
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Ajouter mock_config parameter aux méthodes de test
    content = re.sub(
        r"def (test_\w+)\(self\):",
        r"def \1(self, mock_config):",
        content
    )
    
    # Remplacer GameCache(config={"cache": {}})
    content = re.sub(
        r"GameCache\(config=\{['\"]cache['\"]: \{\}\}(?:, cache_file=[\"'].*?[\"'])?\)",
        r"GameCache(config=mock_config)",
        content
    )
    
    # Remplacer cache = GameCache(...)
    content = re.sub(
        r"cache = GameCache\(config=\{['\"]cache['\"]: \{\}\}(?:, cache_file=[\"'][^\"']*[\"'])?\)",
        r"cache = GameCache(config=mock_config)",
        content
    )
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed {file_path}")


if __name__ == "__main__":
    try:
        fix_test_backends()
        fix_test_game_cache_system()
        fix_test_game_fuzzy_matching()
        print("\n✅ All GameCache tests fixed!")
        print("Tests now use mock_config fixture from conftest.py")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
