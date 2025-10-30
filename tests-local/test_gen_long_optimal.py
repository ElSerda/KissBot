"""
🧪 Test Optimal gen_long: Matrice complète prompt × max_tokens

Teste TOUTES les combinaisons pour trouver l'équilibre parfait:
- Partie 1: Prompts variables (1/2/3 phrases) avec max_tokens FIXE
- Partie 2: Max_tokens variables avec prompts FIXES (1/2/3 phrases)
- Objectif: ≤400 chars, pas de troncature, explications claires
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


async def test_combination(synapse, question, prompt_phrases, max_tokens, test_num, total):
    """Test une combinaison spécifique"""
    print(f"\n{'='*70}")
    print(f"🧪 TEST {test_num}/{total}: {prompt_phrases} phrase(s) | max_tokens={max_tokens}")
    print(f"{'='*70}")
    
    # Construire le prompt adapté
    bot_name = "serda_bot"
    personality = synapse.config.get("bot", {}).get("personality", "")
    
    if prompt_phrases == 1:
        system_prompt = (
            f"Tu es {bot_name}. {personality}\n"
            f"Réponds en 1 PHRASE CLAIRE EN FRANÇAIS, SANS TE PRÉSENTER.\n"
            f"Définition + exemple concret.\n"
            f"Utilise des emojis (💡🔄🎯).\n"
            f"Question: {question}\n"
            f"Réponse:"
        )
    elif prompt_phrases == 2:
        system_prompt = (
            f"Tu es {bot_name}. {personality}\n"
            f"Réponds en 2 PHRASES CLAIRES EN FRANÇAIS, SANS TE PRÉSENTER.\n"
            f"1. Définition simple + exemple\n"
            f"2. Cas d'usage ou approfondissement\n"
            f"Utilise des emojis (💡🔄🎯).\n"
            f"Question: {question}\n"
            f"Réponse:"
        )
    else:  # 3 phrases
        system_prompt = (
            f"Tu es {bot_name}. {personality}\n"
            f"Réponds en 3 PHRASES CLAIRES EN FRANÇAIS, SANS TE PRÉSENTER.\n"
            f"1. Définition simple\n"
            f"2. Exemple concret\n"
            f"3. Cas d'usage pratique\n"
            f"Utilise des emojis (💡🔄🎯).\n"
            f"Question: {question}\n"
            f"Réponse:"
        )
    
    messages = [{"role": "user", "content": system_prompt}]
    
    # Appel direct avec max_tokens custom
    try:
        # Simuler l'appel _transmit_local_signal avec max_tokens custom
        import httpx
        
        payload = {
            "model": synapse.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7,
            "stream": True,
        }
        
        full_response = ""
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
            async with client.stream("POST", synapse.endpoint, json=payload) as response:
                if response.status_code != 200:
                    print(f"❌ Erreur HTTP {response.status_code}")
                    return None
                
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    
                    chunk_data = line[6:]
                    if chunk_data == "[DONE]":
                        break
                    
                    try:
                        import json
                        chunk_json = json.loads(chunk_data)
                        delta = chunk_json.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            full_response += content
                    except:
                        continue
        
        response = full_response.strip()
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return None
    
    if not response:
        print("❌ Pas de réponse générée")
        return None
    
    length = len(response)
    phrase_count = response.count('.') + response.count('!') + response.count('?')
    is_truncated = response.endswith('...') or length >= max_tokens * 3  # Approximation
    
    print(f"📏 Longueur: {length} caractères")
    print(f"📊 Phrases: ~{phrase_count}")
    print(f"✂️ Tronqué: {'OUI ❌' if is_truncated else 'NON ✅'}")
    print(f"📐 Limite 400: {'OK ✅' if length <= 400 else f'DÉPASSÉ ❌ (+{length-400})'}")
    
    # Afficher la réponse complète
    print(f"\n📝 Réponse complète:")
    print(f"   {response}")
    
    # Score de qualité
    score = 0
    if not is_truncated:
        score += 50  # Pas de troncature = crucial
    if length <= 400:
        score += 30  # Respecte la limite
    else:
        score -= (length - 400) // 10  # Pénalité si dépassement
    if phrase_count == prompt_phrases:
        score += 15  # Respecte le nombre de phrases demandé
    elif abs(phrase_count - prompt_phrases) == 1:
        score += 10  # Proche du nombre demandé
    if 150 <= length <= 400:
        score += 5  # Bon équilibre longueur
    
    score = max(0, min(100, score))  # Clamp 0-100
    
    print(f"\n⭐ Score qualité: {score}/100")
    
    await asyncio.sleep(0.5)  # Éviter spam LM Studio
    
    return {
        "prompt_phrases": prompt_phrases,
        "max_tokens": max_tokens,
        "length": length,
        "phrases": phrase_count,
        "truncated": is_truncated,
        "score": score,
        "response": response
    }


async def run_full_matrix_test():
    print("=" * 70)
    print("🎯 TEST MATRICE COMPLÈTE: Prompt × max_tokens")
    print("Objectifs:")
    print("  - ≤400 caractères (Twitch confortable)")
    print("  - Pas de troncature")
    print("  - Nombre de phrases respecté")
    print("=" * 70)
    
    config = load_config()
    synapse = LocalSynapse(config)
    print("✅ LocalSynapse initialized\n")
    
    # Questions variées pour tester robustesse
    questions = [
        "explique moi la causalité",
        "c'est quoi la mécanique quantique",
        "comment fonctionne la gravité",
        "qu'est ce que l'entropie",
        "explique moi la relativité",
    ]
    
    print(f"📢 Questions test ({len(questions)} variantes):")
    for q in questions:
        print(f"   • {q}")
    print()
    
    results = []
    
    # ============================================
    # PARTIE 1: Prompts variables, max_tokens FIXE
    # ============================================
    print("\n" + "🔸" * 35)
    print("📊 PARTIE 1: PROMPTS VARIABLES (max_tokens=250 fixe)")
    print("🔸" * 35)
    
    fixed_max_tokens = 250
    test_num = 0
    total_tests = len(questions) * 9  # 5 questions × 9 configs
    
    for question in questions:
        print(f"\n{'─' * 70}")
        print(f"📝 Question: '{question}'")
        print(f"{'─' * 70}")
        
        for phrases in [1, 2, 3]:
            test_num += 1
            result = await test_combination(synapse, question, phrases, fixed_max_tokens, test_num, total_tests)
            if result:
                result['question'] = question
                results.append(result)
    
    # ============================================
    # PARTIE 2: max_tokens variables, prompts FIXES
    # ============================================
    print("\n" + "🔹" * 35)
    print("📊 PARTIE 2: MAX_TOKENS VARIABLES")
    print("🔹" * 35)
    
    # Test 2.1: 1 phrase, max_tokens variables
    for question in questions:
        print(f"\n{'─' * 70}")
        print(f"📝 Question: '{question}'")
        print(f"{'─' * 70}")
        print("\n--- 1 PHRASE, max_tokens variables ---")
        
        for tokens in [150, 200, 250]:
            test_num += 1
            result = await test_combination(synapse, question, 1, tokens, test_num, total_tests)
            if result:
                result['question'] = question
                results.append(result)
    
    # Test 2.2: 2 phrases, max_tokens variables
    for question in questions:
        print(f"\n{'─' * 70}")
        print(f"📝 Question: '{question}'")
        print(f"{'─' * 70}")
        print("\n--- 2 PHRASES, max_tokens variables ---")
        
        for tokens in [200, 250, 300]:
            test_num += 1
            result = await test_combination(synapse, question, 2, tokens, test_num, total_tests)
            if result:
                result['question'] = question
                results.append(result)
    
    # Analyse finale
    print("\n" + "=" * 70)
    print("📊 ANALYSE FINALE - TOUS LES RÉSULTATS")
    print("=" * 70)
    
    if results:
        # Statistiques globales
        total_tests = len(results)
        avg_score = sum(r['score'] for r in results) / total_tests
        avg_length = sum(r['length'] for r in results) / total_tests
        truncated_count = sum(1 for r in results if r['truncated'])
        over_400_count = sum(1 for r in results if r['length'] > 400)
        
        print(f"\n📈 STATISTIQUES GLOBALES ({total_tests} tests):")
        print(f"   • Score moyen: {avg_score:.1f}/100")
        print(f"   • Longueur moyenne: {avg_length:.0f} caractères")
        print(f"   • Tronqués: {truncated_count}/{total_tests} ({truncated_count/total_tests*100:.1f}%)")
        print(f"   • >400 chars: {over_400_count}/{total_tests} ({over_400_count/total_tests*100:.1f}%)")
        
        # Trier par score
        results.sort(key=lambda x: x['score'], reverse=True)
        
        print("\n🏆 TOP 5 CONFIGURATIONS TOUTES QUESTIONS CONFONDUES:")
        for i, r in enumerate(results[:5], 1):
            print(f"\n{i}. Score: {r['score']}/100")
            print(f"   - Question: '{r['question']}'")
            print(f"   - Prompt: {r['prompt_phrases']} phrase(s)")
            print(f"   - max_tokens: {r['max_tokens']}")
            print(f"   - Longueur: {r['length']} chars")
            print(f"   - Phrases réelles: {r['phrases']}")
            print(f"   - Tronqué: {'OUI ❌' if r['truncated'] else 'NON ✅'}")
        
        # Analyse par configuration (agrégation)
        print("\n📊 PERFORMANCE PAR CONFIGURATION:")
        config_stats = {}
        for r in results:
            key = (r['prompt_phrases'], r['max_tokens'])
            if key not in config_stats:
                config_stats[key] = []
            config_stats[key].append(r['score'])
        
        config_avg = [(k, sum(v)/len(v), len(v)) for k, v in config_stats.items()]
        config_avg.sort(key=lambda x: x[1], reverse=True)
        
        print("\n🎯 TOP 3 CONFIGS (moyenne sur toutes questions):")
        for i, (config, avg, count) in enumerate(config_avg[:3], 1):
            phrases, tokens = config
            print(f"{i}. {phrases} phrase(s) + max_tokens={tokens}")
            print(f"   → Score moyen: {avg:.1f}/100 (sur {count} tests)")
        
        best_config = config_avg[0][0]
        print(f"\n💡 CONFIGURATION OPTIMALE RECOMMANDÉE:")
        print(f"   Prompt: {best_config[0]} phrase(s) claires")
        print(f"   max_tokens: {best_config[1]}")
        print(f"   Robustesse: Testé sur {len(questions)} questions variées")
        print(f"   Score moyen: {config_avg[0][1]:.1f}/100")
        
        # Exemple de meilleure réponse
        best_result = results[0]
        print(f"\n📝 MEILLEURE RÉPONSE (score {best_result['score']}/100):")
        print(f"   Question: '{best_result['question']}'")
        preview = best_result['response'][:300] + "..." if len(best_result['response']) > 300 else best_result['response']
        print(f"   Réponse: {preview}")
    
    print("\n" + "=" * 70)
    print("✅ TEST MATRICE TERMINÉ")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_full_matrix_test())

