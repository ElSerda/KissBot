//! ⏱️ HTTPX Timeout Configuration for Neural Synapses
//!
//! httpx.Timeout() requires 4 explicit parameters:
//! - connect : Establish TCP connection
//! - read    : Read response (LLM streaming = LONG)
//! - write   : Send JSON payload
//! - pool    : Get connection from pool
//!
//! Reference: https://www.python-httpx.org/advanced/#timeout-configuration

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Configuration des timeouts HTTPX avec valeurs par défaut optimisées.
///
/// # Examples
///
/// ```
/// use timeout_config::TimeoutConfig;
///
/// // Defaults
/// let timeouts = TimeoutConfig::default();
/// assert_eq!(timeouts.connect, 5.0);
///
/// // From config
/// let mut config = HashMap::new();
/// config.insert("timeout_connect".to_string(), 3.0);
/// config.insert("timeout_inference".to_string(), 60.0);
/// let timeouts = TimeoutConfig::from_config(&config);
/// assert_eq!(timeouts.connect, 3.0);
/// assert_eq!(timeouts.read, 60.0);
/// ```
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct TimeoutConfig {
    /// TCP connection timeout (short: server down = fast fail)
    pub connect: f64,
    
    /// LLM streaming timeout (long: token-by-token generation)
    pub read: f64,
    
    /// Send payload timeout (medium: can be slow with large context)
    pub write: f64,
    
    /// Connection pool timeout (short: wait for free connection)
    pub pool: f64,
}

impl Default for TimeoutConfig {
    fn default() -> Self {
        Self {
            connect: 5.0,
            read: 30.0,
            write: 10.0,
            pool: 5.0,
        }
    }
}

impl TimeoutConfig {
    /// Creates TimeoutConfig from neural_llm config with intelligent fallbacks.
    ///
    /// # Arguments
    ///
    /// * `config` - neural_llm section from config.yaml
    ///
    /// # Examples
    ///
    /// ```
    /// use std::collections::HashMap;
    /// use timeout_config::TimeoutConfig;
    ///
    /// let mut config = HashMap::new();
    /// config.insert("timeout_connect".to_string(), 3.0);
    /// config.insert("timeout_inference".to_string(), 60.0);
    ///
    /// let timeouts = TimeoutConfig::from_config(&config);
    /// assert_eq!(timeouts.connect, 3.0);
    /// assert_eq!(timeouts.read, 60.0);  // timeout_inference → read (legacy compat)
    /// assert_eq!(timeouts.write, 10.0);  // default
    /// ```
    pub fn from_config(config: &HashMap<String, f64>) -> Self {
        let defaults = Self::default();
        
        Self {
            connect: config.get("timeout_connect").copied().unwrap_or(defaults.connect),
            read: config.get("timeout_inference").copied().unwrap_or(defaults.read),  // Legacy compat
            write: config.get("timeout_write").copied().unwrap_or(defaults.write),
            pool: config.get("timeout_pool").copied().unwrap_or(defaults.pool),
        }
    }
    
    /// Converts to kwargs for httpx.Timeout().
    ///
    /// # Returns
    ///
    /// HashMap with the 4 parameters required by httpx.Timeout
    ///
    /// # Examples
    ///
    /// ```
    /// use timeout_config::TimeoutConfig;
    ///
    /// let timeouts = TimeoutConfig::default();
    /// let kwargs = timeouts.to_httpx_timeout();
    ///
    /// assert_eq!(kwargs.get("connect"), Some(&5.0));
    /// assert_eq!(kwargs.get("read"), Some(&30.0));
    /// assert_eq!(kwargs.get("write"), Some(&10.0));
    /// assert_eq!(kwargs.get("pool"), Some(&5.0));
    /// ```
    pub fn to_httpx_timeout(&self) -> HashMap<&'static str, f64> {
        let mut map = HashMap::new();
        map.insert("connect", self.connect);
        map.insert("read", self.read);
        map.insert("write", self.write);
        map.insert("pool", self.pool);
        map
    }
}

impl std::fmt::Display for TimeoutConfig {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "connect={}s, read={}s, write={}s, pool={}s",
            self.connect, self.read, self.write, self.pool
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_default_values() {
        let config = TimeoutConfig::default();
        assert_eq!(config.connect, 5.0);
        assert_eq!(config.read, 30.0);
        assert_eq!(config.write, 10.0);
        assert_eq!(config.pool, 5.0);
    }
    
    #[test]
    fn test_from_config_with_values() {
        let mut config = HashMap::new();
        config.insert("timeout_connect".to_string(), 3.0);
        config.insert("timeout_inference".to_string(), 60.0);
        config.insert("timeout_write".to_string(), 15.0);
        config.insert("timeout_pool".to_string(), 2.0);
        
        let timeouts = TimeoutConfig::from_config(&config);
        assert_eq!(timeouts.connect, 3.0);
        assert_eq!(timeouts.read, 60.0);
        assert_eq!(timeouts.write, 15.0);
        assert_eq!(timeouts.pool, 2.0);
    }
    
    #[test]
    fn test_from_config_partial() {
        let mut config = HashMap::new();
        config.insert("timeout_connect".to_string(), 3.0);
        
        let timeouts = TimeoutConfig::from_config(&config);
        assert_eq!(timeouts.connect, 3.0);
        assert_eq!(timeouts.read, 30.0);  // default
        assert_eq!(timeouts.write, 10.0);  // default
        assert_eq!(timeouts.pool, 5.0);   // default
    }
    
    #[test]
    fn test_from_config_empty() {
        let config = HashMap::new();
        let timeouts = TimeoutConfig::from_config(&config);
        
        // Should use all defaults
        let defaults = TimeoutConfig::default();
        assert_eq!(timeouts, defaults);
    }
    
    #[test]
    fn test_to_httpx_timeout() {
        let config = TimeoutConfig {
            connect: 3.0,
            read: 60.0,
            write: 15.0,
            pool: 2.0,
        };
        
        let kwargs = config.to_httpx_timeout();
        assert_eq!(kwargs.get("connect"), Some(&3.0));
        assert_eq!(kwargs.get("read"), Some(&60.0));
        assert_eq!(kwargs.get("write"), Some(&15.0));
        assert_eq!(kwargs.get("pool"), Some(&2.0));
    }
    
    #[test]
    fn test_display() {
        let config = TimeoutConfig::default();
        let display = format!("{}", config);
        assert_eq!(display, "connect=5s, read=30s, write=10s, pool=5s");
    }
    
    #[test]
    fn test_clone_and_copy() {
        let original = TimeoutConfig::default();
        let cloned = original.clone();
        let copied = original;
        
        assert_eq!(original, cloned);
        assert_eq!(original, copied);
    }
    
    #[test]
    fn test_serialization() {
        let config = TimeoutConfig::default();
        let json = serde_json::to_string(&config).unwrap();
        let deserialized: TimeoutConfig = serde_json::from_str(&json).unwrap();
        
        assert_eq!(config, deserialized);
    }
}
