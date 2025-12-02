#!/usr/bin/env python3
"""
Test du pipeline complet !ask - End-to-End

Ce script teste le flux RÉEL:
1. Message entrant → message_handler.py
2. Dispatch → intelligence_v2.py  
3. LLM call → cloud_synapse.py
4. Truncation → _smart_truncate()
5. Message sortant → [ASK] response

Usage:
    python tests-commands/test_ask_pipeline_e2e.py
    
    # Avec une vraie requête LLM (nécessite API key):
    python tests-commands/test_ask_pipeline_e2e.py --live
"""
import asyncio
import sys
import os

# Ajouter le projet au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, AsyncMock, patch
from dataclasses import dataclass


@dataclass
class MockOutboundMessage:
    """Mock de OutboundMessage"""
    channel: str
    channel_id: str
    text: str
    prefer: str


class PipelineTestResults:
    """Collecteur de résultats"""
    def __init__(self):
        self.steps = []
        self.final_message = None
        self.errors = []
    
    def log(self, step: str, status: str, details: str = ""):
        self.steps.append((step, status, details))
        emoji = "✅" if status == "OK" else "❌" if status == "FAIL" else "⚠️"
        print(f"  {emoji} {step}: {details[:80] if details else status}")


async def test_pipeline_with_mock_llm(question: str = "correspondance ADS CFT"):
    """
    Test du pipeline avec LLM mocké.
    Valide: imports, dispatch, format [ASK], truncation.
    """
    print("\n" + "="*70)
    print("🧪 TEST PIPELINE !ask (Mock LLM)")
    print("="*70)
    print(f"Question: {question}")
    print("-"*70)
    
    results = PipelineTestResults()
    
    # ═══════════════════════════════════════════════════════════════════
    # STEP 1: Import du handler depuis message_handler.py
    # ═══════════════════════════════════════════════════════════════════
    try:
        from modules.classic_commands.user_commands.intelligence_v2 import handle_ask
        results.log("Import handle_ask", "OK", "modules.classic_commands.user_commands.intelligence_v2")
    except ImportError as e:
        results.log("Import handle_ask", "FAIL", str(e))
        return results
    
    # ═══════════════════════════════════════════════════════════════════
    # STEP 2: Setup des mocks réalistes
    # ═══════════════════════════════════════════════════════════════════
    
    # Réponse LLM simulée (longueur réaliste)
    mock_llm_response = (
        "La correspondance AdS/CFT est une conjecture fondamentale en physique théorique "
        "qui établit une équivalence entre une théorie de gravité quantique dans un espace "
        "anti-de Sitter (AdS) et une théorie conforme des champs (CFT) vivant sur la frontière "
        "de cet espace. Cette dualité holographique, proposée par Juan Maldacena en 1997, "
        "permet d'étudier des systèmes fortement couplés en utilisant des méthodes gravitationnelles."
    )
    
    print(f"\n📝 Réponse LLM simulée ({len(mock_llm_response)} chars):")
    print(f"   \"{mock_llm_response[:100]}...\"")
    
    # Mock du MessageHandler
    class MockHandler:
        def __init__(self):
            self.bus = MagicMock()
            self.published_messages = []
            self.bus.publish = self._capture_publish
            self.config = {'wikipedia': {'lang': 'fr'}}
            self.llm_handler = MagicMock()
            self.llm_handler.ask = AsyncMock(return_value=mock_llm_response)
        
        async def _capture_publish(self, topic, message):
            self.published_messages.append((topic, message))
    
    # Mock du ChatMessage
    class MockMessage:
        user_login = 'test_user'
        user_id = '12345'
        channel = 'test_channel'
        channel_id = '67890'
    
    handler = MockHandler()
    msg = MockMessage()
    results.log("Setup mocks", "OK", "Handler + Message créés")
    
    # ═══════════════════════════════════════════════════════════════════
    # STEP 3: Exécution du handler
    # ═══════════════════════════════════════════════════════════════════
    try:
        # Patch Wikipedia pour éviter les appels réseau
        with patch('modules.integrations.wikipedia.wikipedia_handler.search_wikipedia',
                   new_callable=AsyncMock, return_value=None):
            await handle_ask(handler, msg, question)
        results.log("Exécution handle_ask", "OK", "Sans exception")
    except Exception as e:
        results.log("Exécution handle_ask", "FAIL", str(e))
        results.errors.append(str(e))
        return results
    
    # ═══════════════════════════════════════════════════════════════════
    # STEP 4: Validation du message de sortie
    # ═══════════════════════════════════════════════════════════════════
    if not handler.published_messages:
        results.log("Message publié", "FAIL", "Aucun message publié sur le bus")
        return results
    
    topic, outbound = handler.published_messages[0]
    final_text = outbound.text
    results.final_message = final_text
    
    results.log("Topic bus", "OK" if topic == "chat.outbound" else "FAIL", topic)
    
    # ═══════════════════════════════════════════════════════════════════
    # STEP 5: Validation du préfixe [ASK]
    # ═══════════════════════════════════════════════════════════════════
    if final_text.startswith("[ASK]"):
        results.log("Préfixe [ASK]", "OK", "Message commence par [ASK]")
    else:
        results.log("Préfixe [ASK]", "FAIL", f"Commence par: {final_text[:20]}")
    
    # ═══════════════════════════════════════════════════════════════════
    # STEP 6: Validation de la longueur (≤500 chars Twitch)
    # ═══════════════════════════════════════════════════════════════════
    msg_len = len(final_text)
    if msg_len <= 500:
        results.log("Longueur message", "OK", f"{msg_len}/500 chars")
    else:
        results.log("Longueur message", "FAIL", f"{msg_len}/500 chars - TROP LONG!")
    
    # ═══════════════════════════════════════════════════════════════════
    # STEP 7: Analyse de la truncation
    # ═══════════════════════════════════════════════════════════════════
    prefix_len = len("[ASK] ")  # 6 chars
    content_len = msg_len - prefix_len
    original_len = len(mock_llm_response)
    
    print(f"\n📊 Analyse de la réponse:")
    print(f"   Préfixe [ASK]: {prefix_len} chars")
    print(f"   Contenu: {content_len} chars")
    print(f"   Total: {msg_len} chars")
    print(f"   Limite Twitch: 500 chars")
    print(f"   Marge restante: {500 - msg_len} chars")
    print(f"   LLM original: {original_len} chars")
    
    if content_len < original_len:
        truncated_chars = original_len - content_len
        results.log("Truncation", "WARN", f"Tronqué de {truncated_chars} chars")
    else:
        results.log("Truncation", "OK", "Pas de truncation nécessaire")
    
    # ═══════════════════════════════════════════════════════════════════
    # Résultat final
    # ═══════════════════════════════════════════════════════════════════
    print(f"\n📤 Message final ({msg_len} chars):")
    print(f"   \"{final_text}\"")
    
    return results


