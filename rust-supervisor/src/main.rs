use anyhow::Result;
use serde::Deserialize;
use signal_hook::consts::signal::*;
use signal_hook_tokio::Signals;
use std::collections::HashMap;
use std::path::PathBuf;
use std::process::Stdio;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::process::{Child, Command};
use tokio::sync::RwLock;
use tokio::time::sleep;
use tokio::io::{AsyncBufReadExt, BufReader};
use tracing::{error, info, warn};
use futures::StreamExt;

// ============================================================================
// Configuration
// ============================================================================

#[derive(Debug, Deserialize, Clone)]
struct Config {
    twitch: TwitchConfig,
}

#[derive(Debug, Deserialize, Clone)]
struct TwitchConfig {
    channels: Vec<String>,
}

#[derive(Debug, Clone)]
struct SupervisorConfig {
    config_path: PathBuf,
    use_db: bool,
    db_path: PathBuf,
    enable_hub: bool,
    hub_socket: PathBuf,
    health_check_interval: Duration,
}

// ============================================================================
// Bot Process
// ============================================================================

struct BotProcess {
    channel: String,
    config_path: PathBuf,
    use_db: bool,
    db_path: PathBuf,
    eventsub_mode: String,
    hub_socket: PathBuf,
    process: Option<Child>,
    start_time: Option<Instant>,
    restart_count: u32,
}

impl BotProcess {
    fn new(
        channel: String,
        config_path: PathBuf,
        use_db: bool,
        db_path: PathBuf,
        eventsub_mode: String,
        hub_socket: PathBuf,
    ) -> Self {
        Self {
            channel,
            config_path,
            use_db,
            db_path,
            eventsub_mode,
            hub_socket,
            process: None,
            start_time: None,
            restart_count: 0,
        }
    }

    async fn start(&mut self) -> Result<bool> {
        if let Some(ref mut child) = self.process {
            if let Ok(None) = child.try_wait() {
                warn!(
                    "⚠️  {}: Process already running (PID {})",
                    self.channel,
                    child.id().unwrap_or(0)
                );
                return Ok(false);
            }
        }

        // Use venv python if available
        let venv_python = PathBuf::from("kissbot-venv/bin/python");
        let python_cmd = if venv_python.exists() {
            venv_python.to_str().unwrap()
        } else {
            "python3"
        };

        let mut cmd = Command::new(python_cmd);
        cmd.arg("main.py")
            .arg("--channel")
            .arg(&self.channel)
            .arg("--config")
            .arg(&self.config_path)
            .arg("--eventsub")
            .arg(&self.eventsub_mode);

        if self.use_db {
            cmd.arg("--use-db").arg("--db").arg(&self.db_path);
        }

        if self.eventsub_mode == "hub" {
            cmd.arg("--hub-socket").arg(&self.hub_socket);
        }

        // Redirect stdout/stderr to null (logs go to files)
        cmd.stdout(Stdio::null()).stderr(Stdio::null());

        match cmd.spawn() {
            Ok(child) => {
                let pid = child.id().unwrap_or(0);
                self.process = Some(child);
                self.start_time = Some(Instant::now());

                let mode_emoji = if self.eventsub_mode == "hub" {
                    "🌐"
                } else {
                    "🔌"
                };

                info!(
                    "✅ {}: Started (PID {}) {} {}",
                    self.channel, pid, mode_emoji, self.eventsub_mode
                );

                Ok(true)
            }
            Err(e) => {
                error!("❌ {}: Failed to start: {}", self.channel, e);
                Ok(false)
            }
        }
    }

