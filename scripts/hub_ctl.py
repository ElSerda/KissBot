#!/usr/bin/env python3
"""
Hub Control CLI - Administrative tool for EventSub Hub.

Commands:
    hub_ctl.py status        - Show Hub status (WS, subscriptions, metrics)
    hub_ctl.py resync        - Force reconciliation loop
    hub_ctl.py drain         - Enter maintenance mode (stop accepting new bots)
    hub_ctl.py restart       - Reconnect WebSocket + resync
    hub_ctl.py metrics       - Show detailed metrics
    hub_ctl.py subscriptions - List all desired/active subscriptions

Usage:
    python scripts/hub_ctl.py status --db kissbot.db
    python scripts/hub_ctl.py resync --db kissbot.db --socket /tmp/kissbot_hub.sock
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.manager import DatabaseManager
from core.ipc_protocol import IPCClient, PingMessage


# ============================================================================
# Database Queries
# ============================================================================

def get_hub_state(db_path: str) -> dict:
    """Get Hub state from database."""
    db = DatabaseManager(db_path, key_file=".kissbot.key")
    
    with db._get_connection() as conn:
        # Get hub_state
        state_rows = conn.execute("SELECT key, value FROM hub_state").fetchall()
        state = {row[0]: row[1] for row in state_rows}
        
        # Count desired/active subscriptions
        desired_count = conn.execute("SELECT COUNT(*) FROM desired_subscriptions").fetchone()[0]
        active_count = conn.execute("SELECT COUNT(*) FROM active_subscriptions").fetchone()[0]
        
        # Get channel breakdown
        channel_desired = conn.execute("""
            SELECT channel_id, COUNT(*) 
            FROM desired_subscriptions 
            GROUP BY channel_id
        """).fetchall()
        
        channel_active = conn.execute("""
            SELECT channel_id, COUNT(*) 
            FROM active_subscriptions 
            GROUP BY channel_id
        """).fetchall()
    
    return {
        "state": state,
        "desired_count": desired_count,
        "active_count": active_count,
        "channel_desired": dict(channel_desired),
        "channel_active": dict(channel_active)
    }


def get_subscriptions(db_path: str, status_filter: str = None) -> tuple:
    """Get desired and active subscriptions."""
    db = DatabaseManager(db_path, key_file=".kissbot.key")
    
    with db._get_connection() as conn:
        # Desired subscriptions
        desired = conn.execute("""
            SELECT channel_id, topic, version, transport, created_at
            FROM desired_subscriptions
            ORDER BY channel_id, topic
        """).fetchall()
        
        # Active subscriptions
        query = """
            SELECT twitch_sub_id, channel_id, topic, status, cost, created_at
            FROM active_subscriptions
        """
        if status_filter:
            query += f" WHERE status = '{status_filter}'"
        query += " ORDER BY channel_id, topic"
        
        active = conn.execute(query).fetchall()
    
    return desired, active


def get_metrics(db_path: str) -> dict:
    """Get Hub metrics from database."""
    db = DatabaseManager(db_path, key_file=".kissbot.key")
    
    with db._get_connection() as conn:
        state_rows = conn.execute("SELECT key, value FROM hub_state").fetchall()
        state = {row[0]: row[1] for row in state_rows}
    
    # Parse metrics
    metrics = {}
    for key in ['total_events_routed', 'total_reconciliations', 'total_reconnects',
                'last_reconcile_ts', 'last_reconnect_ts', 'ws_state']:
        metrics[key] = state.get(key, 'N/A')
    
    return metrics


# ============================================================================
# IPC Commands
# ============================================================================

async def send_ipc_ping(socket_path: str) -> bool:
    """Send ping to Hub via IPC to check if it's alive."""
    try:
        client = IPCClient(socket_path)
        await client.connect()
        
        # Send ping
        ping = PingMessage()
        await client.send(ping)
        
        # Wait for pong (timeout 2s)
        response = await asyncio.wait_for(
            anext(client.receive()),
            timeout=2.0
        )
        
        await client.close()
        
        return response.type == "pong"
    
    except Exception as e:
        print(f"❌ Failed to ping Hub: {e}")
        return False


