use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::time::Duration;

use crate::core::GameResult;
use crate::ranking::{Ranker, RankedCandidate};
use crate::error::{Result, GameEngineError};

/// DRAKON HTTP API client for Δₛ³ V3 fuzzy ranking
pub struct DrakonRanker {
    client: Client,
    base_url: String,
}

#[derive(Debug, Serialize)]
struct RankRequest {
    query: String,
    candidates: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct RankResponse {
    results: Vec<RankedResult>,
}

#[derive(Debug, Deserialize)]
struct RankedResult {
    candidate: String,
    score: f64,
    #[allow(dead_code)]
    index: usize,
}

impl DrakonRanker {
    /// Create new DRAKON ranker
    pub async fn new(base_url: impl Into<String>) -> Result<Self> {
        let base_url = base_url.into();
        let client = Client::builder()
            .timeout(Duration::from_millis(500))
            .build()
            .map_err(|e| GameEngineError::HttpRequest(e))?;
        
        // Health check
        let health_url = format!("{}/health", base_url);
        client.get(&health_url)
            .send()
            .await
            .map_err(|e| GameEngineError::DrakonApi(format!("Health check failed: {}", e)))?;
        
        Ok(Self { client, base_url })
    }
    
    /// Rank candidates via DRAKON HTTP API
    async fn rank_http(&self, query: &str, candidates: &[String]) -> Result<Vec<(usize, f64)>> {
        let url = format!("{}/v1/rank", self.base_url);
        
        let request = RankRequest {
            query: query.to_string(),
            candidates: candidates.to_vec(),
        };
        
        let response = self.client
            .post(&url)
            .json(&request)
            .send()
            .await
            .map_err(|e| GameEngineError::DrakonApi(format!("Request failed: {}", e)))?;
        
        if !response.status().is_success() {
            return Err(GameEngineError::DrakonApi(format!(
                "HTTP {}: {}",
                response.status(),
                response.text().await.unwrap_or_default()
            )));
        }
        
        let rank_response: RankResponse = response
            .json()
            .await
            .map_err(|e| GameEngineError::DrakonApi(format!("Invalid JSON: {}", e)))?;
        
        Ok(rank_response
            .results
            .into_iter()
            .map(|r| (r.index, r.score))
            .collect())
    }
}

impl Ranker for DrakonRanker {
    fn rank(&self, query: &str, candidates: &[GameResult]) -> Result<Vec<RankedCandidate>> {
        // Convert to candidate names
        let names: Vec<String> = candidates.iter().map(|g| g.name.clone()).collect();
        
        // Call DRAKON HTTP API (blocking tokio runtime)
        let runtime = tokio::runtime::Handle::current();
        let scores = runtime.block_on(self.rank_http(query, &names))?;
        
        // Map back to GameResult with scores
        let mut ranked: Vec<RankedCandidate> = scores
            .into_iter()
            .map(|(idx, score)| RankedCandidate {
                game: candidates[idx].clone(),
                score,
            })
            .collect();
        
        // Sort by score descending
        ranked.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap_or(std::cmp::Ordering::Equal));
        
        Ok(ranked)
    }
    
    fn name(&self) -> &str {
        "drakon"
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    #[ignore] // Requires DRAKON server running
    async fn test_drakon_ranker() {
        let ranker = DrakonRanker::new("http://127.0.0.1:8000").await.unwrap();
        
        let candidates = vec![
            GameResult::new("steam", "1", "Vampire Survivors"),
            GameResult::new("steam", "2", "Vampire The Masquerade"),
            GameResult::new("steam", "3", "Survivor.io"),
        ];
        
        let ranked = ranker.rank("vampir survivor", &candidates).unwrap();
        
        assert_eq!(ranked.len(), 3);
        assert_eq!(ranked[0].game.name, "Vampire Survivors");
        assert!(ranked[0].score > 50.0);
    }
}
