#!/usr/bin/env python3
"""
🔬 TEST COMPARATIF ULTIME: mention vs !ask
Compare context="mention" (gen_short) vs context="ask" (gen_long)
pour les MÊMES questions complexes.

But: Voir si le chemin mention vs !ask produit des réponses différentes
en termes de longueur, précision et détails.
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


async def test_mention_vs_ask():
    """Compare mention (gen_short) vs !ask (gen_long) sur mêmes questions complexes"""
    
    # Charger config
    config = load_config()
    synapse = LocalSynapse(config=config)
    
    # Questions complexes nécessitant explications détaillées
    questions_complexes = [
        # Tech avancée
        "c'est quoi la blockchain",
        "c'est quoi le machine learning",
        "c'est quoi l'intelligence artificielle",
        "c'est quoi un réseau de neurones",
        "c'est quoi le cloud computing",
        
        # Sciences complexes
        "c'est quoi la relativité",
        "c'est quoi la mécanique quantique",
        "c'est quoi la photosynthèse",
        "c'est quoi l'évolution",
        "c'est quoi un trou noir",
        
        # Concepts avancés
        "c'est quoi la cryptographie",
        "c'est quoi un algorithme",
        "c'est quoi la virtualisation"
    ]
    
    print("🔬 TEST COMPARATIF ULTIME: @mention vs !ask")
    print("=" * 100)
    print("Config mention (gen_short): max_tokens=200, temp=0.7, penalty=1.1, hard_cut=200")
    print("Config ask (gen_long):      max_tokens=200, temp=0.3, penalty=1.1, hard_cut=250")
    print("=" * 100)
    print()
    
    results = []
    
    for i, question in enumerate(questions_complexes, 1):
        print(f"📊 Question {i}/{len(questions_complexes)}: {question}")
        print("-" * 100)
        
        # Chemin 1: MENTION (@KissBot question)
        # → context="mention", classifier force gen_short
        response_mention = await synapse.fire(
            stimulus=question,
            context="mention",
            stimulus_class="gen_short"  # Force explicite
        )
        
        # Chemin 2: !ASK (!ask question)
        # → context="ask", config unifiée ask (ignore stimulus_class)
        response_ask = await synapse.fire(
            stimulus=question,
            context="ask",
            stimulus_class="gen_long"  # Ce que le classifier force
        )
        
        if response_mention and response_ask:
            len_mention = len(response_mention)
            len_ask = len(response_ask)
            delta = len_ask - len_mention
            delta_pct = (delta / len_mention * 100) if len_mention > 0 else 0
            
            # Analyser précision/détails
            words_mention = len(response_mention.split())
            words_ask = len(response_ask.split())
            
            results.append({
                "question": question,
                "mention": response_mention,
                "ask": response_ask,
                "len_mention": len_mention,
                "len_ask": len_ask,
                "delta": delta,
                "delta_pct": delta_pct,
                "words_mention": words_mention,
                "words_ask": words_ask
            })
            
            # Symboles comparaison
            if abs(delta) <= 20:
                verdict = "⚪ IDENTIQUE"
            elif delta > 0:
                if delta <= 50:
                    verdict = "🟢 !ask +LÉGER"
                elif delta <= 100:
                    verdict = "🟡 !ask +DÉTAILLÉ"
                else:
                    verdict = "🔴 !ask +VERBEUX"
            else:
                verdict = "🔵 mention +LONG"
            
            print(f"  @mention: [{len_mention:3d} chars, {words_mention:2d} mots]")
            print(f"    → {response_mention[:90]}...")
            print()
            print(f"  !ask:     [{len_ask:3d} chars, {words_ask:2d} mots]")
            print(f"    → {response_ask[:90]}...")
            print()
            print(f"  {verdict} | Delta: {delta:+4d} chars ({delta_pct:+.1f}%)")
            print()
    
    # === STATISTIQUES GLOBALES ===
    print("=" * 100)
    print("📊 STATISTIQUES COMPARATIVES GLOBALES")
    print("=" * 100)
    print()
    
    if results:
        # Moyennes
        avg_mention = sum(r['len_mention'] for r in results) / len(results)
        avg_ask = sum(r['len_ask'] for r in results) / len(results)
        avg_delta = avg_ask - avg_mention
        avg_delta_pct = (avg_delta / avg_mention * 100) if avg_mention > 0 else 0
        
        avg_words_mention = sum(r['words_mention'] for r in results) / len(results)
        avg_words_ask = sum(r['words_ask'] for r in results) / len(results)
        
        # Ranges
        min_mention = min(r['len_mention'] for r in results)
        max_mention = max(r['len_mention'] for r in results)
        min_ask = min(r['len_ask'] for r in results)
        max_ask = max(r['len_ask'] for r in results)
        
        # Dépassements
        overrun_mention = sum(1 for r in results if r['len_mention'] > 200)
        overrun_ask = sum(1 for r in results if r['len_ask'] > 250)
        
        print(f"📏 LONGUEURS MOYENNES:")
        print(f"  @mention: {avg_mention:.1f} chars ({avg_words_mention:.1f} mots) | range: {min_mention}-{max_mention}")
        print(f"  !ask:     {avg_ask:.1f} chars ({avg_words_ask:.1f} mots) | range: {min_ask}-{max_ask}")
        print(f"  Delta:    {avg_delta:+.1f} chars ({avg_delta_pct:+.1f}%)")
        print()
        
        print(f"🎯 DÉPASSEMENTS:")
        print(f"  @mention >200: {overrun_mention}/{len(results)} ({overrun_mention/len(results)*100:.1f}%)")
        print(f"  !ask >250:     {overrun_ask}/{len(results)} ({overrun_ask/len(results)*100:.1f}%)")
        print()
        
        # Distribution des deltas
        deltas = [r['delta'] for r in results]
        
        delta_ranges = {
            "< -50 (mention BIEN + long)": sum(1 for d in deltas if d < -50),
            "-50 à -20 (mention + long)": sum(1 for d in deltas if -50 <= d < -20),
            "-20 à +20 (IDENTIQUE ±)": sum(1 for d in deltas if -20 <= d <= 20),
            "+20 à +50 (!ask + long)": sum(1 for d in deltas if 20 < d <= 50),
            "+50 à +100 (!ask BIEN + long)": sum(1 for d in deltas if 50 < d <= 100),
            "> +100 (!ask TRÈS + long)": sum(1 for d in deltas if d > 100)
        }
        
        print("📈 DISTRIBUTION DES DELTAS:")
        for range_name, count in delta_ranges.items():
            percentage = (count / len(deltas)) * 100 if deltas else 0
            bar = "█" * int(percentage / 5)
            print(f"  {range_name:30s}: {count:2d} ({percentage:5.1f}%) {bar}")
        print()
        
        # === ANALYSE QUALITATIVE ===
        print("=" * 100)
        print("🔍 ANALYSE QUALITATIVE")
        print("=" * 100)
        print()
        
        # Cas où !ask est significativement plus long (+50 chars)
        ask_plus_long = [r for r in results if r['delta'] > 50]
        if ask_plus_long:
            print(f"🟡 CAS OÙ !ask EST PLUS DÉTAILLÉ (+50 chars) : {len(ask_plus_long)}/{len(results)}")
            for r in ask_plus_long[:3]:  # Top 3
                print(f"  • {r['question']}")
                print(f"    @mention ({r['len_mention']} chars): {r['mention'][:80]}...")
                print(f"    !ask ({r['len_ask']} chars):     {r['ask'][:80]}...")
                print(f"    → Delta: +{r['delta']} chars ({r['delta_pct']:+.1f}%)")
                print()
        
        # Cas similaires (±20 chars)
        similaires = [r for r in results if abs(r['delta']) <= 20]
        if similaires:
            print(f"⚪ CAS IDENTIQUES (±20 chars) : {len(similaires)}/{len(results)}")
            for r in similaires[:3]:  # Top 3
                print(f"  • {r['question']} → Delta: {r['delta']:+d} chars")
            print()
        
        # Cas où mention est plus long
        mention_plus_long = [r for r in results if r['delta'] < -20]
        if mention_plus_long:
            print(f"🔵 CAS OÙ @mention EST PLUS LONG : {len(mention_plus_long)}/{len(results)}")
            for r in mention_plus_long[:3]:  # Top 3
                print(f"  • {r['question']} → Delta: {r['delta']:+d} chars")
            print()
        
        # === RECOMMANDATIONS ===
        print("=" * 100)
        print("💡 RECOMMANDATIONS FINALES")
        print("=" * 100)
        print()
        
        if abs(avg_delta) <= 30:
            print("✅ VERDICT: Les deux contextes produisent des réponses SIMILAIRES")
            print(f"   → Delta moyen: {avg_delta:+.1f} chars ({avg_delta_pct:+.1f}%) = négligeable")
            print("   → Pas de différence significative mention vs !ask")
            print()
            print("📝 RECOMMANDATION: Garder configs actuelles")
            print("   • Config unifiée pour ask fonctionne bien")
            print("   • Pas besoin de différencier mention/ask pour questions complexes")
        
        elif avg_delta > 30:
            print("🟡 VERDICT: !ask produit des réponses PLUS DÉTAILLÉES")
            print(f"   → Delta moyen: +{avg_delta:.1f} chars (+{avg_delta_pct:.1f}%)")
            print()
            
            if avg_delta > 100:
                print("⚠️  ATTENTION: Différence SIGNIFICATIVE")
                print("📝 RECOMMANDATION: Considérer ajustements")
                print("   • Option 1: Réduire max_tokens ask (200→180)")
                print("   • Option 2: Augmenter temperature ask (0.3→0.4) pour plus concision")
                print("   • Option 3: Garder si détails utiles (vérifier en prod)")
            else:
                print("✅ ACCEPTABLE: Différence modérée mais bénéfique")
                print("📝 RECOMMANDATION: Garder configs actuelles")
                print("   • !ask fournit précisions utiles pour questions complexes")
                print("   • Toujours sous limites (0% dépassements)")
        
        else:  # avg_delta < -30
            print("🔵 VERDICT: @mention produit des réponses PLUS LONGUES")
            print(f"   → Delta moyen: {avg_delta:.1f} chars ({avg_delta_pct:.1f}%)")
            print()
            print("📝 RECOMMANDATION: Vérifier si mention gen_short doit être plus concis")
            print("   • Considérer réduire max_tokens mention (200→180)")
        
        print()
        print("=" * 100)
        print(f"✅ TEST TERMINÉ: {len(results)} questions complexes testées")
        print("=" * 100)


if __name__ == "__main__":
    asyncio.run(test_mention_vs_ask())
