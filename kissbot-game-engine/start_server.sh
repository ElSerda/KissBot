#!/bin/bash
# KissBot Game Engine - Quick Start Script

set -e

echo "🎮 KissBot Game Engine - Server Startup"
echo "========================================"

# Configuration
DB_PATH="${DB_PATH:-../kissbot.db}"
PORT="${PORT:-8090}"
RUST_LOG="${RUST_LOG:-game_engine_server=info,kissbot_game_engine=info}"

# Vérifier si le binaire existe
if [ ! -f "target/release/game-engine-server" ]; then
    echo "📦 Binaire pas trouvé, compilation en cours..."
    cargo build --release --bin game-engine-server --features server
fi

echo ""
echo "⚙️  Configuration:"
echo "   - Database: $DB_PATH"
echo "   - Port: $PORT"
echo "   - Log level: $RUST_LOG"
echo ""

# Démarrer le serveur
echo "🚀 Démarrage du serveur..."
DB_PATH="$DB_PATH" PORT="$PORT" RUST_LOG="$RUST_LOG" \
    ./target/release/game-engine-server