async def test_pipeline_live(question: str = "correspondance ADS CFT"):
    """
    Test du pipeline avec VRAI appel LLM.
    Nécessite: config.yaml avec openai_key valide.
    """
    print("\n" + "="*70)
    print("🔴 TEST PIPELINE !ask (LIVE LLM)")
    print("="*70)
    print(f"Question: {question}")
    print("-"*70)
    
    results = PipelineTestResults()
    
    # Charger la vraie config
    try:
        import yaml
        with open('config/config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        results.log("Config chargée", "OK", "config/config.yaml")
    except Exception as e:
        results.log("Config chargée", "FAIL", str(e))
        return results
    
    # Vérifier API key
    api_key = config.get('apis', {}).get('openai_key', '')
    if not api_key or api_key.startswith('sk-xxx'):
        results.log("API Key", "FAIL", "Pas de clé OpenAI valide")
        return results
    results.log("API Key", "OK", f"sk-...{api_key[-4:]}")
    
    # Initialiser le vrai CloudSynapse
    try:
        from modules.intelligence.synapses.cloud_synapse import CloudSynapse
        synapse = CloudSynapse(config)
        results.log("CloudSynapse init", "OK", f"Model: {synapse.model}")
    except Exception as e:
        results.log("CloudSynapse init", "FAIL", str(e))
        return results
    
    # Appel LLM réel
    print("\n⏳ Appel LLM en cours...")
    try:
        response = await synapse.fire(
            stimulus=question,
            context="ask",
            stimulus_class="gen_long"
        )
        
        if response:
            results.log("Réponse LLM", "OK", f"{len(response)} chars")
            print(f"\n📝 Réponse brute LLM ({len(response)} chars):")
            print(f"   \"{response}\"")
            
            # Simuler le format final
            final_msg = f"[ASK] {response}"
            if len(final_msg) > 500:
                final_msg = final_msg[:497] + "..."
            
            print(f"\n📤 Message Twitch final ({len(final_msg)} chars):")
            print(f"   \"{final_msg}\"")
            print(f"   Marge: {500 - len(final_msg)} chars restants")
            
            results.final_message = final_msg
        else:
            results.log("Réponse LLM", "FAIL", "None retourné")
            
    except Exception as e:
        results.log("Appel LLM", "FAIL", str(e))
        results.errors.append(str(e))
    
    return results


async def main():
    """Point d'entrée principal"""
    live_mode = "--live" in sys.argv
    question = " ".join([arg for arg in sys.argv[1:] if not arg.startswith("--")]) or "correspondance ADS CFT"
    
    print("\n" + "🔬 "*20)
    print("       TEST PIPELINE E2E - COMMANDE !ask")
    print("🔬 "*20)
    
    # Test avec mock (toujours)
    mock_results = await test_pipeline_with_mock_llm(question)
    
    # Test live (si demandé)
    if live_mode:
        live_results = await test_pipeline_live(question)
    
    # Résumé
    print("\n" + "="*70)
    print("📋 RÉSUMÉ")
    print("="*70)
    
    mock_ok = all(s[1] == "OK" for s in mock_results.steps if s[1] != "WARN")
    print(f"Mock LLM: {'✅ PASS' if mock_ok else '❌ FAIL'}")
    
    if live_mode:
        live_ok = all(s[1] == "OK" for s in live_results.steps if s[1] != "WARN")
        print(f"Live LLM: {'✅ PASS' if live_ok else '❌ FAIL'}")
    
    # Exit code
    if mock_ok:
        print("\n🎉 Pipeline validé!")
        sys.exit(0)
    else:
        print("\n💥 Pipeline cassé!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
