use rusqlite::{Connection, params, OptionalExtension};
use std::sync::{Arc, Mutex};
use async_trait::async_trait;
use chrono::{DateTime, Utc};

use crate::cache::{GameCache, CachedGame, CacheStats};
use crate::core::GameResult;
use crate::error::{Result, GameEngineError};

/// SQLite-based game cache implementation
/// 
/// Schema compatible with existing Python kissbot.db:
/// ```sql
/// CREATE TABLE game_cache (
///     query TEXT PRIMARY KEY,
///     game_data TEXT NOT NULL,
///     alternatives TEXT,
///     hit_count INTEGER DEFAULT 0,
///     cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
/// );
/// ```
pub struct SqliteCache {
    conn: Arc<Mutex<Connection>>,
}

impl SqliteCache {
    /// Create new SQLite cache
    pub async fn new(db_path: &str) -> Result<Self> {
        let conn = Connection::open(db_path)
            .map_err(|e| GameEngineError::Database(e))?;
        
        // Create table if not exists (compatible with Python schema)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS game_cache (
                query TEXT PRIMARY KEY,
                game_data TEXT NOT NULL,
                alternatives TEXT,
                hit_count INTEGER DEFAULT 0,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )",
            [],
        )?;
        
        // Create index for faster lookups
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cached_at ON game_cache(cached_at)",
            [],
        )?;
        
        Ok(Self {
            conn: Arc::new(Mutex::new(conn)),
        })
    }
    
    /// Normalize query for consistent cache lookups
    fn normalize_query(query: &str) -> String {
        query.trim().to_lowercase()
    }
}

#[async_trait]
impl GameCache for SqliteCache {
    async fn get(&self, query: &str) -> Result<Option<CachedGame>> {
        let normalized = Self::normalize_query(query);
        let conn = self.conn.lock().unwrap();
        
        let result = conn
            .query_row(
                "SELECT query, game_data, alternatives, hit_count, cached_at 
                 FROM game_cache 
                 WHERE query = ?",
                params![normalized],
                |row| {
                    let game_json: String = row.get(1)?;
                    let alternatives_json: Option<String> = row.get(2)?;
                    let hit_count: i32 = row.get(3)?;
                    
                    // Parse game data
                    let game: GameResult = serde_json::from_str(&game_json)
                        .map_err(|e| rusqlite::Error::ToSqlConversionFailure(Box::new(e)))?;
                    
                    // Parse alternatives
                    let alternatives: Vec<GameResult> = if let Some(json) = alternatives_json {
                        serde_json::from_str(&json)
                            .map_err(|e| rusqlite::Error::ToSqlConversionFailure(Box::new(e)))?
                    } else {
                        Vec::new()
                    };
                    
                    // Parse timestamp - handle both TEXT (Python) and INTEGER (SQLite)
                    let cached_at: DateTime<Utc> = match row.get::<_, String>(4) {
                        Ok(timestamp_str) => {
                            DateTime::parse_from_rfc3339(&timestamp_str)
                                .map(|dt| dt.with_timezone(&Utc))
                                .unwrap_or_else(|_| Utc::now())
                        }
                        Err(_) => {
                            // Try as INTEGER (Unix timestamp)
                            match row.get::<_, i64>(4) {
                                Ok(timestamp) => DateTime::from_timestamp(timestamp, 0)
                                    .unwrap_or_else(|| Utc::now())
                                    .with_timezone(&Utc),
                                Err(_) => Utc::now(),
                            }
                        }
                    };
                    
                    Ok(CachedGame {
                        query: normalized.clone(),
                        game,
                        alternatives,
                        hit_count,
                        cached_at,
                    })
                },
            )
            .optional()?;
        
        Ok(result)
    }
    
    async fn save(&self, query: &str, game: &GameResult, alternatives: &[GameResult]) -> Result<()> {
        let normalized = Self::normalize_query(query);
        let conn = self.conn.lock().unwrap();
        
        let game_json = serde_json::to_string(game)?;
        let alternatives_json = if alternatives.is_empty() {
            None
        } else {
            Some(serde_json::to_string(alternatives)?)
        };
        
        conn.execute(
            "INSERT OR REPLACE INTO game_cache (query, game_data, alternatives, hit_count, cached_at)
             VALUES (?1, ?2, ?3, COALESCE((SELECT hit_count FROM game_cache WHERE query = ?1), 0), ?4)",
            params![
                normalized,
                game_json,
                alternatives_json,
                Utc::now().to_rfc3339(),
            ],
        )?;
        
        Ok(())
    }
    
    async fn increment_hit(&self, query: &str) -> Result<()> {
        let normalized = Self::normalize_query(query);
        let conn = self.conn.lock().unwrap();
        
        conn.execute(
            "UPDATE game_cache SET hit_count = hit_count + 1 WHERE query = ?",
            params![normalized],
        )?;
        
        Ok(())
    }
    
