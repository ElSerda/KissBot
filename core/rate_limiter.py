"""
Rate Limiter - Gestion cooldowns par utilisateur
"""

import time


class RateLimiter:
    """Rate limiter simple par utilisateur."""

    def __init__(self, default_cooldown: float = 3.0):
        self.default_cooldown = default_cooldown
        self.last_request: dict[str, float] = {}  # {user_id: timestamp}

    def is_allowed(self, user_id: str, cooldown: float | None = None) -> bool:
        """Vérifie si l'utilisateur peut faire une requête."""
        current_time = time.time()
        effective_cooldown = cooldown or self.default_cooldown

        if user_id not in self.last_request:
            self.last_request[user_id] = current_time
            return True

        time_since_last = current_time - self.last_request[user_id]

        if time_since_last >= effective_cooldown:
            self.last_request[user_id] = current_time
            return True

        return False

    def get_remaining_cooldown(self, user_id: str, cooldown: float | None = None) -> float:
        """Retourne le temps de cooldown restant."""
        if user_id not in self.last_request:
            return 0.0

        effective_cooldown = cooldown or self.default_cooldown
        elapsed = time.time() - self.last_request[user_id]
        remaining = max(0, effective_cooldown - elapsed)

        return remaining
