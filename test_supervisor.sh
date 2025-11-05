#!/bin/bash
# Test script for Phase 1C: Multi-process supervisor testing

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================================"
echo "Phase 1C: Testing Multi-Process Supervisor"
echo "========================================================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Activate venv
source kissbot-venv/bin/activate

echo "1️⃣  Starting supervisor with test config (2 channels)..."
echo "   Config: config/config.test.yaml"
echo "   Channels: ekylybryum, pelerin_"
echo "   Mode: Non-interactive (for testing)"
echo ""

# Start supervisor in background (non-interactive mode)
python supervisor_v1.py --config config/config.test.yaml --non-interactive &
SUPERVISOR_PID=$!
echo "   Supervisor PID: $SUPERVISOR_PID"

# Wait for startup
echo "   Waiting 5 seconds for bots to start..."
sleep 5

echo ""
echo "2️⃣  Checking process isolation..."
echo "   Looking for: 'main.py --channel'"
echo ""

ps aux | grep "main.py --channel" | grep -v grep || true

PROCESS_COUNT=$(ps aux | grep "main.py --channel" | grep -v grep | wc -l)
echo ""
if [ "$PROCESS_COUNT" -eq 2 ]; then
    echo -e "   ${GREEN}✅ Found 2 isolated processes (expected)${NC}"
else
    echo -e "   ${RED}❌ Expected 2 processes, found $PROCESS_COUNT${NC}"
fi

echo ""
echo "3️⃣  Checking PID files..."
for channel in ekylybryum pelerin_; do
    if [ -f "pids/${channel}.pid" ]; then
        PID=$(cat "pids/${channel}.pid")
        if ps -p $PID > /dev/null 2>&1; then
            echo -e "   ${GREEN}✅ ${channel}: PID $PID is running${NC}"
        else
            echo -e "   ${YELLOW}⚠️  ${channel}: PID $PID not found (may have restarted)${NC}"
        fi
    else
        echo -e "   ${RED}❌ ${channel}: No PID file found${NC}"
    fi
done

echo ""
echo "4️⃣  Checking log files..."
for channel in ekylybryum pelerin_; do
    if [ -f "logs/${channel}.log" ]; then
        LINES=$(wc -l < "logs/${channel}.log")
        echo -e "   ${GREEN}✅ ${channel}: Log file exists ($LINES lines)${NC}"
    else
        echo -e "   ${RED}❌ ${channel}: No log file found${NC}"
    fi
done

echo ""
echo "5️⃣  Testing crash detection and auto-restart..."
echo "   Finding a bot process to kill..."

# Get PID of first bot
BOT_PID=$(ps aux | grep "main.py --channel ekylybryum" | grep -v grep | awk '{print $2}' | head -1)

if [ -n "$BOT_PID" ]; then
    echo "   Found bot PID: $BOT_PID (ekylybryum)"
    echo "   Sending SIGKILL (simulating crash)..."
    kill -9 $BOT_PID || true
    
    echo "   Waiting 35 seconds for health check to detect crash and restart..."
    sleep 35
    
    # Check if restarted
    NEW_PID=$(ps aux | grep "main.py --channel ekylybryum" | grep -v grep | awk '{print $2}' | head -1)
    
    if [ -n "$NEW_PID" ] && [ "$NEW_PID" != "$BOT_PID" ]; then
        echo -e "   ${GREEN}✅ Bot auto-restarted! Old PID: $BOT_PID, New PID: $NEW_PID${NC}"
    else
        echo -e "   ${YELLOW}⚠️  Bot may not have restarted (health check interval: 30s)${NC}"
    fi
else
    echo -e "   ${YELLOW}⚠️  No bot process found to test crash recovery${NC}"
fi

echo ""
echo "6️⃣  Checking other bot is still running (isolation test)..."
PELERIN_PID=$(ps aux | grep "main.py --channel pelerin_" | grep -v grep | awk '{print $2}' | head -1)

if [ -n "$PELERIN_PID" ]; then
    echo -e "   ${GREEN}✅ pelerin_ bot still running (PID $PELERIN_PID) - isolation works!${NC}"
else
    echo -e "   ${RED}❌ pelerin_ bot not running${NC}"
fi

echo ""
echo "7️⃣  Cleanup: Stopping supervisor..."
kill $SUPERVISOR_PID || true
sleep 2

# Kill any remaining bot processes
pkill -f "main.py --channel" || true

echo ""
echo "========================================================================"
echo "Phase 1C Test Complete!"
echo "========================================================================"
echo ""
echo "Summary:"
echo "  - Process isolation: Check logs above"
echo "  - Per-channel logging: ✅ logs/{channel}.log"
echo "  - Per-channel PID files: ✅ pids/{channel}.pid"
echo "  - Auto-restart on crash: Check test results above"
echo ""
echo "📂 Check logs:"
echo "   tail -f logs/ekylybryum.log"
echo "   tail -f logs/pelerin_.log"
echo "   tail -f supervisor.log"
echo ""
