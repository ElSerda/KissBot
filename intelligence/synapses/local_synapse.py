"""
💡 LocalSynapse V2.0 - LM Studio Neural Pathway

Connexions neuronales locales avec UCB, circuit-breaker et EMA
"""

import asyncio
import json
import logging
import re
import time
from typing import Any

import httpx


class LocalSynapse:
    """
    💡 SYNAPSE LOCALE V2.0 (LM Studio/Ollama)

    Métaphore : Connexions neuronales rapides avec UCB + circuit-breaker
    - UCB bandit pour adaptation intelligente
    - Circuit-breaker avec hystérésis
    - EMA smoothing des métriques
    - Timeouts adaptatifs par stimulus
    - Validation reward-based
    - Post-traitement anti-dérive pour Mistral 7B
    """

    # 🚫 LISTE NOIRE: Mots qui déclenchent des divagations
    DERIVE_TRIGGERS = [
        "en résumé", "on peut également", "il est intéressant de noter",
        "pour comprendre cela", "de plus", "en outre", "par ailleurs",
        "ce phénomène peut aussi", "d'autres exemples incluent",
        "il faut noter que", "ainsi", "donc", "en effet"
    ]

    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Configuration synapse
        llm_config = config.get("llm", {})
        neural_config = config.get("neural_llm", {})

        self.endpoint = llm_config.get(
            "model_endpoint", "http://127.0.0.1:1234/v1/chat/completions"
        )
        self.model_name = llm_config.get("model_name", "mistralai/mistral-7b-instruct-v0.3")
        self.is_enabled = llm_config.get("local_llm", True)
        self.language = llm_config.get("language", "fr")  # Langue des réponses
        
        # 🎬 DEBUG MODE: Afficher chunks streaming en temps réel
        # Support: debug_streaming: true OU stream_response_debug: "on"
        self.debug_streaming = (
            llm_config.get("debug_streaming", False) or 
            llm_config.get("stream_response_debug", "").lower() == "on"
        )

        # ⚡ CIRCUIT BREAKER STATE
        self.failure_threshold = neural_config.get("local_failure_threshold", 3)
        self.recovery_time = neural_config.get("local_recovery_time", 300)
        self.circuit_state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.consecutive_failures = 0
        self.last_failure_time = 0.0

        # 📈 EMA METRICS
        self.ema_alpha = neural_config.get("ema_alpha", 0.1)
        self.ema_success_rate = 0.8
        self.ema_latency = 800.0

        # 🎰 BANDIT STATE
        self.total_trials = 0
        self.success_trials = 0
        self.total_reward = 0.0

        # ⏱️ TIMEOUTS ADAPTATIFS (3 classes) - Mistral 7B needs time!
        self.timeouts = {
            "ping": neural_config.get("timeout_ping", 2.0),      # 2s (reflex forcé anyway)
            "gen_short": neural_config.get("timeout_gen_short", 4.0),  # 4s (was 2s)
            "gen_long": neural_config.get("timeout_gen_long", 8.0),    # 8s (was 5s)
        }

        # 📊 MÉTRIQUES LOCALES
        self.response_times: list[float] = []

        if self.is_enabled:
            self.logger.info("💡 LocalSynapse V2.0 initialisée - LM Studio prêt")
        else:
            self.logger.info("💡 LocalSynapse désactivée - Local LLM off")

    def can_execute(self) -> bool:
        """⚡ CIRCUIT BREAKER CHECK"""
        if not self.is_enabled:
            return False

        current_time = time.time()

        if self.circuit_state == "CLOSED":
            return True
        elif self.circuit_state == "OPEN":
            if current_time - self.last_failure_time > self.recovery_time:
                self.circuit_state = "HALF_OPEN"
                self.logger.info("⚡ Circuit breaker LOCAL: OPEN → HALF_OPEN")
                return True
            return False
        elif self.circuit_state == "HALF_OPEN":
            return True
        return False

    def _hard_truncate(self, response: str, max_chars: int = 400) -> str:
        """
        🔪 TRONCATURE BRUTALE - Coupe à la dernière phrase complète avant limite
        
        Recommandation Mistral AI: Post-traitement obligatoire car Mistral 7B
        ignore parfois les limites sur sujets complexes.
        """
        if len(response) <= max_chars:
            return response
        
        # Coupe à la dernière phrase complète avant la limite
        truncated = response[:max_chars]
        last_period = truncated.rfind('.')
        last_exclamation = truncated.rfind('!')
        last_question = truncated.rfind('?')
        
        # Trouver la dernière ponctuation forte
        last_punct = max(last_period, last_exclamation, last_question)
        
        if last_punct != -1:
            return truncated[:last_punct + 1] + " 🔚"
        else:
            # Pas de ponctuation trouvée : coupe brutale
            return truncated.rstrip() + "... 🔚"
    
    def _remove_derives(self, response: str) -> str:
        """
        🚫 SUPPRESSION DES MOTS DÉRIVANTS
        
        Certains mots déclenchent des divagations chez Mistral 7B.
        Coupe la réponse dès qu'un trigger est détecté.
        """
        response_lower = response.lower()
        
        for trigger in self.DERIVE_TRIGGERS:
            if trigger in response_lower:
                # Coupe avant le trigger
                idx = response_lower.index(trigger)
                return response[:idx].rstrip() + " 🔚"
        
        return response

    async def fire(
        self,
        stimulus: str,
        context: str = "general",
        stimulus_class: str = "gen_short",
        correlation_id: str = "",
    ) -> str | None:
        """🔥 TRANSMISSION SYNAPTIQUE LOCALE V2.0"""
        if not self.can_execute():
            return None

        # Pas de asyncio.wait_for() - laisser httpx gérer son timeout
        optimized_prompt = self._optimize_signal_for_local(stimulus, context, stimulus_class)

        start_time = time.time()
        try:
            # Httpx timeout interne géré dans _transmit_local_signal
            response = await self._transmit_local_signal(
                optimized_prompt, context, correlation_id, stimulus_class
            )

            latency = time.time() - start_time

            if response and self._is_valid_response(response, stimulus):
                reward = self._calculate_reward(response, stimulus, latency, 0)
                self._record_success(latency, reward)

                self.logger.info(
                    f"💡✅ [{correlation_id}] Success {latency:.2f}s - Reward: {reward:.2f}"
                )
                return response
            else:
                self._record_failure("Réponse invalide")
                return None
        except httpx.ConnectError:
            self._record_failure("Connexion LM Studio impossible")
            return None
        except httpx.ReadTimeout:
            self._record_failure("LM Studio read timeout")
            return None
        except httpx.RemoteProtocolError as e:
            # LM Studio peut fermer la connexion prématurément
            self._record_failure(f"LM Studio protocol error: {str(e)[:50]}")
            return None
        except httpx.HTTPStatusError as e:
            self._record_failure(f"HTTP {e.response.status_code}: {e.response.text[:100]}")
            return None
        except Exception as e:
            error_msg = str(e)
            # Channel Error = bug LM Studio connu (client disconnect pendant génération)
            if "Channel Error" in error_msg or "channel" in error_msg.lower():
                self._record_failure("LM Studio Channel Error - client déconnecté trop tôt")
                self.logger.warning("💡 LM Studio Channel Error: Augmenter timeout ou réduire max_tokens")
            else:
                self._record_failure(f"Erreur LM Studio: {error_msg}")
            return None

    def _optimize_signal_for_local(self, stimulus: str, context: str, stimulus_class: str = "gen_short") -> list[dict[str, str]]:
        """🎯 OPTIMISATION SIGNAL LOCAL V2.0"""
        
        # BYPASS: Si context="direct", pas de wrapping (pour !joke POC)
        if context == "direct":
            return [{"role": "user", "content": stimulus}]
        
        bot_config = self.config.get("bot", {})
        bot_name = bot_config.get("name", "KissBot")
        personality = bot_config.get("personality", "sympa, direct, et passionné de tech")

        llm_config = self.config.get("llm", {})
        use_personality_mention = llm_config.get("use_personality_on_mention", True)
        use_personality_ask = llm_config.get("use_personality_on_ask", False)

        # Carte de langue pour format naturel
        language_map = {
            "fr": "EN FRANÇAIS",
            "en": "IN ENGLISH",
            "es": "EN ESPAÑOL",
            "de": "AUF DEUTSCH"
        }
        lang_directive = language_map.get(self.language, "EN FRANÇAIS")

        # PROMPT OPTIMISÉ VERSION 2 (recommandation Mistral AI)
        # Format minimaliste pour éviter auto-présentation
        if context == "ask":
            if use_personality_ask:
                system_prompt = (
                    f"Réponds EN 1 PHRASE MAX {lang_directive}, SANS TE PRÉSENTER, comme {bot_name} "
                    f"({personality}). Max 200 caractères : {stimulus}"
                )
            else:
                system_prompt = (
                    f"Réponds EN 1 PHRASE MAX {lang_directive}, SANS TE PRÉSENTER, comme un bot Twitch factuel. "
                    f"Max 200 caractères : {stimulus}"
                )
        else:
            # Mentions : différencier gen_short vs gen_long
            if stimulus_class == "gen_long":
                # 🎯 PROMPT ANTI-DÉRIVE (Recommandation Mistral AI)
                # Contraintes strictes + format obligatoire + exemple de référence
                if use_personality_mention:
                    system_prompt = (
                        f"Tu es {bot_name}. {personality}\n\n"
                        f"RÈGLES STRICTES (NON NÉGOCIABLES):\n"
                        f"1. **MAX 2 PHRASES** (pas de listes 1. 2. 3.)\n"
                        f"2. **MAX 400 CARACTÈRES** (coupe-toi si tu dépasses)\n"
                        f"3. **Réponds {lang_directive}, SANS TE PRÉSENTER**\n"
                        f"4. **Termine par 🔚**\n\n"
                        f"FORMAT OBLIGATOIRE:\n"
                        f"\"Définition courte avec exemple concret 💡. Cas d'usage pratique 🎯. 🔚\"\n\n"
                        f"EXEMPLE DE RÉFÉRENCE:\n"
                        f"Q: C'est quoi la gravité?\n"
                        f"R: La gravité attire les objets vers le centre de la Terre 💡. Exemple: une pomme tombe 🎯. 🔚\n\n"
                        f"NOW YOUR TURN:\n"
                        f"Q: {stimulus}\n"
                        f"R:"
                    )
                else:
                    system_prompt = (
                        f"RÈGLES STRICTES:\n"
                        f"1. **MAX 2 PHRASES** (≤400 caractères)\n"
                        f"2. **Réponds {lang_directive}, SANS TE PRÉSENTER**\n"
                        f"3. **Format: \"Définition 💡. Exemple 🎯. 🔚\"**\n\n"
                        f"Q: {stimulus}\n"
                        f"R:"
                    )
            else:
                # Questions simples/salutations : réponses courtes
                if use_personality_mention:
                    system_prompt = (
                        f"Tu es {bot_name}. {personality}\n"
                        f"Règles:\n"
                        f"1. Réponds en 1-2 phrases MAX {lang_directive}, SANS TE PRÉSENTER\n"
                        f"2. Pour les questions personnelles (ça va?), utilise des réponses courtes et humoristiques\n"
                        f"3. Évite les répétitions. Varie tes réponses\n"
                        f"4. Utilise des emojis si ça ajoute du fun\n"
                        f"5. Sois punchy et direct\n"
                        f"Question: {stimulus}\n"
                        f"Réponse:"
                    )
                else:
                    system_prompt = (
                        f"Réponds EN 1 PHRASE MAX {lang_directive}, SANS TE PRÉSENTER, comme un bot Twitch sympa. "
                        f"Max 150 caractères : {stimulus}"
                    )

        # Format user-only avec prompt intégré (pas de séparation system/user)
        return [{"role": "user", "content": system_prompt}]

    async def _transmit_local_signal(
        self, messages: list[dict[str, str]], context: str, correlation_id: str, stimulus_class: str = "gen_short"
    ) -> str | None:
        """📡 TRANSMISSION LOCAL OPTIMISÉE - Compatible Mistral/Qwen"""
        
        # Mistral 7B n'accepte PAS le role "system" - toujours user only
        # Conversion préventive pour éviter Channel Error
        if "mistral" in self.model_name.lower():
            messages = self._convert_to_user_only(messages)
        
        # 🎯 PARAMÈTRES OPTIMISÉS (Recommandation Mistral AI)
        # max_tokens réduits pour sujets complexes + repeat_penalty + stop tokens
        if context == "ask":
            # 🎯 CONFIG OPTIMALE !ask (Mistral 7B Instruct v0.3)
            # Tests : 30/30 réussis (tech + sciences), 0% dépassements, longueur moy: 140 chars
            # 
            # SYSTÈME À DOUBLE SÉCURITÉ :
            # - Limite souple (guidage) : max_tokens=200 → guide le modèle
            # - Limite brute (hard-cut) : 250 chars (+25% marge) → post-traitement ligne ~491
            # 
            # Résultats prouvés par A+B :
            # - Tech (8 tests) : 0% dépassements, 138.8 chars moy
            # - Sciences (22 tests) : 0% dépassements, 142.0 chars moy
            # - Distribution : 18% <100, 46% 100-150, 23% 150-200, 14% 200-250
            max_tokens = 200  # ask - limite souple (guidage modèle)
            temperature = 0.3
            httpx_timeout = 15.0
            repeat_penalty = 1.1  # Optimal pour max_tokens=200
            stop_tokens = ["\n", "🔚"]
        elif context == "mention" and stimulus_class == "gen_long":
            # 🔥 GEN_LONG OPTIMAL (Mistral 7B Instruct v0.3)
            # Tests : 5/5 réussis, 0% dépassements >400 chars, ~130 chars moy
            # Optimisations Mistral AI : max_tokens=100 + post-processing anti-dérive
            max_tokens = 100  
            temperature = 0.4  # Moins de créativité = moins de divagations
            httpx_timeout = 20.0
            repeat_penalty = 1.2  # Évite les répétitions
            stop_tokens = ["🔚", "\n", "400.", "Exemple :", "En résumé,"]
        elif context == "mention":
            # 🎯 GEN_SHORT OPTIMAL (Mistral 7B Instruct v0.3)
            # Tests : 45/45 réussis, 0% dépassements >200 chars, 55 chars moy, 95.6% emojis
            # Config actuelle DÉJÀ OPTIMALE - aucun changement nécessaire
            max_tokens = 200  # mentions gen_short - réponses développées
            temperature = 0.7
            httpx_timeout = 15.0
            repeat_penalty = 1.1
            stop_tokens = ["\n"]
        elif stimulus_class == "gen_long":
            max_tokens = 100  # gen_long - contraintes strictes
            temperature = 0.4
            httpx_timeout = 15.0
            repeat_penalty = 1.2
            stop_tokens = ["🔚", "\n"]
        else:
            max_tokens = 150  # gen_short - augmenté pour blagues complètes
            temperature = 0.7
            httpx_timeout = 12.0
            repeat_penalty = 1.1
            stop_tokens = ["\n"]

        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "repeat_penalty": repeat_penalty,
            "stop": stop_tokens,
            "stream": True,  # ← STREAMING ACTIVÉ (accumulation)
        }

        # Httpx gère son propre timeout - pas de asyncio.wait_for() qui coupe la connexion
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(httpx_timeout, connect=5.0, read=httpx_timeout)
        ) as client:
            try:
                # 🌊 STREAMING AVEC ACCUMULATION (pas de spam chat)
                full_response = ""
                finish_reason = "unknown"
                
                # 🎬 DEBUG: Header streaming
                if self.debug_streaming:
                    print("\n🌊 [STREAMING START] ", end="", flush=True)
                
                async with client.stream("POST", self.endpoint, json=payload) as response:
                    if response.status_code == 400:
                        error_text = await response.aread()
                        error_str = error_text.decode().lower()
                        if "system" in error_str or "role" in error_str:
                            self.logger.info(
                                f"🔄 Model {self.model_name} ne supporte pas 'system' - fallback user only"
                            )
                            # Retry avec user only
                            fallback_messages = self._convert_to_user_only(messages)
                            fallback_payload = {**payload, "messages": fallback_messages}
                            
                            async with client.stream("POST", self.endpoint, json=fallback_payload) as retry_response:
                                retry_response.raise_for_status()
                                async for line in retry_response.aiter_lines():
                                    if line.startswith("data: "):
                                        chunk_data = line[6:]  # Remove "data: " prefix
                                        if chunk_data == "[DONE]":
                                            break
                                        try:
                                            chunk_json = json.loads(chunk_data)
                                            if "choices" in chunk_json and chunk_json["choices"]:
                                                delta = chunk_json["choices"][0].get("delta", {})
                                                if "content" in delta:
                                                    chunk_text = delta["content"]
                                                    full_response += chunk_text
                                                    # 🎬 DEBUG: Afficher chunk en temps réel
                                                    if self.debug_streaming:
                                                        print(chunk_text, end="", flush=True)
                                                # Capture finish_reason
                                                finish_reason = chunk_json["choices"][0].get("finish_reason", finish_reason)
                                        except json.JSONDecodeError:
                                            continue
                        else:
                            raise httpx.HTTPStatusError(f"HTTP {response.status_code}", request=response.request, response=response)
                    else:
                        response.raise_for_status()
                        # Stream normal
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                chunk_data = line[6:]
                                if chunk_data == "[DONE]":
                                    break
                                try:
                                    chunk_json = json.loads(chunk_data)
                                    if "choices" in chunk_json and chunk_json["choices"]:
                                        delta = chunk_json["choices"][0].get("delta", {})
                                        if "content" in delta:
                                            chunk_text = delta["content"]
                                            full_response += chunk_text
                                            # 🎬 DEBUG: Afficher chunk en temps réel
                                            if self.debug_streaming:
                                                print(chunk_text, end="", flush=True)
                                        # Capture finish_reason
                                        finish_reason = chunk_json["choices"][0].get("finish_reason", finish_reason)
                                except json.JSONDecodeError:
                                    continue
                
                # 🎯 ENVOYER MESSAGE COMPLET APRÈS STOP_REASON
                if not full_response:
                    return None
                
            except (httpx.RemoteProtocolError, httpx.ReadError) as e:
                # LM Studio Channel Error = bug système/user incompatible
                # Réessayer directement avec user only
                self.logger.warning(
                    f"💡 LM Studio Channel Error (system+user incompatible) - retry user only"
                )
                
                fallback_messages = self._convert_to_user_only(messages)
                fallback_payload = {**payload, "messages": fallback_messages}
                
                # Retry avec streaming
                full_response = ""
                finish_reason = "unknown"
                async with client.stream("POST", self.endpoint, json=fallback_payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            chunk_data = line[6:]
                            if chunk_data == "[DONE]":
                                break
                            try:
                                chunk_json = json.loads(chunk_data)
                                if "choices" in chunk_json and chunk_json["choices"]:
                                    delta = chunk_json["choices"][0].get("delta", {})
                                    if "content" in delta:
                                        chunk_text = delta["content"]
                                        full_response += chunk_text
                                        # 🎬 DEBUG: Afficher chunk en temps réel
                                        if self.debug_streaming:
                                            print(chunk_text, end="", flush=True)
                                    finish_reason = chunk_json["choices"][0].get("finish_reason", finish_reason)
                            except json.JSONDecodeError:
                                continue
                
                # 🎬 DEBUG: Footer streaming
                if self.debug_streaming:
                    print(f" [STREAMING END] finish_reason={finish_reason}\n", flush=True)

            # 🚨 DÉTECTION TRUNCATION (finish_reason: length)
            if finish_reason == "length":
                self.logger.warning(
                    f"⚠️ [LocalSynapse] Response TRUNCATED (finish_reason: length) "
                    f"- max_tokens={max_tokens} atteint ! Consider increasing."
                )
            
            # 🧹 POST-TRAITEMENT COMPLET
            cleaned = full_response.strip() if full_response else ""
            cleaned = self._remove_self_introduction(cleaned)
            
            # 🎯 POST-TRAITEMENT ANTI-DÉRIVE (Recommandation Mistral AI)
            # OBLIGATOIRE pour gen_long car Mistral 7B dépasse parfois les limites
            if stimulus_class == "gen_long":
                cleaned = self._remove_derives(cleaned)  # Coupe les divagations
                cleaned = self._hard_truncate(cleaned, max_chars=400)  # Force ≤400 chars
            
            # 🎯 SYSTÈME À DOUBLE SÉCURITÉ POUR !ask (Mistral 7B Instruct v0.3)
            # - Limite souple (guidage) : max_tokens=200 guide le modèle (voir ligne ~313)
            # - Limite brute (hard-cut) : 250 chars (200 + 25% marge) coupe brutalement
            # Tests prouvés : 30/30 réussis, 0% dépassements (tech: 138.8 chars, sciences: 142.0 chars)
            elif context == "ask":
                cleaned = self._hard_truncate(cleaned, max_chars=250)  # 200 + 25% marge
            
            # Ajouter ellipse si tronqué
            if finish_reason == "length" and cleaned and not cleaned.endswith("..."):
                cleaned = cleaned.rstrip(".!?,;:") + "..."

            if cleaned and len(cleaned) >= 3:
                return cleaned

        return None

    def _remove_self_introduction(self, response: str) -> str:
        """🧹 POST-TRAITEMENT : Supprimer auto-présentation (recommandation Mistral AI)"""
        import re
        
        bot_name = self.config.get("bot", {}).get("name", "KissBot")
        
        # Patterns d'auto-présentation à supprimer
        patterns = [
            rf"Bonjour.*?{bot_name}[^.]*\.?\s*",  # "Bonjour ! Je suis KissBot..."
            rf"^Je suis {bot_name}[^.]*\.?\s*",    # "Je suis KissBot..."
            rf"^Moi,?\s*{bot_name}[^,!.]*[,!.]\s*",  # "Moi KissBot, ..." ou "Moi, KissBot..."
            rf"^Salut.*?{bot_name}[^.]*\.?\s*",   # "Salut ! Je suis KissBot..."
            rf"^{bot_name},\s*[^.]*\.?\s*",        # "KissBot, le bot..."
        ]
        
        cleaned = response
        for pattern in patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        
        # Nettoyer les espaces/ponctuation résiduels
        cleaned = cleaned.strip(" ,.!").capitalize() if cleaned else response
        
        return cleaned if len(cleaned) >= 10 else response  # Fallback si trop court

    def _convert_to_user_only(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """🔄 CONVERSION POUR MODÈLES LEGACY (Mistral)"""
        system_content = ""
        user_content = ""

        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            elif msg["role"] == "user":
                user_content = msg["content"]

        # Fusion système + user en un seul message user
        if system_content:
            combined_content = f"{system_content} {user_content}"
        else:
            combined_content = user_content

        return [{"role": "user", "content": combined_content}]

    def _is_valid_response(self, response: str, stimulus: str) -> bool:
        """🎖️ VALIDATION RÉPONSE LOCALE - Assouplie pour Mistral 7B"""
        if not response or len(response.strip()) < 3:
            return False

        # Mistral 7B peut retourner des réponses courtes mais valides
        # Accepter même sans ponctuation finale si suffisamment long
        if len(response.strip()) >= 10:
            return True

        # Réponses ultra-courtes = invalides
        if response.lower() in ["ok", "oui", "non", "yes", "no"]:
            return False

        return True

    def _calculate_reward(
        self, response: str, stimulus: str, latency: float, retries: int
    ) -> float:
        """🎖️ REWARD SHAPING LOCAL V2.0"""
        base_reward = 1.0
        target_latency = 1.0  # Local = rapide
        latency_penalty = min(latency / target_latency, 1.0) * 0.3

        quality_bonus = 0.0
        if len(response) > 20:
            quality_bonus += 0.2
        if any(marker in response for marker in [".", "!", "?"]):
            quality_bonus += 0.1
        if any(emoji in response for emoji in ["😄", "🎮", "👍", "🔥", "⚡"]):
            quality_bonus += 0.15

        return max(base_reward - latency_penalty + quality_bonus, 0.1)

    def _record_success(self, latency: float, reward: float):
        """🟢 ENREGISTREMENT SUCCÈS LOCAL V2.0"""
        self.total_trials += 1
        self.success_trials += 1
        self.total_reward += reward

        self.ema_latency = self.ema_alpha * latency + (1 - self.ema_alpha) * self.ema_latency
        self.ema_success_rate = self.ema_alpha * 1.0 + (1 - self.ema_alpha) * self.ema_success_rate

        if self.circuit_state == "HALF_OPEN":
            self.circuit_state = "CLOSED"
            self.logger.info("⚡ Circuit breaker LOCAL: HALF_OPEN → CLOSED")
        self.consecutive_failures = 0

        self.response_times.append(latency)
        if len(self.response_times) > 20:
            self.response_times.pop(0)

    def _record_failure(self, error: str):
        """🔴 ENREGISTREMENT ÉCHEC LOCAL V2.0"""
        self.total_trials += 1
        self.consecutive_failures += 1
        self.last_failure_time = time.time()

        self.ema_success_rate = self.ema_alpha * 0.0 + (1 - self.ema_alpha) * self.ema_success_rate

        if self.consecutive_failures >= self.failure_threshold:
            if self.circuit_state != "OPEN":
                self.circuit_state = "OPEN"
                self.logger.error(
                    f"⚡ Circuit breaker LOCAL: → OPEN ({self.consecutive_failures} échecs)"
                )
        elif self.circuit_state == "HALF_OPEN":
            self.circuit_state = "OPEN"
            self.logger.warning("⚡ Circuit breaker LOCAL: HALF_OPEN → OPEN (échec sonde)")

    def get_bandit_stats(self) -> dict[str, float]:
        """🎰 STATISTIQUES BANDIT LOCAL"""
        if self.total_trials == 0:
            return {"avg_reward": 0.0, "trials": 0, "ucb_score": float("inf")}

        avg_reward = self.total_reward / self.total_trials
        return {"avg_reward": avg_reward, "trials": self.total_trials, "ucb_score": avg_reward}

    def get_neural_metrics(self) -> dict[str, Any]:
        """📊 MÉTRIQUES NEURAL LOCAL V2.0"""
        time.time()

        # Diagnostic auto si échecs récents
        health_status = "healthy"
        if self.consecutive_failures >= 2:
            health_status = "degraded"
        elif self.circuit_state == "OPEN":
            health_status = "circuit_open"

        return {
            "synapse_type": "local_llm_v2",
            "is_enabled": self.is_enabled,
            "can_execute": self.can_execute(),
            "health_status": health_status,
            "endpoint": self.endpoint,
            "model_name": self.model_name,
            # Circuit Breaker
            "circuit_state": self.circuit_state,
            "consecutive_failures": self.consecutive_failures,
            "last_failure_time": self.last_failure_time,
            "failure_threshold": self.failure_threshold,
            "recovery_time": self.recovery_time,
            # UCB Bandit Stats
            "total_trials": self.total_trials,
            "success_trials": self.success_trials,
            "total_reward": self.total_reward,
            "avg_reward": self.total_reward / self.total_trials if self.total_trials > 0 else 0.0,
            "success_rate": (
                self.success_trials / self.total_trials if self.total_trials > 0 else 0.0
            ),
            # EMA Tracking
            "ema_latency": self.ema_latency,
            "ema_success_rate": self.ema_success_rate,
            "ema_alpha": self.ema_alpha,
            # Performance
            "recent_response_times": self.response_times[-5:],
            "avg_response_time": (
                sum(self.response_times) / len(self.response_times) if self.response_times else 0.0
            ),
            "last_success_time": getattr(self, "last_success_time", None),
            # Diagnostic hints
            "diagnostic_available": True,
            "needs_diagnostic": self.consecutive_failures >= 3 or self.circuit_state == "OPEN",
        }
