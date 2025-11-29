use rapidfuzz::distance::jaro_winkler;

use crate::core::GameResult;
use crate::ranking::{Ranker, RankedCandidate};
use crate::error::Result;

/// Rapidfuzz-based ranker (fallback when DRAKON unavailable)
pub struct RapidfuzzRanker;

impl RapidfuzzRanker {
    pub fn new() -> Self {
        Self
    }
}

impl Default for RapidfuzzRanker {
    fn default() -> Self {
        Self::new()
    }
}

impl Ranker for RapidfuzzRanker {
    fn rank(&self, query: &str, candidates: &[GameResult]) -> Result<Vec<RankedCandidate>> {
        let query_lower = query.to_lowercase();
        
        let mut ranked: Vec<RankedCandidate> = candidates
            .iter()
            .map(|game| {
                let name_lower = game.name.to_lowercase();
                
                // Jaro-Winkler similarity (0.0 - 1.0)
                let score = jaro_winkler::normalized_similarity(
                    query_lower.chars(),
                    name_lower.chars(),
                );
                
                // Convert to percentage (0-100)
                let score_pct = score * 100.0;
                
                RankedCandidate {
                    game: game.clone(),
                    score: score_pct,
                }
            })
            .collect();
        
        // Sort by score descending
        ranked.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap_or(std::cmp::Ordering::Equal));
        
        Ok(ranked)
    }
    
    fn name(&self) -> &str {
        "rapidfuzz"
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_rapidfuzz_ranker() {
        let ranker = RapidfuzzRanker::new();
        
        let candidates = vec![
            GameResult::new("steam", "1", "Vampire Survivors"),
            GameResult::new("steam", "2", "Survivor.io"),
            GameResult::new("steam", "3", "Left 4 Dead"),
        ];
        
        let ranked = ranker.rank("vampire survivor", &candidates).unwrap();
        
        assert_eq!(ranked.len(), 3);
        assert_eq!(ranked[0].game.name, "Vampire Survivors");
        assert!(ranked[0].score > ranked[1].score);
    }

    #[test]
    fn test_rapidfuzz_exact_match() {
        let ranker = RapidfuzzRanker::new();
        
        let candidates = vec![
            GameResult::new("steam", "1", "Counter-Strike 2"),
        ];
        
        let ranked = ranker.rank("Counter-Strike 2", &candidates).unwrap();
        
        assert_eq!(ranked[0].score, 100.0);
    }
}
