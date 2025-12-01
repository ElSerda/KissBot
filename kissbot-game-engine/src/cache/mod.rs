pub mod sqlite;

use async_trait::async_trait;
use crate::core::GameResult;
use crate::error::Result;

pub use sqlite::SqliteCache;

/// Trait for game cache implementations
#[async_trait]
pub trait GameCache: Send + Sync {
    /// Get cached game by query string
    async fn get(&self, query: &str) -> Result<Option<CachedGame>>;
    
    /// Save game to cache
    async fn save(&self, query: &str, game: &GameResult, alternatives: &[GameResult]) -> Result<()>;
    
    /// Increment cache hit counter
    async fn increment_hit(&self, query: &str) -> Result<()>;
    
    /// Get cache statistics
    async fn stats(&self) -> Result<CacheStats>;
    
    /// Clear expired entries (older than `max_age_days`)
    async fn cleanup(&self, max_age_days: i64) -> Result<u64>;
}

/// Cached game with metadata
#[derive(Debug, Clone)]
pub struct CachedGame {
    pub query: String,
    pub game: GameResult,
    pub alternatives: Vec<GameResult>,
    pub hit_count: i32,
    pub cached_at: chrono::DateTime<chrono::Utc>,
}

/// Cache statistics
#[derive(Debug, Clone)]
pub struct CacheStats {
    pub total_entries: u64,
    pub total_hits: u64,
    pub avg_hit_count: f64,
    pub oldest_entry: Option<chrono::DateTime<chrono::Utc>>,
    pub newest_entry: Option<chrono::DateTime<chrono::Utc>>,
}
