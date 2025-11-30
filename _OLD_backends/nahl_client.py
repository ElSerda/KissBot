"""
NAHL v3 Client with Smart Fallback

Architecture:
1. Try NAHL API (fast, learned index) with 3-tier confidence
   - Found (d < 0.3): High confidence, use directly
   - Uncertain (0.3 ≤ d < 0.7): Low confidence, suggest to APIs
   - NotFound (d ≥ 0.7): No match, let APIs try raw query
2. Fallback to direct Steam/RAWG search
3. Auto-teach NAHL after successful API fetch

This creates a virtuous learning cycle where NAHL becomes smarter over time!
"""

import httpx
import logging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

class NAHLClient:
    """
    Client for NAHL v3 API with intelligent 3-tier confidence system
    
    Returns:
        - High confidence: Direct title match (99% accurate)
        - Low confidence: Suggestions for API validation
        - No match: Let external APIs try
    """
    
    def __init__(self, api_url: str = "http://localhost:8080"):
        self.api_url = api_url
        self.client = httpx.AsyncClient(timeout=0.5)  # 500ms timeout
        self._api_available = None  # Cache API availability
    
    async def search(self, query: str, limit: int = 5) -> Optional[Dict]:
        """
        Search for game title using NAHL API with 3-tier confidence
        
        Returns:
            - {"confidence": "high", "title": "..."} → Use directly
            - {"confidence": "low", "suggestions": [...]} → Validate with APIs
            - None → NAHL has no useful info, try APIs with raw query
        """
        # Skip API if we know it's down
        if self._api_available == False:
            logger.debug("NAHL API unavailable, skipping")
            return None
        
        try:
            resp = await self.client.get(
                f"{self.api_url}/v1/search",
                params={"q": query, "limit": limit}
            )
            
            if resp.status_code == 200:
                self._api_available = True
                data = resp.json()
                results = data.get("results", [])
                
                if not results:
                    logger.debug(f"🚫 NAHL: No results for '{query}'")
                    return None
                
                best = results[0]
                distance = best["distance"]
                status = best["status"]
                
                # HIGH CONFIDENCE: Found with strict matching (d < 0.3)
                if status == "Found" and distance < 0.3:
                    logger.info(
                        f"✅ NAHL MATCH: '{query}' → '{best['title']}' "
                        f"(d={distance:.3f}, {data.get('took_ms', 0):.2f}ms)"
                    )
                    return {
                        "confidence": "high",
                        "title": best["title"],
                        "distance": distance,
                        "took_ms": data.get("took_ms", 0)
                    }
                
                # LOW CONFIDENCE: Uncertain matches, provide suggestions
                elif status == "Uncertain" and distance < 0.7:
                    suggestions = [r["title"] for r in results[:min(3, len(results))]]
                    logger.debug(
                        f"⚠️  NAHL UNCERTAIN: '{query}' → suggestions: {suggestions} "
                        f"(best d={distance:.3f})"
                    )
                    return {
                        "confidence": "low",
                        "suggestions": suggestions,
                        "distance": distance
                    }
                
                # NO GOOD MATCH: Let APIs try raw query
                else:
                    logger.debug(
                        f"🚫 NAHL NOT FOUND: '{query}' → best match: '{best['title']}' "
                        f"(d={distance:.3f}, status={status})"
                    )
                    return None
            
            logger.warning(f"NAHL API error: {resp.status_code}")
            return None
            
        except httpx.TimeoutException:
            logger.debug(f"NAHL API timeout for '{query}'")
            self._api_available = False
            return None
        except Exception as e:
            logger.debug(f"NAHL API error: {e}")
            self._api_available = False
            return None
    
    async def add_game(self, title: str) -> bool:
        """
        Add game to NAHL index (after successful API fetch)
        
        Returns:
            True if successfully added
        """
        if self._api_available == False:
            return False
        
        try:
            resp = await self.client.post(
                f"{self.api_url}/v1/add",
                json={"title": title},
                timeout=1.0
            )
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    logger.info(f"📚 Taught NAHL: '{title}' (index size: {data['new_index_size']})")
                    return True
            
            return False
            
        except Exception as e:
            logger.debug(f"Failed to teach NAHL: {e}")
            return False
    
    async def close(self):
        """Cleanup"""
        await self.client.aclose()