async def send_ipc_resync(socket_path: str) -> bool:
    """Send resync command to Hub via IPC."""
    # TODO: Implement ResyncMessage in IPC protocol
    print("⚠️ Resync via IPC not yet implemented")
    print("   Workaround: Hub reconciles automatically every 60s")
    return False


# ============================================================================
# Commands
# ============================================================================

def cmd_status(args):
    """Show Hub status."""
    print("\n" + "=" * 80)
    print("EventSub Hub - Status")
    print("=" * 80)
    
    # Get state from DB
    hub_data = get_hub_state(args.db)
    state = hub_data["state"]
    
    # WebSocket state
    ws_state = state.get("ws_state", "unknown")
    ws_emoji = "🟢" if ws_state == "up" else "🔴"
    print(f"\n🌐 WebSocket: {ws_emoji} {ws_state.upper()}")
    
    # Subscriptions
    desired = hub_data["desired_count"]
    active = hub_data["active_count"]
    missing = desired - active
    
    print(f"\n📊 Subscriptions:")
    print(f"   Desired: {desired}")
    print(f"   Active:  {active}")
    if missing > 0:
        print(f"   Missing: {missing} (reconciliation pending)")
    elif missing < 0:
        print(f"   Extra:   {abs(missing)} (cleanup pending)")
    else:
        print(f"   ✅ Perfect sync!")
    
    # Last reconciliation
    last_recon = state.get("last_reconcile_ts")
    if last_recon:
        dt = datetime.fromtimestamp(float(last_recon), tz=timezone.utc)
        elapsed = datetime.now(timezone.utc) - dt
        print(f"\n🔄 Last Reconciliation: {dt.strftime('%Y-%m-%d %H:%M:%S UTC')} ({elapsed.seconds}s ago)")
    
    # Metrics
    total_events = state.get("total_events_routed", "0")
    total_recons = state.get("total_reconciliations", "0")
    total_reconns = state.get("total_reconnects", "0")
    
    print(f"\n📈 Metrics:")
    print(f"   Events Routed:   {total_events}")
    print(f"   Reconciliations: {total_recons}")
    print(f"   Reconnects:      {total_reconns}")
    
    # Channel breakdown
    print(f"\n📺 Channels:")
    channel_desired = hub_data["channel_desired"]
    channel_active = hub_data["channel_active"]
    
    all_channels = set(channel_desired.keys()) | set(channel_active.keys())
    for channel_id in sorted(all_channels):
        desired_count = channel_desired.get(channel_id, 0)
        active_count = channel_active.get(channel_id, 0)
        status = "✅" if desired_count == active_count else "⚠️"
        print(f"   {status} Channel {channel_id}: {active_count}/{desired_count} subs")
    
    # Check if Hub is alive via IPC
    print(f"\n🔌 IPC Status:")
    socket_path = args.socket or "/tmp/kissbot_hub.sock"
    if Path(socket_path).exists():
        print(f"   Socket: {socket_path} (exists)")
        
        # Try to ping
        try:
            is_alive = asyncio.run(send_ipc_ping(socket_path))
            if is_alive:
                print(f"   Hub: 🟢 ALIVE (ping successful)")
            else:
                print(f"   Hub: 🔴 NO RESPONSE (not running or stuck)")
        except Exception as e:
            print(f"   Hub: 🔴 ERROR ({e})")
    else:
        print(f"   Socket: {socket_path} (NOT FOUND)")
        print(f"   Hub: 🔴 NOT RUNNING")
    
    print("=" * 80 + "\n")


