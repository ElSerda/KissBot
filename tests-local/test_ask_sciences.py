#!/usr/bin/env python3
"""
🧪 TEST CONFIG FINALE !ask - SCIENCES
Teste la config actuelle avec questions scientifiques complexes
(physique, chimie, maths, biologie, astronomie)
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


async def test_ask_sciences():
    """Teste la config !ask avec questions scientifiques variées"""
    
    # Charger config
    config = load_config()
    synapse = LocalSynapse(config=config)
    
    questions = [
        # Physique
        "c'est quoi la gravité",
        "c'est quoi un photon",
        "c'est quoi la relativité",
        "c'est quoi l'énergie cinétique",
        "c'est quoi un atome",
        
        # Chimie
        "c'est quoi une molécule",
        "c'est quoi l'ADN",
        "c'est quoi un ion",
        "c'est quoi la photosynthèse",
        
        # Maths
        "c'est quoi un algorithme",
        "c'est quoi une dérivée",
        "c'est quoi un nombre premier",
        "c'est quoi une matrice",
        
        # Biologie
        "c'est quoi une cellule",
        "c'est quoi l'évolution",
        "c'est quoi un virus",
        
        # Astronomie
        "c'est quoi un trou noir",
        "c'est quoi une galaxie",
        "c'est quoi le Big Bang",
        
        # Technologie complexe
        "c'est quoi la blockchain",
        "c'est quoi le machine learning",
        "c'est quoi un GPU quantique"
    ]
    
    print("🧪 TEST CONFIG FINALE !ask - SCIENCES")
    print("=" * 70)
    print("Config: max_tokens=200, temp=0.3, penalty=1.1, hard_cut=250")
    print("Questions: Physique, Chimie, Maths, Bio, Astro, Tech complexe")
    print("=" * 70)
    print()
    
    results = []
    total_length = 0
    overruns = 0
    overruns_details = []
    
    for i, question in enumerate(questions, 1):
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
                overruns_details.append((question, length))
            
            status = "❌ OVERRUN" if is_overrun else "✅"
            
            results.append({
                "question": question,
                "response": response,
                "length": length,
                "overrun": is_overrun
            })
            
            print(f"{status} [{length:3d} chars] [{i:2d}/23] {question}")
            print(f"   → {response}")
            print()
    
    # Statistiques par catégorie
    print("=" * 70)
    print("📊 STATISTIQUES FINALES")
    print("=" * 70)
    print(f"Tests réussis: {len(results)}/{len(questions)}")
    print(f"Longueur moyenne: {total_length / len(results):.1f} chars")
    print(f"Dépassements >250: {overruns}/{len(results)} ({overruns/len(results)*100:.1f}%)")
    print(f"Longueur min: {min(r['length'] for r in results)} chars")
    print(f"Longueur max: {max(r['length'] for r in results)} chars")
    print()
    
    # Distribution des longueurs
    ranges = {
        "< 100": 0,
        "100-150": 0,
        "150-200": 0,
        "200-250": 0,
        "> 250": 0
    }
    
    for r in results:
        length = r['length']
        if length < 100:
            ranges["< 100"] += 1
        elif length < 150:
            ranges["100-150"] += 1
        elif length < 200:
            ranges["150-200"] += 1
        elif length <= 250:
            ranges["200-250"] += 1
        else:
            ranges["> 250"] += 1
    
    print("📈 DISTRIBUTION DES LONGUEURS:")
    for range_name, count in ranges.items():
        percentage = (count / len(results)) * 100
        bar = "█" * int(percentage / 5)
        print(f"  {range_name:12s}: {count:2d} ({percentage:5.1f}%) {bar}")
    print()
    
    # Détail des dépassements
    if overruns_details:
        print("⚠️  DÉPASSEMENTS DÉTECTÉS:")
        for question, length in overruns_details:
            print(f"  - [{length} chars] {question}")
        print()
    
    # Verdict final
    if overruns == 0:
        print("✅ SUCCÈS TOTAL: Aucun dépassement sur questions scientifiques!")
        print("   La config est robuste même sur sujets complexes 🎯")
    elif overruns <= len(results) * 0.1:  # ≤10%
        print(f"✅ SUCCÈS: {overruns} dépassement(s) seulement ({overruns/len(results)*100:.1f}%)")
        print("   La config gère bien les sujets complexes 👍")
    else:
        print(f"⚠️  ATTENTION: {overruns} dépassement(s) ({overruns/len(results)*100:.1f}%)")
        print("   Ajustement peut-être nécessaire pour sujets complexes")


if __name__ == "__main__":
    asyncio.run(test_ask_sciences())
