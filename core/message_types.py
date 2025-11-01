"""
📦 Message Types - DTOs pour le système de messaging

Contrats de données entre transports et logique métier.
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class ChatMessage:
    """Message entrant (chat IRC, EventSub, etc.)"""
    channel: str                    # Nom du channel (sans #)
    channel_id: str                 # ID Twitch du broadcaster
    user_login: str                 # Login de l'utilisateur
    user_id: str                    # ID Twitch de l'utilisateur
    text: str                       # Contenu du message
    is_mod: bool = False            # Est modérateur
    is_broadcaster: bool = False    # Est le broadcaster
    is_vip: bool = False            # Est VIP
    transport: str = "unknown"      # Source: "irc", "eventsub", "helix"
    badges: Dict[str, str] = field(default_factory=dict)  # Badges Twitch
    meta: Dict[str, Any] = field(default_factory=dict)    # Données supplémentaires


@dataclass
class OutboundMessage:
    """Message sortant (à envoyer dans le chat)"""
    channel: str                    # Nom du channel (sans #)
    channel_id: str                 # ID Twitch du broadcaster
    text: str                       # Contenu du message
    prefer: str = "auto"            # "helix", "irc", "auto" (routing intelligent)
    reply_to: Optional[str] = None  # ID du message parent (pour reply)
    meta: Dict[str, Any] = field(default_factory=dict)    # Données supplémentaires


@dataclass
class SystemEvent:
    """Événement système (EventSub, reconnect, erreurs, etc.)"""
    kind: str                       # Type: "eventsub.follow", "irc.reconnect", etc.
    payload: Dict[str, Any]         # Données de l'événement
    timestamp: float = 0.0          # Timestamp
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            import time
            self.timestamp = time.time()