    async fn stop(&mut self, timeout_secs: u64) -> Result<bool> {
        if let Some(ref mut child) = self.process {
            if let Ok(Some(_)) = child.try_wait() {
                warn!("⚠️  {}: Process not running", self.channel);
                return Ok(false);
            }

            info!(
                "🛑 {}: Sending SIGTERM (PID {})",
                self.channel,
                child.id().unwrap_or(0)
            );

            // Send SIGTERM
            #[cfg(unix)]
            {
                use nix::sys::signal::{kill, Signal};
                use nix::unistd::Pid;

                if let Some(pid) = child.id() {
                    let _ = kill(Pid::from_raw(pid as i32), Signal::SIGTERM);
                }
            }

            // Wait for graceful shutdown
            tokio::select! {
                _ = child.wait() => {
                    info!("✅ {}: Stopped gracefully", self.channel);
                    Ok(true)
                }
                _ = sleep(Duration::from_secs(timeout_secs)) => {
                    warn!("⚠️  {}: Timeout, sending SIGKILL", self.channel);
                    let _ = child.kill().await;
                    info!("✅ {}: Killed", self.channel);
                    Ok(true)
                }
            }
        } else {
            warn!("⚠️  {}: Process not running", self.channel);
            Ok(false)
        }
    }

    async fn restart(&mut self) -> Result<bool> {
        info!("🔄 {}: Restarting...", self.channel);
        self.stop(10).await?;
        sleep(Duration::from_secs(1)).await;
        let success = self.start().await?;
        if success {
            self.restart_count += 1;
        }
        Ok(success)
    }

    fn is_running(&mut self) -> bool {
        if let Some(ref mut child) = self.process {
            matches!(child.try_wait(), Ok(None))
        } else {
            false
        }
    }

    fn uptime(&self) -> Option<Duration> {
        if let Some(start) = self.start_time {
            if self.process.is_some() {
                return Some(start.elapsed());
            }
        }
        None
    }

    fn pid(&self) -> Option<u32> {
        self.process.as_ref().and_then(|c| c.id())
    }
}

// ============================================================================
// Hub Process
// ============================================================================

struct HubProcess {
    config_path: PathBuf,
    db_path: PathBuf,
    socket_path: PathBuf,
    process: Option<Child>,
    start_time: Option<Instant>,
    restart_count: u32,
}

impl HubProcess {
    fn new(config_path: PathBuf, db_path: PathBuf, socket_path: PathBuf) -> Self {
        Self {
            config_path,
            db_path,
            socket_path,
            process: None,
            start_time: None,
            restart_count: 0,
        }
    }

    async fn start(&mut self) -> Result<bool> {
        if let Some(ref mut child) = self.process {
            if let Ok(None) = child.try_wait() {
                warn!(
                    "⚠️  EventSub Hub: Process already running (PID {})",
                    child.id().unwrap_or(0)
                );
                return Ok(false);
            }
        }

        // Use venv python if available
        let venv_python = PathBuf::from("kissbot-venv/bin/python");
        let python_cmd = if venv_python.exists() {
            venv_python.to_str().unwrap()
        } else {
            "python3"
        };

        // Create logs directory
        tokio::fs::create_dir_all("logs").await?;

        let mut cmd = Command::new(python_cmd);
        cmd.arg("eventsub_hub.py")
            .arg("--config")
            .arg(&self.config_path)
            .arg("--db")
            .arg(&self.db_path)
            .arg("--socket")
            .arg(&self.socket_path)
            .stdout(Stdio::null())
            .stderr(Stdio::null());

        match cmd.spawn() {
            Ok(child) => {
                let pid = child.id().unwrap_or(0);
                self.process = Some(child);
                self.start_time = Some(Instant::now());

                info!("✅ EventSub Hub: Started (PID {})", pid);

                // Wait for socket creation
                sleep(Duration::from_secs(2)).await;

                if !self.socket_path.exists() {
                    warn!(
                        "⚠️  EventSub Hub: Socket not found at {}",
                        self.socket_path.display()
                    );
                }

                Ok(true)
            }
            Err(e) => {
                error!("❌ EventSub Hub: Failed to start: {}", e);
                Ok(false)
            }
        }
    }

