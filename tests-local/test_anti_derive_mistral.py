"""
🧪 Test Anti-Dérive Mistral AI - Validation des optimisations

Teste les recommandations de Mistral AI:
1. Prompt anti-dérive avec contraintes strictes
2. max_tokens réduits (100) + repeat_penalty (1.2)
3. Stop tokens agressifs
4. Post-traitement: hard_truncate + remove_derives
5. Validation ≤400 chars sur sujets complexes
"""

import asyncio
import yaml
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from intelligence.synapses.local_synapse import LocalSynapse


def load_config():
    with open('config/config.yaml', 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


async def test_anti_derive():
    print("=" * 70)
    print("🎯 TEST ANTI-DÉRIVE - Validation Optimisations Mistral AI")
    print("=" * 70)
    print("\n📋 OPTIMISATIONS TESTÉES:")
    print("  ✅ Prompt anti-dérive avec contraintes strictes")
    print("  ✅ max_tokens=100 (au lieu de 250)")
    print("  ✅ temperature=0.4 (au lieu de 0.7)")
    print("  ✅ repeat_penalty=1.2")
    print("  ✅ stop_tokens: ['🔚', '\\n', '400.', 'Exemple :', 'En résumé,']")
    print("  ✅ Post-traitement: _remove_derives() + _hard_truncate(400)")
    print("\n" + "=" * 70)
    
    config = load_config()
    synapse = LocalSynapse(config)
    print("✅ LocalSynapse initialized\n")
    
    # Questions qui causaient des dépassements (TEST 5, 11, 12, 15)
    problematic_questions = [
        ("c'est quoi la mécanique quantique", "TEST 5/45 - Dépassait 426 chars"),
        ("qu'est ce que l'entropie", "TEST 11/45 - Dépassait 402 chars"),
        ("explique moi la relativité", "TEST 15/45 - Dépassait 496 chars"),
        ("comment fonctionne un ordinateur quantique", "Question bonus complexe"),
        ("c'est quoi la théorie des cordes", "Question bonus très complexe"),
    ]
    
    results = []
    total_success = 0
    
    for i, (question, description) in enumerate(problematic_questions, 1):
        print(f"\n{'=' * 70}")
        print(f"🧪 TEST {i}/{len(problematic_questions)}: {description}")
        print(f"📝 Question: '{question}'")
        print(f"{'=' * 70}")
        
        # Appel via fire() avec stimulus_class="gen_long"
        response = await synapse.fire(
            stimulus=question,
            context="mention",
            stimulus_class="gen_long",
            correlation_id=f"test_anti_derive_{i}"
        )
        
        if not response:
            print("❌ Pas de réponse générée")
            results.append({
                "question": question,
                "success": False,
                "length": 0,
                "reason": "No response"
            })
            continue
        
        length = len(response)
        phrase_count = response.count('.') + response.count('!') + response.count('?')
        has_marker = "🔚" in response
        
        # Validation stricte
        is_valid = length <= 400 and phrase_count <= 3 and not response.endswith("...")
        
        print(f"\n📏 Longueur: {length} caractères {'✅' if length <= 400 else '❌'}")
        print(f"📊 Phrases: ~{phrase_count} {'✅' if phrase_count <= 3 else '❌'}")
        print(f"🔚 Marqueur fin: {'OUI ✅' if has_marker else 'NON'}")
        print(f"✂️ Tronqué: {'OUI ❌' if response.endswith('...') else 'NON ✅'}")
        
        if length > 400:
            print(f"⚠️ DÉPASSEMENT: +{length - 400} caractères")
        
        print(f"\n📝 Réponse complète:")
        print(f"   {response}")
        
        # Score
        score = 100
        if length > 400:
            score -= (length - 400) // 5  # -1 point par 5 chars de dépassement
        if phrase_count > 3:
            score -= (phrase_count - 3) * 10
        if response.endswith("..."):
            score -= 20
        if not has_marker:
            score -= 10
        
        score = max(0, score)
        
        print(f"\n⭐ Score: {score}/100 {'✅' if score >= 80 else '❌'}")
        
        if is_valid:
            total_success += 1
        
        results.append({
            "question": question,
            "success": is_valid,
            "length": length,
            "phrases": phrase_count,
            "score": score,
            "response": response
        })
        
        await asyncio.sleep(0.5)  # Éviter spam LM Studio
    
    # Analyse finale
    print("\n" + "=" * 70)
    print("📊 ANALYSE FINALE")
    print("=" * 70)
    
    success_rate = (total_success / len(problematic_questions)) * 100
    avg_length = sum(r['length'] for r in results) / len(results)
    max_length = max(r['length'] for r in results)
    
    print(f"\n✅ Taux de réussite: {total_success}/{len(problematic_questions)} ({success_rate:.1f}%)")
    print(f"📏 Longueur moyenne: {avg_length:.0f} caractères")
    print(f"📐 Longueur max: {max_length} caractères {'✅' if max_length <= 400 else '❌'}")
    
    # Détails par question
    print("\n📋 DÉTAILS PAR QUESTION:")
    for i, r in enumerate(results, 1):
        status = "✅" if r['success'] else "❌"
        print(f"{i}. {status} {r['question'][:40]:<40} | {r['length']:>3} chars | Score: {r.get('score', 0)}/100")
    
    # Verdict
    print("\n" + "=" * 70)
    if success_rate >= 80:
        print("🎉 VERDICT: OPTIMISATIONS VALIDÉES ✅")
        print("   Les contraintes Mistral AI fonctionnent parfaitement!")
    elif success_rate >= 60:
        print("⚠️ VERDICT: AMÉLIORATION PARTIELLE")
        print("   Mieux qu'avant mais pas optimal. Ajuster max_tokens?")
    else:
        print("❌ VERDICT: OPTIMISATIONS INSUFFISANTES")
        print("   Mistral 7B dépasse encore les limites.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_anti_derive())
