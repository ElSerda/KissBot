use async_trait::async_trait;
use reqwest::Client;
use serde::Deserialize;
use std::time::Duration;

use crate::core::GameResult;
use crate::providers::GameProvider;
use crate::error::{Result, GameEngineError};

/// Steam API provider
pub struct SteamProvider {
    client: Client,
}

#[derive(Debug, Deserialize)]
struct SteamApp {
    appid: u64,
    name: String,
    #[serde(default)]
    icon: String,
    #[serde(default)]
    logo: String,
}

#[derive(Debug, Deserialize)]
struct SteamAppDetailsResponse {
    #[serde(flatten)]
    apps: std::collections::HashMap<String, AppDetailsData>,
}

#[derive(Debug, Deserialize)]
struct AppDetailsData {
    success: bool,
    #[serde(default)]
    data: Option<SteamAppDetails>,
}

#[derive(Debug, Deserialize, Default)]
struct SteamAppDetails {
    #[serde(default)]
    name: String,
    #[serde(default)]
    steam_appid: u64,
    #[serde(default)]
    short_description: String,
    #[serde(default)]
    detailed_description: String,
    #[serde(default)]
    header_image: String,
    #[serde(default)]
    developers: Vec<String>,
    #[serde(default)]
    publishers: Vec<String>,
    #[serde(default)]
    genres: Vec<SteamGenre>,
    #[serde(default)]
    platforms: SteamPlatforms,
    #[serde(default)]
    release_date: SteamReleaseDate,
    #[serde(default)]
    metacritic: Option<SteamMetacritic>,
}

#[derive(Debug, Deserialize)]
struct SteamGenre {
    description: String,
}

#[derive(Debug, Deserialize, Default)]
struct SteamPlatforms {
    #[serde(default)]
    windows: bool,
    #[serde(default)]
    mac: bool,
    #[serde(default)]
    linux: bool,
}

#[derive(Debug, Deserialize, Default)]
struct SteamReleaseDate {
    #[serde(default)]
    date: String,
}

#[derive(Debug, Deserialize)]
struct SteamMetacritic {
    score: i32,
}

impl SteamProvider {
    /// Create new Steam provider
    pub fn new(api_key: Option<String>) -> Self {
        let client = Client::builder()
            .timeout(Duration::from_secs(10))
            .build()
            .expect("Failed to create HTTP client");
        
        Self { client }
    }
    
    /// Search Steam store
    async fn search_steam(&self, query: &str) -> Result<Vec<SteamApp>> {
        let url = format!(
            "https://steamcommunity.com/actions/SearchApps/{}",
            urlencoding::encode(query)
        );
        
        let response = self.client
            .get(&url)
            .send()
            .await
            .map_err(|e| GameEngineError::Provider {
                provider: "steam".to_string(),
                message: format!("Search request failed: {}", e),
            })?;
        
        if !response.status().is_success() {
            return Err(GameEngineError::Provider {
                provider: "steam".to_string(),
                message: format!("HTTP {}", response.status()),
            });
        }
        
        // Steam API returns array directly, not wrapped in object
        let apps: Vec<SteamApp> = response
            .json()
            .await
            .map_err(|e| GameEngineError::Provider {
                provider: "steam".to_string(),
                message: format!("Invalid JSON: {}", e),
            })?;
        
        Ok(apps)
    }
    
    /// Get Steam app details
    async fn get_app_details(&self, appid: &str) -> Result<GameResult> {
        let url = format!(
            "https://store.steampowered.com/api/appdetails?appids={}",
            appid
        );
        
        let response = self.client
            .get(&url)
            .send()
            .await
            .map_err(|e| GameEngineError::Provider {
                provider: "steam".to_string(),
                message: format!("Details request failed: {}", e),
            })?;
        
        let details_response: SteamAppDetailsResponse = response
            .json()
            .await
            .map_err(|e| GameEngineError::Provider {
                provider: "steam".to_string(),
                message: format!("Invalid JSON: {}", e),
            })?;
        
        let app_data = details_response
            .apps
            .get(appid)
            .ok_or_else(|| GameEngineError::Provider {
                provider: "steam".to_string(),
                message: format!("App {} not found", appid),
            })?;
        
        if !app_data.success {
            return Err(GameEngineError::Provider {
                provider: "steam".to_string(),
                message: format!("App {} fetch failed", appid),
            });
        }
        
        let details = app_data.data.as_ref().ok_or_else(|| {
            GameEngineError::Provider {
                provider: "steam".to_string(),
                message: "No data in response".to_string(),
            }
        })?;
        
        Ok(self.details_to_game_result(details))
    }
    
