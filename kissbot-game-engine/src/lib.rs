//! # KissBot Game Engine
//!
//! High-performance game search engine with:
//! - Multi-provider support (Steam, IGDB, RAWG)
//! - SQLite caching layer
//! - DRAKON Δₛ³ V3 fuzzy ranking
//! - Async/await architecture
//! - Multiple interfaces: Rust library, Python bindings, HTTP API, CLI
//!
//! ## Example Usage
//!
//! ```rust,no_run
//! use kissbot_game_engine::{GameEngine, SearchQuery};
//!
//! #[tokio::main]
//! async fn main() -> anyhow::Result<()> {
//!     let engine = GameEngine::new("kissbot.db").await?;
//!     
//!     let results = engine.search(SearchQuery {
//!         query: "vampir survivor".to_string(),
//!         max_results: 5,
//!         use_cache: true,
//!     }).await?;
//!     
//!     println!("Found: {} - {}%", results.game.name, results.score);
//!     Ok(())
//! }
//! ```

pub mod core;
pub mod cache;
pub mod ranking;
pub mod providers;
pub mod engine;
pub mod error;

// Re-export primary types
pub use core::{GameResult, SearchResponse, SearchResultType};
pub use engine::{GameEngine, SearchQuery, SearchOptions};
pub use error::{GameEngineError, Result};
pub use cache::GameCache;

// Python bindings
#[cfg(feature = "python")]
pub mod python;

#[cfg(feature = "python")]
pub use python::*;

/// Library version
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_version() {
        assert!(!VERSION.is_empty());
    }
}
