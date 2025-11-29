/*!
Benchmark binary - Match Python benchmark_optimized.py

Tests 13,259 queries from steam_games_targeted.json against 5,000 titles.
Expected: 97.45% Acc@1 (same as Python)
*/

use delta_s3::semantic_delta_v3;
use rayon::prelude::*;
use serde::{Deserialize, Serialize};
use std::fs;
use std::time::Instant;

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
    println!("🚀 Δₛ³ v3.1 Rust Benchmark");
    println!("{}", "=".repeat(80));
    
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
    
    // Benchmark setup
    println!("\n{}", "=".repeat(80));
    println!("📊 Optimized Evaluation");
    println!("{}", "=".repeat(80));
    println!("Strategy: Each query against ground truth + 100 random distractors");
    println!("Expected: 97.45% Acc@1 (validated in Python)");
    println!("{}", "=".repeat(80));
    
    // Evaluate
    let start = Instant::now();
    
    let results: Vec<bool> = dataset.queries.par_iter()
        .enumerate()
        .map(|(idx, query_data)| {
            if (idx + 1) % 1000 == 0 {
                println!("Progress: {}/{} ({:.1}%)", 
                        idx + 1, 
                        dataset.queries.len(),
                        100.0 * (idx + 1) as f64 / dataset.queries.len() as f64);
            }
            
            evaluate_query(&query_data, &dataset.titles)
        })
        .collect();
    
    let elapsed = start.elapsed();
    
    // Compute metrics
    let correct = results.iter().filter(|&&x| x).count();
    let total = results.len();
    let accuracy = correct as f64 / total as f64;
    
    let avg_time_ms = elapsed.as_secs_f64() * 1000.0 / total as f64;
    let throughput = total as f64 / elapsed.as_secs_f64();
    
    // Print results
    println!("\n{}", "=".repeat(80));
    println!("📈 RESULTS - Targeted Dataset (100% Pattern Coverage)");
    println!("{}", "=".repeat(80));
    println!("Total queries:  {}", total);
    println!("Accuracy@1:     {:.4} ({}/{})", accuracy, correct, total);
    println!();
    println!("⏱️  PERFORMANCE:");
    println!("Total time:     {:.2}s", elapsed.as_secs_f64());
    println!("Avg time:       {:.2}ms per query (101 comparisons)", avg_time_ms);
    println!("Throughput:     {:.0} queries/s", throughput);
    println!("{}", "=".repeat(80));
    println!();
    
    // Verdict
    let verdict = if accuracy >= 0.95 {
        "✅ EXCELLENT"
    } else if accuracy >= 0.90 {
        "🟢 GOOD"
    } else if accuracy >= 0.80 {
        "🟡 ACCEPTABLE"
    } else {
        "🔴 NEEDS IMPROVEMENT"
    };
    
    println!("💡 Verdict: {}", verdict);
    
    // Compare with Python baseline
    let python_acc = 0.9745;
    let python_throughput = 51.0;
    
    let acc_diff = (accuracy - python_acc) * 100.0;
    let speedup = throughput / python_throughput;
    
    println!();
    println!("🐍 Comparison with Python:");
    println!("   Accuracy:   {:.2}% vs {:.2}% ({:+.2} points)", 
             accuracy * 100.0, 
             python_acc * 100.0,
             acc_diff);
    println!("   Throughput: {:.0} vs {:.0} q/s ({:.1}x speedup)", 
             throughput,
             python_throughput,
             speedup);
    
    println!("\n{}", "=".repeat(80));
    println!("✅ Benchmark complete!");
}

fn evaluate_query(query_data: &Query, all_titles: &[String]) -> bool {
    use rand::seq::SliceRandom;
    use rand::SeedableRng;
    
    // Find ground truth index
    let gt_idx = all_titles.iter()
        .position(|t| t == &query_data.ground_truth);
    
    if gt_idx.is_none() {
        return false;
    }
    
    let gt_idx = gt_idx.unwrap();
    
    // Create candidate set: ground truth + 100 random distractors
    let mut rng = rand::rngs::StdRng::seed_from_u64(42);
    
    let distractors: Vec<usize> = (0..all_titles.len())
        .filter(|&i| i != gt_idx)
        .collect::<Vec<_>>()
        .choose_multiple(&mut rng, 100.min(all_titles.len() - 1))
        .cloned()
        .collect();
    
    let mut candidates = vec![gt_idx];
    candidates.extend(distractors);
    
    // Compute deltas
    let mut deltas: Vec<(f64, usize)> = candidates.iter()
        .map(|&idx| {
            let delta = semantic_delta_v3(&query_data.query, &all_titles[idx]);
            (delta, idx)
        })
        .collect();
    
    // Sort by delta (ascending = best match first)
    deltas.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap());
    
    // Check if ground truth is #1
    deltas[0].1 == gt_idx
}
