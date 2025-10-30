#!/usr/bin/env python3
"""
🎯 TEST CONFIG FINALE !ask
Teste la config actuelle dans local_synapse.py (max_tokens=200 + hard_cut=250)
"""

import sys
import asyncio
import yaml
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from intelligence.synapses.local_synapse import LocalSynapse


def load_config():
    """Charge la configuration depuis config/config.yaml"""
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


async def test_ask_config_finale():
    """Teste la config !ask actuelle avec questions variées"""
    
    # Charger config
    config = load_config()
    synapse = LocalSynapse(config=config)
    
    questions = [
        "c'est quoi Python",
        "c'est quoi un GPU", 
        "c'est quoi Twitch",
        "c'est quoi Linux",
        "c'est quoi l'IA",
        "c'est quoi un serveur",
        "c'est quoi JavaScript",
        "c'est quoi la RAM"
    ]
    
    print("🎯 TEST CONFIG FINALE !ask")
    print("=" * 70)
    print("Config: max_tokens=200, temp=0.3, penalty=1.1, hard_cut=250")
    print("=" * 70)
    print()
    
    results = []
    total_length = 0
    overruns = 0
    
    for question in questions:
        response = await synapse.fire(
            stimulus=question,
            context="ask",
            stimulus_class="gen_short"
        )
        
        if response:
            length = len(response)
            total_length += length
            
            # Vérifier dépassement
            is_overrun = length > 250
            if is_overrun:
                overruns += 1
            
            status = "❌ OVERRUN" if is_overrun else "✅"
            
            results.append({
                "question": question,
                "response": response,
                "length": length,
                "overrun": is_overrun
            })
            
            print(f"{status} [{length:3d} chars] {question}")
            print(f"   → {response}")
            print()
    
    # Statistiques
    print("=" * 70)
    print("📊 STATISTIQUES FINALES")
    print("=" * 70)
    print(f"Tests réussis: {len(results)}/{len(questions)}")
    print(f"Longueur moyenne: {total_length / len(results):.1f} chars")
    print(f"Dépassements >250: {overruns}/{len(results)} ({overruns/len(results)*100:.1f}%)")
    print(f"Longueur min: {min(r['length'] for r in results)} chars")
    print(f"Longueur max: {max(r['length'] for r in results)} chars")
    print()
    
    if overruns == 0:
        print("✅ SUCCÈS: Aucun dépassement, config optimale!")
    else:
        print(f"⚠️  ATTENTION: {overruns} dépassement(s) détecté(s)")


if __name__ == "__main__":
    asyncio.run(test_ask_config_finale())
