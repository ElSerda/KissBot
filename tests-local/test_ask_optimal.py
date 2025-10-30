"""
🧪 Test Optimal !ask - Matrice complète

Teste la commande !ask (questions factuelles courtes):
- Questions: "c'est quoi X?", définitions rapides
- Combinaisons: max_tokens (100, 150, 200) × temperature (0.3, 0.5, 0.7)
- Objectif: ≤150 chars, réponses factuelles concises
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


async def test_combination(synapse, question, max_tokens, temperature, repeat_penalty, test_num, total):
    """Test une combinaison spécifique"""
    print(f"\n{'='*70}")
    print(f"🧪 TEST {test_num}/{total}: max_tokens={max_tokens} | temp={temperature} | penalty={repeat_penalty}")
    print(f"{'='*70}")
    
    # Utiliser le fire() avec context="ask"
    response = await synapse.fire(
        stimulus=question,
        context="ask",
        stimulus_class="gen_short",  # ask est toujours gen_short
        correlation_id=f"test_ask_{test_num}"
    )
    
    if not response:
        print("❌ Pas de réponse générée")
        return None
    
    length = len(response)
    phrase_count = response.count('.') + response.count('!') + response.count('?')
    has_emoji = any(char in response for char in "😎🔥💻🎮👍⚡💡🌐📚🔬")
    
    # Validation stricte pour !ask (factuel = concis)
    is_valid = length <= 150 and phrase_count <= 1
    
    print(f"📏 Longueur: {length} caractères {'✅' if length <= 150 else '❌'}")
    print(f"📊 Phrases: ~{phrase_count} {'✅' if phrase_count <= 1 else '⚠️'}")
    print(f"😎 Emojis: {'OUI' if has_emoji else 'NON (OK pour factuel)'}")
    
    if length > 150:
        print(f"⚠️ DÉPASSEMENT: +{length - 150} caractères")
    
    print(f"\n📝 Réponse complète:")
    print(f"   {response}")
    
    # Score de qualité (critères !ask = factuel)
    score = 100
    if length > 150:
        score -= (length - 150) // 3  # Pénalité plus forte pour !ask
    if phrase_count > 1:
        score -= phrase_count * 5  # Léger malus si plusieurs phrases (mais toléré)
    if length < 20:
        score -= 20  # Trop court = pas assez informatif
    if 40 <= length <= 120:
        score += 10  # Sweet spot pour définitions
    
    score = max(0, score)
    
    print(f"\n⭐ Score: {score}/100 {'✅' if score >= 80 else '❌'}")
    
    await asyncio.sleep(0.5)
    
    return {
        "max_tokens": max_tokens,
        "temperature": temperature,
        "repeat_penalty": repeat_penalty,
        "length": length,
        "phrases": phrase_count,
        "has_emoji": has_emoji,
        "score": score,
        "response": response,
        "valid": is_valid
    }


async def run_full_matrix_test():
    print("=" * 70)
    print("🎯 TEST MATRICE: !ask (questions factuelles)")
    print("=" * 70)
    print("\n📋 OBJECTIFS:")
    print("  - ≤150 caractères (concis)")
    print("  - 1 phrase MAX (définition claire)")
    print("  - Factuel, sans fioritures")
    print("  - Informatif mais bref")
    print("\n" + "=" * 70)
    
    config = load_config()
    synapse = LocalSynapse(config)
    print("✅ LocalSynapse initialized\n")
    
    # Questions typiques !ask (factuelles)
    questions = [
        "c'est quoi Python",
        "c'est quoi un GPU",
        "c'est quoi Twitch",
        "c'est quoi Linux",
        "c'est quoi l'IA",
    ]
    
    print(f"📢 Questions test ({len(questions)} variantes):")
    for q in questions:
        print(f"   • {q}")
    print()
    
    # Combinaisons à tester
    # Config actuelle: max_tokens=150, temperature=0.3, repeat_penalty=1.1
    configs = [
        # Config actuelle (baseline)
        {"max_tokens": 150, "temperature": 0.3, "repeat_penalty": 1.1},
        
        # Variations max_tokens
        {"max_tokens": 100, "temperature": 0.3, "repeat_penalty": 1.1},
        {"max_tokens": 200, "temperature": 0.3, "repeat_penalty": 1.1},
        
        # Variations temperature (factuel = bas)
        {"max_tokens": 150, "temperature": 0.2, "repeat_penalty": 1.1},
        {"max_tokens": 150, "temperature": 0.5, "repeat_penalty": 1.1},
        {"max_tokens": 150, "temperature": 0.7, "repeat_penalty": 1.1},
        
        # Variations repeat_penalty
        {"max_tokens": 150, "temperature": 0.3, "repeat_penalty": 1.0},
        {"max_tokens": 150, "temperature": 0.3, "repeat_penalty": 1.2},
        
        # Combos optimisés pour factuel
        {"max_tokens": 120, "temperature": 0.2, "repeat_penalty": 1.1},
        {"max_tokens": 100, "temperature": 0.4, "repeat_penalty": 1.15},
    ]
    
    results = []
    test_num = 0
    total_tests = len(questions) * len(configs)
    
    # Tester chaque question avec chaque config
    for question in questions:
        print(f"\n{'─' * 70}")
        print(f"📝 Question: '{question}'")
        print(f"{'─' * 70}")
        
        for cfg in configs:
            test_num += 1
            result = await test_combination(
                synapse, question, 
                cfg["max_tokens"], 
                cfg["temperature"], 
                cfg["repeat_penalty"],
                test_num, 
                total_tests
            )
            
            if result:
                result['question'] = question
                results.append(result)
    
    # Analyse finale
    print("\n" + "=" * 70)
    print("📊 ANALYSE FINALE")
    print("=" * 70)
    
    if results:
        total_tests = len(results)
        avg_score = sum(r['score'] for r in results) / total_tests
        avg_length = sum(r['length'] for r in results) / total_tests
        over_150_count = sum(1 for r in results if r['length'] > 150)
        single_phrase_count = sum(1 for r in results if r['phrases'] <= 1)
        
        print(f"\n📈 STATISTIQUES GLOBALES ({total_tests} tests):")
        print(f"   • Score moyen: {avg_score:.1f}/100")
        print(f"   • Longueur moyenne: {avg_length:.0f} caractères")
        print(f"   • >150 chars: {over_150_count}/{total_tests} ({over_150_count/total_tests*100:.1f}%)")
        print(f"   • 1 phrase: {single_phrase_count}/{total_tests} ({single_phrase_count/total_tests*100:.1f}%)")
        
        # Trier par score
        results.sort(key=lambda x: x['score'], reverse=True)
        
        print("\n🏆 TOP 5 CONFIGURATIONS:")
        for i, r in enumerate(results[:5], 1):
            print(f"\n{i}. Score: {r['score']}/100")
            print(f"   - Question: '{r['question']}'")
            print(f"   - max_tokens: {r['max_tokens']}")
            print(f"   - temperature: {r['temperature']}")
            print(f"   - repeat_penalty: {r['repeat_penalty']}")
            print(f"   - Longueur: {r['length']} chars")
            print(f"   - Réponse: {r['response'][:80]}{'...' if len(r['response']) > 80 else ''}")
        
        # Analyse par configuration (agrégation)
        print("\n📊 PERFORMANCE PAR CONFIGURATION:")
        config_stats = {}
        for r in results:
            key = (r['max_tokens'], r['temperature'], r['repeat_penalty'])
            if key not in config_stats:
                config_stats[key] = []
            config_stats[key].append(r['score'])
        
        config_avg = [(k, sum(v)/len(v), len(v)) for k, v in config_stats.items()]
        config_avg.sort(key=lambda x: x[1], reverse=True)
        
        print("\n🎯 TOP 3 CONFIGS (moyenne sur toutes questions):")
        for i, (config, avg, count) in enumerate(config_avg[:3], 1):
            tokens, temp, penalty = config
            print(f"{i}. max_tokens={tokens} | temp={temp} | penalty={penalty}")
            print(f"   → Score moyen: {avg:.1f}/100 (sur {count} tests)")
        
        best_config = config_avg[0][0]
        print(f"\n💡 CONFIGURATION OPTIMALE RECOMMANDÉE:")
        print(f"   max_tokens: {best_config[0]}")
        print(f"   temperature: {best_config[1]}")
        print(f"   repeat_penalty: {best_config[2]}")
        print(f"   Score moyen: {config_avg[0][1]:.1f}/100")
        
        # Config actuelle vs meilleure
        current_config = (150, 0.3, 1.1)
        if current_config in config_stats:
            current_avg = sum(config_stats[current_config]) / len(config_stats[current_config])
            best_avg = config_avg[0][1]
            print(f"\n📉 COMPARAISON:")
            print(f"   Config actuelle (150, 0.3, 1.1): {current_avg:.1f}/100")
            print(f"   Meilleure config: {best_avg:.1f}/100")
            improvement = best_avg - current_avg
            if improvement > 5:
                print(f"   ✅ Amélioration: +{improvement:.1f} points")
            elif improvement < -5:
                print(f"   ⚠️ Régression: {improvement:.1f} points")
            else:
                print(f"   ➡️ Équivalent ({improvement:+.1f} points)")
    
    print("\n" + "=" * 70)
    print("✅ TEST TERMINÉ")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_full_matrix_test())