def cmd_metrics(args):
    """Show detailed metrics."""
    print("\n" + "=" * 80)
    print("EventSub Hub - Detailed Metrics")
    print("=" * 80)
    
    metrics = get_metrics(args.db)
    
    print("\n📈 Counters:")
    print(f"   Total Events Routed:   {metrics.get('total_events_routed', 'N/A')}")
    print(f"   Total Reconciliations: {metrics.get('total_reconciliations', 'N/A')}")
    print(f"   Total Reconnects:      {metrics.get('total_reconnects', 'N/A')}")
    
    print("\n🕐 Timestamps:")
    for key in ['last_reconcile_ts', 'last_reconnect_ts']:
        ts = metrics.get(key)
        if ts and ts != 'N/A':
            dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
            print(f"   {key}: {dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        else:
            print(f"   {key}: N/A")
    
    print("\n🌐 WebSocket:")
    print(f"   State: {metrics.get('ws_state', 'unknown').upper()}")
    
    print("=" * 80 + "\n")


def cmd_subscriptions(args):
    """List all desired/active subscriptions."""
    print("\n" + "=" * 80)
    print("EventSub Hub - Subscriptions")
    print("=" * 80)
    
    desired, active = get_subscriptions(args.db, status_filter=args.status)
    
    print(f"\n📋 DESIRED SUBSCRIPTIONS ({len(desired)} total):")
    if desired:
        print(f"   {'Channel ID':<15} {'Topic':<25} {'Version':<10} {'Transport':<15}")
        print(f"   {'-' * 70}")
        for sub in desired:
            channel_id, topic, version, transport, created_at = sub
            print(f"   {channel_id:<15} {topic:<25} {version:<10} {transport:<15}")
    else:
        print("   (none)")
    
    print(f"\n📋 ACTIVE SUBSCRIPTIONS ({len(active)} total):")
    if active:
        print(f"   {'Channel ID':<15} {'Topic':<25} {'Status':<12} {'Cost':<6}")
        print(f"   {'-' * 70}")
        for sub in active:
            twitch_sub_id, channel_id, topic, status, cost, created_at = sub
            print(f"   {channel_id:<15} {topic:<25} {status:<12} {cost:<6}")
    else:
        print("   (none)")
    
    print("=" * 80 + "\n")


def cmd_resync(args):
    """Force Hub reconciliation."""
    print("\n🔄 Forcing Hub reconciliation...")
    
    socket_path = args.socket or "/tmp/kissbot_hub.sock"
    
    # Check if socket exists
    if not Path(socket_path).exists():
        print(f"❌ Hub socket not found: {socket_path}")
        print(f"   Is the Hub running?")
        sys.exit(1)
    
    # Send resync command via IPC
    success = asyncio.run(send_ipc_resync(socket_path))
    
    if success:
        print("✅ Resync command sent")
    else:
        print("❌ Resync failed (not implemented yet)")
        print("   Hub reconciles automatically every 60s")


def cmd_drain(args):
    """Enter maintenance mode."""
    print("⚠️ Drain mode not yet implemented")
    print("   Planned: Stop accepting new bot connections, finish routing events")


def cmd_restart(args):
    """Restart Hub WebSocket."""
    print("⚠️ Restart command not yet implemented")
    print("   Workaround: Kill Hub process (supervisor will auto-restart)")


# ============================================================================
# Main
# ============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="EventSub Hub Control CLI")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Show Hub status")
    status_parser.add_argument("--db", type=str, default="kissbot.db", help="Database path")
    status_parser.add_argument("--socket", type=str, help="Hub socket path")
    
    # Metrics command
    metrics_parser = subparsers.add_parser("metrics", help="Show detailed metrics")
    metrics_parser.add_argument("--db", type=str, default="kissbot.db", help="Database path")
    
    # Subscriptions command
    subs_parser = subparsers.add_parser("subscriptions", help="List subscriptions")
    subs_parser.add_argument("--db", type=str, default="kissbot.db", help="Database path")
    subs_parser.add_argument("--status", type=str, help="Filter by status (enabled/disabled)")
    
    # Resync command
    resync_parser = subparsers.add_parser("resync", help="Force reconciliation")
    resync_parser.add_argument("--db", type=str, default="kissbot.db", help="Database path")
    resync_parser.add_argument("--socket", type=str, help="Hub socket path")
    
    # Drain command
    drain_parser = subparsers.add_parser("drain", help="Enter maintenance mode")
    drain_parser.add_argument("--db", type=str, default="kissbot.db", help="Database path")
    
    # Restart command
    restart_parser = subparsers.add_parser("restart", help="Restart Hub WebSocket")
    restart_parser.add_argument("--db", type=str, default="kissbot.db", help="Database path")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Route to command handlers
    commands = {
        "status": cmd_status,
        "metrics": cmd_metrics,
        "subscriptions": cmd_subscriptions,
        "resync": cmd_resync,
        "drain": cmd_drain,
        "restart": cmd_restart
    }
    
    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        print(f"❌ Unknown command: {args.command}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Interrupted")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
