"""
Command Rate Limiter - Protection APIs externes (IGDB/RAWG/Steam)

Limite les commandes par utilisateur ET par channel:
- Per user: 1 commande / 2 secondes (évite spam individuel)
- Per channel: burst 5 puis 1/s (évite flood collectif)

Utilisé par: !gi, !gc, !wiki, etc.
"""
import logging
import time
from collections import defaultdict
from typing import Dict, List, Tuple

LOGGER = logging.getLogger(__name__)


class CommandRateLimiter:
    """
    Rate limiter pour commandes utilisateur avec double protection.
    
    Stratégie:
    1. Per-user: 1 cmd/2s (anti-spam individuel)
    2. Per-channel: burst 5 puis 1/s (anti-flood collectif)
    """
    
    def __init__(
        self,
        user_cooldown: float = 2.0,      # Cooldown par user (secondes)
        channel_burst: int = 5,           # Burst autorisé per channel
        channel_rate: float = 1.0         # Rate après burst (cmd/s)
    ):
        self.user_cooldown = user_cooldown
        self.channel_burst = channel_burst
        self.channel_rate = channel_rate
        
        # Structure: {user_id: last_command_timestamp}
        self._user_history: Dict[str, float] = {}
        
        # Structure: {channel_id: [timestamps]}
        self._channel_history: Dict[str, List[float]] = defaultdict(list)
        
        LOGGER.info(
            f"CommandRateLimiter init: user={user_cooldown}s cooldown, "
            f"channel=burst {channel_burst} then {channel_rate}/s"
        )
    
    def can_execute(
        self,
        user_id: str,
        channel_id: str,
        command_name: str = "command"
    ) -> Tuple[bool, str]:
        """
        Vérifie si l'utilisateur peut exécuter la commande.
        
        Args:
            user_id: ID Twitch de l'utilisateur
            channel_id: ID du channel Twitch
            command_name: Nom de la commande (pour logs)
        
        Returns:
            (can_execute: bool, error_message: str)
        """
        now = time.monotonic()
        
        # ──────────────────────────────────────────────────────────────────
        # CHECK 1: Rate-limit per user (cooldown 2s)
        # ──────────────────────────────────────────────────────────────────
        if user_id in self._user_history:
            last_cmd = self._user_history[user_id]
            time_since = now - last_cmd
            
            if time_since < self.user_cooldown:
                wait_time = self.user_cooldown - time_since
                LOGGER.debug(
                    f"⏱️ User {user_id} rate-limited: "
                    f"{time_since:.1f}s < {self.user_cooldown}s cooldown"
                )
                return False, f"⏱️ Trop rapide ! Réessaye dans {wait_time:.0f}s"
        
        # ──────────────────────────────────────────────────────────────────
        # CHECK 2: Rate-limit per channel (burst + sustained rate)
        # ──────────────────────────────────────────────────────────────────
        channel_hist = self._channel_history[channel_id]
        
        # Cleanup: enlever timestamps > 10s (sliding window)
        channel_hist[:] = [ts for ts in channel_hist if (now - ts) < 10.0]
        
        # Calculer combien de commandes dans la dernière seconde
        recent_count = sum(1 for ts in channel_hist if (now - ts) < 1.0)
        
        # Si < burst → OK
        if len(channel_hist) < self.channel_burst:
            # Phase burst: autoriser
            pass
        else:
            # Phase sustained: max 1/s
            if recent_count >= self.channel_rate:
                LOGGER.debug(
                    f"⏱️ Channel {channel_id} rate-limited: "
                    f"{recent_count} cmds/s >= {self.channel_rate}/s"
                )
                return False, f"⏱️ Channel busy, réessaye dans 1s"
        
        # ──────────────────────────────────────────────────────────────────
        # OK: Enregistrer et autoriser
        # ──────────────────────────────────────────────────────────────────
        self._user_history[user_id] = now
        channel_hist.append(now)
        
        LOGGER.debug(
            f"✅ {command_name} allowed: user={user_id}, "
            f"channel={channel_id} ({len(channel_hist)} cmds in window)"
        )
        
        return True, ""
    
    def reset_user(self, user_id: str):
        """Reset le cooldown d'un utilisateur (admin override)."""
        if user_id in self._user_history:
            del self._user_history[user_id]
            LOGGER.info(f"🔓 Rate-limit reset for user {user_id}")
    
    def reset_channel(self, channel_id: str):
        """Reset l'historique d'un channel (admin override)."""
        if channel_id in self._channel_history:
            del self._channel_history[channel_id]
            LOGGER.info(f"🔓 Rate-limit reset for channel {channel_id}")
    
    def cleanup_old_entries(self, max_age: float = 300.0):
        """
        Cleanup périodique des vieilles entrées (évite memory leak).
        
        Appeler périodiquement (ex: toutes les 5 minutes).
        
        Args:
            max_age: Age maximum des entrées (secondes)
        """
        now = time.monotonic()
        
        # Cleanup user history
        old_users = [
            uid for uid, ts in self._user_history.items()
            if (now - ts) > max_age
        ]
        for uid in old_users:
            del self._user_history[uid]
        
        # Cleanup channel history
        old_channels = []
        for cid, hist in self._channel_history.items():
            hist[:] = [ts for ts in hist if (now - ts) < max_age]
            if not hist:
                old_channels.append(cid)
        
        for cid in old_channels:
            del self._channel_history[cid]
        
        if old_users or old_channels:
            LOGGER.debug(
                f"🧹 Cleanup: removed {len(old_users)} users, "
                f"{len(old_channels)} channels from rate-limiter"
            )
    
    def get_stats(self) -> Dict[str, int]:
        """Stats pour monitoring."""
        return {
            "tracked_users": len(self._user_history),
            "tracked_channels": len(self._channel_history),
            "total_window_cmds": sum(
                len(hist) for hist in self._channel_history.values()
            )
        }
