use delta_s3::semantic_delta_v3;
use serde::{Deserialize, Serialize};
use std::fs;
use std::time::Instant;
use rayon::prelude::*;

#[derive(Debug, Deserialize)]
struct Dataset {
    metadata: Metadata,
    titles: Vec<String>,
    queries: Vec<Query>,
}

#[derive(Debug, Deserialize)]
struct Metadata {
    total_titles: usize,
    total_queries: usize,
}

#[derive(Debug, Deserialize)]
struct Query {
    query: String,
    ground_truth: String,
    pattern: String,
}

fn main() {
    // Use ALL available threads (auto-detect)
    let num_threads = std::thread::available_parallelism()
        .map(|n| n.get())
        .unwrap_or(16);
    
    rayon::ThreadPoolBuilder::new()
        .num_threads(num_threads)
        .build_global()
        .unwrap();
    
    println!("💀 Δₛ³ v3.1 FULL CATALOG BENCHMARK 💀");
    println!("{}", "=".repeat(80));
    println!("🧵 Using {} threads (auto-detected)", num_threads);
    
    // Load dataset
    println!("\n📥 Loading dataset...");
    let json_path = "../delta-s3/datasets/steam_games_targeted.json";
    let json_str = fs::read_to_string(json_path)
        .expect("Failed to read dataset");
    
    let dataset: Dataset = serde_json::from_str(&json_str)
        .expect("Failed to parse JSON");
    
    println!("✅ Loaded {} titles, {} queries", 
             dataset.titles.len(), 
             dataset.queries.len());
    
    let total_comparisons = dataset.queries.len() as u64 * dataset.titles.len() as u64;
    println!("⚠️  WARNING: {} total comparisons ({} million)", 
             total_comparisons,
             total_comparisons / 1_000_000);
    
    // Benchmark setup
    println!("\n{}", "=".repeat(80));
    println!("📊 FULL CATALOG Evaluation");
    println!("{}", "=".repeat(80));
    println!("Strategy: EVERY query against ALL {} titles", dataset.titles.len());
    println!("Expected: 97.45% Acc@1 (if system survives 💀)");
    println!("{}", "=".repeat(80));
    
    // Evaluate
    println!("\n🔥 Starting full catalog benchmark...");
    let start = Instant::now();
    
    let results: Vec<bool> = dataset.queries.par_iter()
        .enumerate()
        .map(|(idx, query_data)| {
            if (idx + 1) % 500 == 0 {
                let progress = 100.0 * (idx + 1) as f64 / dataset.queries.len() as f64;
                let elapsed = start.elapsed().as_secs_f64();
                let eta = elapsed / (idx + 1) as f64 * dataset.queries.len() as f64 - elapsed;
                println!("Progress: {}/{} ({:.1}%) | Elapsed: {:.1}s | ETA: {:.0}s", 
                        idx + 1, 
                        dataset.queries.len(),
                        progress,
                        elapsed,
                        eta);
            }
            
            evaluate_query_full(&query_data, &dataset.titles)
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
    println!("📈 RESULTS - FULL CATALOG (100% Coverage)");
    println!("{}", "=".repeat(80));
    println!("Total queries:  {}", total);
    println!("Accuracy@1:     {:.4} ({}/{})", accuracy, correct, total);
    
    println!("\n⏱️  PERFORMANCE:");
    println!("Total time:     {:.2}s", total_time_s);
    println!("Avg time:       {:.2}ms per query ({} comparisons)", 
             avg_time_ms, 
             dataset.titles.len());
    println!("Throughput:     {:.0} queries/s", throughput);
    println!("Comparisons:    {:.0} M/s ({} million total)", 
             comparisons_per_sec / 1_000_000.0,
             total_comparisons / 1_000_000);
    println!("{}", "=".repeat(80));
    
    println!("\n💡 Verdict: {}", 
             if accuracy > 0.97 && total_time_s < 120.0 { 
                 "✅ BEAST MODE ACTIVATED" 
             } else if total_time_s < 120.0 {
                 "⚡ FAST BUT CHECK ACCURACY"
             } else {
                 "⏳ SLOW - OPTIMIZE NEEDED"
             });
    
    // Comparison with light benchmark
    let python_acc = 0.9745;
    let light_throughput = 14539.0; // 32T WSL with 101 comparisons
    let scaling_factor = dataset.titles.len() as f64 / 101.0;
    
    println!("\n🐍 Comparison:");
    println!("   Accuracy:   {:.2}% vs {:.2}% ({:+.2} points)", 
             accuracy * 100.0, 
             python_acc * 100.0,
             (accuracy - python_acc) * 100.0);
    println!("   Light bench: {:.0} q/s (101 comp) → Full: {:.0} q/s ({} comp)", 
             light_throughput,
             throughput,
             dataset.titles.len());
    println!("   Expected slowdown: {:.1}x → Actual: {:.1}x", 
             scaling_factor,
             light_throughput / throughput);
    
    println!("\n{}", "=".repeat(80));
    println!("✅ System survived! No BSOD 🎉");
}

fn evaluate_query_full(query_data: &Query, all_titles: &[String]) -> bool {
    // Find ground truth index
    let gt_idx = all_titles.iter()
        .position(|t| t == &query_data.ground_truth);
    
    if gt_idx.is_none() {
        // Ground truth not in catalog
        return false;
    }
    
    let gt_idx = gt_idx.unwrap();
    
    // Compute delta for ALL titles
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
