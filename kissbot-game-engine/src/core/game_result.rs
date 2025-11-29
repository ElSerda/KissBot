use serde::{Deserialize, Serialize};
use chrono::{DateTime, Utc};

fn default_provider() -> String {
    "unknown".to_string()
}

/// Deserialize year from string or int (Python compatibility)
fn deserialize_year<'de, D>(deserializer: D) -> Result<Option<i32>, D::Error>
where
    D: serde::Deserializer<'de>,
{
    use serde::de::Error;
    
    #[derive(Deserialize)]
    #[serde(untagged)]
    enum YearValue {
        Int(i32),
        String(String),
        Null,
    }
    
    match YearValue::deserialize(deserializer)? {
        YearValue::Int(i) => Ok(Some(i)),
        YearValue::String(s) => s.parse::<i32>()
            .map(Some)
            .map_err(|_| Error::custom(format!("Invalid year string: {}", s))),
        YearValue::Null => Ok(None),
    }
}

/// Represents a game with all metadata from various providers
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct GameResult {
    /// Provider source (steam, igdb, rawg)
    #[serde(default = "default_provider")]
    pub provider: String,
    
    /// Unique ID from provider
    #[serde(default)]
    pub id: String,
    
    /// Game name
    #[serde(default)]
    pub name: String,
    
    /// Short description
    #[serde(default)]
    pub short_description: String,
    
    /// Full description
    #[serde(default)]
    pub description: String,
    
    /// Release date (YYYY-MM-DD format or partial)
    #[serde(default)]
    pub release_date: String,
    
    /// Release year
    #[serde(default)]
    #[serde(deserialize_with = "deserialize_year")]
    pub year: Option<i32>,
    
    /// Developer(s)
    #[serde(default)]
    pub developers: Vec<String>,
    
    /// Publisher(s)
    #[serde(default)]
    pub publishers: Vec<String>,
    
    /// Genre(s)
    #[serde(default)]
    pub genres: Vec<String>,
    
    /// Platform(s)
    #[serde(default)]
    pub platforms: Vec<String>,
    
    /// Tags/keywords
    #[serde(default)]
    pub tags: Vec<String>,
    
    /// Metacritic score (0-100)
    #[serde(default)]
    pub metacritic_score: Option<i32>,
    
    /// User rating (0.0-10.0)
    #[serde(default)]
    pub rating: Option<f64>,
    
    /// Steam App ID (for Steam provider)
    #[serde(default)]
    pub steam_appid: Option<String>,
    
    /// IGDB ID (for IGDB provider)
    #[serde(default)]
    pub igdb_id: Option<String>,
    
    /// Header image URL
    #[serde(default)]
    pub header_image: String,
    
    /// Store/details page URL
    #[serde(default)]
    pub url: String,
    
    /// Timestamp when this result was fetched
    #[serde(default = "Utc::now")]
    pub fetched_at: DateTime<Utc>,
}

impl GameResult {
    /// Create a new GameResult with required fields
    pub fn new(provider: impl Into<String>, id: impl Into<String>, name: impl Into<String>) -> Self {
        Self {
            provider: provider.into(),
            id: id.into(),
            name: name.into(),
            short_description: String::new(),
            description: String::new(),
            release_date: String::new(),
            year: None,
            developers: Vec::new(),
            publishers: Vec::new(),
            genres: Vec::new(),
            platforms: Vec::new(),
            tags: Vec::new(),
            metacritic_score: None,
            rating: None,
            steam_appid: None,
            igdb_id: None,
            header_image: String::new(),
            url: String::new(),
            fetched_at: Utc::now(),
        }
    }

    /// Check if game is a DLC/expansion
    pub fn is_dlc(&self) -> bool {
        self.name.to_lowercase().contains("dlc") 
            || self.name.to_lowercase().contains("expansion")
            || self.tags.iter().any(|tag| tag.to_lowercase() == "dlc")
    }

    /// Get display name (for logging/UI)
    pub fn display_name(&self) -> String {
        if let Some(year) = self.year {
            format!("{} ({})", self.name, year)
        } else {
            self.name.clone()
        }
    }

    /// Serialize to JSON string
    pub fn to_json(&self) -> serde_json::Result<String> {
        serde_json::to_string(self)
    }

    /// Deserialize from JSON string
    pub fn from_json(json: &str) -> serde_json::Result<Self> {
        serde_json::from_str(json)
    }
}

impl Default for GameResult {
    fn default() -> Self {
        Self::new("unknown", "0", "Unknown Game")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_game_result_creation() {
        let game = GameResult::new("steam", "730", "Counter-Strike 2");
        assert_eq!(game.provider, "steam");
        assert_eq!(game.id, "730");
        assert_eq!(game.name, "Counter-Strike 2");
    }

    #[test]
    fn test_is_dlc() {
        let mut game = GameResult::new("steam", "1", "Base Game");
        assert!(!game.is_dlc());

        game.name = "Game DLC Pack".to_string();
        assert!(game.is_dlc());

        game.name = "Base Game".to_string();
        game.tags.push("DLC".to_string());
        assert!(game.is_dlc());
    }

    #[test]
    fn test_serialization() {
        let game = GameResult::new("steam", "730", "CS2");
        let json = game.to_json().unwrap();
        let deserialized = GameResult::from_json(&json).unwrap();
        assert_eq!(game.name, deserialized.name);
    }
}
