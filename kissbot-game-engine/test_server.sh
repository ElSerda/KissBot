#!/bin/bash
# Test du serveur KissBot Game Engine

BASE_URL="http://localhost:8090"

echo "🧪 Test du serveur KissBot Game Engine"
echo "======================================"
echo ""

# Test 1: Health check
echo "1️⃣  Health check..."
curl -s "$BASE_URL/health" | jq '.' || echo "❌ Échec"
echo ""

# Test 2: Search - Vampire Survivors
echo "2️⃣  Search: 'vampir survivor'..."
curl -s -X POST "$BASE_URL/v1/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "vampir survivor", "max_results": 3}' \
  | jq '{
      game: .game.name,
      score: .score,
      from_cache: .from_cache,
      latency_ms: .latency_ms,
      ranking_method: .ranking_method
    }' || echo "❌ Échec"
echo ""

# Test 3: Search - Counter-Strike
echo "3️⃣  Search: 'counter-strike'..."
curl -s -X POST "$BASE_URL/v1/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "counter-strike", "max_results": 2}' \
  | jq '{game: .game.name, score: .score}' || echo "❌ Échec"
echo ""

# Test 4: Stats
echo "4️⃣  Cache stats..."
curl -s "$BASE_URL/v1/stats" | jq '.' || echo "❌ Échec"
echo ""

echo "✅ Tests terminés !"
