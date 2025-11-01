#!/usr/bin/env python3
"""
Test de la détection de mention (@bot_name)
Phase 3.2 - Bot Mention Feature
"""
from intelligence.core import extract_mention_message


def test_mention_extraction():
    """Test l'extraction de message après mention"""
    
    bot_name = "serda_bot"
    
    test_cases = [
        # Format @bot_name
        ("@serda_bot tu penses quoi de python?", "tu penses quoi de python?"),
        ("@serda_bot salut", "salut"),
        ("@SERDA_BOT coucou", "coucou"),  # Case-insensitive
        
        # Format bot_name (sans @)
        ("serda_bot c'est quoi ton avis?", "c'est quoi ton avis?"),
        ("SERDA_BOT hello", "hello"),
        
        # Mention au milieu (devrait extraire le reste)
        ("hey @serda_bot comment ça va?", "hey comment ça va?"),  # Note: peut avoir espace double
        
        # Pas de mention
        ("hello world", None),
        ("!ask python", None),
        ("@other_bot salut", None),
    ]
    
    print("🧪 Test Mention Extraction\n")
    
    success = 0
    total = len(test_cases)
    
    for message, expected in test_cases:
        result = extract_mention_message(message, bot_name)
        
        # Normaliser les espaces multiples pour comparaison
        result_normalized = " ".join(result.split()) if result else None
        expected_normalized = " ".join(expected.split()) if expected else None
        
        status = "✅" if result_normalized == expected_normalized else "❌"
        
        if result_normalized == expected_normalized:
            success += 1
        
        print(f"{status} Input: '{message}'")
        print(f"   Expected: {expected}")
        print(f"   Got: {result}\n")
    
    print(f"📊 Results: {success}/{total} tests passed")
    
    if success == total:
        print("✅ Tous les tests passent!")
        return True
    else:
        print("❌ Certains tests ont échoué")
        return False


if __name__ == "__main__":
    test_mention_extraction()
