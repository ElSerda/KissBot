#!/usr/bin/env python3
"""
Monitor viewer - Read metrics.json in real-time

Usage:
    python3 view_metrics.py           # Display all samples
    python3 view_metrics.py --live    # tail -f mode (live updates)
    python3 view_metrics.py --alerts  # Show only alerts
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path


def format_timestamp(ts: float) -> str:
    """Format unix timestamp to readable time."""
    return datetime.fromtimestamp(ts).strftime('%H:%M:%S')


def display_sample(entry: dict, show_all: bool = True):
    """Display a metrics sample."""
    if entry.get("type") == "header":
        print("\n" + "=" * 60)
        print(f"📊 System Monitor - Interval: {entry.get('interval')}s")
        print(f"   Thresholds: CPU={entry['thresholds']['cpu_percent']}% | RAM={entry['thresholds']['ram_mb']}MB")
        print("=" * 60)
        print(f"{'Time':<10} | {'CPU%':<6} | {'RAM(MB)':<8} | {'Threads':<8} | {'Alerts'}")
        print("-" * 60)
        return
    
    if entry.get("type") != "sample":
        return
    
    # Check if we should display (alerts filter)
    if not show_all and "alerts" not in entry:
        return
    
    time_str = format_timestamp(entry["timestamp"])
    cpu = entry["cpu_percent"]
    ram = entry["ram_mb"]
    threads = entry["threads"]
    alerts = " | ".join(entry.get("alerts", []))
    
    # Color coding
    cpu_str = f"{cpu:>5.1f}"
    ram_str = f"{ram:>7.0f}"
    
    if alerts:
        print(f"⚠️ {time_str} | {cpu_str} | {ram_str} | {threads:<8} | {alerts}")
    else:
        print(f"   {time_str} | {cpu_str} | {ram_str} | {threads:<8} |")


def read_metrics(file_path: Path, live: bool = False, alerts_only: bool = False):
    """Read and display metrics."""
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        print("   Make sure the bot is running and generating metrics.json")
        return
    
    if live:
        print("📊 Live monitoring mode (Ctrl+C to stop)")
        print("-" * 60)
        
        # Read existing entries first
        with open(file_path, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    display_sample(entry, show_all=not alerts_only)
                except json.JSONDecodeError:
                    pass
        
        # Then tail -f mode
        with open(file_path, 'r') as f:
            f.seek(0, 2)  # Go to end
            try:
                while True:
                    line = f.readline()
                    if line:
                        try:
                            entry = json.loads(line.strip())
                            display_sample(entry, show_all=not alerts_only)
                        except json.JSONDecodeError:
                            pass
                    else:
                        time.sleep(0.5)
            except KeyboardInterrupt:
                print("\n\n👋 Monitoring stopped")
    else:
        # Read all at once
        with open(file_path, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    display_sample(entry, show_all=not alerts_only)
                except json.JSONDecodeError:
                    pass


def main():
    file_path = Path("metrics.json")
    live_mode = "--live" in sys.argv
    alerts_only = "--alerts" in sys.argv
    
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return
    
    read_metrics(file_path, live=live_mode, alerts_only=alerts_only)


if __name__ == "__main__":
    main()
