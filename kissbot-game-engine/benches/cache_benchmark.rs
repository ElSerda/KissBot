use criterion::{black_box, criterion_group, criterion_main, Criterion, BenchmarkId};
use kissbot_game_engine::{cache::{GameCache, SqliteCache}, core::GameResult};

async fn setup_cache() -> SqliteCache {
    let cache = SqliteCache::new(":memory:").await.unwrap();
    
    // Populate with test data
    for i in 0..100 {
        let game = GameResult::new("steam", i.to_string(), format!("Game {}", i));
        cache.save(&format!("query{}", i), &game, &[]).await.unwrap();
    }
    
    cache
}

fn bench_cache_get(c: &mut Criterion) {
    let runtime = tokio::runtime::Runtime::new().unwrap();
    let cache = runtime.block_on(setup_cache());
    
    c.bench_function("cache_get_hit", |b| {
        b.to_async(&runtime).iter(|| async {
            black_box(cache.get("query50").await.unwrap())
        });
    });
    
    c.bench_function("cache_get_miss", |b| {
        b.to_async(&runtime).iter(|| async {
            black_box(cache.get("nonexistent").await.unwrap())
        });
    });
}

fn bench_cache_save(c: &mut Criterion) {
    let runtime = tokio::runtime::Runtime::new().unwrap();
    
    c.bench_function("cache_save", |b| {
        b.to_async(&runtime).iter(|| async {
            let cache = SqliteCache::new(":memory:").await.unwrap();
            let game = GameResult::new("steam", "123", "Test Game");
            black_box(cache.save("test_query", &game, &[]).await.unwrap())
        });
    });
}

fn bench_cache_increment(c: &mut Criterion) {
    let runtime = tokio::runtime::Runtime::new().unwrap();
    let cache = runtime.block_on(setup_cache());
    
    c.bench_function("cache_increment_hit", |b| {
        b.to_async(&runtime).iter(|| async {
            black_box(cache.increment_hit("query50").await.unwrap())
        });
    });
}

fn bench_game_result_serialization(c: &mut Criterion) {
    let mut game = GameResult::new("steam", "730", "Counter-Strike 2");
    game.developers = vec!["Valve".to_string()];
    game.publishers = vec!["Valve".to_string()];
    game.genres = vec!["Action".to_string(), "FPS".to_string()];
    game.platforms = vec!["Windows".to_string(), "Linux".to_string()];
    game.year = Some(2023);
    
    c.bench_function("game_result_to_json", |b| {
        b.iter(|| black_box(game.to_json().unwrap()));
    });
    
    let json = game.to_json().unwrap();
    c.bench_function("game_result_from_json", |b| {
        b.iter(|| black_box(GameResult::from_json(&json).unwrap()));
    });
}

criterion_group!(
    benches,
    bench_cache_get,
    bench_cache_save,
    bench_cache_increment,
    bench_game_result_serialization
);
criterion_main!(benches);
