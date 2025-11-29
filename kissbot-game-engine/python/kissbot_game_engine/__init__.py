"""
KissBot Game Engine - Python Bindings

High-performance game search engine powered by Rust.

Example:
    >>> import kissbot_game_engine
    >>> engine = kissbot_game_engine.GameEngine("kissbot.db")
    >>> result = engine.search("vampire survivors", max_results=5)
    >>> print(result['game']['name'])
    Vampire Survivors
"""

from .kissbot_game_engine import GameEngine, __version__

__all__ = ["GameEngine", "__version__"]