    async fn stop(&mut self, timeout_secs: u64) -> Result<bool> {
        if let Some(ref mut child) = self.process {
            if let Ok(Some(_)) = child.try_wait() {
                warn!("⚠️  EventSub Hub: Process not running");
                return Ok(false);
            }

            info!(
                "🛑 EventSub Hub: Sending SIGTERM (PID {})",
                child.id().unwrap_or(0)
            );

            // Send SIGTERM
            #[cfg(unix)]
            {
                use nix::sys::signal::{kill, Signal};
                use nix::unistd::Pid;

                if let Some(pid) = child.id() {
                    let _ = kill(Pid::from_raw(pid as i32), Signal::SIGTERM);
                }
            }

            // Wait for graceful shutdown
            tokio::select! {
                _ = child.wait() => {
                    info!("✅ EventSub Hub: Stopped gracefully");
                    Ok(true)
                }
                _ = sleep(Duration::from_secs(timeout_secs)) => {
                    warn!("⚠️  EventSub Hub: Timeout, sending SIGKILL");
                    let _ = child.kill().await;
                    info!("✅ EventSub Hub: Killed");
                    Ok(true)
                }
            }
        } else {
            warn!("⚠️  EventSub Hub: Process not running");
            Ok(false)
        }
    }

    async fn restart(&mut self) -> Result<bool> {
        info!("🔄 EventSub Hub: Restarting...");
        self.stop(10).await?;
        sleep(Duration::from_secs(2)).await;
        let success = self.start().await?;
        if success {
            self.restart_count += 1;
        }
        Ok(success)
    }

    fn is_running(&mut self) -> bool {
        if let Some(ref mut child) = self.process {
            matches!(child.try_wait(), Ok(None))
        } else {
            false
        }
    }

    fn uptime(&self) -> Option<Duration> {
        if let Some(start) = self.start_time {
            if self.process.is_some() {
                return Some(start.elapsed());
            }
        }
        None
    }

    fn pid(&self) -> Option<u32> {
        self.process.as_ref().and_then(|c| c.id())
    }
}

// ============================================================================
// Supervisor
// ============================================================================

struct Supervisor {
    config: SupervisorConfig,
    bots: Arc<RwLock<HashMap<String, BotProcess>>>,
    hub: Arc<RwLock<Option<HubProcess>>>,
    running: Arc<RwLock<bool>>,
}

impl Supervisor {
    async fn new(config: SupervisorConfig) -> Result<Self> {
        // Load YAML config
        let yaml_content = tokio::fs::read_to_string(&config.config_path).await?;
        let yaml_config: Config = serde_yaml::from_str(&yaml_content)?;

        let mut bots = HashMap::new();
        let eventsub_mode = if config.enable_hub { "hub" } else { "direct" };

        for channel in yaml_config.twitch.channels {
            bots.insert(
                channel.clone(),
                BotProcess::new(
                    channel,
                    config.config_path.clone(),
                    config.use_db,
                    config.db_path.clone(),
                    eventsub_mode.to_string(),
                    config.hub_socket.clone(),
                ),
            );
        }

        let hub = if config.enable_hub {
            Some(HubProcess::new(
                config.config_path.clone(),
                config.db_path.clone(),
                config.hub_socket.clone(),
            ))
        } else {
            None
        };

        let mode = if config.use_db { "DATABASE" } else { "YAML" };
        let hub_mode = if config.enable_hub { "HUB" } else { "DIRECT" };

        info!(
            "📋 Supervisor initialized with {} channels (Token: {}, EventSub: {})",
            bots.len(),
            mode,
            hub_mode
        );

        Ok(Self {
            config,
            bots: Arc::new(RwLock::new(bots)),
            hub: Arc::new(RwLock::new(hub)),
            running: Arc::new(RwLock::new(true)),
        })
    }

    async fn start_all(&self) -> Result<()> {
        info!("🚀 Starting all processes...");

        // Start Hub first if enabled
        {
            let mut hub = self.hub.write().await;
            if let Some(ref mut h) = *hub {
                info!("🌐 Starting EventSub Hub FIRST...");
                h.start().await?;
                info!("⏳ Waiting 3s for Hub to stabilize...");
                sleep(Duration::from_secs(3)).await;
            }
        }

        // Then start bots
        info!("🤖 Starting all bots...");
        {
            let mut bots = self.bots.write().await;
            for (_, bot) in bots.iter_mut() {
                bot.start().await?;
                sleep(Duration::from_millis(500)).await;
            }
        }

        Ok(())
    }

