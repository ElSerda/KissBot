"""
Compatibility shim for anti_automod.
The actual implementation is in web/core/anti_automod.py
This file maintains backwards compatibility for existing imports.
"""

from web.core.anti_automod import (
    AntiAutoModFormatter,
    get_anti_automod_formatter,
)

__all__ = [
    "AntiAutoModFormatter",
    "get_anti_automod_formatter",
]


def should_reformat_message(text: str, min_safety_score: int = 70):
    """
    Determine if message should be reformatted.
    
    This is a convenience function that wraps get_anti_automod_formatter().
    """
    formatter = get_anti_automod_formatter()
    return formatter.should_reformat_message(text, min_safety_score)
