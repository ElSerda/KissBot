use axum::{
    extract::{Json, State},
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::{get, post},
    Router,
};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tower_http::cors::CorsLayer;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

use kissbot_game_engine::{GameEngine, SearchQuery, SearchResponse, providers::SteamProvider};

#[derive(Clone)]
struct AppState {
    engine: Arc<GameEngine>,
}

#[derive(Debug, Deserialize)]
struct SearchRequest {
    query: String,
    #[serde(default = "default_max_results")]
    max_results: usize,
    #[serde(default = "default_true")]
    use_cache: bool,
}

fn default_max_results() -> usize { 5 }
fn default_true() -> bool { true }

#[derive(Debug, Serialize)]
struct ErrorResponse {
    error: String,
}

#[derive(Debug, Serialize)]
struct HealthResponse {
    status: String,
    version: String,
}

#[derive(Debug, Serialize)]
struct StatsResponse {
    cache: CacheStatsDto,
}

#[derive(Debug, Serialize)]
struct CacheStatsDto {
    total_entries: u64,
    total_hits: u64,
    avg_hit_count: f64,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize tracing
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "game_engine_server=debug,kissbot_game_engine=debug".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    // Parse CLI args
    let db_path = std::env::var("DB_PATH").unwrap_or_else(|_| "kissbot.db".to_string());
    let port = std::env::var("PORT")
        .ok()
        .and_then(|p| p.parse::<u16>().ok())
        .unwrap_or(8090);

    tracing::info!("🚀 Starting KissBot Game Engine Server");
    tracing::info!("📦 Database: {}", db_path);
    tracing::info!("🔌 Port: {}", port);

    // Create game engine
    let mut engine = GameEngine::new(&db_path).await?;
    
    // Add Steam provider
    let steam_provider = Arc::new(SteamProvider::new(None));
    engine.add_provider(steam_provider);
    
    let state = AppState {
        engine: Arc::new(engine),
    };

    // Build router
    let app = Router::new()
        .route("/health", get(health_handler))
        .route("/v1/search", post(search_handler))
        .route("/v1/stats", get(stats_handler))
        .layer(CorsLayer::permissive())
        .with_state(state);

    // Start server
    let addr = format!("0.0.0.0:{}", port);
    tracing::info!("🎮 Server listening on http://{}", addr);
    
    let listener = tokio::net::TcpListener::bind(&addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}

async fn health_handler() -> Json<HealthResponse> {
    Json(HealthResponse {
        status: "ok".to_string(),
        version: kissbot_game_engine::VERSION.to_string(),
    })
}

async fn search_handler(
    State(state): State<AppState>,
    Json(req): Json<SearchRequest>,
) -> Result<Json<SearchResponse>, AppError> {
    tracing::debug!("Search request: {:?}", req);
    
    let query = SearchQuery {
        query: req.query.clone(),
        max_results: req.max_results,
        use_cache: req.use_cache,
    };
    
    let result = state.engine.search(query).await?;
    
    tracing::info!(
        "✅ {} → {} ({}%, {}ms)",
        req.query,
        result.game.name,
        result.score,
        result.latency_ms
    );
    
    Ok(Json(result))
}

async fn stats_handler(
    State(state): State<AppState>,
) -> Result<Json<StatsResponse>, AppError> {
    let cache_stats = state.engine.cache_stats().await?;
    
    Ok(Json(StatsResponse {
        cache: CacheStatsDto {
            total_entries: cache_stats.total_entries,
            total_hits: cache_stats.total_hits,
            avg_hit_count: cache_stats.avg_hit_count,
        },
    }))
}

// Error handling
struct AppError(kissbot_game_engine::error::GameEngineError);

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, message) = match self.0 {
            kissbot_game_engine::error::GameEngineError::NoResults(query) => {
                (StatusCode::NOT_FOUND, format!("No results found for: {}", query))
            }
            kissbot_game_engine::error::GameEngineError::Provider { provider, message } => {
                (StatusCode::BAD_GATEWAY, format!("Provider '{}' error: {}", provider, message))
            }
            e => (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()),
        };
        
        tracing::error!("❌ Error: {} - {}", status, message);
        
        (status, Json(ErrorResponse { error: message })).into_response()
    }
}

impl<E> From<E> for AppError
where
    E: Into<kissbot_game_engine::error::GameEngineError>,
{
    fn from(err: E) -> Self {
        Self(err.into())
    }
}
