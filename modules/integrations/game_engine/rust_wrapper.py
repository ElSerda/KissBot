"""
Game Lookup - Rust Engine Integration
Wrapper pour utiliser le moteur de jeu Rust via Python bindings
Performance: 60x plus rapide que l'implémentation Python pure
"""

import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# MessageBus pour métriques (optionnel)
_message_bus = None

def set_message_bus(bus):
    """Configure le MessageBus pour publier les métriques"""
    global _message_bus
    _message_bus = bus
    logger.info("📊 MessageBus configuré pour game_lookup_rust")


@dataclass
class GameResult:
    """Résultat de jeu compatible avec game_lookup.py"""
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

# Import du moteur Rust
try:
    import kissbot_game_engine
    RUST_ENGINE_AVAILABLE = True
    logger.info("🦀 Rust Game Engine disponible")
except ImportError:
    RUST_ENGINE_AVAILABLE = False
    logger.warning("⚠️ Rust Game Engine non disponible, fallback Python")


class GameLookup:
    """
    Game Lookup avec moteur Rust
    
    API compatible avec l'ancienne implémentation Python
    Performance: Cache hit ~0.2ms (vs 14ms Python)
    
    Hybrid mode: Utilise cache Rust si disponible, sinon fallback Python enrichi
    """
    
    def __init__(self, db_path: str = "kissbot.db", config: dict = None):
        """
        Initialise le moteur de recherche
        
        Args:
            db_path: Chemin vers la base de données SQLite
            config: Configuration pour fallback Python (RAWG API, etc.)
        """
        self.db_path = db_path
        self.config = config or {}
        self._engine = None
        self._python_lookup = None
        self._initialize_engine()
    
    def _initialize_engine(self):
        """Initialize Rust engine"""
        if not RUST_ENGINE_AVAILABLE:
            raise RuntimeError(
                "Rust Game Engine non disponible. "
                "Installer avec: cd kissbot-game-engine && maturin develop"
            )
        
        try:
            self._engine = kissbot_game_engine.GameEngine(self.db_path)
            logger.info(f"✅ Game Engine initialisé (Rust v{kissbot_game_engine.__version__})")
        except Exception as e:
            logger.error(f"❌ Erreur initialisation Game Engine: {e}")
            raise
        
        # Initialize Python fallback for enriched searches
        if self.config:
            try:
                from modules.integrations.game_engine.python_fallback import GameLookup as PythonGameLookup
                self._python_lookup = PythonGameLookup(self.config)
                logger.info("✅ Python fallback initialisé (enrichissement)")
            except Exception as e:
                logger.warning(f"⚠️ Python fallback non disponible: {e}")
    
    async def search_game(
        self,
        query: str,
        max_results: int = 5,
        use_cache: bool = True
    ) -> Optional[GameResult]:
        """
        Recherche un jeu (API compatible avec l'ancienne version)
        
        Hybrid strategy:
        1. Try Rust cache (ultra-fast ~0.2ms)
        2. If no data/incomplete → Fallback to Python enriched search
        
        Args:
            query: Nom du jeu à rechercher
            max_results: Nombre max de résultats
            use_cache: Utiliser le cache
            
        Returns:
            GameResult du meilleur match ou None
        """
        try:
            # Try Rust cache first
            result = self._engine.search(
                query=query,
                max_results=max_results,
                use_cache=use_cache
            )
            
            # Check if we have enriched data (summary or rating)
            game_data = result['game']
            has_enriched_data = (
                game_data.get('short_description') or 
                game_data.get('rating') or 
                game_data.get('metacritic_score')
            )
            
            # If cache has enriched data, use it
            if has_enriched_data or not self._python_lookup:
                # Convertir le dict Rust en GameResult Python
                game = GameResult(
                    name=game_data.get('name', ''),
                    year=str(game_data.get('year', '?')),
                    rating_rawg=game_data.get('rating', 0.0) or 0.0,
                    metacritic=game_data.get('metacritic_score'),
                    platforms=game_data.get('platforms', []),
                    genres=game_data.get('genres', []),
                    developers=game_data.get('developers', []),
                    publishers=game_data.get('publishers', []),
                    summary=game_data.get('short_description') or game_data.get('summary'),
                    description_raw=game_data.get('description'),
                    reliability_score=result['score'] / 100.0,
                    confidence="HIGH" if result['score'] > 80 else "MEDIUM" if result['score'] > 50 else "LOW",
                    source_count=1,
                    primary_source=game_data.get('provider', 'steam'),
                    api_sources=[game_data.get('provider', 'steam')],
                )
                
                # Log performance
                latency = result['latency_ms']
                from_cache = result['from_cache']
                score = result['score']
                ranking = result['ranking_method']
                
                cache_indicator = "💾" if from_cache else "🌐"
                logger.info(
                    f"{cache_indicator} '{query}' → '{game.name}' "
                    f"({score:.1f}%, {latency:.2f}ms, {ranking})"
                )
                
                # Publier métriques sur MessageBus
                if _message_bus:
                    try:
                        await _message_bus.publish("game.search", {
                            'query': query,
                            'game_name': game.name,
                            'score': score,
                            'from_cache': from_cache,
                            'latency_ms': latency,
                            'ranking_method': ranking,
                        })
                    except Exception as e:
                        logger.debug(f"Failed to publish metrics: {e}")
                
                return game
            
            # No enriched data → Fallback to Python enriched search
            logger.info(f"🔄 Cache incomplet, fallback Python enrichi pour '{query}'")
            python_result = await self._python_lookup.search_game(query)
            
            if python_result:
                logger.info(f"✅ Python enrichi: '{query}' → '{python_result.name}'")
                
                # Publish metrics
                if _message_bus:
                    try:
                        await _message_bus.publish("game.search", {
                            'query': query,
                            'game_name': python_result.name,
                            'score': python_result.reliability_score * 100,
                            'from_cache': False,
                            'latency_ms': 0,  # Not tracked for Python
                            'ranking_method': 'python_enriched',
                        })
                    except Exception as e:
                        logger.debug(f"Failed to publish metrics: {e}")
            
            return python_result
            
        except Exception as e:
            logger.error(f"❌ Erreur recherche '{query}': {e}")
            # Last resort: try Python if available
            if self._python_lookup:
                try:
                    return await self._python_lookup.search_game(query)
                except Exception as e2:
                    logger.error(f"❌ Python fallback failed: {e2}")
            return None
    
    async def search_with_alternatives(
        self,
        query: str,
        max_results: int = 5,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Recherche avec alternatives
        
        Returns:
            Dict avec 'game', 'score', 'alternatives', 'from_cache', etc.
        """
        try:
            result = self._engine.search(
                query=query,
                max_results=max_results,
                use_cache=use_cache
            )
            
            # Convertir alternatives en GameResult
            alternatives = []
            for alt_data in result.get('alternatives', []):
                alt = GameResult(
                    name=alt_data.get('name', ''),
                    year=str(alt_data.get('year', '?')),
                    rating_rawg=alt_data.get('rating', 0.0) or 0.0,
                    metacritic=alt_data.get('metacritic_score'),
                    platforms=alt_data.get('platforms', []),
                    genres=alt_data.get('genres', []),
                    developers=alt_data.get('developers', []),
                    publishers=alt_data.get('publishers', []),
                    summary=alt_data.get('short_description') or alt_data.get('summary'),
                    description_raw=alt_data.get('description'),
                    primary_source=alt_data.get('provider', 'steam'),
                    api_sources=[alt_data.get('provider', 'steam')],
                )
                alternatives.append(alt)
            
            # Convertir game principal
            game_data = result['game']
            game = GameResult(
                name=game_data.get('name', ''),
                year=str(game_data.get('year', '?')),
                rating_rawg=game_data.get('rating', 0.0) or 0.0,
                metacritic=game_data.get('metacritic_score'),
                platforms=game_data.get('platforms', []),
                genres=game_data.get('genres', []),
                developers=game_data.get('developers', []),
                publishers=game_data.get('publishers', []),
                summary=game_data.get('short_description') or game_data.get('summary'),
                description_raw=game_data.get('description'),
                reliability_score=result['score'] / 100.0,
                confidence="HIGH" if result['score'] > 80 else "MEDIUM" if result['score'] > 50 else "LOW",
                source_count=1,
                primary_source=game_data.get('provider', 'steam'),
                api_sources=[game_data.get('provider', 'steam')],
            )
            
            return {
                'game': game,
                'score': result['score'],
                'alternatives': alternatives,
                'from_cache': result['from_cache'],
                'latency_ms': result['latency_ms'],
                'ranking_method': result['ranking_method'],
                'result_type': result['result_type'],
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur recherche avec alternatives '{query}': {e}")
            return None
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Obtenir les statistiques du cache
        
        Returns:
            Dict avec total_entries, total_hits, avg_hit_count
        """
        try:
            return self._engine.cache_stats()
        except Exception as e:
            logger.error(f"❌ Erreur stats cache: {e}")
            return {
                'total_entries': 0,
                'total_hits': 0,
                'avg_hit_count': 0.0
            }
    
    def cleanup_cache(self, max_age_days: int = 30) -> int:
        """
        Nettoyer les anciennes entrées du cache
        
        Args:
            max_age_days: Âge maximum en jours
            
        Returns:
            Nombre d'entrées supprimées
        """
        try:
            deleted = self._engine.cleanup_cache(max_age_days)
            logger.info(f"🧹 Cache nettoyé: {deleted} entrées supprimées")
            return deleted
        except Exception as e:
            logger.error(f"❌ Erreur nettoyage cache: {e}")
            return 0
    
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
            # Limiter à 150 caractères pour Twitch
            summary_short = result.summary[:150].strip()
            if len(result.summary) > 150:
                summary_short += "..."
            output += f" | {summary_short}"
        
        # Version compacte : pas de confidence/sources
        if compact:
            return output
        
        # Version complète : ajouter confidence + sources
        icon = (
            "🔥" if result.confidence == "HIGH" else "✅" if result.confidence == "MEDIUM" else "⚠️"
        )
        return f"{output} - {icon} {result.confidence} ({result.source_count} sources)"


# Singleton pour réutilisation
_game_lookup_instance: Optional[GameLookup] = None


def get_game_lookup(db_path: str = "kissbot.db", config: dict = None) -> GameLookup:
    """
    Obtenir l'instance singleton de GameLookup
    
    Args:
        db_path: Chemin vers la base de données
        config: Configuration pour fallback Python
        
    Returns:
        Instance GameLookup
    """
    global _game_lookup_instance
    
    if _game_lookup_instance is None:
        _game_lookup_instance = GameLookup(db_path, config)
    
    return _game_lookup_instance
