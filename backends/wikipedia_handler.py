"""
🌐 Wikipedia Handler - Basic Wikipedia search wrapper

Simple Wikipedia integration with local caching.
No semantic filtering - just basic search and cache management.

────────────────────────────────────────────────────────────────────────────────
Copyright (c) 2024-2025 ElSerda
Licensed under MIT License
────────────────────────────────────────────────────────────────────────────────
"""

import logging
import json
from pathlib import Path
from typing import Optional
import wikipediaapi

LOGGER = logging.getLogger(__name__)

# Configuration cache
CACHE_FILE = Path(__file__).parent.parent / "cache" / "wikipedia.json"
CACHE_TTL = 30 * 24 * 60 * 60  # 30 jours


# ═══════════════════════════════════════════════════════════════════════════
# Cache Management
# ═══════════════════════════════════════════════════════════════════════════

def load_cache() -> dict:
    """Charge le cache Wikipedia depuis le disque."""
    if not CACHE_FILE.exists():
        return {}
    
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        LOGGER.warning(f"⚠️ Failed to load Wikipedia cache: {e}")
        return {}


def save_cache(cache: dict) -> None:
    """Sauvegarde le cache Wikipedia sur le disque."""
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        LOGGER.warning(f"⚠️ Failed to save Wikipedia cache: {e}")


def get_cached(query: str, cache: dict) -> Optional[dict]:
    """Récupère un résultat du cache s'il existe."""
    normalized_query = query.lower().strip()
    return cache.get(normalized_query)


# ═══════════════════════════════════════════════════════════════════════════
# Wikipedia Search
# ═══════════════════════════════════════════════════════════════════════════

def search_wikipedia(query: str, lang: str = "en", max_length: int = 400) -> str:
    """
    Recherche basique sur Wikipedia avec fallback sur variations.
    
    Args:
        query: Requête de recherche
        lang: Code langue Wikipedia (fr, en, es, etc.)
        max_length: Longueur max du résumé
    
    Returns:
        String formatée prête pour IRC : "📚 Title: summary... URL" ou "❌ Not found"
    """
    # Check cache
    cache = load_cache()
    cached = get_cached(query, cache)
    if cached:
        LOGGER.debug(f"📦 Wikipedia cache hit: {query}")
        # Format from cache (full summary, not just first sentence)
        summary = cached['summary']
        if len(summary) > max_length:
            summary = summary[:max_length-3] + "..."
        return f"📚 {cached['title']}: {summary} {cached['url']} 📦"
    
    # Initialize Wikipedia API with language
    wiki = wikipediaapi.Wikipedia(
        language=lang,
        user_agent='KissBot/2.0 (https://github.com/ElSerda/KissBot)'
    )
    
    # Try common variations
    variations = [
        query.title(),                          # "dark souls" → "Dark Souls"
        query.lower(),                          # "DARK SOULS" → "dark souls"
        query.upper(),                          # "ai" → "AI"
        f"{query.title()} (disambiguation)",    # Disambiguation pages
    ]
    
    for variant in variations:
        page = wiki.page(variant)
        if page.exists():
            # Save to cache (full summary)
            result = {
                'title': page.title,
                'summary': page.summary,  # FULL summary, not truncated yet
                'url': page.fullurl,
            }
            cache[query.lower().strip()] = result
            save_cache(cache)
            
            LOGGER.info(f"✅ Wikipedia found: {page.title}")
            
            # Format and return (truncate for display)
            summary = page.summary
            if len(summary) > max_length:
                summary = summary[:max_length-3] + "..."
            return f"📚 {page.title}: {summary} {page.fullurl}"
    
    # No match found
    LOGGER.info(f"❌ No Wikipedia page found for: {query}")
    return f"❌ No Wikipedia page found for '{query}'"


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════

__all__ = [
    'search_wikipedia',
]
