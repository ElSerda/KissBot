"""
Intelligence Core - Logique métier pure (facile à tester)
Séparation business logic / framework TwitchIO
"""

from rapidfuzz import fuzz


def find_game_in_cache(user_query: str, game_cache, threshold: float = 80.0) -> dict | None:
    """
    Trouve un jeu dans le cache en utilisant fuzzy matching.

    Args:
        user_query: Texte de l'utilisateur (ex: "brottato", "parle moi de brotato")
        game_cache: Instance GameCache
        threshold: Seuil de similarité (80% par défaut)

    Returns:
        dict: Données du jeu si trouvé, None sinon
    """
    if not game_cache or not user_query:
        return None

    user_query_lower = user_query.lower()
    best_match = None
    best_score = 0.0

    # Adapté pour GameCache quantum
    for cache_key, quantum_state in game_cache.quantum_states.items():
        superpositions = quantum_state.get("superpositions", [])
        
        # Prendre la première superposition (meilleur score)
        if not superpositions:
            continue
            
        game_data = superpositions[0].get("game", {})
        game_name = game_data.get("name", "")

        if not game_name:
            continue

        # Utiliser token_set_ratio pour gérer ordres de mots et fautes
        # Ex: "brottato game" match "Brotato" avec score élevé
        score = float(fuzz.token_set_ratio(game_name.lower(), user_query_lower))

        if score >= threshold and score > best_score:
            best_score = score
            best_match = game_data

    return best_match


async def process_llm_request(
    llm_handler,
    prompt: str,
    context: str,
    user_name: str,
    game_cache=None,
    pre_optimized: bool = False,  # Nouveau param: prompt déjà optimisé ?
    stimulus_class: str = "gen_short",  # Classe de stimulus pour prompts pré-optimisés
    channel_id: str = ""  # ID du channel pour personnalité custom
) -> str | None:
    """
    Traite une requête LLM - Logique métier pure.

    Args:
        llm_handler: Instance LLMHandler
        prompt: Question/message de l'utilisateur
        context: Context ("ask" ou "mention")
        user_name: Nom de l'utilisateur
        game_cache: Cache des jeux (optionnel pour enrichissement contexte)
        pre_optimized: Si True, le prompt est déjà au format optimal (skip wrapping)
        stimulus_class: Classe de stimulus si pre_optimized=True ("ping"/"gen_short"/"gen_long")

    Returns:
        str: Réponse formatée (tronquée si nécessaire) ou None si erreur
    """
    import logging
    logger = logging.getLogger(__name__)

    # ✅ VALIDATION DÉFENSIVE (fork-safe, language-agnostic)
    if not llm_handler:
        logger.error("❌ llm_handler est None")
        return None

    # Normalisation pre_optimized: garantir bool
    if not isinstance(pre_optimized, bool):
        logger.warning(f"⚠️ pre_optimized type invalide ({type(pre_optimized)}), conversion bool")
        pre_optimized = bool(pre_optimized)

    # Validation stimulus_class: whitelist stricte
    valid_classes = ["ping", "gen_short", "gen_long"]
    if stimulus_class not in valid_classes:
        logger.warning(f"⚠️ stimulus_class invalide '{stimulus_class}', fallback 'gen_short'")
        stimulus_class = "gen_short"

    try:
        # ✅ PROMPT PRÉ-OPTIMISÉ : Appel direct synapse (bypass wrapping)
        if pre_optimized:
            logger.info("🎯 Prompt pré-optimisé détecté → Appel direct synapse")
            if hasattr(llm_handler, 'local_synapse'):
                response = await llm_handler.local_synapse.fire(
                    stimulus=prompt,
                    context="direct",  # Skip _optimize_signal_for_local()
                    stimulus_class=stimulus_class,
                    correlation_id=f"preopt_{context}"
                )
            else:
                # Fallback: utiliser process_stimulus
                logger.warning("⚠️ local_synapse non disponible, fallback process_stimulus")
                response = await llm_handler.process_stimulus(
                    stimulus=prompt,
                    context=context
                )
        else:
            # 🎮 PROMPT BRUT : Pipeline normal avec enrichissement + wrapping
            enriched_prompt = (
                await enrich_prompt_with_game_context(prompt, game_cache) if game_cache else prompt
            )

            response = await llm_handler.process_stimulus(
                stimulus=enriched_prompt, context=context, channel_id=channel_id
            )

        if not response:
            return None

        # Truncate si trop long (Twitch: 500 chars - [ASK] 6 chars = 494 max)
        # Sécurité IRC à 450 chars (marge 44 chars pour edge cases)
        if len(response) > 450:
            response = response[:447] + "..."

        return response

    except Exception:
        # Log l'erreur mais ne crash pas
        return None


