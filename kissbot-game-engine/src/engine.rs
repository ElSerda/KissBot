use crate::core::{GameResult, SearchResponse, SearchResultType};
use crate::cache::{GameCache, SqliteCache};
use crate::ranking::{Ranker, DrakonRanker, RapidfuzzRanker};
use crate::providers::GameProvider;
use crate::error::{Result, GameEngineError};
use std::sync::Arc;
use std::time::Instant;

/// Main game search engine orchestrator
pub struct GameEngine {
    cache: Arc<dyn GameCache>,
    ranker: Arc<dyn Ranker>,
    providers: Vec<Arc<dyn GameProvider>>,
}

/// Search query parameters
#[derive(Debug, Clone)]
pub struct SearchQuery {
    pub query: String,
    pub max_results: usize,
    pub use_cache: bool,
}

/// Search options/configuration
#[derive(Debug, Clone)]
pub struct SearchOptions {
    pub cache_enabled: bool,
    pub drakon_enabled: bool,
    pub min_score: f64,
    pub max_alternatives: usize,
}

impl Default for SearchOptions {
    fn default() -> Self {
        Self {
            cache_enabled: true,
            drakon_enabled: true,
            min_score: 70.0,
            max_alternatives: 5,
        }
    }
}

impl GameEngine {
    /// Create new game engine with default SQLite cache
    pub async fn new(db_path: impl AsRef<str>) -> Result<Self> {
        let cache = Arc::new(SqliteCache::new(db_path.as_ref()).await?);
        
        // Try DRAKON first, fallback to rapidfuzz
        let ranker: Arc<dyn Ranker> = match DrakonRanker::new("http://127.0.0.1:8000").await {
            Ok(drakon) => {
                tracing::info!("✅ DRAKON ranker initialized");
                Arc::new(drakon)
            }
            Err(e) => {
                tracing::warn!("⚠️ DRAKON unavailable, using rapidfuzz: {}", e);
                Arc::new(RapidfuzzRanker::new())
            }
        };
        
        Ok(Self {
            cache,
            ranker,
            providers: Vec::new(),
        })
    }

    /// Add a game provider
    pub fn add_provider(&mut self, provider: Arc<dyn GameProvider>) {
        self.providers.push(provider);
    }

    /// Search for a game
    pub async fn search(&self, query: SearchQuery) -> Result<SearchResponse> {
        let start = Instant::now();
        
        // Check cache first
        if query.use_cache {
            if let Some(cached) = self.cache.get(&query.query).await? {
                let latency_ms = start.elapsed().as_secs_f64() * 1000.0;
                
                self.cache.increment_hit(&query.query).await?;
                
                return Ok(SearchResponse {
                    game: cached.game,
                    score: 100.0, // Cache hit = exact match
                    result_type: SearchResultType::CacheHit,
                    alternatives: cached.alternatives,
                    from_cache: true,
                    latency_ms,
                    provider: "cache".to_string(),
                    ranking_method: "cache".to_string(),
                });
            }
        }
        
        // Fetch from providers
        let mut all_candidates = Vec::new();
        for provider in &self.providers {
            match provider.search(&query.query).await {
                Ok(mut results) => {
                    tracing::debug!("Provider {} returned {} results", provider.name(), results.len());
                    all_candidates.append(&mut results);
                }
                Err(e) => {
                    tracing::warn!("Provider {} failed: {}", provider.name(), e);
                }
            }
        }
        
        if all_candidates.is_empty() {
            return Err(GameEngineError::NoResults(query.query.clone()));
        }
        
        // Rank candidates
        let ranked = self.ranker.rank(&query.query, &all_candidates)?;
        
        if ranked.is_empty() {
            return Err(GameEngineError::NoResults(query.query.clone()));
        }
        
        let best = ranked[0].clone();
        let alternatives: Vec<GameResult> = ranked
            .iter()
            .skip(1)
            .take(query.max_results.saturating_sub(1))
            .map(|r| r.game.clone())
            .collect();
        
        // Save to cache
        if query.use_cache && best.score >= 70.0 {
            if let Err(e) = self.cache.save(&query.query, &best.game, &alternatives).await {
                tracing::warn!("Failed to save to cache: {}", e);
            }
        }
        
        let latency_ms = start.elapsed().as_secs_f64() * 1000.0;
        
        let result_type = if best.score >= 95.0 {
            SearchResultType::Exact
        } else if best.score >= 70.0 {
            SearchResultType::Fuzzy
        } else {
            SearchResultType::Fallback
        };
        
        Ok(SearchResponse {
            game: best.game.clone(),
            score: best.score,
            result_type,
            alternatives,
            from_cache: false,
            latency_ms,
            provider: best.game.provider.clone(),
            ranking_method: self.ranker.name().to_string(),
        })
    }
    
    /// Get cache statistics
    pub async fn cache_stats(&self) -> Result<crate::cache::CacheStats> {
        self.cache.stats().await
    }
    
    /// Clean up old cache entries
    pub async fn cleanup_cache(&self, max_age_days: i64) -> Result<u64> {
        self.cache.cleanup(max_age_days).await
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_engine_creation() {
        let result = GameEngine::new(":memory:").await;
        assert!(result.is_ok());
    }
}
