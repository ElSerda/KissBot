"""
☁️ CloudSynapse V2.0 - OpenAI Neural Pathway

Connexions neuronales cloud avec UCB, circuit-breaker et rate limiting intelligent
"""

import asyncio
import logging
import random
import time
from typing import Any

import httpx

from modules.intelligence.synapses.constants import (
    TWITCH_MAX_CHARS, ASK_PREFIX_LEN, ASK_TARGET_CHARS,
    ASK_PROMPT_RANGE, ASK_MAX_TOKENS_CLOUD, MENTION_MAX_CHARS
)


class CloudSynapse:
    """
    ☁️ SYNAPSE CLOUD V2.0 (OpenAI)

    Métaphore : Connexions neuronales distantes haute qualité avec intelligence
    - UCB bandit + circuit-breaker avec hystérésis
    - Rate limiting + quota management intelligent
    - EMA smoothing des métriques cloud
    - Backoff exponentiel avec jitter
    - Reward shaping sophistiqué
    """

    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Configuration synapse cloud
        apis_config = config.get("apis", {})
        llm_config = config.get("llm", {})
        neural_config = config.get("neural_llm", {})

        self.api_key = apis_config.get("openai_key")
        self.model = llm_config.get("openai_model", "gpt-3.5-turbo")
        self.endpoint = "https://api.openai.com/v1/chat/completions"

        # ⚡ CIRCUIT BREAKER STATE
        self.failure_threshold = neural_config.get("cloud_failure_threshold", 5)
        self.recovery_time = neural_config.get("cloud_recovery_time", 600)
        self.circuit_state = "CLOSED"
        self.consecutive_failures = 0
        self.last_failure_time = 0.0

        # 📈 EMA METRICS
        self.ema_alpha = neural_config.get("ema_alpha", 0.2)
        self.ema_success_rate = 0.5
        self.ema_latency = 2000.0

        # 🎰 BANDIT STATE
        self.total_trials = 0
        self.success_trials = 0
        self.total_reward = 0.0

        # ⏱️ RATE LIMITING + QUOTAS
        self.rate_limited_until = 0.0
        self.quota_exhausted = False
        self.quota_errors = 0
        self.rate_limit_errors = 0

        # 🔄 BACKOFF EXPONENTIAL
        self.base_backoff = 1.0
        self.max_backoff = 60.0
        self.current_backoff = self.base_backoff

        # ⏱️ TIMEOUTS EXPLICITES (4 valeurs httpx obligatoires)
        # timeout_connect: Connexion HTTP (court: 5s)
        # timeout_inference: Génération LLM (long: 30s)
        # timeout_write: Envoi payload (moyen: 10s)
        # timeout_pool: Pool connexions (court: 5s)
        neural_config = config.get("neural_llm", {})
        self.timeout_connect = neural_config.get("timeout_connect", 5.0)
        self.timeout_inference = neural_config.get("timeout_inference", 30.0)
        self.timeout_write = neural_config.get("timeout_write", 10.0)
        self.timeout_pool = neural_config.get("timeout_pool", 5.0)

        # 📊 MÉTRIQUES CLOUD
        self.response_times: list[float] = []

        # ⚡ ACTIVATION/DÉSACTIVATION
        # Supporte 3 modes provider: local, cloud, auto
        llm_provider = llm_config.get("provider", "auto")
        has_valid_key = bool(self.api_key and len(self.api_key) > 10)
        
        # Logique d'activation selon provider
        if llm_provider == "cloud":
            # Force cloud : activé si clé valide
            self.is_enabled = has_valid_key
            reason = "forcé via provider=cloud"
        elif llm_provider == "local":
            # Force local : cloud désactivé
            self.is_enabled = False
            reason = "désactivé via provider=local"
        elif llm_provider == "auto":
            # Auto : activé si clé valide (UCB décide)
            self.is_enabled = has_valid_key
            reason = "UCB auto" if has_valid_key else "pas de clé valide"
        else:
            # Provider inconnu : fallback auto
            self.logger.warning(f"⚠️ Provider inconnu '{llm_provider}', fallback 'auto'")
            self.is_enabled = has_valid_key
            reason = "fallback auto"
        
        if self.is_enabled:
            self.logger.info(f"☁️ CloudSynapse V2.0 ACTIVÉE - {reason}")
        else:
            self.logger.info(f"☁️ CloudSynapse DÉSACTIVÉE - {reason}")
            # Force circuit breaker OPEN si désactivée
            self.circuit_state = "OPEN"

    def can_execute(self) -> bool:
        """⚡ CIRCUIT BREAKER + RATE LIMIT CHECK"""
        # 🛡️ DEBUG FORCE LOG
        self.logger.warning(f"☁️ DEBUG can_execute: is_enabled={self.is_enabled}, circuit_state={self.circuit_state}, rate_limited_until={self.rate_limited_until}, quota_exhausted={self.quota_exhausted}")
        
        # 🛡️ PROTECTION: Si synapse désactivée, retourne False immédiatement
        if not self.is_enabled:
            self.logger.warning("☁️❌ can_execute: is_enabled=False")
            return False
        
        current_time = time.time()

        if current_time < self.rate_limited_until or self.quota_exhausted:
            return False

        if self.circuit_state == "CLOSED":
            return True
        elif self.circuit_state == "OPEN":
            if current_time - self.last_failure_time > self.recovery_time:
                self.circuit_state = "HALF_OPEN"
                self.logger.info("⚡ Circuit breaker CLOUD: OPEN → HALF_OPEN")
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
        channel_id: str = "",
    ) -> str | None:
        """🔥 TRANSMISSION SYNAPTIQUE CLOUD V2.0"""
        if not self.api_key:
            self.logger.warning(f"☁️❌ [{correlation_id}] API key missing or invalid")
            return None
        
        if not self.can_execute():
            self.logger.warning(f"☁️❌ [{correlation_id}] can_execute() returned False (circuit_state={self.circuit_state}, is_enabled={self.is_enabled})")
            return None

        self.logger.warning(f"☁️ DEBUG fire(): Starting transmission for stimulus_class={stimulus_class}, timeout={self.timeout_inference}s")
        
        # Utilise timeout_inference pour l'opération complète (génération LLM)
        timeout = self.timeout_inference
        optimized_messages = self._optimize_signal_for_cloud(stimulus, context, channel_id)
        
        self.logger.warning(f"☁️ DEBUG fire(): Messages optimized, calling _transmit_cloud_signal...")

        start_time = time.time()
        try:
            response = await asyncio.wait_for(
                self._transmit_cloud_signal(optimized_messages, context, correlation_id),
                timeout=timeout,
            )

            latency = time.time() - start_time

            if response and self._is_valid_response(response, stimulus):
                reward = self._calculate_reward(response, stimulus, latency, 0)
                self._record_success(latency, reward)
                self._reset_backoff()

                self.logger.info(
                    f"☁️✅ [{correlation_id}] Success {latency:.2f}s - Reward: {reward:.2f}"
                )
                return response
            else:
                self._record_failure("Réponse invalide")
                return None

        except asyncio.TimeoutError:
            self._record_failure(f"Timeout {timeout}s")
            self.logger.warning(f"☁️⏱️ Timeout OpenAI après {timeout}s (réseau lent ou réponse longue)")
            return None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                self._handle_rate_limit(e.response)
            elif e.response.status_code in (402, 403):
                # 402: Payment Required, 403: Forbidden (quota/billing)
                self._handle_quota_exhaustion()
            elif e.response.status_code == 401:
                # Clé API invalide ou expirée
                self.logger.error(f"☁️🔑 API Key invalide ou expirée (HTTP 401) - Vérifier config.apis.openai_key")
                self._record_failure("API Key invalide")
            elif e.response.status_code == 500:
                # Erreur serveur OpenAI
                self.logger.error(f"☁️💥 Erreur serveur OpenAI (HTTP 500) - Problème temporaire côté OpenAI, réessayer plus tard")
                self._record_failure("Erreur serveur OpenAI")
            elif e.response.status_code == 503:
                # Service indisponible (maintenance OpenAI ou surcharge)
                self.logger.warning(f"☁️🛠️ OpenAI surchargé/en maintenance (HTTP 503) - Réessayer plus tard")
                self._record_failure("Service surchargé")
            else:
                # Autre erreur HTTP (problème côté OpenAI)
                self.logger.warning(f"☁️⚠️ Erreur API OpenAI (HTTP {e.response.status_code}) - Problème côté serveur OpenAI")
                self._record_failure(f"HTTP {e.response.status_code}")
            return None
        except httpx.ConnectError as e:
            # Problème réseau/DNS
            self.logger.error(f"☁️🌐 Impossible de contacter OpenAI - Vérifier connexion réseau")
            self._record_failure("Erreur réseau")
            return None
        except Exception as e:
            # Erreur inattendue (potentiellement bug code)
            self.logger.error(f"☁️❌ Erreur inattendue (possiblement bug KissBot): {e}", exc_info=True)
            self._record_failure(str(e))
            return None

    def _optimize_signal_for_cloud(self, stimulus: str, context: str, channel_id: str = "") -> list[dict[str, str]]:
        """🎯 OPTIMISATION SIGNAL GPT V2.0 avec personnalité par channel"""
        bot_config = self.config.get("bot", {})
        bot_name = bot_config.get("name", "KissBot")
        default_personality = bot_config.get("personality", "sympa, direct, et passionné de tech")

        llm_config = self.config.get("llm", {})
        use_personality_mention = llm_config.get("use_personality_on_mention", True)
        use_personality_ask = llm_config.get("use_personality_on_ask", False)
        
        # 🎭 Récupérer la personnalité du channel si disponible
        channel_preset = None
        channel_personality_prompt = None
        if channel_id:
            try:
                from modules.personality import get_personality_store, get_system_prompt
                store = get_personality_store()
                channel_personality = store.get(channel_id)
                channel_preset = channel_personality.preset
                # Utiliser le system prompt du preset
                channel_personality_prompt = get_system_prompt(channel_preset, bot_name)
                self.logger.debug(f"🎭 Using channel personality: {channel_preset}")
            except Exception as e:
                self.logger.debug(f"🎭 Personality store not available: {e}")

        if context == "ask":
            if use_personality_ask and channel_personality_prompt:
                # Utiliser la personnalité du channel
                system_prompt = channel_personality_prompt + f"\nRéponds en {ASK_PROMPT_RANGE} caractères, complète tes phrases."
            elif use_personality_ask:
                system_prompt = (
                    f"Tu es {bot_name}. {default_personality}\n"
                    f"Réponds naturellement avec TON opinion et TON style. "
                    f"N'hésite pas à clasher, être drôle, prendre position. "
                    f"Pas de langue de bois. Réponds en {ASK_PROMPT_RANGE} caractères."
                )
            else:
                system_prompt = (
                    f"Tu es {bot_name}, bot Twitch gaming expert et pédagogue. "
                    f"Pour les questions (!ask), réponds de manière DÉTAILLÉE et COMPLÈTE :\n"
                    f"- Explique le contexte et les enjeux\n"
                    f"- Donne des exemples concrets si pertinent\n"
                    f"- Ton accessible mais précis, style vulgarisation scientifique\n"
                    f"- Si théorie du complot : démonte avec FACTS, mais reste sympa\n"
                    f"Réponds en {ASK_PROMPT_RANGE} caractères. Termine toujours ta dernière phrase."
                )
        else:
            # Mentions et autres contextes
            if channel_personality_prompt:
                # Utiliser la personnalité du channel
                system_prompt = channel_personality_prompt + "\nMax 150 caractères."
            elif use_personality_mention:
                system_prompt = (
                    f"Tu es {bot_name}. {default_personality}\n"
                    f"MODE: SANS FILTRE, CASH, PROVOCATEUR\n"
                    f"- Humour: sarcasme mordant, second degré assumé\n"
                    f"- Ton: direct, sans langue de bois, punchlines qui marquent\n"
                    f"- INTERDIT: politesse excessive, 'désolé', nuances molles\n"
                    f"- Chaque réponse doit CLASHER ou faire RIRE, jamais neutre\n"
                    f"- Ose les comparaisons osées, les métaphores trash\n"
                    f"Max 150 chars. Fais une VRAIE vanne, pas une phrase sage."
                )
            else:
                system_prompt = (
                    f"Tu es {bot_name}, bot Twitch ultra sarcastique. "
                    f"Réponds avec humour NOIR, vannes CASH, zéro filtre. "
                    f"Provoque, clash, assume. Max 150 caractères."
                )

        return [{"role": "system", "content": system_prompt}, {"role": "user", "content": stimulus}]

    async def _transmit_cloud_signal(
        self, messages: list[dict[str, str]], context: str, correlation_id: str
    ) -> str | None:
        """📡 TRANSMISSION CLOUD OPTIMISÉE"""
        self.logger.warning(f"☁️ DEBUG _transmit_cloud_signal: START")
        
        # 🧠 Paramètres d'inférence depuis config (avec fallbacks)
        llm_config = self.config.get("llm", {})
        inference_config = llm_config.get("inference", {})
        cloud_config = inference_config.get("cloud", {})
        
        # context == "ask" ou stimulus_class == "gen_long" → réponse détaillée
        if context == "ask":
            # ASK_MAX_TOKENS_CLOUD tokens → cible ASK_TARGET_CHARS chars (15% marge sur 500)
            max_tokens = cloud_config.get("max_tokens_long", ASK_MAX_TOKENS_CLOUD)
            self.logger.debug(f"☁️📏 ASK mode: max_tokens={max_tokens}, target={ASK_TARGET_CHARS} chars")
            temperature = cloud_config.get("temperature_long", 0.7)
        else:
            # gen_short ou mention standard
            max_tokens = cloud_config.get("max_tokens_short", 90)
            temperature = cloud_config.get("temperature_short", 0.4)

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        self.logger.warning(f"☁️ DEBUG: About to send POST to {self.endpoint}")
        
        if self.current_backoff > self.base_backoff:
            jitter = random.uniform(0.8, 1.2)
            wait_time = self.current_backoff * jitter
            await asyncio.sleep(wait_time)

        # ⏱️ TIMEOUTS EXPLICITES (connect court, inference long)
        try:
            self.logger.warning(f"☁️ DEBUG: Creating httpx client...")
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=self.timeout_connect,   # Connexion HTTP (court: 5s)
                    read=self.timeout_inference,    # Inférence LLM (long: 30s)
                    write=self.timeout_write,       # Envoi payload (moyen: 10s)
                    pool=self.timeout_pool          # Pool connexion (court: 5s)
                )
            ) as client:
                self.logger.warning(f"☁️ DEBUG: Sending POST request...")
                response = await client.post(self.endpoint, json=payload, headers=headers)
                self.logger.warning(f"☁️ DEBUG: Got response, status={response.status_code}")
                response.raise_for_status()

                data = response.json()
                if "choices" in data and data["choices"]:
                    raw_response = data["choices"][0]["message"]["content"]
                    cleaned = raw_response.strip() if raw_response else ""

                    if cleaned and len(cleaned) >= 3:
                        # ✂️ Truncation intelligente: ASK_TARGET_CHARS max
                        truncated = self._smart_truncate(cleaned, max_chars=ASK_TARGET_CHARS)
                        self.logger.debug(f"☁️📏 Raw: {len(cleaned)} chars → Truncated: {len(truncated)} chars (limit: {ASK_TARGET_CHARS})")
                        if len(truncated) < len(cleaned):
                            self.logger.info(f"☁️✂️ Response truncated: {len(cleaned)} → {len(truncated)} chars")
                        self.logger.warning(f"☁️ DEBUG: Returning response: {truncated[:50]}...")
                        return truncated

            self.logger.warning(f"☁️ DEBUG: No valid response found, returning None")
            return None
        except Exception as e:
            self.logger.error(f"☁️❌ _transmit_cloud_signal exception: {e}", exc_info=True)
            raise

    def _smart_truncate(self, text: str, max_chars: int = ASK_TARGET_CHARS) -> str:
        """✂️ TRUNCATION INTELLIGENTE pour Twitch (TWITCH_MAX_CHARS chars max)
        
        Coupe le texte proprement à une frontière de phrase si possible,
        sinon à un espace, avec indicateur de continuation.
        """
        if len(text) <= max_chars:
            return text
        
        # Chercher une fin de phrase propre
        truncated = text[:max_chars]
        
        # Priorité: fin de phrase (. ! ?)
        last_period = truncated.rfind('.')
        last_exclamation = truncated.rfind('!')
        last_question = truncated.rfind('?')
        last_punct = max(last_period, last_exclamation, last_question)
        
        if last_punct > max_chars * 0.6:  # Au moins 60% du texte conservé
            return truncated[:last_punct + 1]
        
        # Sinon: couper à un espace
        last_space = truncated.rfind(' ')
        if last_space > max_chars * 0.7:
            return truncated[:last_space] + "..."
        
        # Dernier recours: coupe brute
        return truncated.rstrip() + "..."

    def _is_valid_response(self, response: str, stimulus: str) -> bool:
        """🎖️ VALIDATION RÉPONSE CLOUD"""
        if not response or len(response.strip()) < 3:
            return False

        if response.lower() in ["yes", "no", "ok", "oui", "non"]:
            return False

        return True

    def _calculate_reward(
        self, response: str, stimulus: str, latency: float, retries: int
    ) -> float:
        """🎖️ REWARD SHAPING CLOUD V2.0"""
        base_reward = 1.0
        target_latency = 2.0
        latency_penalty = min(latency / target_latency, 1.0) * 0.2

        quality_bonus = 0.0
        if len(response) > 30:
            quality_bonus += 0.15
        if any(marker in response for marker in [".", "!", "?"]):
            quality_bonus += 0.05
        if any(emoji in response for emoji in ["😎", "🔥", "💡", "🎯", "⚡"]):
            quality_bonus += 0.1

        return max(base_reward - latency_penalty + quality_bonus, 0.1)

    def _handle_rate_limit(self, response: httpx.Response):
        """⏳ GESTION RATE LIMIT V2.0"""
        self._increase_backoff()

        retry_after = response.headers.get("retry-after", "60")
        try:
            wait_time = int(retry_after)
        except ValueError:
            wait_time = 60

        self.rate_limited_until = time.time() + wait_time
        self.rate_limit_errors += 1

        self.logger.warning(
            f"☁️⏳ Rate limit OpenAI (HTTP 429) - Trop de requêtes, attente {wait_time}s "
            f"(Problème: compte OpenAI free/quota)"
        )
        self._record_failure(f"Rate limit {wait_time}s")

    def _handle_quota_exhaustion(self):
        """💸 GESTION QUOTA ÉPUISÉ V2.0"""
        self.quota_exhausted = True
        self.quota_errors += 1
        self.logger.error(
            f"☁️💸 Quota OpenAI épuisé (HTTP 402/403) - "
            f"Ajouter des crédits sur https://platform.openai.com/account/billing"
        )
        self._record_failure("Quota épuisé")

    def _increase_backoff(self):
        """🔄 BACKOFF EXPONENTIEL"""
        self.current_backoff = min(self.current_backoff * 2, self.max_backoff)

    def _reset_backoff(self):
        """✅ RESET BACKOFF SUR SUCCÈS"""
        self.current_backoff = self.base_backoff

    def _record_success(self, latency: float, reward: float):
        """🟢 ENREGISTREMENT SUCCÈS CLOUD V2.0"""
        self.total_trials += 1
        self.success_trials += 1
        self.total_reward += reward

        self.ema_latency = self.ema_alpha * latency + (1 - self.ema_alpha) * self.ema_latency
        self.ema_success_rate = self.ema_alpha * 1.0 + (1 - self.ema_alpha) * self.ema_success_rate

        if self.circuit_state == "HALF_OPEN":
            self.circuit_state = "CLOSED"
            self.logger.info("⚡ Circuit breaker CLOUD: HALF_OPEN → CLOSED")
        self.consecutive_failures = 0

        self.response_times.append(latency)
        if len(self.response_times) > 10:
            self.response_times.pop(0)

    def _record_failure(self, error: str):
        """🔴 ENREGISTREMENT ÉCHEC CLOUD V2.0"""
        self.total_trials += 1
        self.consecutive_failures += 1
        self.last_failure_time = time.time()

        self.ema_success_rate = self.ema_alpha * 0.0 + (1 - self.ema_alpha) * self.ema_success_rate

        if self.consecutive_failures >= self.failure_threshold:
            if self.circuit_state != "OPEN":
                self.circuit_state = "OPEN"
                self.logger.error(
                    f"⚡ Circuit breaker CLOUD: → OPEN ({self.consecutive_failures} échecs)"
                )
        elif self.circuit_state == "HALF_OPEN":
            self.circuit_state = "OPEN"
            self.logger.warning("⚡ Circuit breaker CLOUD: HALF_OPEN → OPEN (échec sonde)")

        if "rate limit" not in error.lower():
            self._increase_backoff()

    def get_bandit_stats(self) -> dict[str, float]:
        """🎰 STATISTIQUES BANDIT CLOUD"""
        if self.total_trials == 0:
            return {"avg_reward": 0.0, "trials": 0, "ucb_score": float("inf")}

        avg_reward = self.total_reward / self.total_trials
        return {"avg_reward": avg_reward, "trials": self.total_trials, "ucb_score": avg_reward}

    def get_neural_metrics(self) -> dict[str, Any]:
        """📊 MÉTRIQUES CLOUD COMPLÈTES V2.0"""
        success_rate_raw = self.success_trials / self.total_trials if self.total_trials > 0 else 0
        avg_latency_raw = (
            sum(self.response_times) / len(self.response_times) if self.response_times else 0
        )

        current_time = time.time()
        rate_limited = current_time < self.rate_limited_until
        rate_limit_remaining = max(0, int(self.rate_limited_until - current_time))

        return {
            "synapse_type": "cloud",
            "model": self.model,
            "has_api_key": bool(self.api_key),
            "ema_success_rate": round(self.ema_success_rate, 3),
            "ema_latency_ms": round(self.ema_latency * 1000, 1),
            "raw_success_rate": round(success_rate_raw, 3),
            "raw_avg_latency_ms": round(avg_latency_raw * 1000, 1),
            "circuit_state": self.circuit_state,
            "consecutive_failures": self.consecutive_failures,
            "failure_threshold": self.failure_threshold,
            "total_trials": self.total_trials,
            "total_reward": round(self.total_reward, 2),
            "avg_reward": (
                round(self.total_reward / self.total_trials, 3) if self.total_trials > 0 else 0
            ),
            "rate_limited": rate_limited,
            "rate_limit_remaining_seconds": rate_limit_remaining,
            "quota_exhausted": self.quota_exhausted,
            "current_backoff_seconds": round(self.current_backoff, 1),
            "can_execute": self.can_execute(),
            "timeout_connect": self.timeout_connect,
            "timeout_inference": self.timeout_inference,
        }
