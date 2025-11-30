"""
!wiki command - Basic Wikipedia search

Simple Wikipedia scraping with wikipediaapi.
No advanced filtering - just search and summary.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from twitchio import Message

LOGGER = logging.getLogger(__name__)


async def wiki_command(ctx: "Message", *args):
    """
    !wiki <query> - Search Wikipedia and get summary
    
    Examples:
        !wiki artificial intelligence
        !wiki dark souls lore
        !wiki python programming
    
    Returns:
        First sentence of Wikipedia article + URL
    """
    if not args:
        await ctx.channel.send("Usage: !wiki <query>")
        return
    
    query = " ".join(args)
    
    try:
        import wikipediaapi
    except ImportError:
        await ctx.channel.send("❌ Wikipedia API not installed")
        return
    
    try:
        # Initialize Wikipedia API
        wiki = wikipediaapi.Wikipedia(
            language='en',
            user_agent='KissBot/1.0 (https://github.com/ElSerda/KissBot)'
        )
        
        # Try exact match (title case)
        page = wiki.page(query.title())
        
        if not page.exists():
            # Try lowercase
            page = wiki.page(query.lower())
        
        if not page.exists():
            # Try uppercase
            page = wiki.page(query.upper())
        
        if not page.exists():
            await ctx.channel.send(f"❌ No Wikipedia page found for '{query}'")
            return
        
        # Extract first sentence (up to 300 chars)
        summary = page.summary.split('.')[0][:300]
        if len(page.summary.split('.')[0]) > 300:
            summary += "..."
        
        # Format message
        message = f"📚 {page.title}: {summary}. | {page.fullurl}"
        
        await ctx.channel.send(message)
    
    except Exception as e:
        LOGGER.error(f"!wiki error: {e}", exc_info=True)
        await ctx.channel.send(f"❌ Wikipedia search failed: {str(e)}")


# Export
__all__ = ["wiki_command"]
