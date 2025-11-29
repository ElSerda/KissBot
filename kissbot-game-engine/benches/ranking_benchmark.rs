use criterion::{black_box, criterion_group, criterion_main, Criterion};
use kissbot_game_engine::{
    ranking::{Ranker, RapidfuzzRanker},
    core::GameResult,
};

fn create_test_candidates(count: usize) -> Vec<GameResult> {
    (0..count)
        .map(|i| {
            let mut game = GameResult::new("steam", i.to_string(), format!("Test Game {}", i));
            game.year = Some(2020 + (i % 5) as i32);
            game.developers = vec![format!("Developer {}", i % 10)];
            game
        })
        .collect()
}

fn bench_rapidfuzz_ranking(c: &mut Criterion) {
    let ranker = RapidfuzzRanker::new();
    
    let candidates_10 = create_test_candidates(10);
    let candidates_50 = create_test_candidates(50);
    let candidates_100 = create_test_candidates(100);
    
    c.bench_function("rapidfuzz_rank_10", |b| {
        b.iter(|| {
            black_box(ranker.rank("test game 5", &candidates_10).unwrap())
        });
    });
    
    c.bench_function("rapidfuzz_rank_50", |b| {
        b.iter(|| {
            black_box(ranker.rank("test game 25", &candidates_50).unwrap())
        });
    });
    
    c.bench_function("rapidfuzz_rank_100", |b| {
        b.iter(|| {
            black_box(ranker.rank("test game 50", &candidates_100).unwrap())
        });
    });
}

criterion_group!(benches, bench_rapidfuzz_ranking);
criterion_main!(benches);
