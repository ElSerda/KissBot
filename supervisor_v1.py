#!/usr/bin/env python3
"""
KissBot Supervisor V1 (YAML-based)
Multi-process bot manager - reads channels from config.yaml

Each channel runs in an isolated process with its own:
- Log file: logs/{channel}.log
- PID file: pids/{channel}.pid
- Independent crash/restart behavior
"""

import argparse
import asyncio
import logging
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Optional

import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    handlers=[
        logging.FileHandler("supervisor.log"),
        logging.StreamHandler()
    ]
)

LOGGER = logging.getLogger(__name__)


class BotProcess:
    """Represents a single bot process for a channel"""
    
    def __init__(self, channel: str, config_path: str = "config/config.yaml", 
                 use_db: bool = False, db_path: str = "kissbot.db",
                 eventsub_mode: str = "direct", hub_socket: str = "/tmp/kissbot_hub.sock"):
        self.channel = channel
        self.config_path = config_path
        self.use_db = use_db
        self.db_path = db_path
        self.eventsub_mode = eventsub_mode  # direct, hub, or disabled
        self.hub_socket = hub_socket
        self.process: Optional[subprocess.Popen] = None
        self.start_time: Optional[float] = None
        self.restart_count = 0
    
    def start(self) -> bool:
        """Start the bot process"""
        if self.process and self.process.poll() is None:
            LOGGER.warning(f"⚠️ {self.channel}: Process already running (PID {self.process.pid})")
            return False
        
        try:
            # Use venv python if available
            venv_python = Path("kissbot-venv/bin/python")
            python_cmd = str(venv_python) if venv_python.exists() else "python3"
            
            cmd = [
                python_cmd,
                "main.py",
                "--channel", self.channel,
                "--config", self.config_path,
                "--eventsub", self.eventsub_mode,  # Add EventSub mode
                "--chat-transport", "eventsub"  # Use EventSub Chat (Twitch-recommended)
            ]
            
            # Add --use-db if enabled
            if self.use_db:
                cmd.extend(["--use-db", "--db", self.db_path])
            
            # Add --hub-socket if in hub mode
            if self.eventsub_mode == "hub":
                cmd.extend(["--hub-socket", self.hub_socket])
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=Path.cwd()
            )
            
            self.start_time = time.time()
            mode_emoji = "🌐" if self.eventsub_mode == "hub" else "🔌"
            LOGGER.info(f"✅ {self.channel}: Started (PID {self.process.pid}) {mode_emoji} {self.eventsub_mode}")
            return True
            
        except Exception as e:
            LOGGER.error(f"❌ {self.channel}: Failed to start: {e}")
            return False
    
    def stop(self, timeout: int = 10) -> bool:
        """Stop the bot process gracefully"""
        if not self.process or self.process.poll() is not None:
            LOGGER.warning(f"⚠️ {self.channel}: Process not running")
            return False
        
        try:
            LOGGER.info(f"🛑 {self.channel}: Sending SIGTERM (PID {self.process.pid})")
            self.process.terminate()
            
            # Wait for graceful shutdown
            try:
                self.process.wait(timeout=timeout)
                LOGGER.info(f"✅ {self.channel}: Stopped gracefully")
                return True
            except subprocess.TimeoutExpired:
                LOGGER.warning(f"⚠️ {self.channel}: Timeout, sending SIGKILL")
                self.process.kill()
                self.process.wait()
                LOGGER.info(f"✅ {self.channel}: Killed")
                return True
                
        except Exception as e:
            LOGGER.error(f"❌ {self.channel}: Error stopping: {e}")
            return False
    
    def restart(self) -> bool:
        """Restart the bot process"""
        LOGGER.info(f"🔄 {self.channel}: Restarting...")
        self.stop()
        time.sleep(1)  # Small delay between stop and start
        success = self.start()
        if success:
            self.restart_count += 1
        return success
    
    def is_running(self) -> bool:
        """Check if process is still running"""
        if not self.process:
            return False
        return self.process.poll() is None
    
    def uptime(self) -> Optional[float]:
        """Get uptime in seconds"""
        if not self.start_time or not self.is_running():
            return None
        return time.time() - self.start_time
    
    def status(self) -> dict:
        """Get process status info"""
        return {
            "channel": self.channel,
            "running": self.is_running(),
            "pid": self.process.pid if self.process else None,
            "uptime": self.uptime(),
            "restart_count": self.restart_count,
            "start_time": self.start_time
        }


