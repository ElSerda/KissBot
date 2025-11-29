use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::sync::Arc;
use tokio::runtime::Runtime;

use crate::{GameEngine as RustGameEngine, SearchQuery as RustSearchQuery};
use crate::core::{GameResult as RustGameResult, SearchResponse as RustSearchResponse};
use crate::providers::SteamProvider;

/// Python wrapper for GameEngine
#[pyclass]
struct GameEngine {
    engine: Arc<RustGameEngine>,
    runtime: Arc<Runtime>,
}

#[pymethods]
impl GameEngine {
    /// Create new GameEngine
    #[new]
    fn new(db_path: String) -> PyResult<Self> {
        let runtime = Arc::new(
            Runtime::new()
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?
        );
        
        let engine = runtime.block_on(async {
            let mut engine = RustGameEngine::new(&db_path).await
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;
            
            // Add Steam provider
            let steam = Arc::new(SteamProvider::new(None));
            engine.add_provider(steam);
            
            Ok::<_, PyErr>(engine)
        })?;
        
        Ok(Self {
            engine: Arc::new(engine),
            runtime,
        })
    }
    
    /// Search for a game
    fn search(&self, query: String, max_results: Option<usize>, use_cache: Option<bool>) -> PyResult<PyObject> {
        let search_query = RustSearchQuery {
            query,
            max_results: max_results.unwrap_or(5),
            use_cache: use_cache.unwrap_or(true),
        };
        
        let engine = self.engine.clone();
        let result = self.runtime.block_on(async move {
            engine.search(search_query).await
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))
        })?;
        
        // Convert to Python dict
        Python::with_gil(|py| {
            search_response_to_py(py, &result)
        })
    }
    
    /// Get cache statistics
    fn cache_stats(&self) -> PyResult<PyObject> {
        let engine = self.engine.clone();
        let stats = self.runtime.block_on(async move {
            engine.cache_stats().await
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))
        })?;
        
        Python::with_gil(|py| {
            let dict = PyDict::new(py);
            dict.set_item("total_entries", stats.total_entries)?;
            dict.set_item("total_hits", stats.total_hits)?;
            dict.set_item("avg_hit_count", stats.avg_hit_count)?;
            Ok(dict.into())
        })
    }
    
    /// Clean up old cache entries
    fn cleanup_cache(&self, max_age_days: i64) -> PyResult<u64> {
        let engine = self.engine.clone();
        self.runtime.block_on(async move {
            engine.cleanup_cache(max_age_days).await
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))
        })
    }
}

/// Convert GameResult to Python dict
fn game_result_to_py(py: Python, game: &RustGameResult) -> PyResult<PyObject> {
    let dict = PyDict::new(py);
    dict.set_item("provider", &game.provider)?;
    dict.set_item("id", &game.id)?;
    dict.set_item("name", &game.name)?;
    dict.set_item("short_description", &game.short_description)?;
    dict.set_item("description", &game.description)?;
    dict.set_item("release_date", &game.release_date)?;
    dict.set_item("year", game.year)?;
    dict.set_item("developers", &game.developers)?;
    dict.set_item("publishers", &game.publishers)?;
    dict.set_item("genres", &game.genres)?;
    dict.set_item("platforms", &game.platforms)?;
    dict.set_item("tags", &game.tags)?;
    dict.set_item("metacritic_score", game.metacritic_score)?;
    dict.set_item("rating", game.rating)?;
    dict.set_item("steam_appid", &game.steam_appid)?;
    dict.set_item("igdb_id", &game.igdb_id)?;
    dict.set_item("header_image", &game.header_image)?;
    dict.set_item("url", &game.url)?;
    Ok(dict.into())
}

/// Convert SearchResponse to Python dict
fn search_response_to_py(py: Python, response: &RustSearchResponse) -> PyResult<PyObject> {
    let dict = PyDict::new(py);
    dict.set_item("game", game_result_to_py(py, &response.game)?)?;
    dict.set_item("score", response.score)?;
    dict.set_item("result_type", format!("{:?}", response.result_type))?;
    
    // Alternatives
    let alternatives: PyResult<Vec<PyObject>> = response.alternatives
        .iter()
        .map(|alt| game_result_to_py(py, alt))
        .collect();
    dict.set_item("alternatives", alternatives?)?;
    
    dict.set_item("from_cache", response.from_cache)?;
    dict.set_item("latency_ms", response.latency_ms)?;
    dict.set_item("provider", &response.provider)?;
    dict.set_item("ranking_method", &response.ranking_method)?;
    
    Ok(dict.into())
}

/// Python module
#[pymodule]
fn kissbot_game_engine(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<GameEngine>()?;
    m.add("__version__", crate::VERSION)?;
    Ok(())
}
