use delta_s3::semantic_delta_v3;
use serde::Deserialize;
use std::fs;
use std::time::Instant;
use rayon::prelude::*;

#[derive(Debug, Deserialize)]
struct SteamData {
    applist: AppList,
}

#[derive(Debug, Deserialize)]
struct AppList {
    apps: Vec<SteamApp>,
}

#[derive(Debug, Deserialize)]
struct SteamApp {
    name: String,
}

#[derive(Debug, Deserialize)]
struct QueryDataset {
    queries: Vec<Query>,
}

#[derive(Debug, Deserialize)]
struct Query {
    query: String,
    ground_truth: String,
}

fn main() {
    // Use ALL available threads
    let num_threads = std::thread::available_parallelism()
        .map(|n| n.get())
        .unwrap_or(16);
    
    rayon::ThreadPoolBuilder::new()
        .num_threads(num_threads)
        .build_global()
        .unwrap();
    
    println!("🔥 FULL STEAM CATALOG BENCHMARK (276K TITLES) 🔥");
    println!("{}", "=".repeat(80));
    println!("🧵 Using {} threads", num_threads);
    
    // Load 276K Steam catalog
    println!("\n📥 Loading FULL Steam catalog...");
    let steam_json = fs::read_to_string("../delta-s3/Dataset/steam-game/steam-game.json")
        .expect("Failed to read Steam dataset");
    
    let steam_data: SteamData = serde_json::from_str(&steam_json)
        .expect("Failed to parse Steam JSON");
    
    let all_titles: Vec<String> = steam_data.applist.apps
        .into_iter()
        .map(|app| app.name)
        .collect();
    
    println!("✅ Loaded {} Steam titles", all_titles.len());
    
    // Load queries (sample 1000)
    println!("\n📥 Loading query dataset...");
    let query_json = fs::read_to_string("../delta-s3/datasets/steam_games_targeted.json")
        .expect("Failed to read query dataset");
    
    let query_data: QueryDataset = serde_json::from_str(&query_json)
        .expect("Failed to parse query JSON");
    
    // Take first 1000 queries for reasonable runtime
    let sample_size = 1000.min(query_data.queries.len());
    let queries: Vec<Query> = query_data.queries.into_iter().take(sample_size).collect();
    
    println!("✅ Loaded {} queries (sampled from full dataset)", queries.len());
    
    let total_comparisons = queries.len() as u64 * all_titles.len() as u64;
    println!("\n⚠️  WARNING: {} total comparisons ({} million)", 
             total_comparisons,
             total_comparisons / 1_000_000);
    
    // Benchmark setup
    println!("\n{}", "=".repeat(80));
    println!("📊 FULL CATALOG Evaluation");
    println!("{}", "=".repeat(80));
    println!("Strategy: EVERY query against ALL {} Steam titles", all_titles.len());
    println!("Sample: {} queries (for reasonable runtime ~3 min)", sample_size);
    println!("{}", "=".repeat(80));
    
    // Evaluate
    println!("\n🔥 Starting MEGA benchmark...");
    let start = Instant::now();
    
    let results: Vec<bool> = queries.par_iter()
        .enumerate()
        .map(|(idx, query_data)| {
            if (idx + 1) % 100 == 0 {
                let progress = 100.0 * (idx + 1) as f64 / queries.len() as f64;
                let elapsed = start.elapsed().as_secs_f64();
                let eta = elapsed / (idx + 1) as f64 * queries.len() as f64 - elapsed;
                println!("Progress: {}/{} ({:.1}%) | Elapsed: {:.1}s | ETA: {:.0}s", 
                        idx + 1, 
                        queries.len(),
                        progress,
                        elapsed,
                        eta);
            }
            
            evaluate_query_276k(&query_data, &all_titles)
        })
        .collect();
    
    let elapsed = start.elapsed();
    
    // Compute metrics
    let correct = results.iter().filter(|&&x| x).count();
    let total = results.len();
    let accuracy = correct as f64 / total as f64;
    
    let total_time_s = elapsed.as_secs_f64();
    let avg_time_ms = (total_time_s * 1000.0) / total as f64;
    let throughput = total as f64 / total_time_s;
    let comparisons_per_sec = total_comparisons as f64 / total_time_s;
    
    // Print results
    println!("\n{}", "=".repeat(80));
    println!("📈 RESULTS - FULL STEAM CATALOG (276K Titles)");
    println!("{}", "=".repeat(80));
    println!("Total queries:  {}", total);
    println!("Accuracy@1:     {:.4} ({}/{})", accuracy, correct, total);
    
    println!("\n⏱️  PERFORMANCE:");
    println!("Total time:     {:.2}s ({:.1} min)", total_time_s, total_time_s / 60.0);
    println!("Avg time:       {:.2}ms per query ({} comparisons)", 
             avg_time_ms, 
             all_titles.len());
    println!("Throughput:     {:.1} queries/s", throughput);
    println!("Comparisons:    {:.1} M/s ({} million total)", 
             comparisons_per_sec / 1_000_000.0,
             total_comparisons / 1_000_000);
    println!("{}", "=".repeat(80));
    
    println!("\n💡 Verdict: {}", 
             if accuracy > 0.85 && total_time_s < 300.0 { 
                 "🔥 ABSOLUTE BEAST MODE" 
             } else if total_time_s < 300.0 {
                 "⚡ FAST - Check accuracy"
             } else {
                 "⏳ SLOW - Need more optimization"
             });
    
    // Comparison with 5K benchmark
    let small_throughput = 286.0; // From previous 5K benchmark
    let scaling_factor = all_titles.len() as f64 / 5000.0;
    
    println!("\n📊 Comparison:");
    println!("   5K catalog:   {:.0} q/s → 276K catalog: {:.1} q/s", 
             small_throughput,
             throughput);
    println!("   Expected slowdown: {:.1}x → Actual: {:.1}x", 
             scaling_factor,
             small_throughput / throughput);
    println!("   Accuracy: {:.2}% (sampled {} queries)", accuracy * 100.0, sample_size);
    
    println!("\n{}", "=".repeat(80));
    println!("✅ System survived {} MILLION comparisons! 🎉", total_comparisons / 1_000_000);
}

fn evaluate_query_276k(query_data: &Query, all_titles: &[String]) -> bool {
    // Find ground truth index
    let gt_idx = all_titles.iter()
        .position(|t| t == &query_data.ground_truth);
    
    if gt_idx.is_none() {
        // Ground truth not in catalog
        return false;
    }
    
    let gt_idx = gt_idx.unwrap();
    
    // Compute delta for ALL 276K titles
    let mut scores: Vec<(usize, f64)> = all_titles.iter()
        .enumerate()
        .map(|(idx, title)| {
            let delta = semantic_delta_v3(&query_data.query, title);
            (idx, delta)
        })
        .collect();
    
    // Sort by delta ASCENDING (lower distance = better match)
    scores.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap());
    
    // Check if ground truth index is rank #1
    scores[0].0 == gt_idx
}
