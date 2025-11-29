use delta_s3::semantic_delta_v3;
use serde::Deserialize;
use std::fs;

#[derive(Debug, Deserialize)]
struct Dataset {
    titles: Vec<String>,
    queries: Vec<Query>,
}

#[derive(Debug, Deserialize)]
struct Query {
    query: String,
    ground_truth: String,
}

fn main() {
    println!("🔍 Debug FIRST query");
    
    let json_path = "../delta-s3/datasets/steam_games_targeted.json";
    let json_str = fs::read_to_string(json_path).unwrap();
    let dataset: Dataset = serde_json::from_str(&json_str).unwrap();
    
    let first_query = &dataset.queries[0];
    
    println!("\nQuery: '{}'", first_query.query);
    println!("Ground truth: '{}'", first_query.ground_truth);
    
    // Find GT index
    let gt_idx = dataset.titles.iter()
        .position(|t| t == &first_query.ground_truth);
    
    println!("GT found at index: {:?}", gt_idx);
    
    if let Some(idx) = gt_idx {
        println!("Title at GT index: '{}'", dataset.titles[idx]);
        
        // Compute deltas for first 10 titles
        println!("\nTop 10 scores:");
        let mut scores: Vec<(usize, f64, &String)> = dataset.titles.iter()
            .enumerate()
            .take(10)
            .map(|(i, title)| {
                let delta = semantic_delta_v3(&first_query.query, title);
                (i, delta, title)
            })
            .collect();
        
        scores.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
        
        for (i, (title_idx, delta, title)) in scores.iter().enumerate() {
            let marker = if *title_idx == idx { "← GT" } else { "" };
            println!("  {}. [idx={}] Δ={:.4} '{}' {}", i+1, title_idx, delta, title, marker);
        }
        
        // Now check ALL titles
        println!("\n🔥 Computing delta for ALL {} titles...", dataset.titles.len());
        let mut all_scores: Vec<(usize, f64)> = dataset.titles.iter()
            .enumerate()
            .map(|(i, title)| {
                let delta = semantic_delta_v3(&first_query.query, title);
                (i, delta)
            })
            .collect();
        
        all_scores.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
        
        println!("\nTop 5 overall:");
        for (rank, (title_idx, delta)) in all_scores.iter().take(5).enumerate() {
            let marker = if *title_idx == idx { "← GT ✅" } else { "" };
            println!("  {}. [idx={}] Δ={:.4} '{}' {}", 
                     rank+1, 
                     title_idx, 
                     delta, 
                     dataset.titles[*title_idx],
                     marker);
        }
        
        // Find GT rank
        let gt_rank = all_scores.iter()
            .position(|(i, _)| *i == idx)
            .map(|r| r + 1);
        
        println!("\nGround truth rank: {:?}", gt_rank);
        println!("Result: {}", if gt_rank == Some(1) { "✅ PASS" } else { "❌ FAIL" });
    } else {
        println!("❌ Ground truth NOT FOUND in titles!");
    }
}
