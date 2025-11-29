use kissbot_game_engine::{GameEngine, SearchQuery, providers::SteamProvider};
use std::sync::Arc;

#[tokio::test]
async fn test_engine_integration() {
    // Create engine with in-memory database
    let mut engine = GameEngine::new(":memory:").await.unwrap();
    
    // Add Steam provider
    let steam = Arc::new(SteamProvider::new(None));
    engine.add_provider(steam);
    
    // Search (will hit API since cache is empty)
    let query = SearchQuery {
        query: "counter-strike".to_string(),
        max_results: 5,
        use_cache: true,
    };
    
    // Note: This test requires network access and will be slow
    // In real CI, you'd mock the providers
    #[cfg(not(feature = "ci"))]
    {
        let result = engine.search(query.clone()).await;
        if result.is_ok() {
            let res = result.unwrap();
            assert!(res.game.name.to_lowercase().contains("counter"));
            assert!(!res.from_cache);
            
            // Search again - should hit cache
            let cached_result = engine.search(query).await.unwrap();
            assert!(cached_result.from_cache);
            assert_eq!(cached_result.game.name, res.game.name);
        }
    }
}

#[tokio::test]
async fn test_cache_stats() {
    let engine = GameEngine::new(":memory:").await.unwrap();
    
    let stats = engine.cache_stats().await.unwrap();
    assert_eq!(stats.total_entries, 0);
    assert_eq!(stats.total_hits, 0);
}

#[tokio::test]
async fn test_cache_cleanup() {
    let engine = GameEngine::new(":memory:").await.unwrap();
    
    // Cleanup old entries (0 days = everything)
    let deleted = engine.cleanup_cache(0).await.unwrap();
    assert_eq!(deleted, 0); // Nothing to delete in empty cache
}