    async fn stats(&self) -> Result<CacheStats> {
        let conn = self.conn.lock().unwrap();
        
        let total_entries: u64 = conn.query_row(
            "SELECT COUNT(*) FROM game_cache",
            [],
            |row| row.get(0),
        )?;
        
        let total_hits: u64 = conn.query_row(
            "SELECT COALESCE(SUM(hit_count), 0) FROM game_cache",
            [],
            |row| row.get(0),
        )?;
        
        let avg_hit_count: f64 = if total_entries > 0 {
            total_hits as f64 / total_entries as f64
        } else {
            0.0
        };
        
        let oldest_entry: Option<DateTime<Utc>> = conn
            .query_row(
                "SELECT MIN(cached_at) FROM game_cache",
                [],
                |row| {
                    // Try as TEXT first, then INTEGER
                    row.get::<_, Option<String>>(0)
                        .or_else(|_| row.get::<_, Option<i64>>(0).map(|ts| ts.map(|t| t.to_string())))
                },
            )
            .ok()
            .flatten()
            .and_then(|s| {
                DateTime::parse_from_rfc3339(&s)
                    .ok()
                    .map(|dt| dt.with_timezone(&Utc))
                    .or_else(|| s.parse::<i64>().ok().and_then(|ts| DateTime::from_timestamp(ts, 0).map(|dt| dt.with_timezone(&Utc))))
            });
        
        let newest_entry: Option<DateTime<Utc>> = conn
            .query_row(
                "SELECT MAX(cached_at) FROM game_cache",
                [],
                |row| {
                    row.get::<_, Option<String>>(0)
                        .or_else(|_| row.get::<_, Option<i64>>(0).map(|ts| ts.map(|t| t.to_string())))
                },
            )
            .ok()
            .flatten()
            .and_then(|s| {
                DateTime::parse_from_rfc3339(&s)
                    .ok()
                    .map(|dt| dt.with_timezone(&Utc))
                    .or_else(|| s.parse::<i64>().ok().and_then(|ts| DateTime::from_timestamp(ts, 0).map(|dt| dt.with_timezone(&Utc))))
            });
        
        Ok(CacheStats {
            total_entries,
            total_hits,
            avg_hit_count,
            oldest_entry,
            newest_entry,
        })
    }
    
    async fn cleanup(&self, max_age_days: i64) -> Result<u64> {
        let conn = self.conn.lock().unwrap();
        
        let cutoff_date = Utc::now() - chrono::Duration::days(max_age_days);
        
        let deleted = conn.execute(
            "DELETE FROM game_cache WHERE cached_at < ?",
            params![cutoff_date.to_rfc3339()],
        )?;
        
        Ok(deleted as u64)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_cache_create() {
        let cache = SqliteCache::new(":memory:").await.unwrap();
        let stats = cache.stats().await.unwrap();
        assert_eq!(stats.total_entries, 0);
    }

    #[tokio::test]
    async fn test_cache_save_and_get() {
        let cache = SqliteCache::new(":memory:").await.unwrap();
        
        let game = GameResult::new("steam", "730", "CS2");
        let alternatives = vec![
            GameResult::new("steam", "10", "Counter-Strike"),
        ];
        
        cache.save("cs2", &game, &alternatives).await.unwrap();
        
        let cached = cache.get("cs2").await.unwrap();
        assert!(cached.is_some());
        
        let cached = cached.unwrap();
        assert_eq!(cached.game.name, "CS2");
        assert_eq!(cached.alternatives.len(), 1);
        assert_eq!(cached.hit_count, 0);
    }

    #[tokio::test]
    async fn test_cache_normalize_query() {
        let cache = SqliteCache::new(":memory:").await.unwrap();
        
        let game = GameResult::new("steam", "1", "Game");
        cache.save("  TeSt Query  ", &game, &[]).await.unwrap();
        
        // Should find with different casing/whitespace
        assert!(cache.get("test query").await.unwrap().is_some());
        assert!(cache.get("TEST QUERY").await.unwrap().is_some());
        assert!(cache.get("  test query  ").await.unwrap().is_some());
    }

    #[tokio::test]
    async fn test_cache_increment_hit() {
        let cache = SqliteCache::new(":memory:").await.unwrap();
        
        let game = GameResult::new("steam", "1", "Game");
        cache.save("test", &game, &[]).await.unwrap();
        
        cache.increment_hit("test").await.unwrap();
        cache.increment_hit("test").await.unwrap();
        
        let cached = cache.get("test").await.unwrap().unwrap();
        assert_eq!(cached.hit_count, 2);
    }

    #[tokio::test]
    async fn test_cache_stats() {
        let cache = SqliteCache::new(":memory:").await.unwrap();
        
        let game1 = GameResult::new("steam", "1", "Game1");
        let game2 = GameResult::new("steam", "2", "Game2");
        
        cache.save("game1", &game1, &[]).await.unwrap();
        cache.save("game2", &game2, &[]).await.unwrap();
        
        cache.increment_hit("game1").await.unwrap();
        cache.increment_hit("game1").await.unwrap();
        cache.increment_hit("game2").await.unwrap();
        
        let stats = cache.stats().await.unwrap();
        assert_eq!(stats.total_entries, 2);
        assert_eq!(stats.total_hits, 3);
        assert_eq!(stats.avg_hit_count, 1.5);
        assert!(stats.oldest_entry.is_some());
        assert!(stats.newest_entry.is_some());
    }

    #[tokio::test]
    async fn test_cache_cleanup() {
        let cache = SqliteCache::new(":memory:").await.unwrap();
        
        let game = GameResult::new("steam", "1", "Game");
        cache.save("old_game", &game, &[]).await.unwrap();
        
        // Cleanup entries older than 0 days (should delete all)
        let deleted = cache.cleanup(0).await.unwrap();
        assert_eq!(deleted, 1);
        
        let stats = cache.stats().await.unwrap();
        assert_eq!(stats.total_entries, 0);
    }
}
