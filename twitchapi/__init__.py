"""
twitchapi/
==========

Module dédié à TOUTE la gestion de l'API Twitch.

Organisation:
- auth_manager.py : Gestion des tokens utilisateurs (bot + broadcasters)
- scope_validator.py : Validation des permissions Twitch
- transports/ : Clients API Twitch
  - helix_readonly.py : Helix avec App Token (lecture seule)
  - irc_client.py : IRC Twitch (chat)

Philosophie:
- Séparation claire : core/ = bot logic, twitchapi/ = Twitch-specific
- Réutilisable : Facilite l'ajout de kickapi/, discordapi/, etc.
- Testable : Code Twitch isolé = mocking facile
"""

from twitchapi.auth_manager import AuthManager, TokenInfo

__all__ = ["AuthManager", "TokenInfo"]