class HubProcess:
    """Represents the EventSub Hub process"""
    
    def __init__(self, config_path: str, db_path: str, socket_path: str = "/tmp/kissbot_hub.sock"):
        self.config_path = config_path
        self.db_path = db_path
        self.socket_path = socket_path
        self.process: Optional[subprocess.Popen] = None
        self.start_time: Optional[float] = None
        self.restart_count = 0
    
    def start(self) -> bool:
        """Start the EventSub Hub process"""
        if self.process and self.process.poll() is None:
            LOGGER.warning(f"⚠️ EventSub Hub: Process already running (PID {self.process.pid})")
            return False
        
        try:
            # Use venv python if available
            venv_python = Path("kissbot-venv/bin/python")
            python_cmd = str(venv_python) if venv_python.exists() else "python3"
            
            cmd = [
                python_cmd,
                "eventsub_hub.py",
                "--config", self.config_path,
                "--db", self.db_path,
                "--socket", self.socket_path
            ]
            
            # Create logs directory if needed
            Path("logs").mkdir(exist_ok=True)
            
            # Start Hub with output redirected to log file
            log_file = Path("logs/hub.out")
            self.process = subprocess.Popen(
                cmd,
                stdout=open(log_file, 'a'),
                stderr=subprocess.STDOUT,
                cwd=Path.cwd()
            )
            
            self.start_time = time.time()
            LOGGER.info(f"✅ EventSub Hub: Started (PID {self.process.pid})")
            
            # Wait a bit for socket to be created
            time.sleep(2)
            
            # Verify socket exists
            if not Path(self.socket_path).exists():
                LOGGER.warning(f"⚠️ EventSub Hub: Socket not found at {self.socket_path}")
            
            return True
            
        except Exception as e:
            LOGGER.error(f"❌ EventSub Hub: Failed to start: {e}")
            return False
    
    def stop(self, timeout: int = 10) -> bool:
        """Stop the Hub process gracefully"""
        if not self.process or self.process.poll() is not None:
            LOGGER.warning(f"⚠️ EventSub Hub: Process not running")
            return False
        
        try:
            LOGGER.info(f"🛑 EventSub Hub: Sending SIGTERM (PID {self.process.pid})")
            self.process.terminate()
            
            # Wait for graceful shutdown
            try:
                self.process.wait(timeout=timeout)
                LOGGER.info(f"✅ EventSub Hub: Stopped gracefully")
                return True
            except subprocess.TimeoutExpired:
                LOGGER.warning(f"⚠️ EventSub Hub: Timeout, sending SIGKILL")
                self.process.kill()
                self.process.wait()
                LOGGER.info(f"✅ EventSub Hub: Killed")
                return True
                
        except Exception as e:
            LOGGER.error(f"❌ EventSub Hub: Error stopping: {e}")
            return False
    
    def restart(self) -> bool:
        """Restart the Hub process"""
        LOGGER.info(f"🔄 EventSub Hub: Restarting...")
        self.stop()
        time.sleep(2)  # Wait for socket cleanup
        success = self.start()
        if success:
            self.restart_count += 1
        return success
    
    def is_running(self) -> bool:
        """Check if process is still running"""
        if not self.process:
            return False
        return self.process.poll() is None
    
    def uptime(self) -> Optional[float]:
        """Get uptime in seconds"""
        if not self.start_time or not self.is_running():
            return None
        return time.time() - self.start_time
    
    def status(self) -> dict:
        """Get process status info"""
        return {
            "name": "EventSub Hub",
            "running": self.is_running(),
            "pid": self.process.pid if self.process else None,
            "uptime": self.uptime(),
            "restart_count": self.restart_count,
            "start_time": self.start_time,
            "socket": self.socket_path
        }