    /// Convert Steam details to GameResult
    fn details_to_game_result(&self, details: &SteamAppDetails) -> GameResult {
        let mut platforms = Vec::new();
        if details.platforms.windows { platforms.push("Windows".to_string()); }
        if details.platforms.mac { platforms.push("Mac".to_string()); }
        if details.platforms.linux { platforms.push("Linux".to_string()); }
        
        let genres = details.genres.iter()
            .map(|g| g.description.clone())
            .collect();
        
        // Extract year from date (format: "MMM DD, YYYY" or just "YYYY")
        let year = details.release_date.date
            .split(',')
            .last()
            .and_then(|s| s.trim().parse::<i32>().ok())
            .or_else(|| details.release_date.date.parse::<i32>().ok());
        
        let mut game = GameResult::new(
            "steam",
            details.steam_appid.to_string(),
            &details.name,
        );
        
        game.short_description = details.short_description.clone();
        game.description = details.detailed_description.clone();
        game.release_date = details.release_date.date.clone();
        game.year = year;
        game.developers = details.developers.clone();
        game.publishers = details.publishers.clone();
        game.genres = genres;
        game.platforms = platforms;
        game.metacritic_score = details.metacritic.as_ref().map(|m| m.score);
        game.steam_appid = Some(details.steam_appid.to_string());
        game.header_image = details.header_image.clone();
        game.url = format!("https://store.steampowered.com/app/{}", details.steam_appid);
        
        game
    }
}

#[async_trait]
impl GameProvider for SteamProvider {
    async fn search(&self, query: &str) -> Result<Vec<GameResult>> {
        let apps = self.search_steam(query).await?;
        
        let mut results = Vec::new();
        
        // Fetch details for top results (limit to avoid rate limiting)
        for app in apps.iter().take(10) {
            match self.get_app_details(&app.appid.to_string()).await {
                Ok(game) => results.push(game),
                Err(e) => {
                    tracing::warn!("Failed to fetch details for {}: {}", app.name, e);
                    
                    // Create minimal result from search data
                    let mut game = GameResult::new("steam", app.appid.to_string(), &app.name);
                    game.steam_appid = Some(app.appid.to_string());
                    game.header_image = app.logo.clone();
                    game.url = format!("https://store.steampowered.com/app/{}", app.appid);
                    results.push(game);
                }
            }
            
            // Small delay to avoid rate limiting
            tokio::time::sleep(Duration::from_millis(100)).await;
        }
        
        Ok(results)
    }
    
    async fn get_by_id(&self, id: &str) -> Result<GameResult> {
        self.get_app_details(id).await
    }
    
    fn name(&self) -> &str {
        "steam"
    }
    
    async fn is_available(&self) -> bool {
        // Try to fetch a known app (CS2 - 730)
        self.get_app_details("730").await.is_ok()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    #[ignore] // Requires network access
    async fn test_steam_search() {
        let provider = SteamProvider::new(None);
        let results = provider.search("counter-strike").await.unwrap();
        
        assert!(!results.is_empty());
        assert!(results.iter().any(|g| g.name.contains("Counter-Strike")));
    }

    #[tokio::test]
    #[ignore] // Requires network access
    async fn test_steam_get_by_id() {
        let provider = SteamProvider::new(None);
        let game = provider.get_by_id("730").await.unwrap();
        
        assert_eq!(game.provider, "steam");
        assert!(game.name.contains("Counter-Strike"));
        assert_eq!(game.steam_appid, Some("730".to_string()));
    }
}
