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
                 use_db: bool = False, db_path: str = "kissbot.db"):
        self.channel = channel
        self.config_path = config_path
        self.use_db = use_db
        self.db_path = db_path
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
                "--config", self.config_path
            ]
            
            # Add --use-db if enabled
            if self.use_db:
                cmd.extend(["--use-db", "--db", self.db_path])
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=Path.cwd()
            )
            
            self.start_time = time.time()
            LOGGER.info(f"✅ {self.channel}: Started (PID {self.process.pid})")
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


class SimpleSupervisor:
    """Simple supervisor for managing multiple bot processes"""
    
    def __init__(self, config_path: str = "config/config.yaml", interactive: bool = True,
                 use_db: bool = False, db_path: str = "kissbot.db"):
        self.config_path = config_path
        self.interactive = interactive
        self.use_db = use_db
        self.db_path = db_path
        self.bots: Dict[str, BotProcess] = {}
        self.running = False
        self.health_check_interval = 30  # Check every 30 seconds
        
        # Load config
        self.config = self._load_config()
        
        # Initialize bot processes
        channels = self.config.get("twitch", {}).get("channels", [])
        for channel in channels:
            self.bots[channel] = BotProcess(
                channel, 
                config_path, 
                use_db=use_db, 
                db_path=db_path
            )
        
        mode = "DATABASE" if use_db else "YAML"
        LOGGER.info(f"📋 Supervisor initialized with {len(self.bots)} channels (mode: {mode})")
    
    def _load_config(self) -> dict:
        """Load config.yaml"""
        config_file = Path(self.config_path)
        if not config_file.exists():
            LOGGER.error(f"❌ Config file not found: {self.config_path}")
            sys.exit(1)
        
        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def start_all(self):
        """Start all bot processes"""
        LOGGER.info("🚀 Starting all bots...")
        for channel, bot in self.bots.items():
            bot.start()
            time.sleep(0.5)  # Small delay between starts
    
    def stop_all(self):
        """Stop all bot processes"""
        LOGGER.info("🛑 Stopping all bots...")
        for channel, bot in self.bots.items():
            bot.stop()
    
    def restart_all(self):
        """Restart all bot processes"""
        LOGGER.info("🔄 Restarting all bots...")
        for channel, bot in self.bots.items():
            bot.restart()
            time.sleep(0.5)
    
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
        """Get status of all bots"""
        return {
            channel: bot.status()
            for channel, bot in self.bots.items()
        }
    
    def print_status(self):
        """Print formatted status"""
        print("\n" + "=" * 80)
        print("KissBot Supervisor - Status")
        print("=" * 80)
        
        status = self.status()
        for channel, info in status.items():
            running = "🟢 RUNNING" if info["running"] else "🔴 STOPPED"
            pid = f"PID {info['pid']}" if info['pid'] else "N/A"
            uptime = f"{info['uptime']:.0f}s" if info['uptime'] else "N/A"
            restarts = info['restart_count']
            
            print(f"  {channel:20s} {running:15s} {pid:12s} Uptime: {uptime:8s} Restarts: {restarts}")
        
        print("=" * 80 + "\n")
    
    async def health_check_loop(self):
        """Monitor bot processes and auto-restart if crashed"""
        LOGGER.info(f"💚 Health check loop started (interval={self.health_check_interval}s)")
        
        while self.running:
            await asyncio.sleep(self.health_check_interval)
            
            for channel, bot in self.bots.items():
                if not bot.is_running():
                    LOGGER.warning(f"⚠️ {channel}: Process crashed! Auto-restarting...")
                    bot.restart()
    
    async def interactive_cli(self):
        """Interactive CLI for managing bots"""
        print("\n" + "=" * 80)
        print("KissBot Supervisor - Interactive CLI")
        print("=" * 80)
        print("Commands:")
        print("  status              - Show status of all bots")
        print("  start <channel>     - Start a specific bot")
        print("  stop <channel>      - Stop a specific bot")
        print("  restart <channel>   - Restart a specific bot")
        print("  start-all           - Start all bots")
        print("  stop-all            - Stop all bots")
        print("  restart-all         - Restart all bots")
        print("  quit / exit         - Stop all and exit")
        print("=" * 80 + "\n")
        
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
                    print("✅ All bots started")
                
                elif cmd == "stop-all":
                    self.stop_all()
                    print("✅ All bots stopped")
                
                elif cmd == "restart-all":
                    self.restart_all()
                    print("✅ All bots restarted")
                
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
                    # Interactive mode: CLI + health check
                    loop.run_until_complete(asyncio.gather(
                        self.health_check_loop(),
                        self.interactive_cli()
                    ))
                else:
                    # Non-interactive mode: just health check
                    loop.run_until_complete(self.health_check_loop())
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
    args = parser.parse_args()
    
    print("=" * 80)
    print("KissBot Supervisor V1")
    print(f"Config: {args.config}")
    print(f"Token Source: {'DATABASE' if args.use_db else 'YAML'}")
    if args.use_db:
        print(f"Database: {args.db}")
    print(f"Mode: {'Non-interactive' if args.non_interactive else 'Interactive'}")
    print("=" * 80)
    
    supervisor = SimpleSupervisor(
        config_path=args.config,
        interactive=not args.non_interactive,
        use_db=args.use_db,
        db_path=args.db
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
