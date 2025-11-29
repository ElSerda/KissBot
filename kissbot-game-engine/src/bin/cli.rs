use clap::{Parser, Subcommand};
use kissbot_game_engine::{GameEngine, SearchQuery, providers::SteamProvider};
use std::sync::Arc;

#[derive(Parser)]
#[command(name = "game-engine-cli")]
#[command(about = "KissBot Game Engine CLI", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
    
    /// Database path
    #[arg(short, long, default_value = "kissbot.db")]
    db: String,
}

#[derive(Subcommand)]
enum Commands {
    /// Search for a game
    Search {
        /// Search query
        query: String,
        
        /// Maximum results
        #[arg(short, long, default_value = "5")]
        max_results: usize,
        
        /// Disable cache
        #[arg(long)]
        no_cache: bool,
    },
    
    /// Get cache statistics
    Stats,
    
    /// Clean up old cache entries
    Cleanup {
        /// Maximum age in days
        #[arg(short, long, default_value = "30")]
        max_age_days: i64,
    },
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize tracing
    tracing_subscriber::fmt::init();
    
    let cli = Cli::parse();
    
    // Create engine
    let mut engine = GameEngine::new(&cli.db).await?;
    
    // Add Steam provider
    let steam = Arc::new(SteamProvider::new(None));
    engine.add_provider(steam);
    
    match cli.command {
        Commands::Search { query, max_results, no_cache } => {
            println!("🔍 Searching for: {}", query);
            
            let search_query = SearchQuery {
                query: query.clone(),
                max_results,
                use_cache: !no_cache,
            };
            
            let result = engine.search(search_query).await?;
            
            println!("\n✅ Found: {}", result.game.name);
            println!("   Score: {:.1}%", result.score);
            println!("   Provider: {}", result.provider);
            println!("   Year: {}", result.game.year.map(|y| y.to_string()).unwrap_or_else(|| "N/A".to_string()));
            println!("   URL: {}", result.game.url);
            println!("   Cached: {}", result.from_cache);
            println!("   Latency: {:.2}ms", result.latency_ms);
            
            if !result.alternatives.is_empty() {
                println!("\n📋 Alternatives:");
                for (i, alt) in result.alternatives.iter().enumerate() {
                    println!("   {}. {}", i + 1, alt.name);
                }
            }
        }
        
        Commands::Stats => {
            let stats = engine.cache_stats().await?;
            
            println!("📊 Cache Statistics:");
            println!("   Total entries: {}", stats.total_entries);
            println!("   Total hits: {}", stats.total_hits);
            println!("   Avg hits/entry: {:.2}", stats.avg_hit_count);
            
            if let Some(oldest) = stats.oldest_entry {
                println!("   Oldest entry: {}", oldest.format("%Y-%m-%d %H:%M:%S"));
            }
            
            if let Some(newest) = stats.newest_entry {
                println!("   Newest entry: {}", newest.format("%Y-%m-%d %H:%M:%S"));
            }
        }
        
        Commands::Cleanup { max_age_days } => {
            println!("🧹 Cleaning up entries older than {} days...", max_age_days);
            
            let deleted = engine.cleanup_cache(max_age_days).await?;
            
            println!("✅ Deleted {} entries", deleted);
        }
    }
    
    Ok(())
}
