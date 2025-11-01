"""
🚌 MessageBus - Système de pub/sub interne

Découple les transports de la logique métier.
Fire-and-forget pour éviter les blocages.
"""
import asyncio
import logging
from typing import Callable, Dict, List, Any

LOGGER = logging.getLogger(__name__)


class MessageBus:
    """Bus de messages asynchrone simple (pub/sub)"""
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._task_group: List[asyncio.Task] = []
        
    def subscribe(self, topic: str, handler: Callable):
        """
        Abonne un handler à un topic.
        
        Args:
            topic: Nom du topic ("chat.inbound", "chat.outbound", etc.)
            handler: Fonction async qui traite les messages
        """
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(handler)
        LOGGER.info(f"📌 Subscriber ajouté: {topic} -> {handler.__name__}")
        
    async def publish(self, topic: str, data: Any):
        """
        Publie un message sur un topic (fire-and-forget).
        
        Args:
            topic: Nom du topic
            data: Données à publier (ChatMessage, OutboundMessage, etc.)
        """
        handlers = self._subscribers.get(topic, [])
        
        if not handlers:
            LOGGER.debug(f"⚠️ MessageBus: Aucun subscriber pour topic: {topic}")
            return
            
        LOGGER.debug(f"📤 MessageBus: Publish [{topic}] vers {len(handlers)} handlers")
        
        # Fire-and-forget: créer des tasks sans await
        for handler in handlers:
            try:
                LOGGER.debug(f"   ↳ Création task pour handler: {handler.__name__}")
                task = asyncio.create_task(self._safe_handle(handler, data, topic))
                self._task_group.append(task)
                # Nettoyage auto des tasks terminées
                task.add_done_callback(lambda t: self._task_group.remove(t) if t in self._task_group else None)
            except Exception as e:
                LOGGER.error(f"❌ Erreur création task pour {handler.__name__}: {e}")
                
    async def _safe_handle(self, handler: Callable, data: Any, topic: str):
        """Wrapper sécurisé pour exécuter les handlers"""
        try:
            await handler(data)
        except Exception as e:
            LOGGER.error(f"❌ Erreur handler {handler.__name__} sur topic {topic}: {e}", exc_info=True)
            
    async def wait_all(self):
        """Attend que toutes les tasks en cours se terminent"""
        if self._task_group:
            LOGGER.info(f"⏳ Attente de {len(self._task_group)} tasks...")
            await asyncio.gather(*self._task_group, return_exceptions=True)
            
    def get_stats(self) -> Dict[str, int]:
        """Retourne les stats du bus"""
        return {
            "topics": len(self._subscribers),
            "subscribers": sum(len(h) for h in self._subscribers.values()),
            "active_tasks": len(self._task_group)
        }
