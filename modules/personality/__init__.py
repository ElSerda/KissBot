"""
🎭 Personality Module - Personnalisation du ton par channel

Permet aux broadcasters de choisir le ton du bot sur leur chaîne:
- !kbpersona <preset> : Change le preset
- !kbpersona : Affiche le preset actuel
- !kbpersona list : Liste les presets disponibles
- !kbnsfw on/off : Active/désactive le mode 18+

Presets disponibles:
- soft : Sympa et bienveillant
- normal : Équilibré (défaut)
- spicy : Sarcastique et piquant
- unhinged : Full déglingué (18+ requis)
- gamer : 100% gaming vibes
- uwu : Kawaii anime style
"""

from .presets import (
    PERSONALITY_PRESETS,
    DEFAULT_PRESET,
    get_preset,
    get_system_prompt,
    list_presets,
    format_preset_list,
    SAFE_PRESETS,
    NSFW_PRESETS
)

from .store import (
    PersonalityStore,
    ChannelPersonality,
    get_personality_store
)

__all__ = [
    "PERSONALITY_PRESETS",
    "DEFAULT_PRESET", 
    "get_preset",
    "get_system_prompt",
    "list_presets",
    "format_preset_list",
    "SAFE_PRESETS",
    "NSFW_PRESETS",
    "PersonalityStore",
    "ChannelPersonality",
    "get_personality_store"
]
