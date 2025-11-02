#!/usr/bin/env python3
"""
Test StreamMonitor + StreamAnnouncer
- Quick validation test
"""
import asyncio
import logging
from unittest.mock import MagicMock, AsyncMock

from core.message_bus import MessageBus
from core.stream_announcer import StreamAnnouncer
from twitchapi.monitors.stream_monitor import StreamMonitor

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")


async def test_stream_monitoring():
    """Test basic flow: StreamMonitor → system.event → StreamAnnouncer"""
    
    print("\n🧪 Test Stream Monitoring Flow\n")
    print("=" * 60)
    
    # Setup
    bus = MessageBus()
    
    # Mock Helix client
    mock_helix = MagicMock()
    
    # Mock get_streams to return offline first, then online
    call_count = 0
    async def mock_get_streams(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        
        if call_count == 1:
            # First call: offline
            return None
        else:
            # Second call: online (simulate transition)
            return {
                "user_id": "44456636",
                "user_login": "el_serda",
                "user_name": "El_Serda",
                "game_name": "Science & Technology",
                "title": "Test Stream Title",
                "viewer_count": 42,
                "started_at": "2025-11-01T00:00:00Z"
            }
    
    mock_helix.get_streams = mock_get_streams
    
    # Config
    config = {
        "announcements": {
            "stream_online": {
                "enabled": True,
                "message": "🔴 @{channel} est en live ! 🎮 {title}"
            },
            "stream_offline": {
                "enabled": False
            }
        }
    }
    
    # Create components
    print("📦 Creating StreamAnnouncer...")
    announcer = StreamAnnouncer(bus, config)
    
    print("📦 Creating StreamMonitor (interval=3s for test)...")
    monitor = StreamMonitor(
        helix=mock_helix,
        bus=bus,
        channels=["el_serda"],
        interval=3  # 3 seconds for quick test
    )
    
    # Intercept chat.outbound to verify announcement
    announcements_received = []
    async def capture_announcement(msg):
        announcements_received.append(msg)
        print(f"\n📢 ANNOUNCEMENT CAPTURED:")
        print(f"   Channel: {msg.channel}")
        print(f"   Text: {msg.text}\n")
    
    bus.subscribe("chat.outbound", capture_announcement)
    
    # Start monitoring
    print("🚀 Starting StreamMonitor...\n")
    await monitor.start()
    
    # Wait for checks
    print("⏳ Waiting for monitoring checks...")
    print("   Check 1 (t=0s): Should detect offline")
    print("   Check 2 (t=3s): Should detect online → ANNOUNCEMENT\n")
    
    await asyncio.sleep(7)  # Wait for 2 checks (0s + 3s + margin)
    
    # Stop monitoring
    print("🛑 Stopping StreamMonitor...")
    await monitor.stop()
    
    # Verify results
    print("\n" + "=" * 60)
    print("📊 Test Results:\n")
    
    # Check state
    state = monitor.get_state("el_serda")
    print(f"✅ Final state: {state['status']}")
    
    # Check announcement
    if announcements_received:
        print(f"✅ Announcement received: {len(announcements_received)}")
        print(f"   Message: {announcements_received[0].text}")
    else:
        print("❌ No announcement received!")
    
    print("\n" + "=" * 60)
    
    # Validate
    assert state['status'] == "online", "Stream should be online"
    assert len(announcements_received) == 1, "Should have 1 announcement"
    assert "🔴" in announcements_received[0].text, "Should contain red circle emoji"
    assert "el_serda" in announcements_received[0].text, "Should mention channel"
    
    print("✅ All tests passed!\n")


if __name__ == "__main__":
    asyncio.run(test_stream_monitoring())
