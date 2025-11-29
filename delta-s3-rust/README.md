# Δₛ³ v3.1 - Rust Implementation

High-performance semantic delta algorithm for fuzzy string matching.

## Validated Performance

**Python baseline:**
- Accuracy@1: 97.45% (13,259 queries)
- Throughput: 51 q/s (WSL, 4 cores)
- Latency: 19.6ms per query

**Rust targets:**
- Accuracy@1: 97.45% (identical algorithm)
- Throughput: 1,000+ q/s (WSL, 4 cores)
- Latency: <1ms per query

## Build & Run

```bash
# Development build
cargo build

# Release build (optimized)
cargo build --release

# Run benchmark
cargo run --release --bin benchmark

# Run tests
cargo test
```

## Benchmark

Matches Python's `benchmark_optimized.py`:
- 13,259 queries from `steam_games_targeted.json`
- Each query vs ground truth + 100 random distractors
- Expected: 97.45% Acc@1

```bash
cd delta-s3-rust
cargo run --release --bin benchmark
```

## Next Steps

1. ✅ Validate 97.45% accuracy (same as Python)
2. 🚀 Measure throughput on WSL
3. 🐧 Deploy to VPS (Debian) for native Linux perf
4. 🐍 Create PyO3 bindings for KissBot integration

## Architecture

```
src/
├── lib.rs           # Core Δₛ³ algorithm
└── bin/
    └── benchmark.rs # Benchmark binary
```

## Profile

- **TITLE mode**: Gaming/tech names (wJ=0.40, wL=0.40, wR=0.20)
- Features: Roman mapping, DLC debias, symmetric Levenshtein
- Corrections: α=0.25, β=0.35, J_cap=0.80
