"""
Moderation Module - Outils de modération automatisés

Contient:
- BanWordManager: Gestion des mots bannis par channel (auto-ban)
- (Future) TimeoutManager: Timeouts automatiques
- (Future) BlocklistManager: Blocklist par channel

Usage:
    from modules.moderation import get_banword_manager
    
    manager = get_banword_manager()
    manager.add_banword("channel", "spamword", "mod_username")
"""

from .banword_manager import BanWordManager, get_banword_manager

__all__ = [
    "BanWordManager",
    "get_banword_manager",
]