class SimpleSupervisor:
    """Simple supervisor for managing multiple bot processes + EventSub Hub"""
    
    def __init__(self, config_path: str = "config/config.yaml", interactive: bool = True,
                 use_db: bool = False, db_path: str = "kissbot.db", 
                 enable_hub: bool = False, hub_socket: str = "/tmp/kissbot_hub.sock"):
        self.config_path = config_path
        self.interactive = interactive
        self.use_db = use_db
        self.db_path = db_path
        self.enable_hub = enable_hub
        self.hub_socket = hub_socket
        self.bots: Dict[str, BotProcess] = {}
        self.hub: Optional[HubProcess] = None
        self.running = False
        self.health_check_interval = 30  # Check every 30 seconds
        
        # Load config
        self.config = self._load_config()
        
        # Initialize EventSub Hub if enabled AND not already running
        if self.enable_hub:
            # Check if hub socket already exists (external hub running)
            if Path(hub_socket).exists():
                LOGGER.info("🌐 EventSub Hub: EXTERNAL (socket already exists, not starting internal hub)")
                self.hub = None  # Don't manage hub, use external one
            else:
                LOGGER.info("🌐 EventSub Hub: ENABLED (starting internal hub)")
                self.hub = HubProcess(config_path, db_path, hub_socket)
        else:
            LOGGER.info("🌐 EventSub Hub: DISABLED (bots use direct mode)")
        
        # Initialize bot processes
        channels = self.config.get("twitch", {}).get("channels", [])
        eventsub_mode = "hub" if enable_hub else "direct"
        
        for channel in channels:
            self.bots[channel] = BotProcess(
                channel, 
                config_path, 
                use_db=use_db, 
                db_path=db_path,
                eventsub_mode=eventsub_mode,
                hub_socket=hub_socket
            )
        
        mode = "DATABASE" if use_db else "YAML"
        hub_mode = "HUB" if enable_hub else "DIRECT"
        LOGGER.info(f"📋 Supervisor initialized with {len(self.bots)} channels (Token: {mode}, EventSub: {hub_mode})")
    
    def _load_config(self) -> dict:
        """Load config.yaml"""
        config_file = Path(self.config_path)
        if not config_file.exists():
            LOGGER.error(f"❌ Config file not found: {self.config_path}")
            sys.exit(1)
        
        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def start_all(self):
        """Start all processes (Hub first if enabled, then bots)"""
        LOGGER.info("🚀 Starting all processes...")
        
        # START HUB FIRST (critical!)
        if self.hub:
            LOGGER.info("🌐 Starting EventSub Hub FIRST...")
            self.hub.start()
            LOGGER.info("⏳ Waiting 3s for Hub to stabilize...")
            time.sleep(3)  # Give Hub time to connect to Twitch + create socket
        
        # Then start bots
        LOGGER.info("🤖 Starting all bots...")
        for channel, bot in self.bots.items():
            bot.start()
            time.sleep(0.5)  # Small delay between starts
    
    def stop_all(self):
        """Stop all processes (bots first, then Hub)"""
        LOGGER.info("🛑 Stopping all processes...")
        
        # Stop bots first
        LOGGER.info("🤖 Stopping all bots...")
        for channel, bot in self.bots.items():
            bot.stop()
        
        # Then stop Hub (after bots disconnected)
        if self.hub:
            LOGGER.info("🌐 Stopping EventSub Hub...")
            self.hub.stop()
    
    def restart_all(self):
        """Restart all processes (stops all, then starts all)"""
        LOGGER.info("🔄 Restarting all processes...")
        self.stop_all()
        time.sleep(2)  # Wait for cleanup
        self.start_all()
    
    def start_bot(self, channel: str) -> bool:
        """Start a specific bot"""
        if channel not in self.bots:
            LOGGER.error(f"❌ Unknown channel: {channel}")
            return False
        return self.bots[channel].start()
    
    def stop_bot(self, channel: str) -> bool:
        """Stop a specific bot"""
        if channel not in self.bots:
            LOGGER.error(f"❌ Unknown channel: {channel}")
            return False
        return self.bots[channel].stop()
    
    def restart_bot(self, channel: str) -> bool:
        """Restart a specific bot"""
        if channel not in self.bots:
            LOGGER.error(f"❌ Unknown channel: {channel}")
            return False
        return self.bots[channel].restart()
    
    def status(self) -> dict:
        """Get status of all processes (Hub + bots)"""
        result = {}
        
        # Hub status first
        if self.hub:
            result["__hub__"] = self.hub.status()
        
        # Bot statuses
        for channel, bot in self.bots.items():
            result[channel] = bot.status()
        
        return result
    
    def print_status(self):
        """Print formatted status"""
        print("\n" + "=" * 90)
        print("KissBot Supervisor - Status")
        print("=" * 90)
        
        status = self.status()
        
        # Print Hub status first
        if "__hub__" in status:
            hub_info = status["__hub__"]
            running = "🟢 RUNNING" if hub_info["running"] else "🔴 STOPPED"
            pid = f"PID {hub_info['pid']}" if hub_info['pid'] else "N/A"
            uptime = f"{hub_info['uptime']:.0f}s" if hub_info['uptime'] else "N/A"
            restarts = hub_info['restart_count']
            
            print(f"🌐 EventSub Hub:")
            print(f"     Status: {running:15s} {pid:12s} Uptime: {uptime:8s} Restarts: {restarts}")
            print(f"     Socket: {hub_info['socket']}")
            print()
        
        # Print bot statuses
        print("🤖 Bots:")
        for channel, info in status.items():
            if channel == "__hub__":
                continue
            
            running = "🟢 RUNNING" if info["running"] else "🔴 STOPPED"
            pid = f"PID {info['pid']}" if info['pid'] else "N/A"
            uptime = f"{info['uptime']:.0f}s" if info['uptime'] else "N/A"
            restarts = info['restart_count']
            
            print(f"     {channel:20s} {running:15s} {pid:12s} Uptime: {uptime:8s} Restarts: {restarts}")
        
        print("=" * 90 + "\n")
    
    async def health_check_loop(self):
        """Monitor processes and auto-restart if crashed (with backoff on repeated failures)"""
        LOGGER.info(f"💚 Health check loop started (interval={self.health_check_interval}s)")
        
        # Backoff settings to prevent restart loops
        MAX_RESTARTS_BEFORE_BACKOFF = 5
        BACKOFF_DELAY = 60  # seconds
        
        while self.running:
            # Sleep in small chunks to be more responsive to crashes
            for _ in range(int(self.health_check_interval / 2)):  # Check every 2s
                if not self.running:
                    break
                await asyncio.sleep(2)
            
            # Check Hub first (critical!)
            if self.hub and not self.hub.is_running():
                if self.hub.restart_count >= MAX_RESTARTS_BEFORE_BACKOFF:
                    LOGGER.error(f"🚨 EventSub Hub crashed {self.hub.restart_count}x! Waiting {BACKOFF_DELAY}s before retry...")
                    await asyncio.sleep(BACKOFF_DELAY)
                
                LOGGER.error(f"🚨 EventSub Hub CRASHED! Auto-restarting... (restart #{self.hub.restart_count + 1})")
                self.hub.restart()
                
                # Wait for Hub to stabilize before checking bots
                await asyncio.sleep(3)
            
            # Check bots (with backoff on repeated failures)
            for channel, bot in self.bots.items():
                if not bot.is_running():
                    if bot.restart_count >= MAX_RESTARTS_BEFORE_BACKOFF:
                        LOGGER.error(f"🚨 {channel}: Crashed {bot.restart_count}x! Waiting {BACKOFF_DELAY}s before retry...")
                        await asyncio.sleep(BACKOFF_DELAY)
                    
                    LOGGER.warning(f"⚠️ {channel}: Process crashed! Auto-restarting... (restart #{bot.restart_count + 1})")
                    bot.restart()
    
    async def broadcast_listener_loop(self):
        """Listen for broadcast requests via file"""
        from pathlib import Path
        
        LOGGER.info("📡 Broadcast listener started")
        broadcast_file = Path("pids/supervisor.broadcast")
        
        while self.running:
            try:
                if broadcast_file.exists():
                    # Read broadcast request
                    broadcast_data = broadcast_file.read_text().strip()
                    
                    # Delete file immediately
                    broadcast_file.unlink()
                    
                    # Parse: timestamp|source_channel|message
                    parts = broadcast_data.split("|", 2)
                    if len(parts) != 3:
                        LOGGER.error(f"❌ Invalid broadcast format: {broadcast_data}")
                        await asyncio.sleep(0.1)
                        continue
                    
                    timestamp, source_channel, message = parts
                    
                    LOGGER.info(
                        f"📢 BROADCAST REQUEST | source={source_channel} | "
                        f"message={message[:50]}... | dispatching to {len(self.bots)} bots"
                    )
                    
                    # Dispatch to all running bots EXCEPT source
                    success_count = 0
                    failed_channels = []
                    
                    for channel, bot in self.bots.items():
                        # Skip source channel (no self-broadcast)
                        if channel == source_channel:
                            LOGGER.debug(f"⏭️ Skip {channel} (source channel)")
                            continue
                        
                        if not bot.is_running():
                            LOGGER.debug(f"⏭️ Skip {channel} (not running)")
                            failed_channels.append(channel)
                            continue
                        
                        try:
                            # Write broadcast message to bot's special file
                            # Format: source_channel|message
                            bot_broadcast_file = Path(f"pids/{channel}.broadcast_in")
                            bot_broadcast_file.write_text(f"{source_channel}|{message}\n")
                            
                            success_count += 1
                            LOGGER.debug(f"✅ Broadcast dispatched to {channel}")
                            
                        except Exception as e:
                            LOGGER.error(f"❌ Failed to dispatch to {channel}: {e}")
                            failed_channels.append(channel)
                    
                    # Log results
                    total_targets = len(self.bots) - 1  # Exclude source
                    success_rate = (success_count / total_targets * 100) if total_targets > 0 else 0
                    
                    LOGGER.info(
                        f"📊 BROADCAST DISPATCHED | "
                        f"success={success_count}/{total_targets} ({success_rate:.1f}%) | "
                        f"failed={failed_channels if failed_channels else 'none'}"
                    )
            
            except Exception as e:
                LOGGER.error(f"❌ Broadcast listener error: {e}")
            
            await asyncio.sleep(0.1)  # Check every 100ms
    
    async def command_listener_loop(self):
        """Listen for external commands from kissbot.sh"""
        from pathlib import Path
        
        LOGGER.info("📡 Command listener started")
        cmd_file = Path("pids/supervisor.cmd")
        result_file = Path("pids/supervisor.result")
        
        while self.running:
            try:
                if cmd_file.exists():
                    # Read command
                    cmd = cmd_file.read_text().strip()
                    LOGGER.info(f"📨 Received command: {cmd}")
                    
                    # Delete command file immediately
                    cmd_file.unlink()
                    
                    # Execute command
                    result = "ERROR: Unknown command"
                    
                    if cmd.startswith("start "):
                        channel = cmd.split(maxsplit=1)[1]
                        if channel in self.bots:
                            bot = self.bots[channel]
                            if bot.is_running():
                                result = f"ERROR: {channel} already running (PID {bot.process.pid})"
                            else:
                                bot.start()
                                await asyncio.sleep(1)
                                if bot.is_running():
                                    result = f"SUCCESS: {channel} started (PID {bot.process.pid})"
                                else:
                                    result = f"ERROR: {channel} failed to start"
                        else:
                            result = f"ERROR: Channel '{channel}' not found"
                    
                    elif cmd.startswith("stop "):
                        channel = cmd.split(maxsplit=1)[1]
                        if channel in self.bots:
                            bot = self.bots[channel]
                            if not bot.is_running():
                                result = f"ERROR: {channel} not running"
                            else:
                                old_pid = bot.process.pid if bot.process else "unknown"
                                bot.stop()
                                await asyncio.sleep(0.5)
                                if not bot.is_running():
                                    result = f"SUCCESS: {channel} stopped (was PID {old_pid})"
                                else:
                                    result = f"ERROR: {channel} failed to stop"
                        else:
                            result = f"ERROR: Channel '{channel}' not found"
                    
                    elif cmd.startswith("restart "):
                        channel = cmd.split(maxsplit=1)[1]
                        if channel in self.bots:
                            bot = self.bots[channel]
                            bot.restart()
                            # Wait a bit for the bot to start
                            await asyncio.sleep(1)
                            if bot.is_running():
                                result = f"SUCCESS: {channel} restarted (PID {bot.process.pid})"
                            else:
                                result = f"ERROR: {channel} failed to restart"
                        else:
                            result = f"ERROR: Channel '{channel}' not found"
                    
                    elif cmd == "status":
                        # Return status of all bots
                        statuses = []
                        for ch, bot in self.bots.items():
                            status = "RUNNING" if bot.is_running() else "STOPPED"
                            pid = bot.process.pid if bot.is_running() else "N/A"
                            statuses.append(f"{ch}:{status}:{pid}")
                        result = "SUCCESS: " + " | ".join(statuses)
                    
                    # Write result
                    result_file.write_text(result)
                    LOGGER.info(f"📤 Command result: {result}")
            
            except Exception as e:
                LOGGER.error(f"❌ Command listener error: {e}")
                if cmd_file.exists():
                    cmd_file.unlink()
                result_file.write_text(f"ERROR: {e}")
            
            await asyncio.sleep(0.1)  # Check every 100ms
    
    async def interactive_cli(self):
        """Interactive CLI for managing processes"""
        print("\n" + "=" * 90)
        print("KissBot Supervisor - Interactive CLI")
        print("=" * 90)
        print("Commands:")
        print("  status              - Show status of all processes")
        print("  start <channel>     - Start a specific bot")
        print("  stop <channel>      - Stop a specific bot")
        print("  restart <channel>   - Restart a specific bot")
        print("  start-all           - Start all processes (Hub + Bots)")
        print("  stop-all            - Stop all processes")
        print("  restart-all         - Restart all processes")
        print("  hub-status          - Show Hub status + stats")
        print("  hub-restart         - Restart EventSub Hub")
        print("  hub-resync          - Force immediate Hub reconciliation")
        print("  quit / exit         - Stop all and exit")
        print("=" * 90 + "\n")
        
        while self.running:
            try:
                # Use asyncio-friendly input
                await asyncio.sleep(0.1)
                
                # Non-blocking input check (basic version)
                # For production, use aioconsole for proper async input
                cmd = input("supervisor> ").strip().lower()
                
                if cmd in ["quit", "exit"]:
                    print("👋 Shutting down...")
                    self.running = False
                    break
                
                elif cmd == "status":
                    self.print_status()
                
                elif cmd == "start-all":
                    self.start_all()
                    print("✅ All processes started")
                
                elif cmd == "stop-all":
                    self.stop_all()
                    print("✅ All processes stopped")
                
                elif cmd == "restart-all":
                    self.restart_all()
                    print("✅ All processes restarted")
                
                elif cmd == "hub-status":
                    if self.hub:
                        info = self.hub.status()
                        print("\n🌐 EventSub Hub Status:")
                        print(f"  Running: {'✅ YES' if info['running'] else '❌ NO'}")
                        print(f"  PID: {info['pid'] if info['pid'] else 'N/A'}")
                        print(f"  Uptime: {info['uptime']:.0f}s" if info['uptime'] else "  Uptime: N/A")
                        print(f"  Restarts: {info['restart_count']}")
                        print(f"  Socket: {info['socket']}")
                        print()
                    else:
                        print("❌ EventSub Hub not enabled")
                
                elif cmd == "hub-restart":
                    if self.hub:
                        print("🔄 Restarting EventSub Hub...")
                        self.hub.restart()
                        print("✅ Hub restarted")
                    else:
                        print("❌ EventSub Hub not enabled")
                
                elif cmd == "hub-resync":
                    if self.hub:
                        print("🔄 Forcing immediate Hub reconciliation...")
                        await self.hub._reconcile()
                        print("✅ Hub reconciliation complete")
                    else:
                        print("❌ EventSub Hub not enabled")
                
                elif cmd.startswith("start "):
                    channel = cmd.split(" ", 1)[1]
                    if self.start_bot(channel):
                        print(f"✅ Bot {channel} started")
                    else:
                        print(f"❌ Failed to start {channel}")
                
                elif cmd.startswith("stop "):
                    channel = cmd.split(" ", 1)[1]
                    if self.stop_bot(channel):
                        print(f"✅ Bot {channel} stopped")
                    else:
                        print(f"❌ Failed to stop {channel}")
                
                elif cmd.startswith("restart "):
                    channel = cmd.split(" ", 1)[1]
                    if self.restart_bot(channel):
                        print(f"✅ Bot {channel} restarted")
                    else:
                        print(f"❌ Failed to restart {channel}")
                
                elif cmd:
                    print(f"❌ Unknown command: {cmd}")
                
            except EOFError:
                # Handle Ctrl+D
                print("\n👋 Shutting down...")
                self.running = False
                break
            except KeyboardInterrupt:
                # Handle Ctrl+C
                print("\n👋 Shutting down...")
                self.running = False
                break
            except Exception as e:
                LOGGER.error(f"❌ CLI error: {e}")
    
    def run(self):
        """Run the supervisor"""
        self.running = True
        
        # Setup signal handlers
        def signal_handler(signum, frame):
            LOGGER.info(f"🛑 Received signal {signum}, shutting down...")
            self.running = False
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        try:
            # Start all bots
            self.start_all()
            
            # Print initial status
            self.print_status()
            
            # Run event loop with health check + CLI
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                if self.interactive:
                    # Interactive mode: CLI + health check + command listener + broadcast listener
                    loop.run_until_complete(asyncio.gather(
                        self.health_check_loop(),
                        self.command_listener_loop(),
                        self.broadcast_listener_loop(),
                        self.interactive_cli()
                    ))
                else:
                    # Non-interactive mode: health check + command listener + broadcast listener
                    loop.run_until_complete(asyncio.gather(
                        self.health_check_loop(),
                        self.command_listener_loop(),
                        self.broadcast_listener_loop()
                    ))
            except KeyboardInterrupt:
                LOGGER.info("🛑 Keyboard interrupt")
            finally:
                loop.close()
        
        finally:
            # Cleanup
            LOGGER.info("🧹 Cleaning up...")
            self.stop_all()
            LOGGER.info("✅ Supervisor stopped")


