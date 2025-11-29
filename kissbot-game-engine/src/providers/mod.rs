pub mod base;
pub mod steam;

use async_trait::async_trait;
use crate::core::GameResult;
use crate::error::Result;

pub use steam::SteamProvider;

/// Trait for game data providers (Steam, IGDB, RAWG, etc.)
#[async_trait]
pub trait GameProvider: Send + Sync {
    /// Search for games by query string
    async fn search(&self, query: &str) -> Result<Vec<GameResult>>;
    
    /// Get game by ID
    async fn get_by_id(&self, id: &str) -> Result<GameResult>;
    
    /// Get provider name
    fn name(&self) -> &str;
    
    /// Check if provider is available
    async fn is_available(&self) -> bool;
}