    async fn stop_all(&self) -> Result<()> {
        info!("🛑 Stopping all processes...");

        // Stop bots first
        info!("🤖 Stopping all bots...");
        {
            let mut bots = self.bots.write().await;
            for (_, bot) in bots.iter_mut() {
                bot.stop(10).await?;
            }
        }

        // Then stop Hub
        {
            let mut hub = self.hub.write().await;
            if let Some(ref mut h) = *hub {
                info!("🌐 Stopping EventSub Hub...");
                h.stop(10).await?;
            }
        }

        Ok(())
    }

    async fn print_status(&self) {
        println!("\n{}", "=".repeat(90));
        println!("KissBot Supervisor (Rust) - Status");
        println!("{}", "=".repeat(90));

        // Hub status
        {
            let mut hub = self.hub.write().await;
            if let Some(ref mut h) = *hub {
                let running = if h.is_running() {
                    "🟢 RUNNING"
                } else {
                    "🔴 STOPPED"
                };
                let pid = h.pid().map(|p| format!("PID {}", p)).unwrap_or_else(|| "N/A".to_string());
                let uptime = h.uptime().map(|d| format!("{}s", d.as_secs())).unwrap_or_else(|| "N/A".to_string());

                println!("🌐 EventSub Hub:");
                println!("     Status: {:15} {:12} Uptime: {:8} Restarts: {}", 
                    running, pid, uptime, h.restart_count);
                println!("     Socket: {}", self.config.hub_socket.display());
                println!();
            }
        }

        // Bot statuses
        println!("🤖 Bots:");
        {
            let mut bots = self.bots.write().await;
            for (channel, bot) in bots.iter_mut() {
                let running = if bot.is_running() {
                    "🟢 RUNNING"
                } else {
                    "🔴 STOPPED"
                };
                let pid = bot.pid().map(|p| format!("PID {}", p)).unwrap_or_else(|| "N/A".to_string());
                let uptime = bot.uptime().map(|d| format!("{}s", d.as_secs())).unwrap_or_else(|| "N/A".to_string());

                println!("     {:20} {:15} {:12} Uptime: {:8} Restarts: {}", 
                    channel, running, pid, uptime, bot.restart_count);
            }
        }

        println!("{}\n", "=".repeat(90));
    }

    async fn health_check_loop(&self) -> Result<()> {
        info!(
            "💚 Health check loop started (interval={}s)",
            self.config.health_check_interval.as_secs()
        );

        while *self.running.read().await {
            // Check every 2s
            for _ in 0..(self.config.health_check_interval.as_secs() / 2) {
                if !*self.running.read().await {
                    break;
                }
                sleep(Duration::from_secs(2)).await;
            }

            // Check Hub first (critical!)
            {
                let mut hub = self.hub.write().await;
                if let Some(ref mut h) = *hub {
                    if !h.is_running() {
                        error!("🚨 EventSub Hub CRASHED! Auto-restarting...");
                        h.restart().await?;
                        sleep(Duration::from_secs(3)).await;
                    }
                }
            }

            // Check bots
            {
                let mut bots = self.bots.write().await;
                for (channel, bot) in bots.iter_mut() {
                    if !bot.is_running() {
                        warn!("⚠️  {}: Process crashed! Auto-restarting...", channel);
                        bot.restart().await?;
                    }
                }
            }
        }

        Ok(())
    }