def main():
    """Main entry point"""
    # Parse arguments
    parser = argparse.ArgumentParser(description="KissBot Supervisor V1")
    parser.add_argument(
        '--config',
        type=str,
        default='config/config.yaml',
        help='Path to config file (default: config/config.yaml)'
    )
    parser.add_argument(
        '--non-interactive',
        action='store_true',
        help='Run in non-interactive mode (no CLI, just health checks)'
    )
    parser.add_argument(
        '--use-db',
        action='store_true',
        help='Use database for tokens instead of config.yaml'
    )
    parser.add_argument(
        '--db',
        type=str,
        default='kissbot.db',
        help='Path to database file (default: kissbot.db)'
    )
    parser.add_argument(
        '--enable-hub',
        action='store_true',
        help='Enable EventSub Hub (centralized WebSocket for all bots)'
    )
    parser.add_argument(
        '--hub-socket',
        type=str,
        default='/tmp/kissbot_hub.sock',
        help='Path to Hub IPC socket (default: /tmp/kissbot_hub.sock)'
    )
    args = parser.parse_args()
    
    print("=" * 90)
    print("KissBot Supervisor V1")
    print(f"Config: {args.config}")
    print(f"Token Source: {'DATABASE' if args.use_db else 'YAML'}")
    if args.use_db:
        print(f"Database: {args.db}")
    print(f"EventSub Hub: {'ENABLED' if args.enable_hub else 'DISABLED (bots use direct mode)'}")
    if args.enable_hub:
        print(f"Hub Socket: {args.hub_socket}")
    print(f"Mode: {'Non-interactive' if args.non_interactive else 'Interactive'}")
    print("=" * 90)
    
    supervisor = SimpleSupervisor(
        config_path=args.config,
        interactive=not args.non_interactive,
        use_db=args.use_db,
        db_path=args.db,
        enable_hub=args.enable_hub,
        hub_socket=args.hub_socket
    )
    supervisor.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        LOGGER.error(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
