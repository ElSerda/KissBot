"""
💡 LocalSynapse V2.0 - LM Studio Neural Pathway

Connexions neuronales locales avec UCB, circuit-breaker et EMA
"""

import asyncio
import logging
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
    """

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

        # ⚡ CIRCUIT BREAKER STATE
        self.failure_threshold = neural_config.get("local_failure_threshold", 3)
        self.recovery_time = neural_config.get("local_recovery_time", 300)
        self.circuit_state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.consecutive_failures = 0
        self.last_failure_time = 0

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
        optimized_prompt = self._optimize_signal_for_local(stimulus, context)

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

    def _optimize_signal_for_local(self, stimulus: str, context: str) -> list[dict[str, str]]:
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
                    f"({personality}). Max 120 caractères : {stimulus}"
                )
            else:
                system_prompt = (
                    f"Réponds EN 1 PHRASE MAX {lang_directive}, SANS TE PRÉSENTER, comme un bot Twitch factuel. "
                    f"Max 120 caractères : {stimulus}"
                )
        else:
            if use_personality_mention:
                system_prompt = (
                    f"Réponds EN 1 PHRASE MAX {lang_directive}, SANS TE PRÉSENTER, comme {bot_name} "
                    f"({personality}). Max 80 caractères : {stimulus}"
                )
            else:
                system_prompt = (
                    f"Réponds EN 1 PHRASE MAX {lang_directive}, SANS TE PRÉSENTER, comme un bot Twitch sympa. "
                    f"Max 80 caractères : {stimulus}"
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
        
        if context == "ask":
            max_tokens = 150  # ask - limite raisonnable
            temperature = 0.3
            httpx_timeout = 15.0
        elif stimulus_class == "gen_long":
            max_tokens = 150  # gen_long - sans présentation devrait suffire
            temperature = 0.7
            httpx_timeout = 15.0
        else:
            max_tokens = 100  # gen_short - limite normale
            temperature = 0.7
            httpx_timeout = 12.0

        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }

        # Httpx gère son propre timeout - pas de asyncio.wait_for() qui coupe la connexion
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(httpx_timeout, connect=5.0, read=httpx_timeout)
        ) as client:
            try:
                # Première tentative avec le format original (system + user)
                response = await client.post(self.endpoint, json=payload)

                # Si erreur 400 et message concernant "system role", fallback sans système
                if response.status_code == 400:
                    error_text = response.text.lower()
                    if "system" in error_text or "role" in error_text:
                        self.logger.info(
                            f"🔄 Model {self.model_name} ne supporte pas 'system' - fallback user only"
                        )

                        # Conversion: system + user → user seul avec contexte intégré
                        fallback_messages = self._convert_to_user_only(messages)
                        fallback_payload = {**payload, "messages": fallback_messages}

                        response = await client.post(self.endpoint, json=fallback_payload)

                response.raise_for_status()
                
            except (httpx.RemoteProtocolError, httpx.ReadError) as e:
                # LM Studio Channel Error = bug système/user incompatible
                # Réessayer directement avec user only
                self.logger.warning(
                    f"💡 LM Studio Channel Error (system+user incompatible) - retry user only"
                )
                
                fallback_messages = self._convert_to_user_only(messages)
                fallback_payload = {**payload, "messages": fallback_messages}
                
                response = await client.post(self.endpoint, json=fallback_payload)
                response.raise_for_status()

            data = response.json()
            if "choices" in data and data["choices"]:
                choice = data["choices"][0]
                
                # 🚨 DÉTECTION TRUNCATION (finish_reason: length)
                finish_reason = choice.get("finish_reason", "unknown")
                if finish_reason == "length":
                    self.logger.warning(
                        f"⚠️ [LocalSynapse] Response TRUNCATED (finish_reason: length) "
                        f"- max_tokens={max_tokens} atteint ! Consider increasing."
                    )
                
                if choice and "message" in choice and choice["message"]:
                    message = choice["message"]
                    if "content" in message and message["content"]:
                        raw_response = message["content"]
                        cleaned = raw_response.strip() if raw_response else ""
                        
                        # POST-TRAITEMENT : Supprimer auto-présentation (recommandation Mistral AI)
                        cleaned = self._remove_self_introduction(cleaned)
                        
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