    async fn interactive_cli(&self) -> Result<()> {
        println!();
        println!("{}", "=".repeat(90));
        println!("KissBot Supervisor (Rust) - Interactive CLI");
        println!("{}", "=".repeat(90));
        println!("Commands:");
        println!("  status              - Show status of all processes");
        println!("  start <channel>     - Start a specific bot");
        println!("  stop <channel>      - Stop a specific bot");
        println!("  restart <channel>   - Restart a specific bot");
        println!("  start-all           - Start all processes (Hub + Bots)");
        println!("  stop-all            - Stop all processes");
        println!("  restart-all         - Restart all processes");
        println!("  hub-status          - Show Hub status");
        println!("  hub-restart         - Restart EventSub Hub");
        println!("  quit / exit         - Stop all and exit");
        println!("{}", "=".repeat(90));
        println!();

        let stdin = BufReader::new(tokio::io::stdin());
        let mut lines = stdin.lines();

        while *self.running.read().await {
            // Print prompt
            print!("supervisor> ");
            use std::io::Write;
            std::io::stdout().flush().ok();

            // Read line (blocking until input - CLI waits for user)
            let line = match lines.next_line().await {
                Ok(Some(line)) => line,
                Ok(None) => break, // EOF (Ctrl+D)
                Err(e) => {
                    error!("❌ Input error: {}", e);
                    continue;
                }
            };

            let cmd = line.trim().to_lowercase();
            
            if cmd.is_empty() {
                continue;
            }

            match cmd.as_str() {
                "quit" | "exit" => {
                    println!("👋 Shutting down...");
                    *self.running.write().await = false;
                    break;
                }

                "status" => {
                    self.print_status().await;
                }

                "start-all" => {
                    if let Err(e) = self.start_all().await {
                        println!("❌ Error starting all: {}", e);
                    } else {
                        println!("✅ All processes started");
                    }
                }

                "stop-all" => {
                    if let Err(e) = self.stop_all().await {
                        println!("❌ Error stopping all: {}", e);
                    } else {
                        println!("✅ All processes stopped");
                    }
                }

                "restart-all" => {
                    println!("🔄 Restarting all...");
                    if let Err(e) = self.stop_all().await {
                        println!("❌ Error stopping: {}", e);
                    }
                    sleep(Duration::from_secs(2)).await;
                    if let Err(e) = self.start_all().await {
                        println!("❌ Error starting: {}", e);
                    } else {
                        println!("✅ All processes restarted");
                    }
                }

                "hub-status" => {
                    let mut hub = self.hub.write().await;
                    if let Some(ref mut h) = *hub {
                        let status = if h.is_running() { "🟢 RUNNING" } else { "🔴 STOPPED" };
                        let pid = h.pid().map(|p| p.to_string()).unwrap_or_else(|| "N/A".to_string());
                        let uptime = h.uptime().map(|d| format!("{}s", d.as_secs())).unwrap_or_else(|| "N/A".to_string());
                        
                        println!();
                        println!("🌐 EventSub Hub Status:");
                        println!("  Status: {}", status);
                        println!("  PID: {}", pid);
                        println!("  Uptime: {}", uptime);
                        println!("  Restarts: {}", h.restart_count);
                        println!("  Socket: {}", self.config.hub_socket.display());
                        println!();
                    } else {
                        println!("❌ EventSub Hub not enabled");
                    }
                }

                "hub-restart" => {
                    let mut hub = self.hub.write().await;
                    if let Some(ref mut h) = *hub {
                        println!("🔄 Restarting EventSub Hub...");
                        if let Err(e) = h.restart().await {
                            println!("❌ Error: {}", e);
                        } else {
                            println!("✅ Hub restarted");
                        }
                    } else {
                        println!("❌ EventSub Hub not enabled");
                    }
                }

                _ if cmd.starts_with("start ") => {
                    let channel = cmd.strip_prefix("start ").unwrap().trim();
                    let mut bots = self.bots.write().await;
                    
                    if let Some(bot) = bots.get_mut(channel) {
                        if bot.is_running() {
                            println!("⚠️  {} already running (PID {})", channel, bot.pid().unwrap_or(0));
                        } else {
                            match bot.start().await {
                                Ok(true) => println!("✅ {} started (PID {})", channel, bot.pid().unwrap_or(0)),
                                _ => println!("❌ {} failed to start", channel),
                            }
                        }
                    } else {
                        println!("❌ Channel '{}' not found", channel);
                    }
                }

                _ if cmd.starts_with("stop ") => {
                    let channel = cmd.strip_prefix("stop ").unwrap().trim();
                    let mut bots = self.bots.write().await;
                    
                    if let Some(bot) = bots.get_mut(channel) {
                        if !bot.is_running() {
                            println!("⚠️  {} not running", channel);
                        } else {
                            let pid = bot.pid().unwrap_or(0);
                            let _ = bot.stop(10).await;
                            println!("✅ {} stopped (was PID {})", channel, pid);
                        }
                    } else {
                        println!("❌ Channel '{}' not found", channel);
                    }
                }

                _ if cmd.starts_with("restart ") => {
                    let channel = cmd.strip_prefix("restart ").unwrap().trim();
                    let mut bots = self.bots.write().await;
                    
                    if let Some(bot) = bots.get_mut(channel) {
                        println!("🔄 Restarting {}...", channel);
                        if let Err(e) = bot.restart().await {
                            println!("❌ Error: {}", e);
                        } else {
                            println!("✅ {} restarted (PID {})", channel, bot.pid().unwrap_or(0));
                        }
                    } else {
                        println!("❌ Channel '{}' not found", channel);
                    }
                }

                _ => {
                    println!("❓ Unknown command: '{}'. Type 'status' for help.", cmd);
                }
            }
        }

        Ok(())
    }

