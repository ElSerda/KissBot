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

fn main() {
    // Use ALL available threads for maximum performance
    let num_threads = std::thread::available_parallelism()
        .map(|n| n.get())
        .unwrap_or(16);
    
    rayon::ThreadPoolBuilder::new()
        .num_threads(num_threads)
        .build_global()
        .unwrap();
    
    println!("🦀 RUST CPU vs GPU CUDA - Steam 276K Benchmark");
    println!("{}", "=".repeat(80));
    println!("🧵 Using {} CPU threads (Rayon parallel)", num_threads);
    println!();
    
    // Load 276K Steam catalog
    println!("📥 Loading Steam catalog...");
    let steam_json = fs::read_to_string("../delta-s3/Dataset/steam-game/steam-game.json")
        .expect("Failed to read Steam dataset");
    
    let steam_data: SteamData = serde_json::from_str(&steam_json)
        .expect("Failed to parse Steam JSON");
    
    let all_titles: Vec<String> = steam_data.applist.apps
        .into_iter()
        .map(|app| app.name)
        .collect();
    
    println!("✅ Loaded {} Steam titles", all_titles.len());
    println!();
    
    // Same test queries as GPU benchmark
    let test_queries = vec![
        "Counter-Strike",
        "Half-Life",
        "Portal 2",
        "Team Fortress",
        "Dota 2",
    ];
    
    println!("{}", "=".repeat(80));
    println!("🦀 RUST CPU (Rayon Parallel)");
    println!("{}", "=".repeat(80));
    println!();
    
    let mut total_time_ns = 0u128;
    let mut times_ns = Vec::new();
    
    for (i, query) in test_queries.iter().enumerate() {
        let start = Instant::now();
        
        // Compute delta for ALL 276K titles in PARALLEL
        let mut scores: Vec<(usize, f64)> = all_titles.par_iter()
            .enumerate()
            .map(|(idx, title)| {
                let delta = semantic_delta_v3(query, title);
                (idx, delta)
            })
            .collect();
        
        // Sort by delta ASCENDING (lower = better)
        scores.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap());
        
        let elapsed = start.elapsed();
        let elapsed_ns = elapsed.as_nanos();
        let elapsed_ms = elapsed.as_secs_f64() * 1000.0;
        
        times_ns.push(elapsed_ns);
        total_time_ns += elapsed_ns;
        
        // Show top-3 for first query
        if i == 0 {
            println!("   Top-3 for '{}':", query);
            for (rank, (idx, score)) in scores.iter().take(3).enumerate() {
                println!("     {}. [{}] {} → {:.3}", rank + 1, idx, all_titles[*idx], score);
            }
            println!();
        }
        
        println!("   Query {}: {:.3} ms  ({:>15} ns)", i + 1, elapsed_ms, elapsed_ns);
    }
    
    let avg_ns = total_time_ns / test_queries.len() as u128;
    let avg_ms = avg_ns as f64 / 1_000_000.0;
    
    println!();
    println!("   Average times:");
    println!("     Total:    {:.3} ms  ({:>15} ns)", avg_ms, avg_ns);
    println!();
    
    println!("{}", "=".repeat(80));
    println!("📊 COMPARISON vs GPU CUDA (from previous benchmark)");
    println!("{}", "=".repeat(80));
    println!();
    
    // GPU results (from previous run)
    let gpu_total_ns = 61_881_269u128;
    let gpu_kernel_ns = 0u128;  // Too fast to measure
    let cpu_python_ns = 10_602_937_237u128;
    
    println!("{:<30} {:>20} {:>20}", "Metric", "Rust CPU", "GPU CUDA");
    println!("{}", "-".repeat(72));
    println!("{:<30} {:>20} {:>20}", 
             "Query time (ns)", 
             format!("{}", avg_ns),
             format!("{}", gpu_total_ns));
    println!("{:<30} {:>20} {:>20}", 
             "Query time (ms)", 
             format!("{:.3}", avg_ms),
             format!("{:.3}", gpu_total_ns as f64 / 1_000_000.0));
    println!("{:<30} {:>20} {:>20}", 
             "Speedup vs Python CPU", 
             format!("{:.0}x", cpu_python_ns as f64 / avg_ns as f64),
             format!("171x"));
    println!("{:<30} {:>20} {:>20}", 
             "Rust vs GPU", 
             format!("1.0x"),
             format!("{:.2}x", avg_ns as f64 / gpu_total_ns as f64));
    println!();
    
    println!("{}", "=".repeat(80));
    println!("💡 KEY FINDINGS");
    println!("{}", "=".repeat(80));
    println!();
    
    let rust_speedup = cpu_python_ns as f64 / avg_ns as f64;
    let gpu_speedup_vs_rust = avg_ns as f64 / gpu_total_ns as f64;
    
    println!("  🦀 Rust CPU is {:.0}x faster than Python CPU!", rust_speedup);
    println!("  🎮 GPU is {:.1}x faster than Rust CPU!", gpu_speedup_vs_rust);
    println!("  ⚡ Rust can handle {:.1} queries per second", 1000.0 / avg_ms);
    println!("  🧵 Using {} CPU threads for parallelism", num_threads);
    println!();
    
    if gpu_speedup_vs_rust < 1.0 {
        println!("  ✅ Rust CPU WINS for 276K dataset!");
    } else if gpu_speedup_vs_rust < 2.0 {
        println!("  ⚖️  Rust CPU competitive with GPU (within 2x)");
    } else {
        println!("  🎮 GPU clearly wins ({:.1}x faster)", gpu_speedup_vs_rust);
    }
    
    println!();
    println!("{}", "=".repeat(80));
}
