#!/usr/bin/env python3
"""
LLM Handler Backend - Phase 3.2
Wrapper simple autour de l'intelligence/ existante pour MessageHandler

Includes:
- LLM usage logging (tokens in/out, latency, cost estimation)
- Integration with core/llm_usage_logger.py
"""
import logging
import time
from typing import Optional, Dict
from modules.intelligence.neural_pathway_manager import NeuralPathwayManager
from modules.intelligence.core import process_llm_request
from core.llm_usage_logger import log_llm_usage, estimate_tokens


LOGGER = logging.getLogger(__name__)


class LLMHandler:
    """
    Backend LLM pour MessageHandler (Phase 3.2)
    
    Wrapper autour de NeuralPathwayManager pour intégration propre.
    Inclut le logging automatique des appels LLM.
    """
    
    def __init__(self, config: Dict):
        """
        Args:
            config: Configuration du bot (dict depuis config.yaml)
        """
        self.config = config
        self.neural_pathway = None
        
        # Model name for logging
        llm_config = config.get("llm", {})
        self.model_name = llm_config.get("openai_model", "gpt-3.5-turbo")
        
        # Initialiser NeuralPathwayManager
        try:
            self.neural_pathway = NeuralPathwayManager(config)
            LOGGER.info("✅ LLMHandler initialized with NeuralPathwayManager")
        except Exception as e:
            LOGGER.error(f"❌ Failed to initialize NeuralPathwayManager: {e}")
            self.neural_pathway = None
    
    async def ask(
        self,
        question: str,
        user_name: str,
        channel: str,
        game_cache=None,
        channel_id: str = ""
    ) -> Optional[str]:
        """
        Pose une question au LLM.
        
        Args:
            question: Question de l'utilisateur
            user_name: Nom de l'utilisateur
            channel: Nom du channel
            game_cache: Cache des jeux (optionnel, pour contexte)
            channel_id: ID du channel pour personnalité custom
            
        Returns:
            Réponse du LLM ou None si erreur
        """
        if not self.neural_pathway:
            LOGGER.error("❌ NeuralPathwayManager not initialized")
            return None
        
        try:
            LOGGER.info(f"🧠 Processing LLM request from {user_name}: {question[:50]}...")
            
            # Start timing
            start_time = time.perf_counter()
            
            # Estimate input tokens before call
            tokens_in = estimate_tokens(question, self.model_name)
            
            # Utiliser process_llm_request (logique existante)
            response = await process_llm_request(
                llm_handler=self.neural_pathway,
                prompt=question,
                context="ask",  # Context pour !ask
                user_name=user_name,
                game_cache=game_cache,
                pre_optimized=False,  # User input brut
                channel_id=channel_id  # 🎭 Personnalité par channel
            )
            
            # Calculate latency
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            if response:
                # Estimate output tokens
                tokens_out = estimate_tokens(response, self.model_name)
                
                # Log LLM usage
                log_llm_usage(
                    channel=channel,
                    model=self.model_name,
                    feature="ask",
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    latency_ms=latency_ms
                )
                
                LOGGER.info(f"✅ LLM response generated ({len(response)} chars, {tokens_out} tokens, {latency_ms:.0f}ms)")
                return response
            else:
                LOGGER.warning("⚠️ LLM returned None")
                return None
                
        except Exception as e:
            LOGGER.error(f"❌ Error processing LLM request: {e}", exc_info=True)
            return None
    
    async def mention(
        self,
        message: str,
        user_name: str,
        channel: str,
        channel_id: str = ""
    ) -> Optional[str]:
        """
        Génère une réponse pour une mention du bot.
        
        Args:
            message: Message de l'utilisateur
            user_name: Nom de l'utilisateur
            channel: Nom du channel
            channel_id: ID du channel
            
        Returns:
            Réponse du LLM ou None
        """
        if not self.neural_pathway:
            LOGGER.error("❌ NeuralPathwayManager not initialized")
            return None
        
        try:
            start_time = time.perf_counter()
            tokens_in = estimate_tokens(message, self.model_name)
            
            response = await process_llm_request(
                llm_handler=self.neural_pathway,
                prompt=message,
                context="mention",
                user_name=user_name,
                game_cache=None,
                pre_optimized=False,
                channel_id=channel_id
            )
            
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            if response:
                tokens_out = estimate_tokens(response, self.model_name)
                
                log_llm_usage(
                    channel=channel,
                    model=self.model_name,
                    feature="mention",
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    latency_ms=latency_ms
                )
                
                return response
            return None
            
        except Exception as e:
            LOGGER.error(f"❌ Error processing mention: {e}", exc_info=True)
            return None
    
    def is_available(self) -> bool:
        """Check if LLM is properly initialized."""
        return self.neural_pathway is not None
