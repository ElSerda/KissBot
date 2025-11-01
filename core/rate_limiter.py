"""
RateLimiter - Protection contre les bans Twitch

Limite les messages par channel selon les quotas Twitch:
- Non-verifie: 18 messages / 30 secondes
- Verifie: 90 messages / 30 secondes
- Moderateur: 100 messages / 30 secondes
"""
import logging
import time
from collections import defaultdict, deque
from typing import Dict, Deque

LOGGER = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter par channel avec fenetre glissante."""
    
    def __init__(
        self,
        per30_non_verified: int = 18,
        per30_verified: int = 90,
        per30_mod: int = 100
    ):
        self.per30_non_verified = per30_non_verified
        self.per30_verified = per30_verified
        self.per30_mod = per30_mod
        self._history: Dict[str, Deque[float]] = defaultdict(deque)
        
        LOGGER.info(
            f"RateLimiter init: {per30_non_verified}/{per30_verified}/{per30_mod} "
            "messages per 30s"
        )
        
    def can_send(
        self,
        channel_id: str,
        cost: int = 1,
        is_mod: bool = False,
        is_verified: bool = False
    ) -> bool:
        """Verifie si on peut envoyer un message dans ce channel."""
        if is_mod:
            limit = self.per30_mod
        elif is_verified:
            limit = self.per30_verified
        else:
            limit = self.per30_non_verified
            
        hist = self._history[channel_id]
        now = time.monotonic()
        
        while hist and (now - hist[0]) > 30:
            hist.popleft()
            
        if len(hist) + cost > limit:
            LOGGER.warning(
                f"Rate limit atteint pour {channel_id}: "
                f"{len(hist)}/{limit} (cost={cost})"
            )
            return False
            
        for _ in range(cost):
            hist.append(now)
            
        return True
