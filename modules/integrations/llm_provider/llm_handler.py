#!/usr/bin/env python3
"""
LLM Handler Backend - Phase 3.2
Wrapper simple autour de l'intelligence/ existante pour MessageHandler
"""
import logging
from typing import Optional, Dict
from modules.intelligence.neural_pathway_manager import NeuralPathwayManager
from modules.intelligence.core import process_llm_request


LOGGER = logging.getLogger(__name__)


class LLMHandler:
    """
    Backend LLM pour MessageHandler (Phase 3.2)
    
    Wrapper autour de NeuralPathwayManager pour intégration propre.
    """
    
    def __init__(self, config: Dict):
        """
        Args:
            config: Configuration du bot (dict depuis config.yaml)
        """
        self.config = config
        self.neural_pathway = None
        
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
            
            if response:
                LOGGER.info(f"✅ LLM response generated ({len(response)} chars)")
                return response
            else:
                LOGGER.warning("⚠️ LLM returned None")
                return None
                
        except Exception as e:
            LOGGER.error(f"❌ Error processing LLM request: {e}", exc_info=True)
            return None
    
    def is_available(self) -> bool:
        """Check if LLM is properly initialized."""
        return self.neural_pathway is not None
