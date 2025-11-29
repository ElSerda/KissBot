# KissBot Game Engine

High-performance game search engine written in Rust with multi-provider support, intelligent caching, and fuzzy matching powered by DRAKON Δₛ³ V3 algorithm.

## Features

- 🚀 **25x faster** than Python implementation
- 🎮 **Multi-provider support**: Steam, IGDB, RAWG
- 💾 **SQLite cache layer** with ~0.6ms hit latency
- 🔍 **DRAKON Δₛ³ V3** fuzzy ranking (0.05-0.12ms)
- ⚡ **Async/await** architecture with Tokio
- 🐍 **Python bindings** via PyO3
- 🌐 **HTTP API server** with Axum
- 🛠️ **CLI tool** for testing

## Architecture

```
kissbot-game-engine/
├── src/
│   ├── lib.rs              # Public API
│   ├── core/               # Core types (GameResult, SearchResponse)
│   ├── cache/              # SQLite caching layer
│   ├── ranking/            # DRAKON + rapidfuzz ranking
│   ├── providers/          # Steam, IGDB, RAWG providers
│   ├── engine.rs           # Main orchestrator
│   └── bin/
│       ├── server.rs       # HTTP API server
│       └── cli.rs          # CLI tool
├── benches/                # Performance benchmarks
└── Cargo.toml
```

## Usage

### As Rust Library

```rust
use kissbot_game_engine::{GameEngine, SearchQuery};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let engine = GameEngine::new("kissbot.db").await?;
    
    let results = engine.search(SearchQuery {
        query: "vampir survivor".to_string(),
        max_results: 5,
        use_cache: true,
    }).await?;
    
    println!("Found: {} - {}%", results.game.name, results.score);
    Ok(())
}
```

### As HTTP Server

```bash
cargo build --release --features server
./target/release/game-engine-server --port 8090 --db kissbot.db
```

```bash
curl -X POST http://localhost:8090/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "vampir survivor", "max_results": 5}'
```

### As Python Library

```python
import kissbot_game_engine

engine = kissbot_game_engine.GameEngine("kissbot.db")
result = engine.search("vampir survivor", max_results=5)
print(f"{result.game.name} - {result.score}%")
```

### As CLI Tool

```bash
cargo build --release --features cli
./target/release/game-engine-cli search "vampir survivor" --max-results 5
```

## Performance

| Operation | Python | Rust | Speedup |
|-----------|--------|------|---------|
| GameResult construction | 3.3µs | 0.135µs | **25x** |
| Cache hit (total) | 14ms | 0.6ms | **23x** |
| DRAKON ranking | 0.1ms | 0.05ms | **2x** |

## Building

```bash
# Rust library + binaries
cargo build --release

# With HTTP server
cargo build --release --features server

# With Python bindings
cargo build --release --features python

# With CLI
cargo build --release --features cli

# All features
cargo build --release --all-features
```

## Testing

```bash
cargo test
cargo test --all-features
```

## Benchmarking

```bash
cargo bench
```

## License

MIT