    async fn run(&self, interactive: bool) -> Result<()> {
        // Start all processes
        self.start_all().await?;

        // Print initial status
        self.print_status().await;

        // Setup signal handling
        let mut signals = Signals::new(&[SIGTERM, SIGINT])?;
        let running = Arc::clone(&self.running);

        tokio::spawn(async move {
            while let Some(signal) = signals.next().await {
                info!("🛑 Received signal {:?}, shutting down...", signal);
                *running.write().await = false;
            }
        });

        // Spawn command listener in background (for kissbot.sh compatibility)
        let bots = Arc::clone(&self.bots);
        let running = Arc::clone(&self.running);
        tokio::spawn(async move {
            let cmd_file = PathBuf::from("pids/supervisor.cmd");
            let result_file = PathBuf::from("pids/supervisor.result");
            
            info!("📡 Command listener started");
            
            while *running.read().await {
                if cmd_file.exists() {
                    match tokio::fs::read_to_string(&cmd_file).await {
                        Ok(cmd) => {
                            let cmd = cmd.trim();
                            info!("📨 Received command: {}", cmd);
                            
                            let _ = tokio::fs::remove_file(&cmd_file).await;
                            
                            let result = execute_cmd(&cmd, &bots).await;
                            
                            if let Err(e) = tokio::fs::write(&result_file, &result).await {
                                error!("❌ Failed to write result file: {}", e);
                            } else {
                                info!("📤 Command result: {}", result);
                            }
                        }
                        Err(e) => {
                            error!("❌ Failed to read command file: {}", e);
                            let _ = tokio::fs::remove_file(&cmd_file).await;
                        }
                    }
                }
                
                sleep(Duration::from_millis(100)).await;
            }
        });

        // Run interactive CLI or health check loop
        if interactive {
            // Interactive mode: CLI takes over
            self.interactive_cli().await?;
        } else {
            // Daemon mode: just health checks
            self.health_check_loop().await?;
        }

        // Cleanup
        info!("🧹 Cleaning up...");
        self.stop_all().await?;
        info!("✅ Supervisor stopped");

        Ok(())
    }
}

// ============================================================================
// Command Execution Helper
// ============================================================================

