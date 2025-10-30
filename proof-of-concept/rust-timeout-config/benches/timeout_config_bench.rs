use criterion::{black_box, criterion_group, criterion_main, Criterion};
use std::collections::HashMap;
use timeout_config::TimeoutConfig;

fn benchmark_default_creation(c: &mut Criterion) {
    c.bench_function("TimeoutConfig::default", |b| {
        b.iter(|| black_box(TimeoutConfig::default()))
    });
}

fn benchmark_from_config(c: &mut Criterion) {
    let mut config = HashMap::new();
    config.insert("timeout_connect".to_string(), 3.0);
    config.insert("timeout_inference".to_string(), 60.0);
    config.insert("timeout_write".to_string(), 15.0);
    config.insert("timeout_pool".to_string(), 2.0);
    
    c.bench_function("TimeoutConfig::from_config", |b| {
        b.iter(|| black_box(TimeoutConfig::from_config(&config)))
    });
}

fn benchmark_to_httpx_timeout(c: &mut Criterion) {
    let config = TimeoutConfig::default();
    
    c.bench_function("TimeoutConfig::to_httpx_timeout", |b| {
        b.iter(|| black_box(config.to_httpx_timeout()))
    });
}

fn benchmark_display(c: &mut Criterion) {
    let config = TimeoutConfig::default();
    
    c.bench_function("TimeoutConfig::Display", |b| {
        b.iter(|| black_box(format!("{}", config)))
    });
}

fn benchmark_serialization(c: &mut Criterion) {
    let config = TimeoutConfig::default();
    
    c.bench_function("TimeoutConfig::serialize", |b| {
        b.iter(|| black_box(serde_json::to_string(&config).unwrap()))
    });
}

criterion_group!(
    benches,
    benchmark_default_creation,
    benchmark_from_config,
    benchmark_to_httpx_timeout,
    benchmark_display,
    benchmark_serialization
);
criterion_main!(benches);
