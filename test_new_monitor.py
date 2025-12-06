#!/usr/bin/env python3
"""
Test simple de la nouvelle architecture monitor fire-and-forget
"""

import asyncio
import json
import tempfile
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.monitor_client import MonitorClient
from core.monitor import KissBotMonitor

async def test_monitor_architecture():
    """Test du pattern fire-and-forget avec queue"""
    temp_dir = tempfile.mkdtemp()
    socket_path = os.path.join(temp_dir, "test_monitor.sock")
    db_path = os.path.join(temp_dir, "test_monitor.db")
    
    print(f"📍 Setup: {temp_dir}")
    
    # Démarrer le monitor en tâche background
    monitor = KissBotMonitor(socket_path=socket_path, db_path=db_path)
    
    async def run_monitor():
        try:
            await asyncio.wait_for(monitor.start(), timeout=10)
        except asyncio.TimeoutError:
            pass
    
    monitor_task = asyncio.create_task(run_monitor())
    
    try:
        await asyncio.sleep(0.5)
        print("✅ Monitor started")
        
        # Test 1: Register with real PID
        print("\n▶️ Test 1: Register")
        client = MonitorClient(channel="test_chan", pid=os.getpid(), socket_path=socket_path)
        result = await client.register(features={"llm": True, "translator": False})
        print(f"   Result: {result}")
        assert result, "Register failed"
        
        await asyncio.sleep(0.2)
        assert "test_chan" in monitor.bots, "Bot should be registered"
        print(f"   ✅ Bot in monitor.bots: {list(monitor.bots.keys())}")
        
        # Test 2: Heartbeat
        print("\n▶️ Test 2: Heartbeat")
        result = await client.heartbeat()
        print(f"   Result: {result}")
        assert result, "Heartbeat failed"
        
        await asyncio.sleep(0.2)
        bot = monitor.bots.get("test_chan")
        assert bot is not None and bot.last_heartbeat, "Heartbeat should be recorded"
        print(f"   ✅ Heartbeat recorded")
        
        # Test 3: LLM Usage
        print("\n▶️ Test 3: LLM Usage")
        result = await client.log_llm_usage(
            model="gpt-4",
            feature="jokes",
            tokens_in=100,
            tokens_out=50,
            latency_ms=1200
        )
        print(f"   Result: {result}")
        assert result, "LLM usage failed"
        
        await asyncio.sleep(0.2)
        print(f"   ✅ LLM usage logged")
        
        print(f"\n📊 Queue size: {monitor.event_queue.qsize()}")
        print("\n✨ TOUS LES TESTS PASSENT!")
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        monitor._running = False
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    success = asyncio.run(test_monitor_architecture())
    sys.exit(0 if success else 1)

