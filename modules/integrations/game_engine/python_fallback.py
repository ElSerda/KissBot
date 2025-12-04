"""
Game Lookup with API Cascade + DRAKON Ranking

Architecture:
- Steam/RAWG/IGDB APIs fetch multiple raw results (5 candidates)
- DRAKON (Rust Δₛ³ V3) ranks candidates by fuzzy match quality (0.3ms)
- Return best match based on DRAKON scoring
- Redis cache for results (shared across all bots)

Flow:
1. User query → Steam/RAWG/IGDB API → 5 raw game results
2. DRAKON fuzzy match: query vs each candidate title → scores
3. Pick candidate with best DRAKON score (highest similarity)
4. Enrich metadata from selected candidate
5. Cache result (shared across all bots)

Performance:
- API fetch: 200-500ms (Steam/RAWG/IGDB search)
- DRAKON ranking: 0.3ms (5 candidates × 0.06ms each)
- Total: 200-700ms (dominated by API latency)

DRAKON Role: RANKING/FILTERING API results, NOT a dataset source!
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Any

import httpx


class SearchResultType(Enum):
    """Types de résultats de recherche pour réponses intelligentes du chatbot."""
    NO_API_RESULTS = "no_api_results"  # Aucune API n'a retourné de résultats
    NO_MATCH = "no_match"  # APIs ont des résultats mais aucun match après ranking
    SINGLE_RESULT = "single_result"  # 1 seul résultat trouvé
    MULTIPLE_RESULTS = "multiple_results"  # Plusieurs résultats (possible typo)
    SUCCESS = "success"  # Match unique et confiant


@dataclass
class SearchResponse:
    """Réponse enrichie avec contexte pour le chatbot."""
    result_type: SearchResultType
    best_match: Optional['GameResult'] = None
    alternatives: list['GameResult'] = None
    total_candidates: int = 0
    
    def __post_init__(self):
        if self.alternatives is None:
            self.alternatives = []

# Import optionnel de CacheManager
CacheManager: Optional[Any] = None
try:
    from core.cache import CacheManager as _CacheManager
    CacheManager = _CacheManager
except ImportError:
    pass

# Import NAHL client
from modules.integrations.nahl.nahl_client import NAHLClient
# Optional DRAKON HTTP API client (fast fuzzy search)
DrakonHTTPClient = None
try:
    from modules.integrations.game_lookup_drakon import DrakonClient as _DrakonClient
    DrakonHTTPClient = _DrakonClient
except Exception:
    # Not available or not desired
    DrakonHTTPClient = None


@dataclass
class GameResult:
    """Résultat de jeu avec validation de fiabilité et données enrichies."""
    name: str
    year: str = "?"
    rating_rawg: float = 0.0
    ratings_count: int = 0
    metacritic: int | None = None
    steam_reviews: str | None = None
    platforms: list[str] | None = None
    genres: list[str] | None = None
    developers: list[str] | None = None
    publishers: list[str] | None = None
    playtime: int = 0
    popularity: int = 0
    esrb_rating: str = ""
    is_early_access: bool = False
    summary: str | None = None
    description_raw: str | None = None
    reliability_score: float = 0.0
    confidence: str = "LOW"
    source_count: int = 1
    primary_source: str = "unknown"
    api_sources: list[str] | None = None
    possible_typo: bool = False

    def __post_init__(self):
        if self.platforms is None:
            self.platforms = []
        if self.genres is None:
            self.genres = []
        if self.developers is None:
            self.developers = []
        if self.publishers is None:
            self.publishers = []
        if self.api_sources is None:
            self.api_sources = []


class GameLookup:
    """
    Game lookup using API results ranked by DRAKON fuzzy matching.
    
    Architecture:
        1. Query → Steam/RAWG → Multiple raw results (5 candidates)
        2. DRAKON ranks candidates by fuzzy match score (0.3ms)
        3. Pick best candidate based on DRAKON scoring
        4. Return enriched metadata for best match
        5. Cache result → Shared across all bots
    
    DRAKON Advantages:
        - Ranks API results by fuzzy similarity (Δₛ³ V3)
        - 0.06ms per candidate (5 candidates = 0.3ms total)
        - Handles typos, abbreviations, variations
        - CPU-only (10 MB RAM, no GPU)
    
    Fallback: NAHL v3 for ranking when DRAKON unavailable
    """

    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Performance tracking (microsecond precision)
        from core.performance_tracker import PerformanceTracker
        self.perf = PerformanceTracker()

        # HTTP client avec timeout
        apis_config = config.get("apis", {})
        api_timeout = apis_config.get("timeout", 10.0)
        self.http_client = httpx.AsyncClient(timeout=api_timeout)

        # NAHL v3 Client
        self.nahl = NAHLClient(api_url="http://localhost:8000")
        
        # DatabaseManager for intelligent game cache
        try:
            from database.manager import DatabaseManager
            db_path = config.get('db_path', 'kissbot.db')
            self.db = DatabaseManager(db_path=db_path)
            self.logger.info(f"💾 Game cache enabled (SQLite): {db_path}")
        except Exception as e:
            self.db = None
            self.logger.warning(f"⚠️  DatabaseManager unavailable - cache disabled: {e}")
        
        # Legacy CacheManager (optionnel, pour compatibilité)
        if CacheManager is not None:
            self.cache = CacheManager(config)
        else:
            self.cache = None

        # API keys
        self.rawg_key = apis_config.get("rawg_key")
        self.steam_key = apis_config.get("steam_key")
        self.igdb_client_id = apis_config.get("igdb_client_id")
        self.igdb_client_secret = apis_config.get("igdb_client_secret")

        # Initialize providers (modular API backends)
        from modules.integrations.game_engine.providers import SteamProvider, IGDBProvider, RAWGProvider
        self.providers = []
        
        if self.steam_key or True:  # Steam store search doesn't need key
            self.providers.append(SteamProvider(self.http_client, self.steam_key))
            self.logger.info("✅ SteamProvider initialized (weight: 0.40)")
        
        if self.igdb_client_id and self.igdb_client_secret:
            self.providers.append(IGDBProvider(self.http_client, self.igdb_client_id, self.igdb_client_secret))
            self.logger.info("✅ IGDBProvider initialized (weight: 0.35)")
        
        if self.rawg_key:
            self.providers.append(RAWGProvider(self.http_client, self.rawg_key))
            self.logger.info("✅ RAWGProvider initialized (weight: 0.25)")
        
        if not self.providers:
            raise ValueError("At least one game provider must be configured")

        # Background executor for async cache writes (shared, not recreated each time)
        import concurrent.futures
        self._cache_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, 
            thread_name_prefix="cache_writer"
        )

        # DRAKON HTTP API (optional fast path)
        drakon_cfg = config.get("drakon", {})
        self.use_drakon = bool(drakon_cfg.get("enabled", False))
        self.drakon_url = drakon_cfg.get("url", "http://127.0.0.1:8080")
        if self.use_drakon:
            self.logger.info(f"🐉 DRAKON HTTP API enabled: {self.drakon_url}")
        
        if not self.rawg_key:
            raise ValueError("RAWG API key manquante dans config")

    def _is_acronym(self, query: str) -> bool:
        """
        Detect if query is likely an acronym or multi-part acronym.
        
        Heuristics:
        - Single acronym: 2-6 chars, no spaces (e.g., "gta", "botw")
        - Multi-part acronym: 2-3 parts, each 1-4 chars (e.g., "gta sa", "cod mw", "loz botw")
        - All alphabetic (lowercase or uppercase)
        
        Examples: "gta", "GTA", "botw", "gta sa", "cod mw", "loz botw"
        """
        q = query.strip().lower()
        
        # No spaces: single acronym (2-6 chars)
        if ' ' not in q:
            return 2 <= len(q) <= 6 and q.isalpha()
        
        # With spaces: check if multi-part acronym
        parts = q.split()
        if len(parts) > 3:  # Too many parts, probably not acronym
            return False
        
        # Each part should be short (1-4 chars) and alphabetic
        return all(1 <= len(part) <= 4 and part.isalpha() for part in parts)
    
    def _acronym_match(self, acronym: str, title: str) -> float:
        """
        Check if acronym matches title (initials of words in order, flexible positioning).
        
        Algorithm:
        - Extract first letter of EVERY word in title (no filtering!)
        - Search for acronym letters in ORDER (but not necessarily consecutive)
        - Score based on match position: prefix > substring > flexible
        
        Examples:
        - "gta" vs "Grand Theft Auto" → [G][T][A] consecutive → 1.0 ✅
        - "gta" vs "Grand Turismo Arena" → [G]...[T]...[A] in order → 1.0 ✅
        - "gta" vs "Great Tactical Adventure" → [G]...[T]...[A] in order → 1.0 ✅
        - "gta sa" vs "Grand Theft Auto: San Andreas" → [G][T][A][S][A] → 1.0 ✅
        - "cod mw" vs "Call of Duty: Modern Warfare" → [C][O][D][M][W] → 1.0 ✅
        - "gta" vs "The Grand Adventure" → [T][G][A] wrong order → 0.0 ❌
        
        Args:
            acronym: Short query (e.g., "gta", "gta sa", "cod mw")
            title: Full game title (e.g., "Grand Theft Auto V")
        
        Returns:
            1.0 if perfect match (consecutive from start)
            0.95 if substring match (consecutive anywhere)
            0.90 if flexible match (in order, not consecutive)
            0.0 if no match or wrong order
        """
        # Normalize: remove spaces from acronym to get continuous string
        acronym_normalized = acronym.lower().strip().replace(' ', '')
        
        # Extract ALL words (no filtering - keep "of", "the", etc.!)
        words = title.lower().split()
        
        # Extract initials from ALL words
        initials = ''.join(w[0] for w in words if len(w) > 0 and w[0].isalpha())
        
        # Strategy 1: Check if acronym matches initials (prefix match, consecutive)
        if initials.startswith(acronym_normalized):
            return 1.0
        
        # Strategy 2: Check if acronym matches ANY consecutive sequence
        for i in range(len(initials) - len(acronym_normalized) + 1):
            if initials[i:i+len(acronym_normalized)] == acronym_normalized:
                return 0.95  # Slightly lower score for non-prefix match
        
        # Strategy 3: FLEXIBLE MATCHING - letters in order but not consecutive
        # Example: "gta" matches "Grand Turismo Arena" → G...T...A
        acronym_idx = 0
        initials_idx = 0
        
        while acronym_idx < len(acronym_normalized) and initials_idx < len(initials):
            if initials[initials_idx] == acronym_normalized[acronym_idx]:
                acronym_idx += 1  # Found this letter, move to next
            initials_idx += 1  # Always advance in initials
        
        # If we found ALL acronym letters in order
        if acronym_idx == len(acronym_normalized):
            return 0.90  # Lower score for flexible (non-consecutive) match
        
        return 0.0
    
    def _title_similarity(self, title1: str, title2: str) -> float:
        """
        Calculate title similarity with DRAKON Δₛ³ V3 enhancements.
        
        Features:
        - Exact match: 1.0
        - Substring match: 0.9
        - Acronym match: 1.0 (e.g., "gta" → "Grand Theft Auto")
        - Token overlap: Jaccard similarity
        
        Args:
            title1: Query (potentially acronym)
            title2: Candidate title from API
        
        Returns:
            Similarity score [0.0, 1.0]
        """
        t1 = title1.lower().strip()
        t2 = title2.lower().strip()
        
        # Exact match
        if t1 == t2:
            return 1.0
        
        # Acronym detection and matching (NEW!)
        if self._is_acronym(t1):
            acronym_score = self._acronym_match(t1, t2)
            if acronym_score > 0:
                return acronym_score
        
        # Substring match
        if t1 in t2 or t2 in t1:
            return 0.9
        
        # Fuzzy match pour gérer les typos (NEW!)
        # Utilise rapidfuzz pour comparer les titres complets
        from rapidfuzz import fuzz
        fuzzy_score = fuzz.ratio(t1, t2) / 100.0
        
        # Si le fuzzy match est bon (>80%), utiliser ce score
        if fuzzy_score >= 0.8:
            return fuzzy_score
        
        # Token overlap (simple Jaccard) pour les cas restants
        tokens1 = set(t1.split())
        tokens2 = set(t2.split())
        
        if not tokens1 or not tokens2:
            return 0.0
        
        intersection = tokens1 & tokens2
        union = tokens1 | tokens2
        
        return len(intersection) / len(union) if union else 0.0

    async def _fetch_multiple_candidates(self, query: str, limit: int = 5) -> list[dict]:
        """
        Fetch multiple game candidates from Steam/RAWG/IGDB APIs (parallel).
        
        Strategy: Fetch 5 results from EACH API (15 total), then DRAKON ranks all!
        
        Args:
            query: User search query
            limit: Candidates per API (default: 5 per API = 15 total)
        
        Returns:
            List of candidate dicts with keys: name, api_data, source
            Returns up to limit*3 candidates (IGDB + Steam + RAWG)
        """
        # Use providers instead of legacy methods
        search_tasks = []
        for provider in self.providers:
            if provider.is_available():
                search_tasks.append(provider.search(query, limit))
            else:
                # Provider not available, add empty list placeholder
                search_tasks.append(asyncio.sleep(0, result=[]))
        
        # Wait for all results (parallel = fast!)
        provider_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        # Combine ALL results (prioritize by provider weight: IGDB > Steam > RAWG)
        candidates = []
        for i, provider in enumerate(self.providers):
            results = provider_results[i]
            
            # Handle exceptions
            if isinstance(results, Exception):
                self.logger.warning(f"{provider.name.upper()} provider failed: {results}")
                continue
            
            # Results are already in dict format from providers
            candidates.extend(results)
        
        # Return ALL candidates for DRAKON ranking (up to 15)
        self.logger.debug(f"Fetched {len(candidates)} total candidates from {len(self.providers)} providers")
        return candidates
    async def _rank_with_drakon(self, query: str, candidates: list[dict]) -> Optional[dict]:
        """
        Use DRAKON-like fuzzy matching to rank candidates (legacy, retourne seulement le meilleur).
        
        Pour obtenir tous les candidats classés, utiliser _rank_all_with_drakon().
        """
        ranked = await self._rank_all_with_drakon(query, candidates)
        return ranked[0] if ranked else None

    async def _rank_all_with_nahl(self, query: str, candidates: list[dict]) -> list[dict]:
        """
        Fallback ranking using DRAKON HTTP API or rapidfuzz heuristic for ALL candidates.
        
        Priority:
        1. DRAKON HTTP API (if enabled and available)
        2. Rapidfuzz local fuzzy match (fallback)
        
        Args:
            query: Original user query
            candidates: List of candidate dicts
        
        Returns:
            List of candidates sorted by score (best first), with 'drakon_score' field added
        """
        if not candidates:
            return []
        
        # Try DRAKON HTTP API first if enabled
        if self.use_drakon:
            try:
                scored_candidates = await self._rank_with_drakon_http(query, candidates)
                if scored_candidates:
                    return scored_candidates
                else:
                    self.logger.warning("⚠️ DRAKON HTTP returned empty, falling back to rapidfuzz")
            except Exception as e:
                self.logger.warning(f"⚠️ DRAKON HTTP failed: {e}, falling back to rapidfuzz")
        
        # Fallback: rapidfuzz local fuzzy match
        scored_candidates = []
        
        for candidate in candidates:
            score = self._title_similarity(query, candidate["name"])
            candidate['drakon_score'] = score  # Ajouter le score
            scored_candidates.append((score, candidate))
        
        # Sort by score (descending)
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        
        if scored_candidates:
            best_score, best_candidate = scored_candidates[0]
            self.logger.info(
                f"📊 Rapidfuzz fallback: '{query}' → '{best_candidate['name']}' "
                f"(score: {best_score:.1%})"
            )
            
            # Log top 5 for debugging
            self.logger.info(f"   📋 Top 5 candidates:")
            for i, (score, cand) in enumerate(scored_candidates[:5], 1):
                self.logger.info(f"      {i}. {cand['name']} ({score:.1%})")
        
        # Return sorted list of candidates
        return [cand for _, cand in scored_candidates]
    
    async def _rank_with_drakon_http(self, query: str, candidates: list[dict]) -> list[dict]:
        """
        Use DRAKON HTTP API to rank candidates by fuzzy match quality.
        
        Args:
            query: User search query
            candidates: List of candidate dicts with 'name' field
        
        Returns:
            Sorted list of candidates with 'drakon_score' added
        """
        import httpx
        
        self.logger.debug(f"🐉 Calling DRAKON HTTP API: {self.drakon_url}/v1/rank")
        
        # Build request payload
        candidate_names = [c["name"] for c in candidates]
        
        async with httpx.AsyncClient(timeout=1.0) as client:
            response = await client.post(
                f"{self.drakon_url}/v1/rank",
                json={"query": query, "candidates": candidate_names}
            )
            response.raise_for_status()
            result = response.json()
        
        # Parse response: {"ranked": [{"name": "...", "score": 0.95}, ...], "latency_ms": 0.014}
        ranked = result.get("ranked", [])
        latency_ms = result.get("latency_ms", 0.0)
        
        if not ranked:
            return []
        
        # Match scores back to original candidates
        score_map = {item["name"]: item["score"] for item in ranked}
        
        scored_candidates = []
        for candidate in candidates:
            score = score_map.get(candidate["name"], 0.0)
            candidate['drakon_score'] = score
            scored_candidates.append((score, candidate))
        
        # Sort by score (descending)
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        
        if scored_candidates:
            best_score, best_candidate = scored_candidates[0]
            self.logger.info(
                f"🐉 DRAKON HTTP API: '{query}' → '{best_candidate['name']}' "
                f"(score: {best_score:.1%}, latency: {latency_ms:.3f}ms)"
            )
            
            # Log top 5
            self.logger.info(f"   📋 Top 5 candidates:")
            for i, (score, cand) in enumerate(scored_candidates[:5], 1):
                self.logger.info(f"      {i}. {cand['name']} ({score:.1%})")
        
        return [cand for _, cand in scored_candidates]

    async def _enrich_candidate(self, candidate: dict, language: str = "french") -> Optional[GameResult]:
        """
        Enrich candidate with MERGED metadata from all 3 APIs.
        
        NEW: Multi-source fusion for best data quality:
        - Fetches Steam + IGDB + RAWG in parallel
        - Verifies alignment (same game?)
        - Merges intelligently by field priority
        - Fallback to single source if mismatch
        
        Args:
            candidate: Candidate dict with name, api_data, source
            language: "french" or "english" for Steam API
        
        Returns:
            Complete GameResult with merged data or None
        """
        name = candidate.get("name")
        source = candidate.get("source", "unknown")
        
        self.logger.debug(f"🔄 Enriching '{name}' (source: {source})...")
        
        # Strategy: Enrich primarily from source provider, others only if source fails or for verification
        # This reduces HTTP calls from 3 to 1-2 in most cases (780ms → 260-520ms)
        try:
            with self.perf.track("http_parallel_fetch"):
                # Find source provider
                source_provider = next((p for p in self.providers if p.name == source), None)
                
                # FAST PATH: If source provider available, use it first
                if source_provider and source_provider.is_available():
                    self.logger.debug(f"🎯 Using source provider: {source}")
                    
                    # Enrich from source
                    if source_provider.name == "steam":
                        source_data = await source_provider.enrich_by_name(name, language)
                    else:
                        source_data = await source_provider.enrich_by_name(name)
                    
                    # If source enrichment succeeded with good data, use it directly
                    if source_data and source_data.summary and len(source_data.summary) > 50:
                        self.logger.info(f"✅ Single source enrichment: {source} (fast path)")
                        return source_data
                    
                    # Source data weak, fetch others for verification
                    self.logger.debug(f"⚠️  Source data weak, fetching others for verification")
                
                # SLOW PATH: Fetch all providers in parallel (fallback or verification)
                enrich_tasks = []
                for provider in self.providers:
                    if provider.is_available():
                        # SteamProvider accepts language parameter, others don't
                        if provider.name == "steam":
                            enrich_tasks.append(provider.enrich_by_name(name, language))
                        else:
                            enrich_tasks.append(provider.enrich_by_name(name))
                    else:
                        enrich_tasks.append(asyncio.sleep(0, result=None))
                
                results = await asyncio.gather(*enrich_tasks, return_exceptions=True)
            
            # Map results back to providers (steam, igdb, rawg)
            provider_data = {}
            for i, provider in enumerate(self.providers):
                result = results[i]
                if isinstance(result, Exception):
                    self.logger.warning(f"{provider.name.upper()} fetch failed: {result}")
                    provider_data[provider.name] = None
                else:
                    provider_data[provider.name] = result
            
            steam_data = provider_data.get("steam")
            igdb_data = provider_data.get("igdb")
            rawg_data = provider_data.get("rawg")
            
            # Count valid sources
            valid_sources = sum([
                steam_data is not None,
                igdb_data is not None,
                rawg_data is not None
            ])
            
            if valid_sources == 0:
                self.logger.error(f"❌ All APIs failed for '{name}'")
                return None
            
            # Single source: return directly
            if valid_sources == 1:
                result = steam_data or igdb_data or rawg_data
                self.logger.info(f"✅ Single source: {result.primary_source}")
                return result
            
            # Multiple sources: verify alignment and merge
            with self.perf.track("alignment_verify"):
                alignment_score = self._verify_game_alignment(steam_data, igdb_data, rawg_data)
            
            if alignment_score < 0.7:
                self.logger.warning(
                    f"⚠️  APIs mismatch for '{name}' (alignment: {alignment_score:.0%})"
                )
                # Fallback: pick best single source
                return self._pick_best_single_source(steam_data, igdb_data, rawg_data)
            
            # Alignment OK: merge intelligently
            self.logger.info(f"✅ Multi-source merge (alignment: {alignment_score:.0%}, sources: {valid_sources})")
            with self.perf.track("merge_results"):
                return self._merge_game_results(steam_data, igdb_data, rawg_data, language)
            
        except Exception as e:
            self.logger.error(f"❌ Enrichment failed for '{name}': {e}", exc_info=True)
            return None
    
    def _verify_game_alignment(
        self,
        steam_data: Optional[GameResult],
        igdb_data: Optional[GameResult],
        rawg_data: Optional[GameResult]
    ) -> float:
        """
        Verify that all APIs returned data for the SAME game with WEIGHTED scoring.
        
        NEW: Each API has a reliability weight:
        - Steam: 40% (reliable for PC games, weak for console-only)
        - IGDB: 35% (rich metadata, good coverage)
        - RAWG: 25% (good ratings/trends but can diverge)
        
        Compares: name, developers, publishers, year
        Returns weighted alignment score 0.0-1.0 (1.0 = perfect match)
        
        Args:
            steam_data, igdb_data, rawg_data: GameResult from each API
        
        Returns:
            Weighted alignment score (0.7+ = safe to merge)
        """
        from rapidfuzz import fuzz
        
        # API reliability weights
        API_WEIGHTS = {
            'steam': 0.40,
            'igdb': 0.35,
            'rawg': 0.25
        }
        
        sources = [s for s in [steam_data, igdb_data, rawg_data] if s is not None]
        if len(sources) < 2:
            return 1.0  # Single source, no alignment needed
        
        # Map sources to their weights
        source_map = {}
        if steam_data:
            source_map['steam'] = steam_data
        if igdb_data:
            source_map['igdb'] = igdb_data
        if rawg_data:
            source_map['rawg'] = rawg_data
        
        # Extract comparable fields with source tracking
        names = [(s.name.lower(), src) for src, s in source_map.items()]
        years = [(s.year, src) for src, s in source_map.items() if s.year and s.year != "?"]
        devs = [(set(d.lower() for d in s.developers), src) for src, s in source_map.items() if s.developers]
        pubs = [(set(p.lower() for p in s.publishers), src) for src, s in source_map.items() if s.publishers]
        
        # Field importance weights (same as before)
        FIELD_WEIGHTS = {
            'name': 0.50,
            'year': 0.20,
            'dev': 0.20,
            'pub': 0.10
        }
        
        total_weighted_score = 0.0
        total_weight = 0.0
        
        # 1. Name similarity (weighted by API reliability)
        if len(names) >= 2:
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    name_i, src_i = names[i]
                    name_j, src_j = names[j]
                    
                    # Fuzzy match
                    sim = fuzz.ratio(name_i, name_j) / 100.0
                    
                    # Weight by both field importance AND API reliability
                    pair_weight = (API_WEIGHTS[src_i] + API_WEIGHTS[src_j]) / 2
                    contribution = sim * FIELD_WEIGHTS['name'] * pair_weight
                    
                    total_weighted_score += contribution
                    total_weight += FIELD_WEIGHTS['name'] * pair_weight
        
        # 2. Year match (weighted by API reliability)
        if len(years) >= 2:
            for i in range(len(years)):
                for j in range(i + 1, len(years)):
                    year_i, src_i = years[i]
                    year_j, src_j = years[j]
                    
                    year_match = 1.0 if year_i == year_j else 0.5
                    
                    pair_weight = (API_WEIGHTS[src_i] + API_WEIGHTS[src_j]) / 2
                    contribution = year_match * FIELD_WEIGHTS['year'] * pair_weight
                    
                    total_weighted_score += contribution
                    total_weight += FIELD_WEIGHTS['year'] * pair_weight
        
        # 3. Developer overlap (weighted by API reliability)
        if len(devs) >= 2:
            for i in range(len(devs)):
                for j in range(i + 1, len(devs)):
                    dev_i, src_i = devs[i]
                    dev_j, src_j = devs[j]
                    
                    if dev_i and dev_j:
                        intersection = len(dev_i & dev_j)
                        union = len(dev_i | dev_j)
                        overlap = intersection / union if union > 0 else 0.0
                        
                        pair_weight = (API_WEIGHTS[src_i] + API_WEIGHTS[src_j]) / 2
                        contribution = overlap * FIELD_WEIGHTS['dev'] * pair_weight
                        
                        total_weighted_score += contribution
                        total_weight += FIELD_WEIGHTS['dev'] * pair_weight
        
        # 4. Publisher overlap (weighted by API reliability)
        if len(pubs) >= 2:
            for i in range(len(pubs)):
                for j in range(i + 1, len(pubs)):
                    pub_i, src_i = pubs[i]
                    pub_j, src_j = pubs[j]
                    
                    if pub_i and pub_j:
                        intersection = len(pub_i & pub_j)
                        union = len(pub_i | pub_j)
                        overlap = intersection / union if union > 0 else 0.0
                        
                        pair_weight = (API_WEIGHTS[src_i] + API_WEIGHTS[src_j]) / 2
                        contribution = overlap * FIELD_WEIGHTS['pub'] * pair_weight
                        
                        total_weighted_score += contribution
                        total_weight += FIELD_WEIGHTS['pub'] * pair_weight
        
        # Normalize by total weight
        if total_weight > 0:
            final_score = total_weighted_score / total_weight
        else:
            final_score = 0.5  # No comparable data
        
        self.logger.debug(
            f"Weighted alignment: Steam={API_WEIGHTS['steam']}, IGDB={API_WEIGHTS['igdb']}, RAWG={API_WEIGHTS['rawg']} "
            f"→ Score: {final_score:.0%}"
        )
        
        return final_score
    
    def _pick_best_single_source(
        self,
        steam_data: Optional[GameResult],
        igdb_data: Optional[GameResult],
        rawg_data: Optional[GameResult]
    ) -> Optional[GameResult]:
        """
        Pick best single source when APIs mismatch.
        
        Priority: IGDB > Steam > RAWG
        (IGDB is most canonical, Steam has FR content, RAWG is community-driven)
        
        Args:
            steam_data, igdb_data, rawg_data: GameResult from each API
        
        Returns:
            Best single source GameResult
        """
        if igdb_data:
            self.logger.info("🎯 Fallback: IGDB (canonical source)")
            return igdb_data
        elif steam_data:
            self.logger.info("🎯 Fallback: Steam (FR content)")
            return steam_data
        elif rawg_data:
            self.logger.info("🎯 Fallback: RAWG (community data)")
            return rawg_data
        else:
            return None
    
    def _merge_game_results(
        self,
        steam_data: Optional[GameResult],
        igdb_data: Optional[GameResult],
        rawg_data: Optional[GameResult],
        language: str = "french"
    ) -> GameResult:
        """
        Intelligently merge data from multiple APIs.
        
        Priority by field:
        - name: IGDB > Steam > RAWG (canonical)
        - year: IGDB > Steam > RAWG
        - summary: Steam FR > IGDB EN > RAWG EN
        - dev/pub: IGDB > Steam > RAWG (most complete)
        - rating: RAWG > Metacritic > IGDB (community-driven)
        - platforms: IGDB > Steam > RAWG
        - genres: IGDB > Steam > RAWG
        - playtime: RAWG only
        
        Args:
            steam_data, igdb_data, rawg_data: GameResult from each API
            language: "french" or "english"
        
        Returns:
            Merged GameResult with best data from all sources
        """
        # Base result (priority: IGDB > Steam > RAWG)
        base = igdb_data or steam_data or rawg_data
        
        if not base:
            return None
        
        # Merge fields with priority
        merged = GameResult(
            # Name: IGDB (most canonical)
            name=igdb_data.name if igdb_data else (steam_data.name if steam_data else rawg_data.name),
            
            # Year: IGDB > Steam > RAWG
            year=(igdb_data.year if igdb_data and igdb_data.year != "?" else
                  (steam_data.year if steam_data and steam_data.year != "?" else
                   (rawg_data.year if rawg_data else "?"))),
            
            # Summary: Steam FR > IGDB EN > RAWG EN
            summary=self._pick_best_summary(steam_data, igdb_data, rawg_data, language),
            
            # Developers: IGDB (most complete) > others
            developers=igdb_data.developers if igdb_data and igdb_data.developers else
                      (steam_data.developers if steam_data else
                       (rawg_data.developers if rawg_data else [])),
            
            # Publishers: IGDB > Steam > RAWG
            publishers=igdb_data.publishers if igdb_data and igdb_data.publishers else
                      (steam_data.publishers if steam_data else
                       (rawg_data.publishers if rawg_data else [])),
            
            # Rating: RAWG (community) > Metacritic > IGDB
            rating_rawg=rawg_data.rating_rawg if rawg_data and rawg_data.rating_rawg > 0 else
                       (steam_data.rating_rawg if steam_data else
                        (igdb_data.rating_rawg if igdb_data else 0.0)),
            
            ratings_count=rawg_data.ratings_count if rawg_data else
                         (igdb_data.ratings_count if igdb_data else 0),
            
            # Metacritic: Steam > RAWG > IGDB
            metacritic=steam_data.metacritic if steam_data and steam_data.metacritic else
                      (rawg_data.metacritic if rawg_data else
                       (igdb_data.metacritic if igdb_data else None)),
            
            # Platforms: IGDB (most accurate) > Steam > RAWG
            platforms=igdb_data.platforms if igdb_data and igdb_data.platforms else
                     (steam_data.platforms if steam_data else
                      (rawg_data.platforms if rawg_data else [])),
            
            # Genres: IGDB > Steam > RAWG
            genres=igdb_data.genres if igdb_data and igdb_data.genres else
                  (steam_data.genres if steam_data else
                   (rawg_data.genres if rawg_data else [])),
            
            # Playtime: RAWG only (unique to RAWG)
            playtime=rawg_data.playtime if rawg_data else 0,
            
            # Popularity: RAWG > IGDB
            popularity=rawg_data.popularity if rawg_data else
                      (igdb_data.popularity if igdb_data else 0),
            
            # ESRB: RAWG > Steam > IGDB
            esrb_rating=rawg_data.esrb_rating if rawg_data and rawg_data.esrb_rating else
                       (steam_data.esrb_rating if steam_data else
                        (igdb_data.esrb_rating if igdb_data else "")),
            
            # Metadata
            reliability_score=0.98,  # Multi-source = high confidence
            confidence="MULTI_SOURCE_VERIFIED",
            source_count=sum([steam_data is not None, igdb_data is not None, rawg_data is not None]),
            primary_source="multi",
            api_sources=[s.primary_source for s in [steam_data, igdb_data, rawg_data] if s]
        )
        
        self.logger.info(
            f"🔀 Merged: {merged.name} (sources: {merged.source_count}, "
            f"APIs: {','.join(merged.api_sources)})"
        )
        
        return merged
    
    def _pick_best_summary(
        self,
        steam_data: Optional[GameResult],
        igdb_data: Optional[GameResult],
        rawg_data: Optional[GameResult],
        language: str
    ) -> Optional[str]:
        """
        Pick best summary with language priority.
        
        For French: Steam FR > IGDB EN > RAWG EN
        For English: IGDB EN > Steam EN > RAWG EN
        
        Args:
            steam_data, igdb_data, rawg_data: GameResult from each API
            language: "french" or "english"
        
        Returns:
            Best summary string or None
        """
        if language == "french":
            # Priority: Steam FR (best French content)
            if steam_data and steam_data.summary and len(steam_data.summary.strip()) > 20:
                return steam_data.summary
            
            # Fallback: IGDB EN (better than nothing)
            if igdb_data and igdb_data.summary:
                return igdb_data.summary
            
            # Last resort: RAWG EN
            if rawg_data and rawg_data.summary:
                return rawg_data.summary
        else:
            # English: IGDB > Steam > RAWG
            if igdb_data and igdb_data.summary:
                return igdb_data.summary
            
            if steam_data and steam_data.summary:
                return steam_data.summary
            
            if rawg_data and rawg_data.summary:
                return rawg_data.summary
        
        return None

    async def search_game(self, game_name: str) -> GameResult | None:
        """
        Point d'entrée principal pour recherche de jeu (legacy, retourne GameResult).
        Utilise search_game_v2 en interne et retourne seulement le meilleur résultat.
        
        Pour une réponse enrichie, utiliser search_game_v2().
        """
        response = await self.search_game_v2(game_name)
        return response.best_match if response else None

    async def search_game_v2(self, game_name: str) -> SearchResponse | None:
        """
        Point d'entrée principal pour recherche de jeu avec contexte enrichi.
        
        NEW Flow with DRAKON as ranking engine:
            1. Fetch multiple candidates from Steam/RAWG/IGDB (15 results)
            2. Use DRAKON to rank candidates by fuzzy match quality
            3. Analyse les résultats pour déterminer le type de réponse:
               - NO_API_RESULTS: Aucune API n'a retourné de résultats
               - NO_MATCH: APIs ont des résultats mais aucun match après ranking
               - SUCCESS: Match unique et confiant (score > 0.85)
               - MULTIPLE_RESULTS: Plusieurs résultats proches (possible typo)
            4. Return SearchResponse avec contexte pour le chatbot
        
        Returns:
            SearchResponse avec result_type + best_match + alternatives
        """
        # Clear previous timings and start tracking
        self.perf.clear()
        
        with self.perf.track("total_search"):
            if not game_name or not game_name.strip():
                self.logger.warning("❌ Nom de jeu vide ou invalide")
                return None

            game_name = game_name.strip()

            # Step 1: Check intelligent cache (SQLite with confidence tracking)
            with self.perf.track("cache_check"):
                cached = self.db.get_cached_game(game_name.lower()) if self.db else None
            
            if cached:
                confidence = cached['confidence']
                result_type = cached['result_type']
                
                # CAS 1: Haute confiance (95%+) → Instant return
                if confidence >= 0.95:
                    with self.perf.track("cache_deserialize"):
                        self.logger.info(f"✅ Cache HIT (95%+): {game_name} (confidence: {confidence:.2f})")
                        if self.db:
                            self.db.increment_cache_hit(game_name.lower())
                        
                        # Désérialiser game_data
                        game_result = GameResult(**cached['game_data'])
                        
                        # Fix: result_type peut être "SUCCESS" (uppercase) ou "success" (lowercase)
                        try:
                            result_type_enum = SearchResultType(result_type.lower())
                        except (ValueError, AttributeError):
                            result_type_enum = SearchResultType.SUCCESS
                    
                    # Log performance report for cache hit
                    self.logger.info(f"🔬 {self.perf.get_report()}")
                    
                    return SearchResponse(
                        result_type=result_type_enum,
                        best_match=game_result,
                        alternatives=[GameResult(**alt) for alt in (cached.get('alternatives') or [])],
                        total_candidates=1
                    )
                
                # CAS 2: Bonne confiance (90-95%) → Check canonical upgrade
                elif confidence >= 0.90:
                    with self.perf.track("cache_deserialize"):
                        canonical = cached.get('canonical_query')
                        if canonical:
                            # Vérifier si version canonique existe et est meilleure
                            canonical_cached = self.db.get_cached_game(canonical)
                            if canonical_cached and canonical_cached['confidence'] > confidence:
                                self.logger.info(
                                    f"💡 Upgrade: '{game_name}' → '{canonical}' "
                                    f"({confidence:.0%} → {canonical_cached['confidence']:.0%})"
                                )
                                self.db.increment_cache_hit(canonical)
                                
                                game_result = GameResult(**canonical_cached['game_data'])
                                
                                # Fix: result_type peut être uppercase
                                try:
                                    canonical_result_type = SearchResultType(canonical_cached['result_type'].lower())
                                except (ValueError, AttributeError):
                                    canonical_result_type = SearchResultType.SUCCESS
                    
                    if canonical and canonical_cached and canonical_cached['confidence'] > confidence:
                        # Log performance report
                        self.logger.info(f"🔬 {self.perf.get_report()}")
                        return SearchResponse(
                            result_type=canonical_result_type,
                            best_match=game_result,
                            alternatives=[GameResult(**alt) for alt in (canonical_cached.get('alternatives') or [])],
                            total_candidates=1
                        )
                    
                    # Pas d'upgrade disponible, utiliser cache actuel
                    with self.perf.track("cache_deserialize"):
                        self.logger.info(f"✅ Cache HIT (90%+): {game_name} (confidence: {confidence:.2f})")
                        self.db.increment_cache_hit(game_name.lower())
                        
                        game_result = GameResult(**cached['game_data'])
                        
                        # Fix: result_type peut être uppercase
                        try:
                            result_type_enum = SearchResultType(result_type.lower())
                        except (ValueError, AttributeError):
                            result_type_enum = SearchResultType.SUCCESS
                    
                    # Log performance report
                    self.logger.info(f"🔬 {self.perf.get_report()}")
                    return SearchResponse(
                        result_type=result_type_enum,
                        best_match=game_result,
                        alternatives=[GameResult(**alt) for alt in (cached.get('alternatives') or [])],
                        total_candidates=1
                    )
                
                # CAS 3: MULTIPLE_RESULTS → Retourner alternatives
                elif result_type == 'MULTIPLE_RESULTS':
                    with self.perf.track("cache_deserialize"):
                        self.logger.info(f"🔍 Cache HIT (Multiple): {game_name}")
                        self.db.increment_cache_hit(game_name.lower())
                        
                        game_result = GameResult(**cached['game_data'])
                    
                    # Log performance report
                    self.logger.info(f"🔬 {self.perf.get_report()}")
                    return SearchResponse(
                        result_type=SearchResultType.MULTIPLE_RESULTS,
                        best_match=game_result,
                        alternatives=[GameResult(**alt) for alt in (cached.get('alternatives') or [])],
                        total_candidates=len(cached.get('alternatives') or []) + 1
                    )
                
                # CAS 4: Confiance faible (<90%) → Recheck APIs pour améliorer
                else:
                    self.logger.info(
                        f"⚠️  Cache LOW confidence ({confidence:.0%}): {game_name} → Rechecking APIs"
                    )
                    # Continue to API fetch below
            
            # Legacy cache check (fallback)
            elif self.cache:
                cached_legacy = self.cache.get(f"game:{game_name.lower()}")
                if cached_legacy:
                    self.logger.info(f"✅ Cache HIT (legacy): {game_name}")
                    # Log performance report
                    self.logger.info(f"🔬 {self.perf.get_report()}")
                    return SearchResponse(
                        result_type=SearchResultType.SUCCESS,
                        best_match=cached_legacy,
                        alternatives=[],
                        total_candidates=1
                    )

        try:
            # Step 1: Fetch multiple candidates from APIs (15 results: 5 per API)
            with self.perf.track("api_fetch_candidates"):
                candidates = await self._fetch_multiple_candidates(game_name, limit=5)
            
            if not candidates:
                self.logger.warning(f"❌ No API results for '{game_name}'")
                self.logger.info(f"🔬 {self.perf.get_report()}")
                return SearchResponse(
                    result_type=SearchResultType.NO_API_RESULTS,
                    best_match=None,
                    alternatives=[],
                    total_candidates=0
                )
            
            self.logger.info(f"📊 Fetched {len(candidates)} candidates from APIs")
            
            # Step 2: Rank candidates (DRAKON HTTP if enabled, else rapidfuzz)
            with self.perf.track("ranking_candidates"):
                ranked_candidates = await self._rank_all_with_nahl(game_name, candidates)
            
            if not ranked_candidates:
                self.logger.warning(f"❌ No suitable match after ranking for '{game_name}'")
                self.logger.info(f"🔬 {self.perf.get_report()}")
                return SearchResponse(
                    result_type=SearchResultType.NO_MATCH,
                    best_match=None,
                    alternatives=[],
                    total_candidates=len(candidates)
                )
            
            # Step 3: Analyser les scores pour déterminer le type de résultat
            best_candidate = ranked_candidates[0]
            best_score = best_candidate.get('drakon_score', 0.0)
            
            # Enrichir le meilleur résultat
            with self.perf.track("enrich_best_match"):
                result = await self._enrich_candidate(best_candidate)
            
            if not result:
                self.logger.warning(f"❌ Failed to enrich candidate: {best_candidate.get('name')}")
                self.logger.info(f"🔬 {self.perf.get_report()}")
                return SearchResponse(
                    result_type=SearchResultType.NO_MATCH,
                    best_match=None,
                    alternatives=[],
                    total_candidates=len(candidates)
                )
            
            # Analyse: Multiple résultats proches ou résultat unique ?
            # Cas 1: Plusieurs résultats avec scores très proches (écart < 0.05)
            close_matches = []
            for i, candidate in enumerate(ranked_candidates[1:5], 1):  # Check top 5
                score = candidate.get('drakon_score', 0.0)
                score_diff = best_score - score
                
                # Si l'écart est petit (< 0.05) et score décent (> 0.75), c'est ambigu
                if score_diff < 0.05 and score > 0.75:
                    close_matches.append(candidate)
                    self.logger.debug(f"  Close match #{i+1}: {candidate['name']} (Δ={score_diff:.3f})")
            
            # Cas 2: Plusieurs résultats avec score élevé (> 0.85) même si écart > 0.05
            high_score_matches = [c for c in ranked_candidates[1:4] if c.get('drakon_score', 0.0) >= 0.85]
            
            # Détection: Requête courte/ambiguë avec plusieurs résultats décents
            is_short_query = len(game_name.split()) <= 1 and len(game_name) <= 5
            has_multiple_high_scores = len(high_score_matches) >= 1
            has_close_scores = len(close_matches) >= 1
            
            if (is_short_query and has_multiple_high_scores) or (has_close_scores and best_score < 0.95):
                # Plusieurs résultats proches → possible typo ou requête ambiguë
                result_type = SearchResultType.MULTIPLE_RESULTS
                
                # Enrichir les alternatives
                alternatives = []
                all_alternatives = close_matches + high_score_matches
                # Dédupliquer par nom
                seen_names = {result.name}
                for candidate in all_alternatives[:3]:  # Max 3 alternatives
                    if candidate['name'] not in seen_names:
                        alt = await self._enrich_candidate(candidate)
                        if alt:
                            alternatives.append(alt)
                            seen_names.add(alt.name)
                
                self.logger.info(f"🔍 Multiple results detected for '{game_name}': best={best_score:.2f}, alternatives={len(alternatives)}")
            else:
                # Match unique et confiant
                result_type = SearchResultType.SUCCESS
                alternatives = []
            
            # Step 4: Teach NAHL (auto-learning)
            if result and result.name:
                try:
                    asyncio.create_task(self.nahl.add_game(result.name))
                except Exception:
                    pass
            
            # Step 5: Cache result with intelligent confidence tracking
            # Track decision time, but execute write in background
            with self.perf.track("cache_decision"):
                if self.db and result:
                    # Préparer alternatives pour cache
                    alternatives_data = None
                    if alternatives:
                        alternatives_data = [alt.__dict__ for alt in alternatives]
                    
                    # Décision de cache basée sur confidence
                    should_cache = False
                    
                    # Cache si match excellent (95%+)
                    if best_score >= 0.95:
                        should_cache = True
                    
                    # Cache si bon score ET pas ambigu
                    elif best_score >= 0.90 and result_type == SearchResultType.SUCCESS:
                        should_cache = True
                    
                    # Cache même MULTIPLE_RESULTS si score élevé (utile pour requêtes ambiguës)
                    elif best_score >= 0.90 and result_type == SearchResultType.MULTIPLE_RESULTS:
                        should_cache = True
                    
                    if should_cache:
                        # Fire-and-forget: cache write in background thread (with internal perf tracking)
                        # Use shared executor to avoid thread leak
                        def _cache_write():
                            try:
                                cache_start = time.perf_counter()
                                self.db.cache_game(
                                    query=game_name.lower(),
                                    game_data=result.__dict__,
                                    confidence=best_score,
                                    result_type=result_type.value,
                                    alternatives=alternatives_data,
                                    canonical_query=None
                                )
                                cache_time = (time.perf_counter() - cache_start) * 1_000_000
                                self.logger.debug(
                                    f"💾 Cached (async {cache_time:.0f}µs): {game_name} → {result.name} "
                                    f"(confidence: {best_score:.2f}, type: {result_type.value})"
                                )
                            except Exception as e:
                                self.logger.warning(f"Cache write failed: {e}")
                        
                        self._cache_executor.submit(_cache_write)
                    else:
                        self.logger.debug(
                            f"⏭️  Skip cache: {game_name} "
                            f"(confidence: {best_score:.2f} too low)"
                        )
                
                # Legacy cache (fallback)
                elif self.cache and result:
                    self.cache.set(f"game:{game_name.lower()}", result)
                    self.logger.info(f"💾 Cached (legacy): {game_name} → {result.name}")
            
            # Log final performance report
            self.logger.info(f"🔬 {self.perf.get_report()}")
            
            return SearchResponse(
                result_type=result_type,
                best_match=result,
                alternatives=alternatives,
                total_candidates=len(candidates)
            )

        except Exception as e:
            self.logger.error(f"❌ Error searching game '{game_name}': {e}", exc_info=True)
            self.logger.info(f"🔬 {self.perf.get_report()}")
            return None

    async def enrich_game_from_igdb_id(self, igdb_id: str) -> Optional[GameResult]:
        """
        Enrichit un jeu depuis son ID IGDB exact (utilisé pour !gc avec Twitch game_id).
        
        Cette méthode utilise l'ID IGDB fourni par Twitch pour récupérer
        la version EXACTE du jeu que le streamer joue, résolvant les ambiguïtés
        comme "Painkiller" (2004 vs 2024).
        
        Args:
            igdb_id: ID IGDB du jeu (fourni par Twitch category)
        
        Returns:
            GameResult avec métadonnées complètes ou None si erreur
        """
        # Find IGDB provider
        igdb_provider = next((p for p in self.providers if p.name == "igdb"), None)
        if not igdb_provider:
            self.logger.error("❌ IGDB provider not available")
            return None
        
        # Use provider's enrich method
        return await igdb_provider.enrich(igdb_id)

    def format_result(self, result: GameResult, compact: bool = False) -> str:
        """
        Formate le résultat pour affichage Twitch.
        
        Args:
            result: Résultat du jeu à formater
            compact: Si True, format ultra-compact pour !gc (sans confidence/sources)
        """
        output = f"🎮 {result.name}"
        
        # Early Access flag (safe check pour compatibilité anciens caches)
        if getattr(result, 'is_early_access', False):
            output += " 🚧"
        
        if result.year != "?":
            output += f" ({result.year})"
        
        # Développeurs/Éditeurs (prioritaire)
        if result.developers:
            dev_names = ', '.join(result.developers[:2])
            output += f" - Dev: {dev_names}"
        if result.publishers:
            pub_names = ', '.join(result.publishers[:2])
            output += f" - Pub: {pub_names}"
        
        # Notes et plateformes (tout normalisé sur /5)
        if result.metacritic:
            # Convertir Metacritic /100 → /5
            rating_normalized = result.metacritic / 20.0
            output += f" - ⭐ {rating_normalized:.1f}/5"
        elif result.rating_rawg > 0:
            output += f" - ⭐ {result.rating_rawg:.1f}/5"
        if result.platforms:
            output += f" - 🕹️ {', '.join(result.platforms[:3])}"
        
        # Description (summary) si disponible - SEULEMENT en mode non-compact
        if not compact and result.summary:
            # Calculer espace restant (450 - prefix actuel)
            current_len = len(output)
            max_summary = 450 - current_len - 3  # -3 pour " | "
            if max_summary > 50:  # Au moins 50 chars de résumé
                summary_short = result.summary[:max_summary].strip()
                if len(result.summary) > max_summary:
                    last_dot = summary_short.rfind('. ')
                    last_space = summary_short.rfind(' ')
                    if last_dot > max_summary * 0.7:
                        summary_short = summary_short[:last_dot + 1]
                    elif last_space > max_summary * 0.8:
                        summary_short = summary_short[:last_space] + "..."
                    else:
                        summary_short += "..."
                output += f" | {summary_short}"
        
        # Version compacte : pas de confidence/sources
        if compact:
            return output
        
        # Version complète : juste le résumé, pas de confidence/sources en prod
        return output

    async def close(self):
        """Cleanup resources."""
        await self.http_client.aclose()
        await self.nahl.close()
