#!/usr/bin/env python3
"""
🔬 TEST COMPARATIF: !ask gen_short vs gen_long
Compare les 2 stimulus_class pour context="ask" avec les mêmes questions
pour voir le delta de longueur et qualité
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


async def test_ask_comparison():
    """Compare gen_short vs gen_long pour les mêmes questions"""
    
    # Charger config
    config = load_config()
    synapse = LocalSynapse(config=config)
    
    questions = [
        # Tech basique
        "c'est quoi Python",
        "c'est quoi un GPU",
        "c'est quoi Twitch",
        
        # Sciences
        "c'est quoi la gravité",
        "c'est quoi un photon",
        "c'est quoi la relativité",
        "c'est quoi l'ADN",
        "c'est quoi un trou noir",
        
        # Tech complexe
        "c'est quoi la blockchain",
        "c'est quoi le machine learning"
    ]
    
    print("🔬 TEST COMPARATIF: !ask gen_short vs gen_long")
    print("=" * 90)
    print("Config ask (ligne 313-329 local_synapse.py):")
    print("  - max_tokens=200, temp=0.3, penalty=1.1, hard_cut=250")
    print()
    print("Config gen_long mention (ligne 330-338 local_synapse.py):")
    print("  - max_tokens=100, temp=0.4, penalty=1.2, hard_cut=400, anti-dérive")
    print("=" * 90)
    print()
    
    results_short = []
    results_long = []
    
    for i, question in enumerate(questions, 1):
        print(f"📊 Question {i}/{len(questions)}: {question}")
        print("-" * 90)
        
        # Test avec gen_short
        response_short = await synapse.fire(
            stimulus=question,
            context="ask",
            stimulus_class="gen_short"
        )
        
        # Test avec gen_long (PRODUCTION)
        response_long = await synapse.fire(
            stimulus=question,
            context="ask",
            stimulus_class="gen_long"
        )
        
        if response_short and response_long:
            len_short = len(response_short)
            len_long = len(response_long)
            delta = len_long - len_short
            delta_pct = (delta / len_short * 100) if len_short > 0 else 0
            
            results_short.append({
                "question": question,
                "response": response_short,
                "length": len_short
            })
            
            results_long.append({
                "question": question,
                "response": response_long,
                "length": len_long
            })
            
            # Symboles delta
            if delta > 0:
                delta_symbol = "📈 +"
                color = "🟢" if delta <= 100 else "🟡" if delta <= 200 else "🔴"
            elif delta < 0:
                delta_symbol = "📉 "
                color = "🔵"
            else:
                delta_symbol = "➡️  "
                color = "⚪"
            
            print(f"  gen_short: [{len_short:3d} chars] {response_short[:80]}...")
            print(f"  gen_long:  [{len_long:3d} chars] {response_long[:80]}...")
            print(f"  {color} Delta: {delta_symbol}{delta:+4d} chars ({delta_pct:+.1f}%)")
            print()
    
    # Statistiques globales
    print("=" * 90)
    print("📊 STATISTIQUES COMPARATIVES")
    print("=" * 90)
    
    if results_short and results_long:
        avg_short = sum(r['length'] for r in results_short) / len(results_short)
        avg_long = sum(r['length'] for r in results_long) / len(results_long)
        avg_delta = avg_long - avg_short
        avg_delta_pct = (avg_delta / avg_short * 100) if avg_short > 0 else 0
        
        min_short = min(r['length'] for r in results_short)
        max_short = max(r['length'] for r in results_short)
        
        min_long = min(r['length'] for r in results_long)
        max_long = max(r['length'] for r in results_long)
        
        overrun_short = sum(1 for r in results_short if r['length'] > 250)
        overrun_long = sum(1 for r in results_long if r['length'] > 400)
        
        print(f"📏 LONGUEURS MOYENNES:")
        print(f"  gen_short: {avg_short:.1f} chars (range: {min_short}-{max_short})")
        print(f"  gen_long:  {avg_long:.1f} chars (range: {min_long}-{max_long})")
        print(f"  Delta moyen: {avg_delta:+.1f} chars ({avg_delta_pct:+.1f}%)")
        print()
        
        print(f"🎯 DÉPASSEMENTS:")
        print(f"  gen_short >250: {overrun_short}/{len(results_short)} ({overrun_short/len(results_short)*100:.1f}%)")
        print(f"  gen_long >400:  {overrun_long}/{len(results_long)} ({overrun_long/len(results_long)*100:.1f}%)")
        print()
        
        # Distribution des deltas
        deltas = [results_long[i]['length'] - results_short[i]['length'] 
                  for i in range(len(results_short))]
        
        delta_ranges = {
            "< 0 (plus court)": sum(1 for d in deltas if d < 0),
            "0-50 (+léger)": sum(1 for d in deltas if 0 <= d <= 50),
            "51-100 (+modéré)": sum(1 for d in deltas if 50 < d <= 100),
            "101-200 (+important)": sum(1 for d in deltas if 100 < d <= 200),
            "> 200 (+massif)": sum(1 for d in deltas if d > 200)
        }
        
        print("📈 DISTRIBUTION DES DELTAS:")
        for range_name, count in delta_ranges.items():
            percentage = (count / len(deltas)) * 100 if deltas else 0
            bar = "█" * int(percentage / 5)
            print(f"  {range_name:20s}: {count:2d} ({percentage:5.1f}%) {bar}")
        print()
        
        # Recommandation
        print("=" * 90)
        print("💡 RECOMMANDATIONS:")
        print("=" * 90)
        
        if avg_delta <= 50:
            print("✅ gen_short et gen_long similaires : OK pour les deux")
        elif avg_delta <= 150:
            print("⚠️  gen_long plus verbeux (+modéré) : vérifier si détails utiles")
        else:
            print("🔴 gen_long beaucoup plus long : risque de sur-explication")
        
        print()
        
        if overrun_long > 0:
            print(f"⚠️  {overrun_long} dépassement(s) >400 chars avec gen_long")
            print("   → Config gen_long peut nécessiter ajustement pour !ask")
        else:
            print("✅ Aucun dépassement avec gen_long : config robuste!")
        
        print()
        
        # Verdict final sur stimulus_class pour !ask
        print("🎯 VERDICT FINAL pour context='ask':")
        if overrun_short == 0 and avg_short < 200:
            print(f"  🥇 RECOMMANDÉ: gen_short ({avg_short:.1f} chars moy, 0% dépassements)")
            print("     → Plus concis, idéal pour questions factuelles rapides")
        elif overrun_long == 0 and avg_delta <= 100:
            print(f"  🥈 ACCEPTABLE: gen_long ({avg_long:.1f} chars moy, 0% dépassements)")
            print(f"     → Plus détaillé (+{avg_delta:.1f} chars), bon pour explications")
        
        print()
        print("📝 NOTE: Production actuelle force gen_long (unified_quantum_classifier.py:230)")
        print("   Si gen_short meilleur, modifier le classifier pour !ask")


if __name__ == "__main__":
    asyncio.run(test_ask_comparison())
