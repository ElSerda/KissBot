.PHONY: help build test bench run clean check fmt lint install-cli

help:
	@echo "🎮 KissBot Game Engine - Makefile"
	@echo "================================="
	@echo ""
	@echo "Commandes disponibles:"
	@echo "  make build        - Build release (serveur)"
	@echo "  make build-all    - Build tous les binaires"
	@echo "  make test         - Run tests unitaires"
	@echo "  make test-all     - Run tous les tests (avec network)"
	@echo "  make bench        - Run benchmarks"
	@echo "  make run          - Démarrer le serveur"
	@echo "  make check        - Check compilation"
	@echo "  make fmt          - Format code"
	@echo "  make lint         - Run clippy"
	@echo "  make clean        - Clean build artifacts"
	@echo "  make install-cli  - Install CLI dans ~/.cargo/bin"
	@echo "  make doc          - Générer documentation"

build:
	@echo "📦 Building release server..."
	cargo build --release --bin game-engine-server --features server

build-all:
	@echo "📦 Building all binaries..."
	cargo build --release --all-features

test:
	@echo "🧪 Running tests..."
	cargo test --lib

test-all:
	@echo "🧪 Running all tests (including network)..."
	cargo test --all-features -- --include-ignored

bench:
	@echo "⚡ Running benchmarks..."
	cargo bench

run:
	@echo "🚀 Starting server..."
	@./start_server.sh

check:
	@echo "🔍 Checking code..."
	cargo check --all-features

fmt:
	@echo "✨ Formatting code..."
	cargo fmt

lint:
	@echo "🔧 Running clippy..."
	cargo clippy --all-features -- -D warnings

clean:
	@echo "🧹 Cleaning..."
	cargo clean
	rm -f *.db *.db-*

install-cli:
	@echo "📥 Installing CLI..."
	cargo install --path . --features cli --bin game-engine-cli

doc:
	@echo "📚 Generating documentation..."
	cargo doc --no-deps --open

# Development shortcuts
dev-server:
	@echo "🔄 Dev server with auto-reload..."
	cargo watch -x 'run --bin game-engine-server --features server'

dev-test:
	@echo "🔄 Dev tests with auto-reload..."
	cargo watch -x test

# Performance profiling
profile:
	@echo "📊 Profiling with perf..."
	cargo build --release --bin game-engine-server --features server
	perf record -g ./target/release/game-engine-server
	perf report

# Size optimization
bloat:
	@echo "📏 Analyzing binary size..."
	cargo bloat --release --bin game-engine-server --features server

# Database operations
db-backup:
	@echo "💾 Backing up database..."
	@cp -v ../kissbot.db ../kissbot.db.backup_$(shell date +%Y%m%d_%H%M%S)

db-stats:
	@echo "📊 Database statistics..."
	@sqlite3 ../kissbot.db "SELECT COUNT(*) as entries FROM game_cache; SELECT SUM(hit_count) as total_hits FROM game_cache;"