async fn execute_cmd(cmd: &str, bots: &Arc<RwLock<HashMap<String, BotProcess>>>) -> String {
    let parts: Vec<&str> = cmd.split_whitespace().collect();
    
    if parts.is_empty() {
        return "ERROR: Empty command".to_string();
    }
    
    match parts[0] {
        "start" => {
            if parts.len() < 2 {
                return "ERROR: Usage: start <channel>".to_string();
            }
            
            let channel = parts[1];
            let mut bots = bots.write().await;
            
            if let Some(bot) = bots.get_mut(channel) {
                if bot.is_running() {
                    let pid = bot.pid().unwrap_or(0);
                    format!("ERROR: {} already running (PID {})", channel, pid)
                } else {
                    match bot.start().await {
                        Ok(true) => {
                            sleep(Duration::from_secs(1)).await;
                            if bot.is_running() {
                                let pid = bot.pid().unwrap_or(0);
                                format!("SUCCESS: {} started (PID {})", channel, pid)
                            } else {
                                format!("ERROR: {} failed to start", channel)
                            }
                        }
                        _ => format!("ERROR: {} failed to start", channel),
                    }
                }
            } else {
                format!("ERROR: Channel '{}' not found", channel)
            }
        }
        
        "stop" => {
            if parts.len() < 2 {
                return "ERROR: Usage: stop <channel>".to_string();
            }
            
            let channel = parts[1];
            let mut bots = bots.write().await;
            
            if let Some(bot) = bots.get_mut(channel) {
                if !bot.is_running() {
                    format!("ERROR: {} not running", channel)
                } else {
                    let old_pid = bot.pid().unwrap_or(0);
                    let _ = bot.stop(10).await;
                    sleep(Duration::from_millis(500)).await;
                    
                    if !bot.is_running() {
                        format!("SUCCESS: {} stopped (was PID {})", channel, old_pid)
                    } else {
                        format!("ERROR: {} failed to stop", channel)
                    }
                }
            } else {
                format!("ERROR: Channel '{}' not found", channel)
            }
        }
        
        "restart" => {
            if parts.len() < 2 {
                return "ERROR: Usage: restart <channel>".to_string();
            }
            
            let channel = parts[1];
            let mut bots = bots.write().await;
            
            if let Some(bot) = bots.get_mut(channel) {
                match bot.restart().await {
                    Ok(_) => {
                        sleep(Duration::from_secs(1)).await;
                        if bot.is_running() {
                            let pid = bot.pid().unwrap_or(0);
                            format!("SUCCESS: {} restarted (PID {})", channel, pid)
                        } else {
                            format!("ERROR: {} failed to restart", channel)
                        }
                    }
                    Err(e) => format!("ERROR: {} failed to restart: {}", channel, e),
                }
            } else {
                format!("ERROR: Channel '{}' not found", channel)
            }
        }
        
        "status" => {
            let mut bots = bots.write().await;
            let mut statuses = Vec::new();
            
            for (channel, bot) in bots.iter_mut() {
                let status = if bot.is_running() { "RUNNING" } else { "STOPPED" };
                let pid = bot.pid().map(|p| p.to_string()).unwrap_or_else(|| "N/A".to_string());
                statuses.push(format!("{}:{}:{}", channel, status, pid));
            }
            
            format!("SUCCESS: {}", statuses.join(" | "))
        }
        
        _ => format!("ERROR: Unknown command '{}'", parts[0]),
    }
}

// ============================================================================
// Main
// ============================================================================

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize tracing
    tracing_subscriber::fmt()
        .with_target(false)
        .with_thread_ids(false)
        .with_file(false)
        .with_line_number(false)
        .init();

    // Parse arguments (simple version - could use clap)
    let args: Vec<String> = std::env::args().collect();

    let mut config_path = PathBuf::from("config/config.yaml");
    let mut use_db = false;
    let mut db_path = PathBuf::from("kissbot.db");
    let mut enable_hub = false;
    let mut hub_socket = PathBuf::from("/tmp/kissbot_hub.sock");
    let mut interactive = false;

    // Simple arg parsing
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--config" => {
                config_path = PathBuf::from(&args[i + 1]);
                i += 2;
            }
            "--use-db" => {
                use_db = true;
                i += 1;
            }
            "--db" => {
                db_path = PathBuf::from(&args[i + 1]);
                i += 2;
            }
            "--enable-hub" => {
                enable_hub = true;
                i += 1;
            }
            "--hub-socket" => {
                hub_socket = PathBuf::from(&args[i + 1]);
                i += 2;
            }
            "-i" | "--interactive" => {
                interactive = true;
                i += 1;
            }
            _ => i += 1,
        }
    }

    println!("{}", "=".repeat(90));
    println!("KissBot Supervisor (Rust)");
    println!("Config: {}", config_path.display());
    println!("Token Source: {}", if use_db { "DATABASE" } else { "YAML" });
    if use_db {
        println!("Database: {}", db_path.display());
    }
    println!(
        "EventSub Hub: {}",
        if enable_hub {
            "ENABLED"
        } else {
            "DISABLED (bots use direct mode)"
        }
    );
    if enable_hub {
        println!("Hub Socket: {}", hub_socket.display());
    }
    println!("Interactive: {}", if interactive { "YES" } else { "NO (daemon mode)" });
    println!("{}", "=".repeat(90));

    let config = SupervisorConfig {
        config_path,
        use_db,
        db_path,
        enable_hub,
        hub_socket,
        health_check_interval: Duration::from_secs(30),
    };

    let supervisor = Supervisor::new(config).await?;
    supervisor.run(interactive).await?;

    Ok(())
}