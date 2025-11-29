use thiserror::Error;

/// Main error type for the game engine
#[derive(Error, Debug)]
pub enum GameEngineError {
    /// Database errors
    #[error("Database error: {0}")]
    Database(#[from] rusqlite::Error),

    /// HTTP request errors
    #[error("HTTP request failed: {0}")]
    HttpRequest(#[from] reqwest::Error),

    /// JSON serialization errors
    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),

    /// DRAKON API errors
    #[error("DRAKON API error: {0}")]
    DrakonApi(String),

    /// Provider errors
    #[error("Provider '{provider}' error: {message}")]
    Provider { provider: String, message: String },

    /// Cache errors
    #[error("Cache error: {0}")]
    Cache(String),

    /// No results found
    #[error("No results found for query: {0}")]
    NoResults(String),

    /// Generic errors
    #[error("{0}")]
    Other(String),
}

impl From<String> for GameEngineError {
    fn from(s: String) -> Self {
        GameEngineError::Other(s)
    }
}

impl From<&str> for GameEngineError {
    fn from(s: &str) -> Self {
        GameEngineError::Other(s.to_string())
    }
}

/// Result type alias
pub type Result<T> = std::result::Result<T, GameEngineError>;