async def enrich_prompt_with_game_context(prompt: str, game_cache) -> str:
    """
    SMART CONTEXT 2.0: Auto-enrichissement révolutionnaire !
    NOUVELLE LOGIQUE: Si jeu détecté dans prompt → enrichir automatiquement
    Plus besoin de keywords - détection basée sur contenu réel !

    Args:
        prompt: Question originale de l'user
        game_cache: Instance GameCache

    Returns:
        str: Prompt enrichi ou prompt original si aucun jeu détecté
    """
    if not game_cache or not prompt:
        return prompt

    # 🔍 DEBUG: Log Smart Context 2.0
    import logging

    logger = logging.getLogger(__name__)
    logger.info(f"🧠 Smart Context 2.0: Analyse prompt '{prompt[:50]}...' pour jeux disponibles")

    # 🚀 RÉVOLUTION: Chercher jeu d'abord, keywords après !
    game_info = find_game_in_cache(prompt, game_cache)

    if game_info:
        logger.info(
            f"🎮 Smart Context 2.0 AUTO-ACTIVÉ: Jeu '{game_info.get('name')}' détecté ! Keywords plus nécessaires !"
        )
    else:
        logger.info(
            f"❌ Smart Context 2.0: Aucun jeu détecté dans '{prompt[:30]}...', prompt original conservé"
        )
        return prompt

    # 🎮 Si jeu trouvé → ENRICHIR AUTOMATIQUEMENT (peu importe l'intention)
    if game_info:
        # 🔍 DEBUG: Log Smart Context activation
        logger.info(
            f"🎮 Smart Context ACTIVÉ: Jeu '{game_info.get('name')}' détecté pour prompt '{prompt[:50]}...'"
        )

        # 🎯 Extraire les données du jeu pour enrichissement
        name = game_info.get("name", "")
        year = game_info.get("year", "")
        
        # Plateformes (max 3)
        platforms = (
            ", ".join(game_info.get("platforms", [])[:3]) if game_info.get("platforms") else ""
        )
        
        # Genres avec traduction française (max 3)
        genres_text = ""
        genres_fr = []  # 🐛 FIX: Initialisation avant le if pour éviter UnboundLocalError
        if game_info.get("genres"):
            genres = game_info.get("genres", [])[:3]
            genre_translations = {
                "Action": "Action",
                "RPG": "RPG",
                "Indie": "Indépendant",
                "Casual": "Décontracté",
                "Adventure": "Aventure",
                "Simulation": "Simulation",
                "Strategy": "Stratégie",
                "Shooter": "Tir",
                "Racing": "Course",
            }
            genres_fr = [genre_translations.get(g, g) for g in genres if g and isinstance(g, str)]
            genres_text = ", ".join(genres_fr) if genres_fr else ""
        
        # Description (priorité: summary > description_raw > description)
        description = ""
        if game_info.get("summary"):
            description = game_info.get("summary", "")[:150]
        elif game_info.get("description_raw"):
            description = game_info.get("description_raw", "")[:150]
        elif game_info.get("description"):
            description = game_info.get("description", "")[:150]

        # 🎯 STRATÉGIE ADAPTATIVE : Prompt différent selon richesse des données
        has_rich_data = bool(genres_text and description)  # Genres ET description = données riches
        
        if has_rich_data:
            # 💎 Données complètes → Prompt DIRECTIF (utilise tout)
            directif_prompt = f"""[CONTEXTE STRICT :
- Nom : {name}
- Année : {year}
- Plateformes : {platforms}
- Genres : {genres_text}
- Description : {description}
OBLIGATOIRE : Utilise TOUTES ces infos dans ta réponse.]

Question : {prompt}"""
        else:
            # 📦 Données partielles → Prompt SUGGESTIF (indique !gameinfo)
            context_parts = [f"Nom : {name}"]
            if year:
                context_parts.append(f"Année : {year}")
            if platforms:
                context_parts.append(f"Plateformes : {platforms}")
            if genres_text:
                context_parts.append(f"Genres : {genres_text}")
            if description:
                context_parts.append(f"Description : {description}")
            
            context_str = "\n- ".join(context_parts)
            directif_prompt = f"""[CONTEXTE PARTIEL :
- {context_str}

Note : Données limitées disponibles. Si la question nécessite plus d'infos (gameplay, graphismes, mécaniques), suggère d'utiliser !gameinfo {name} pour enrichir le cache.]

Question : {prompt}"""

        return directif_prompt

    return prompt


def extract_question_from_command(message_content: str) -> str | None:
    """
    Extrait la question d'une commande !ask.

    Args:
        message_content: Contenu complet du message "!ask <question>"

    Returns:
        str: Question extraite ou None si invalide
    """
    parts = message_content.strip().split(maxsplit=1)
    if len(parts) < 2:
        return None
    return parts[1].strip()


def extract_mention_message(message_content: str, bot_name: str) -> str | None:
    """
    Extrait le message d'une mention @bot ou bot_name.

    Args:
        message_content: Contenu complet du message contenant bot_name
        bot_name: Nom du bot (case-insensitive)

    Returns:
        str: Message extrait (avec bot_name retiré) ou None si bot_name absent
        
    Règles de détection:
    - bot_name ou @bot_name N'IMPORTE OÙ dans le message = mention
    - Le système neural (UCB bandit) gère ensuite le contexte et la pertinence
    """
    import re
    
    content_lower = message_content.lower()
    bot_lower = bot_name.lower()
    
    # Vérifier si bot_name ou @bot_name est présent (case-insensitive)
    if f"@{bot_lower}" not in content_lower and bot_lower not in content_lower:
        return None
    
    # Pattern: @bot_name ou bot_name (word boundary pour éviter "leserda_bot")
    pattern = rf"@?{re.escape(bot_name)}\b"
    message = re.sub(pattern, "", message_content, count=1, flags=re.IGNORECASE)
    message = message.strip()
    
    # Retourner le message même si vide (mention sans texte = ping)
    return message if message else "ping"
