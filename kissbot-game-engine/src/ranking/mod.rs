pub mod drakon;
pub mod fallback;

use crate::core::GameResult;
use crate::error::Result;

pub use drakon::DrakonRanker;
pub use fallback::RapidfuzzRanker;

/// Trait for ranking/fuzzy matching implementations
pub trait Ranker: Send + Sync {
    /// Rank candidates against query, return sorted by score (highest first)
    fn rank(&self, query: &str, candidates: &[GameResult]) -> Result<Vec<RankedCandidate>>;
    
    /// Get ranker name for logging
    fn name(&self) -> &str;
}

/// Candidate with similarity score
#[derive(Debug, Clone)]
pub struct RankedCandidate {
    pub game: GameResult,
    pub score: f64,
}

impl RankedCandidate {
    pub fn new(game: GameResult, score: f64) -> Self {
        Self { game, score }
    }
}
