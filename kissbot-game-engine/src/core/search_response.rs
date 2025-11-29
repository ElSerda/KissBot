use serde::{Deserialize, Serialize};
use crate::core::GameResult;

/// Type of search result
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum SearchResultType {
    /// Exact match (100% score)
    Exact,
    /// Fuzzy match (>70% score)
    Fuzzy,
    /// Cache hit (from database)
    CacheHit,
    /// Fallback result (no good match)
    Fallback,
}

/// Search response with game result and metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchResponse {
    /// The matched game
    pub game: GameResult,
    
    /// Match score (0.0 - 100.0)
    pub score: f64,
    
    /// Result type
    pub result_type: SearchResultType,
    
    /// Alternative matches (if any)
    #[serde(default)]
    pub alternatives: Vec<GameResult>,
    
    /// Whether result came from cache
    pub from_cache: bool,
    
    /// Search latency in milliseconds
    pub latency_ms: f64,
    
    /// Provider that returned the result
    pub provider: String,
    
    /// Ranking method used (drakon, rapidfuzz)
    pub ranking_method: String,
}

impl SearchResponse {
    /// Create a new search response
    pub fn new(
        game: GameResult,
        score: f64,
        result_type: SearchResultType,
        from_cache: bool,
        latency_ms: f64,
    ) -> Self {
        let provider = game.provider.clone();
        Self {
            game,
            score,
            result_type,
            alternatives: Vec::new(),
            from_cache,
            latency_ms,
            provider,
            ranking_method: String::from("unknown"),
        }
    }

    /// Add alternative match
    pub fn add_alternative(&mut self, game: GameResult) {
        self.alternatives.push(game);
    }

    /// Set ranking method
    pub fn with_ranking_method(mut self, method: impl Into<String>) -> Self {
        self.ranking_method = method.into();
        self
    }

    /// Check if match is good enough (score >= 70%)
    pub fn is_good_match(&self) -> bool {
        self.score >= 70.0
    }

    /// Get display string for logging
    pub fn display(&self) -> String {
        format!(
            "{} - {}% ({}) [{}] {:?}",
            self.game.display_name(),
            self.score,
            self.provider,
            self.ranking_method,
            self.result_type
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_search_response_creation() {
        let game = GameResult::new("steam", "730", "CS2");
        let response = SearchResponse::new(game, 95.5, SearchResultType::Fuzzy, false, 12.3);
        
        assert_eq!(response.score, 95.5);
        assert_eq!(response.result_type, SearchResultType::Fuzzy);
        assert!(!response.from_cache);
        assert!(response.is_good_match());
    }

    #[test]
    fn test_good_match_threshold() {
        let game = GameResult::new("steam", "1", "Game");
        
        let good = SearchResponse::new(game.clone(), 75.0, SearchResultType::Fuzzy, false, 1.0);
        assert!(good.is_good_match());
        
        let bad = SearchResponse::new(game, 65.0, SearchResultType::Fuzzy, false, 1.0);
        assert!(!bad.is_good_match());
    }
}
