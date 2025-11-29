# VPS Optimized Build Instructions

## 🎯 Target Performance
- **Current**: 1,969 q/s (0.51ms/query)
- **Target**: 2,500-3,000 q/s (0.33-0.40ms/query)
- **Expected gain**: +25-40% with native optimizations

## 🔧 Optimized Build (VPS)

```bash
# Sur le VPS Debian
cd /tmp/delta-s3-rust

# Build avec optimisations natives CPU
RUSTFLAGS="-C target-cpu=native -C opt-level=3 -C lto=fat -C codegen-units=1" \
cargo build --release

# Warm cache avant benchmark
cat ../delta-s3/datasets/steam_games_targeted.json > /dev/null

# Run benchmark
./target/release/benchmark
```

## 📊 Optimizations Applied

### 1. **target-cpu=native** (+15-20%)
- Auto-détecte AVX2, SSE4.2, etc.
- Utilise toutes les instructions SIMD disponibles
- Crucial pour Levenshtein + Jaccard (vectorisés)

### 2. **lto=fat** (+5-10%)
- Link-Time Optimization aggressive
- Inline cross-crate (rayon + delta-s3)
- Élimine dead code entre modules

### 3. **codegen-units=1** (+5%)
- Maximum optimization (vs 16 par défaut)
- Build plus lent, runtime plus rapide
- Meilleur inlining + constant folding

### 4. **opt-level=3** (déjà fait)
- Niveau max d'optimisation
- Loop unrolling, vectorization auto

## 🧪 Expected Results

| Metric | Before | After | Gain |
|--------|--------|-------|------|
| Throughput | 1,969 q/s | 2,500-3,000 q/s | +27-52% |
| Latency | 0.51ms | 0.33-0.40ms | -22-35% |
| Accuracy | 97.69% | 97.69% | 0% (stable) |

## 🔍 Profiling (optional)

```bash
# Installer perf tools
sudo apt install linux-perf

# Profile CPU hotspots
perf record --call-graph dwarf ./target/release/benchmark
perf report
```

## 📈 Thread Tuning (déjà optimal)

Rayon utilise automatiquement tous les cores :
- VPS 4 vCores → 4 threads
- Pas de gain à forcer manuellement

## ⚠️ Cache Warmup

```bash
# Précharger dataset en RAM
sudo sh -c 'echo 3 > /proc/sys/vm/drop_caches'  # Clear cache
cat ../delta-s3/datasets/steam_games_targeted.json > /dev/null
./target/release/benchmark  # Run immédiatement
```

## 🎯 Production Recommendations

### Option A: WSL Localhost (FASTEST)
- **5,216 q/s** prouvé
- Latence réseau = 0 (localhost)
- KissBot call `http://localhost:8080/search`

### Option B: VPS Distant (RELIABLE)
- **2,500-3,000 q/s** (optimized)
- Haute disponibilité
- +10-20ms latency réseau

### Option C: Hybrid
- VPS primary (99% uptime)
- WSL fallback (dev/backup)
