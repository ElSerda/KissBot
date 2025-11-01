#!/usr/bin/env python3
"""
System Monitor - Lightweight CPU/RAM monitoring avec JSON logging

Log les métriques système du bot dans un fichier JSON pour monitoring externe.
Permet de `cat metrics.json` ou `tail -f metrics.json` dans un terminal séparé.
"""
import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Optional

try:
    import psutil
except ImportError:
    psutil = None

LOGGER = logging.getLogger(__name__)


class SystemMonitor:
    """
    Monitor CPU/RAM/Threads du bot et log dans JSON file.
    
    Architecture KISS:
        - 1 ligne JSON par sample
        - tail -f friendly (newline-delimited JSON)
        - Configurable interval
        - Alertes automatiques si seuils dépassés
    
    Usage:
        monitor = SystemMonitor(interval=60, log_file="metrics.json")
        asyncio.create_task(monitor.start())
    
    Lecture externe:
        tail -f metrics.json
        cat metrics.json | jq '.[] | select(.cpu > 50)'  # Filtrer high CPU
    """
    
    def __init__(
        self,
        interval: int = 60,
        log_file: str = "metrics.json",
        cpu_threshold: float = 50.0,
        ram_threshold_mb: int = 500
    ):
        """
        Initialize system monitor.
        
        Args:
            interval: Seconds between samples (default: 60s, use 5-10 for dev)
            log_file: JSON log file path (default: metrics.json)
            cpu_threshold: CPU % warning threshold (default: 50%)
            ram_threshold_mb: RAM MB warning threshold (default: 500MB)
        """
        self.interval = interval
        self.log_file = Path(log_file)
        self.cpu_threshold = cpu_threshold
        self.ram_threshold_mb = ram_threshold_mb
        
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.process = psutil.Process() if psutil else None
        self._start_time = time.time()  # Pour uptime
        self._last_sample: Optional[dict] = None  # Cache last sample pour !stats
        
        if not psutil:
            LOGGER.warning("⚠️ psutil not installed, SystemMonitor disabled")
        else:
            LOGGER.info(f"📊 SystemMonitor init: interval={interval}s, log={log_file}")
    
    async def start(self):
        """Start monitoring loop."""
        if not psutil:
            LOGGER.warning("⚠️ SystemMonitor: psutil not available, skipping")
            return
        
        if self._running:
            LOGGER.warning("⚠️ SystemMonitor already running")
            return
        
        self._running = True
        LOGGER.info("📊 SystemMonitor started")
        
        # Créer le fichier avec header info
        self._write_header()
        
        # Loop de monitoring
        try:
            while self._running:
                await self._sample_and_log()
                await asyncio.sleep(self.interval)
        except Exception as e:
            LOGGER.error(f"❌ SystemMonitor error: {e}")
        finally:
            self._running = False
    
    async def stop(self):
        """Stop monitoring loop."""
        if not self._running:
            return
        
        LOGGER.info("🛑 SystemMonitor stopping...")
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    def _write_header(self):
        """Write initial header/metadata to log file."""
        header = {
            "type": "header",
            "timestamp": time.time(),
            "interval": self.interval,
            "thresholds": {
                "cpu_percent": self.cpu_threshold,
                "ram_mb": self.ram_threshold_mb
            }
        }
        
        # Créer ou reset le fichier
        with open(self.log_file, 'w') as f:
            json.dump(header, f)
            f.write('\n')
    
    async def _sample_and_log(self):
        """Sample system metrics and log to JSON."""
        try:
            # Gather metrics
            cpu_percent = self.process.cpu_percent(interval=1)
            mem_info = self.process.memory_info()
            ram_mb = mem_info.rss / 1024 / 1024  # RSS in MB
            threads = self.process.num_threads()
            
            # Prepare JSON entry
            entry = {
                "type": "sample",
                "timestamp": time.time(),
                "cpu_percent": round(cpu_percent, 1),
                "ram_mb": round(ram_mb, 1),
                "threads": threads,
            }
            
            # Check thresholds et ajouter alerts
            alerts = []
            if cpu_percent > self.cpu_threshold:
                alerts.append(f"HIGH_CPU={cpu_percent:.1f}%")
            if ram_mb > self.ram_threshold_mb:
                alerts.append(f"HIGH_RAM={ram_mb:.0f}MB")
            
            if alerts:
                entry["alerts"] = alerts
            
            # Cache last sample pour !stats command
            self._last_sample = entry
            
            # Write to JSON log (newline-delimited)
            with open(self.log_file, 'a') as f:
                json.dump(entry, f)
                f.write('\n')
            
            # Log to stdout (console)
            log_msg = f"📊 CPU={cpu_percent:.1f}% RAM={ram_mb:.0f}MB Threads={threads}"
            
            if alerts:
                LOGGER.warning(f"⚠️ {log_msg} | {' '.join(alerts)}")
            else:
                LOGGER.info(log_msg)
        
        except Exception as e:
            LOGGER.error(f"❌ Failed to sample metrics: {e}")
    
    def get_current_stats(self) -> Optional[dict]:
        """
        Get current system stats (for !stats command).
        
        Returns dict with:
            - cpu_percent: Current CPU usage
            - ram_mb: Current RAM usage in MB
            - threads: Number of threads
            - uptime_seconds: Bot uptime in seconds
            - alerts: List of alerts (if any)
        
        Returns None if monitoring not available.
        """
        if not psutil or not self._last_sample:
            return None
        
        # Add uptime to cached sample
        uptime_seconds = time.time() - self._start_time
        stats = self._last_sample.copy()
        stats["uptime_seconds"] = int(uptime_seconds)
        
        return stats
    
    def format_stats_message(self) -> str:
        """
        Format stats as chat message (for !stats command).
        
        Returns formatted string like:
        "📊 CPU: 2.3% | RAM: 58MB | Threads: 9 | Uptime: 2h34m"
        
        Returns error message if stats not available.
        """
        stats = self.get_current_stats()
        
        if not stats:
            return "⚠️ System monitoring not available"
        
        # Format uptime (human-readable)
        uptime_sec = stats["uptime_seconds"]
        hours = uptime_sec // 3600
        minutes = (uptime_sec % 3600) // 60
        
        if hours > 0:
            uptime_str = f"{hours}h{minutes}m"
        else:
            uptime_str = f"{minutes}m"
        
        # Base message
        msg = (
            f"📊 CPU: {stats['cpu_percent']}% | "
            f"RAM: {stats['ram_mb']:.0f}MB | "
            f"Threads: {stats['threads']} | "
            f"Uptime: {uptime_str}"
        )
        
        # Add alerts if present
        if "alerts" in stats:
            msg += f" | ⚠️ {', '.join(stats['alerts'])}"
        
        return msg
    
    def is_running(self) -> bool:
        """Check if monitor is running."""
        return self._running
