#!/bin/bash
# KissBot Supervisor - Start/Stop/Restart Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$SCRIPT_DIR/kissbot-venv"
SUPERVISOR_SCRIPT="$SCRIPT_DIR/supervisor_v1.py"
RUST_SUPERVISOR="$SCRIPT_DIR/rust-supervisor/target/release/kissbot-supervisor"
HUB_SCRIPT="$SCRIPT_DIR/eventsub_hub.py"
CONFIG_FILE="$SCRIPT_DIR/config/config.yaml"
DB_FILE="$SCRIPT_DIR/kissbot.db"
PID_DIR="$SCRIPT_DIR/pids"
LOG_DIR="$SCRIPT_DIR/logs"
SUPERVISOR_PID_FILE="$PID_DIR/supervisor.pid"
HUB_PID_FILE="$PID_DIR/eventsub_hub.pid"
SUPERVISOR_LOG="$SCRIPT_DIR/supervisor.log"
HUB_LOG="$SCRIPT_DIR/eventsub_hub.log"
HUB_SOCKET="/tmp/kissbot_hub.sock"

# Web Backend
WEB_DIR="$SCRIPT_DIR/web/backend"
WEB_PID_FILE="$PID_DIR/web.pid"
WEB_LOG="$SCRIPT_DIR/web.log"
WEB_PORT="${WEB_PORT:-3000}"

# Parse --use-db, --rust, and --mono options
USE_DB_FLAG=""
USE_RUST=false
USE_MONO=false
for arg in "$@"; do
    case $arg in
        --use-db)
            USE_DB_FLAG="--use-db --db $DB_FILE"
            ;;
        --rust)
            USE_RUST=true
            ;;
        --mono)
            USE_MONO=true
            ;;
    esac
done

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if Hub is running
is_hub_running() {
    if [ -f "$HUB_PID_FILE" ]; then
        PID=$(cat "$HUB_PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$HUB_PID_FILE"
        fi
    fi
    
    # Check for eventsub_hub.py process
    if pgrep -f "python.*eventsub_hub\.py" > /dev/null 2>&1; then
        return 0
    fi
    
    return 1
}

# Function to start EventSub Hub
start_hub() {
    if is_hub_running; then
        echo -e "${YELLOW}⚠️  EventSub Hub already running (PID: $(cat $HUB_PID_FILE 2>/dev/null || echo 'unknown'))${NC}"
        return 0
    fi
    
    echo -e "${GREEN}🔌 Starting EventSub Hub...${NC}"
    
    # Create directories
    mkdir -p "$PID_DIR" "$LOG_DIR"
    
    # Activate venv and start hub in background
    cd "$SCRIPT_DIR"
    source "$VENV_PATH/bin/activate"
    nohup python "$HUB_SCRIPT" --config "$CONFIG_FILE" --db "$DB_FILE" > "$HUB_LOG" 2>&1 &
    
    # Save PID
    HUB_PID=$!
    echo $HUB_PID > "$HUB_PID_FILE"
    
    # Wait and check
    sleep 2
    if is_hub_running; then
        echo -e "${GREEN}✅ EventSub Hub started successfully (PID: $HUB_PID)${NC}"
        return 0
    else
        echo -e "${RED}❌ Failed to start EventSub Hub. Check logs: $HUB_LOG${NC}"
        rm -f "$HUB_PID_FILE"
        return 1
    fi
}

# Function to stop EventSub Hub
stop_hub() {
    if ! is_hub_running; then
        echo -e "${YELLOW}⚠️  EventSub Hub is not running${NC}"
        return 1
    fi
    
    if [ -f "$HUB_PID_FILE" ]; then
        PID=$(cat "$HUB_PID_FILE")
    else
        PID=$(pgrep -f "python.*eventsub_hub\.py" | head -n 1)
    fi
    
    if [ -z "$PID" ]; then
        echo -e "${RED}❌ Could not find EventSub Hub process${NC}"
        return 1
    fi
    
    echo -e "${YELLOW}🛑 Stopping EventSub Hub (PID: $PID)...${NC}"
    kill -TERM "$PID" 2>/dev/null || true
    
    # Wait for graceful shutdown
    sleep 2
    
    # Force kill if still running
    if ps -p "$PID" > /dev/null 2>&1; then
        kill -9 "$PID" 2>/dev/null || true
        sleep 1
    fi
    
    rm -f "$HUB_PID_FILE"
    rm -f "$HUB_SOCKET"
    echo -e "${GREEN}✅ EventSub Hub stopped${NC}"
}

# ============================================================
# WEB BACKEND FUNCTIONS
# ============================================================

# Function to check if Web is running
is_web_running() {
    if [ -f "$WEB_PID_FILE" ]; then
        PID=$(cat "$WEB_PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$WEB_PID_FILE"
        fi
    fi
    
    # Check for uvicorn process
    if pgrep -f "uvicorn.*web\.backend\.main" > /dev/null 2>&1; then
        return 0
    fi
    if pgrep -f "uvicorn main:app.*--port $WEB_PORT" > /dev/null 2>&1; then
        return 0
    fi
    
    return 1
}

# Function to start Web Backend
start_web() {
    if is_web_running; then
        echo -e "${YELLOW}⚠️  Web Backend already running (PID: $(cat $WEB_PID_FILE 2>/dev/null || echo 'unknown'))${NC}"
        return 0
    fi
    
    # Check if web directory exists
    if [ ! -d "$WEB_DIR" ]; then
        echo -e "${RED}❌ Web backend not found: $WEB_DIR${NC}"
        return 1
    fi
    
    # Check if .env exists
    if [ ! -f "$WEB_DIR/.env" ]; then
        echo -e "${RED}❌ Web backend .env not found. Copy .env.example and configure it.${NC}"
        echo "   cp $WEB_DIR/.env.example $WEB_DIR/.env"
        return 1
    fi
    
    echo -e "${GREEN}🌐 Starting Web Backend (port $WEB_PORT)...${NC}"
    
    # Create directories
    mkdir -p "$PID_DIR" "$LOG_DIR"
    
    # Activate venv and start web in background
    cd "$SCRIPT_DIR"
    source "$VENV_PATH/bin/activate"
    
    # Set PYTHONPATH and start uvicorn
    PYTHONPATH="$WEB_DIR:$SCRIPT_DIR" nohup python -m uvicorn web.backend.main:app \
        --host 0.0.0.0 \
        --port "$WEB_PORT" \
        --workers 1 \
        > "$WEB_LOG" 2>&1 &
    
    # Save PID
    WEB_PID=$!
    echo $WEB_PID > "$WEB_PID_FILE"
    
    # Wait and check
    sleep 2
    if is_web_running; then
        echo -e "${GREEN}✅ Web Backend started successfully (PID: $WEB_PID)${NC}"
        echo -e "${GREEN}   🌐 URL: http://localhost:$WEB_PORT${NC}"
        return 0
    else
        echo -e "${RED}❌ Failed to start Web Backend. Check logs: $WEB_LOG${NC}"
        rm -f "$WEB_PID_FILE"
        return 1
    fi
}

# Function to stop Web Backend
stop_web() {
    if ! is_web_running; then
        echo -e "${YELLOW}⚠️  Web Backend is not running${NC}"
        return 1
    fi
    
    if [ -f "$WEB_PID_FILE" ]; then
        PID=$(cat "$WEB_PID_FILE")
    else
        PID=$(pgrep -f "uvicorn.*web\.backend\.main" | head -n 1)
        if [ -z "$PID" ]; then
            PID=$(pgrep -f "uvicorn main:app.*--port $WEB_PORT" | head -n 1)
        fi
    fi
    
    if [ -z "$PID" ]; then
        echo -e "${RED}❌ Could not find Web Backend process${NC}"
        return 1
    fi
    
    echo -e "${YELLOW}🛑 Stopping Web Backend (PID: $PID)...${NC}"
    kill -TERM "$PID" 2>/dev/null || true
    
    # Wait for graceful shutdown
    sleep 2
    
    # Force kill if still running
    if ps -p "$PID" > /dev/null 2>&1; then
        kill -9 "$PID" 2>/dev/null || true
        sleep 1
    fi
    
    rm -f "$WEB_PID_FILE"
    echo -e "${GREEN}✅ Web Backend stopped${NC}"
}

# ============================================================
# SUPERVISOR FUNCTIONS
# ============================================================
is_running() {
    if [ -f "$SUPERVISOR_PID_FILE" ]; then
        PID=$(cat "$SUPERVISOR_PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$SUPERVISOR_PID_FILE"
        fi
    fi
    
    # Check for Python supervisor_v1.py process
    if pgrep -f "python.*supervisor_v1\.py" > /dev/null 2>&1; then
        return 0
    fi
    
    # Check for Rust kissbot-supervisor process
    if pgrep -f "kissbot-supervisor" > /dev/null 2>&1; then
        return 0
    fi
    
    return 1
}

# Function to start the supervisor
start() {
    if is_running; then
        echo -e "${YELLOW}⚠️  KissBot Supervisor is already running (PID: $(cat $SUPERVISOR_PID_FILE 2>/dev/null || echo 'unknown'))${NC}"
        return 1
    fi
    
    # Create directories
    mkdir -p "$PID_DIR" "$LOG_DIR"
    cd "$SCRIPT_DIR"
    
    if [ "$USE_RUST" = true ]; then
        # === RUST SUPERVISOR ===
        if [ ! -f "$RUST_SUPERVISOR" ]; then
            echo -e "${RED}❌ Rust supervisor not built. Run: cd rust-supervisor && cargo build --release${NC}"
            return 1
        fi
        
        # Build flags
        RUST_FLAGS="--config $CONFIG_FILE --enable-hub"
        if [ -n "$USE_DB_FLAG" ]; then
            RUST_FLAGS="$RUST_FLAGS --use-db --db $DB_FILE"
        fi
        if [ "$USE_MONO" = true ]; then
            RUST_FLAGS="$RUST_FLAGS --mono"
            echo -e "${GREEN}🦀 Starting KissBot Supervisor (Rust) [MONO-PROCESS]...${NC}"
        else
            echo -e "${GREEN}🦀 Starting KissBot Supervisor (Rust) [MULTI-PROCESS]...${NC}"
        fi
        
        nohup "$RUST_SUPERVISOR" $RUST_FLAGS > "$SUPERVISOR_LOG" 2>&1 &
        SUPERVISOR_PID=$!
        echo $SUPERVISOR_PID > "$SUPERVISOR_PID_FILE"
        
        sleep 2
        if is_running; then
            echo -e "${GREEN}✅ KissBot Supervisor (Rust) started (PID: $SUPERVISOR_PID)${NC}"
            if [ "$USE_MONO" = true ]; then
                echo -e "${GREEN}   🦀 Mode: MONO-PROCESS (all channels in 1 process)${NC}"
            else
                echo -e "${GREEN}   🦀 Mode: MULTI-PROCESS (1 process per channel)${NC}"
            fi
            echo -e "${GREEN}   🦀 RAM: ~5MB | CPU: <0.5% | Startup: <50ms${NC}"
            echo -e "${GREEN}📝 Supervisor log: tail -f $SUPERVISOR_LOG${NC}"
        else
            echo -e "${RED}❌ Failed to start Rust Supervisor. Check logs: $SUPERVISOR_LOG${NC}"
            rm -f "$SUPERVISOR_PID_FILE"
            return 1
        fi
    else
        # === PYTHON SUPERVISOR ===
        # Start Hub first
        start_hub
        if [ $? -ne 0 ]; then
            echo -e "${RED}❌ Failed to start EventSub Hub. Cannot start supervisor.${NC}"
            return 1
        fi
        
        echo -e "${GREEN}🐍 Starting KissBot Supervisor (Python)...${NC}"
        
        source "$VENV_PATH/bin/activate"
        nohup python "$SUPERVISOR_SCRIPT" --config "$CONFIG_FILE" --non-interactive --enable-hub --hub-socket="$HUB_SOCKET" $USE_DB_FLAG > "$SUPERVISOR_LOG" 2>&1 &
        
        SUPERVISOR_PID=$!
        echo $SUPERVISOR_PID > "$SUPERVISOR_PID_FILE"
        
        sleep 3
        if is_running; then
            echo -e "${GREEN}✅ KissBot Supervisor (Python) started (PID: $SUPERVISOR_PID)${NC}"
            echo -e "${GREEN}📝 Supervisor log: tail -f $SUPERVISOR_LOG${NC}"
        else
            echo -e "${RED}❌ Failed to start Python Supervisor. Check logs: $SUPERVISOR_LOG${NC}"
            rm -f "$SUPERVISOR_PID_FILE"
            return 1
        fi
    fi
    
    echo ""
        
    # Wait for bots to be fully started (supervisor writes PID files)
    echo -e "${YELLOW}⏳ Waiting for bots to start...${NC}"
    sleep 5
    
    # Count bot PIDs from PID files (more reliable than pgrep)
    BOT_COUNT=0
    BOT_PIDS=""
    for pidfile in "$PID_DIR"/*.pid; do
        if [ -f "$pidfile" ]; then
            filename=$(basename "$pidfile")
            # Skip supervisor and hub PIDs
            if [[ "$filename" != "supervisor.pid" ]] && [[ "$filename" != "eventsub_hub.pid" ]]; then
                pid=$(cat "$pidfile" 2>/dev/null)
                if [ -n "$pid" ] && ps -p "$pid" > /dev/null 2>&1; then
                    channel=${filename%.pid}
                    BOT_COUNT=$((BOT_COUNT + 1))
                    BOT_PIDS="$BOT_PIDS\n   - PID $pid: --channel $channel"
                fi
            fi
        fi
    done
    
    echo -e "${GREEN}🤖 Started $BOT_COUNT bot processes${NC}"
    
    # List bot processes
    if [ "$BOT_COUNT" -gt 0 ]; then
        echo -e "${GREEN}   Bot processes:${NC}"
        echo -e "$BOT_PIDS"
    fi
}

# Function to stop the supervisor and all bots
stop() {
    if ! is_running; then
        echo -e "${YELLOW}⚠️  KissBot Supervisor is not running${NC}"
        
        # Check for orphaned bot processes
        BOT_COUNT=$(pgrep -f "main\.py --channel" | wc -l)
        if [ "$BOT_COUNT" -gt 0 ]; then
            echo -e "${YELLOW}⚠️  Found $BOT_COUNT orphaned bot processes, cleaning up...${NC}"
            pkill -f "main\.py --channel"
            sleep 2
            echo -e "${GREEN}✅ Orphaned bots stopped${NC}"
        fi
        return 1
    fi
    
    # Find supervisor PID (Python or Rust)
    if [ -f "$SUPERVISOR_PID_FILE" ]; then
        PID=$(cat "$SUPERVISOR_PID_FILE")
    else
        # Try Python first, then Rust
        PID=$(pgrep -f "python.*supervisor_v1\\.py" | head -n 1)
        if [ -z "$PID" ]; then
            PID=$(pgrep -f "kissbot-supervisor" | head -n 1)
        fi
    fi
    
    if [ -z "$PID" ]; then
        echo -e "${RED}❌ Could not find KissBot Supervisor process${NC}"
        return 1
    fi
    
    echo -e "${YELLOW}🛑 Stopping KissBot Supervisor (PID: $PID)...${NC}"
    
    # Send SIGTERM to supervisor (it will stop all bots gracefully)
    kill -TERM "$PID" 2>/dev/null || true
    
    # Wait for supervisor to stop (max 15 seconds)
    for i in {1..15}; do
        if ! ps -p "$PID" > /dev/null 2>&1; then
            break
        fi
        sleep 1
    done
    
    # Force kill supervisor if still running
    if ps -p "$PID" > /dev/null 2>&1; then
        echo -e "${RED}⚠️  Force killing supervisor...${NC}"
        kill -9 "$PID" 2>/dev/null || true
    fi
    
    # Clean up any remaining bot processes
    BOT_COUNT=$(pgrep -f "main\.py --channel" | wc -l)
    if [ "$BOT_COUNT" -gt 0 ]; then
        echo -e "${YELLOW}⚠️  Cleaning up $BOT_COUNT remaining bot processes...${NC}"
        pkill -TERM -f "main\.py --channel" || true
        sleep 2
        pkill -9 -f "main\.py --channel" || true
    fi
    
    rm -f "$SUPERVISOR_PID_FILE"
    echo -e "${GREEN}✅ KissBot Supervisor stopped (all bots terminated)${NC}"
    
    # Stop Hub
    stop_hub
}

# Function to restart the supervisor
restart() {
    echo -e "${YELLOW}🔄 Restarting KissBot Stack (Hub + Supervisor + Bots)...${NC}"
    stop
    sleep 2
    start
}

# Function to restart a single channel
restart_channel() {
    CHANNEL="$1"
    
    if [ -z "$CHANNEL" ]; then
        echo -e "${RED}❌ Error: Channel name required${NC}"
        echo "Usage: $0 restart-channel <channel_name>"
        return 1
    fi
    
    # Check if supervisor is running
    if ! is_running; then
        echo -e "${RED}❌ Supervisor is not running. Start it first with: $0 start${NC}"
        return 1
    fi
    
    echo -e "${YELLOW}🔄 Restarting bot for channel: $CHANNEL${NC}"
    
    # Get current PID
    OLD_PID=$(pgrep -f "main\.py --channel $CHANNEL")
    if [ -n "$OLD_PID" ]; then
        echo "   Current PID: $OLD_PID"
    else
        echo "   ⚠️  Bot not currently running"
    fi
    
    # Send restart command to supervisor
    CMD_FILE="$SCRIPT_DIR/pids/supervisor.cmd"
    RESULT_FILE="$SCRIPT_DIR/pids/supervisor.result"
    
    # Clean old result
    rm -f "$RESULT_FILE"
    
    # Write command
    echo "restart $CHANNEL" > "$CMD_FILE"
    echo "   📨 Sending restart command to supervisor..."
    
    # Wait for supervisor to process command and write result
    MAX_WAIT_MS=30000  # 30 seconds max
    ELAPSED_MS=0
    INTERVAL_MS=100   # Check every 100ms
    
    while [ $ELAPSED_MS -lt $MAX_WAIT_MS ]; do
        if [ -f "$RESULT_FILE" ]; then
            # Read result
            RESULT=$(cat "$RESULT_FILE")
            rm -f "$RESULT_FILE"
            
            # Parse result
            if [[ "$RESULT" == SUCCESS:* ]]; then
                echo -e "${GREEN}   ✅ $RESULT${NC}"
                echo ""
                echo -e "${GREEN}📝 View logs: $0 logs $CHANNEL -f${NC}"
                return 0
            else
                echo -e "${RED}   ❌ $RESULT${NC}"
                echo ""
                echo "   Check supervisor logs: tail -f $SUPERVISOR_LOG"
                return 1
            fi
        fi
        
        sleep 0.1
        ELAPSED_MS=$((ELAPSED_MS + INTERVAL_MS))
    done
    
    # Timeout
    TIMEOUT_SEC=$(echo "scale=0; $MAX_WAIT_MS / 1000" | bc)
    echo -e "${RED}   ❌ Timeout: No response from supervisor after ${TIMEOUT_SEC}s${NC}"
    echo "   Check if supervisor is responsive: $0 status"
    rm -f "$CMD_FILE"  # Clean up
    return 1
}

# Function to start a single channel
start_channel() {
    CHANNEL="$1"
    
    if [ -z "$CHANNEL" ]; then
        echo -e "${RED}❌ Error: Channel name required${NC}"
        echo "Usage: $0 start-channel <channel_name>"
        return 1
    fi
    
    # Check if supervisor is running
    if ! is_running; then
        echo -e "${RED}❌ Supervisor is not running. Start it first with: $0 start${NC}"
        return 1
    fi
    
    echo -e "${GREEN}🚀 Starting bot for channel: $CHANNEL${NC}"
    
    # Send start command to supervisor
    CMD_FILE="$SCRIPT_DIR/pids/supervisor.cmd"
    RESULT_FILE="$SCRIPT_DIR/pids/supervisor.result"
    
    # Clean old result
    rm -f "$RESULT_FILE"
    
    # Write command
    echo "start $CHANNEL" > "$CMD_FILE"
    echo "   📨 Sending start command to supervisor..."
    
    # Wait for supervisor to process command
    MAX_WAIT_MS=30000
    ELAPSED_MS=0
    INTERVAL_MS=100
    
    while [ $ELAPSED_MS -lt $MAX_WAIT_MS ]; do
        if [ -f "$RESULT_FILE" ]; then
            RESULT=$(cat "$RESULT_FILE")
            rm -f "$RESULT_FILE"
            
            if [[ "$RESULT" == SUCCESS:* ]]; then
                echo -e "${GREEN}   ✅ $RESULT${NC}"
                echo ""
                echo -e "${GREEN}📝 View logs: $0 logs $CHANNEL -f${NC}"
                return 0
            else
                echo -e "${RED}   ❌ $RESULT${NC}"
                return 1
            fi
        fi
        
        sleep 0.1
        ELAPSED_MS=$((ELAPSED_MS + INTERVAL_MS))
    done
    
    echo -e "${RED}   ❌ Timeout: No response from supervisor${NC}"
    rm -f "$CMD_FILE"
    return 1
}

# Function to stop a single channel
stop_channel() {
    CHANNEL="$1"
    
    if [ -z "$CHANNEL" ]; then
        echo -e "${RED}❌ Error: Channel name required${NC}"
        echo "Usage: $0 stop-channel <channel_name>"
        return 1
    fi
    
    # Check if supervisor is running
    if ! is_running; then
        echo -e "${RED}❌ Supervisor is not running${NC}"
        return 1
    fi
    
    echo -e "${YELLOW}🛑 Stopping bot for channel: $CHANNEL${NC}"
    
    # Send stop command to supervisor
    CMD_FILE="$SCRIPT_DIR/pids/supervisor.cmd"
    RESULT_FILE="$SCRIPT_DIR/pids/supervisor.result"
    
    # Clean old result
    rm -f "$RESULT_FILE"
    
    # Write command
    echo "stop $CHANNEL" > "$CMD_FILE"
    echo "   📨 Sending stop command to supervisor..."
    
    # Wait for supervisor to process command
    MAX_WAIT_MS=30000
    ELAPSED_MS=0
    INTERVAL_MS=100
    
    while [ $ELAPSED_MS -lt $MAX_WAIT_MS ]; do
        if [ -f "$RESULT_FILE" ]; then
            RESULT=$(cat "$RESULT_FILE")
            rm -f "$RESULT_FILE"
            
            if [[ "$RESULT" == SUCCESS:* ]]; then
                echo -e "${GREEN}   ✅ $RESULT${NC}"
                return 0
            else
                echo -e "${RED}   ❌ $RESULT${NC}"
                return 1
            fi
        fi
        
        sleep 0.1
        ELAPSED_MS=$((ELAPSED_MS + INTERVAL_MS))
    done
    
    echo -e "${RED}   ❌ Timeout: No response from supervisor${NC}"
    rm -f "$CMD_FILE"
    return 1
}

# Function to show status
status() {
    echo "========================================================================"
    echo " KissBot Stack Status"
    echo "========================================================================"
    echo ""
    
    # Check Web Backend
    if is_web_running; then
        if [ -f "$WEB_PID_FILE" ]; then
            WEB_PID=$(cat "$WEB_PID_FILE")
        else
            WEB_PID=$(pgrep -f "uvicorn.*web\.backend\.main" | head -n 1)
        fi
        
        if [ -n "$WEB_PID" ] && ps -p "$WEB_PID" > /dev/null 2>&1; then
            UPTIME=$(ps -p "$WEB_PID" -o etime= | tr -d ' ')
            MEM=$(ps -p "$WEB_PID" -o rss= | awk '{printf "%.1f MB", $1/1024}')
            echo -e "${GREEN}✅ Web Backend: RUNNING${NC}"
            echo -e "   PID:    $WEB_PID"
            echo -e "   URL:    http://localhost:$WEB_PORT"
            echo -e "   Uptime: $UPTIME"
            echo -e "   Memory: $MEM"
        else
            echo -e "${RED}❌ Web Backend: NOT RUNNING${NC}"
        fi
    else
        echo -e "${RED}❌ Web Backend: NOT RUNNING${NC}"
    fi
    
    echo ""
    
    # Check Hub
    if is_hub_running; then
        if [ -f "$HUB_PID_FILE" ]; then
            HUB_PID=$(cat "$HUB_PID_FILE")
        else
            HUB_PID=$(pgrep -f "python.*eventsub_hub\.py" | head -n 1)
        fi
        
        if [ -n "$HUB_PID" ] && ps -p "$HUB_PID" > /dev/null 2>&1; then
            UPTIME=$(ps -p "$HUB_PID" -o etime= | tr -d ' ')
            MEM=$(ps -p "$HUB_PID" -o rss= | awk '{printf "%.1f MB", $1/1024}')
            echo -e "${GREEN}✅ EventSub Hub: RUNNING${NC}"
            echo -e "   PID:    $HUB_PID"
            echo -e "   Uptime: $UPTIME"
            echo -e "   Memory: $MEM"
        else
            echo -e "${RED}❌ EventSub Hub: NOT RUNNING${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  EventSub Hub: NOT RUNNING (optional)${NC}"
    fi
    
    echo ""
    
    # Check supervisor
    if is_running; then
        if [ -f "$SUPERVISOR_PID_FILE" ]; then
            SUPER_PID=$(cat "$SUPERVISOR_PID_FILE")
        else
            SUPER_PID=$(pgrep -f "python.*supervisor_v1\.py" | head -n 1)
        fi
        
        if [ -n "$SUPER_PID" ] && ps -p "$SUPER_PID" > /dev/null 2>&1; then
            UPTIME=$(ps -p "$SUPER_PID" -o etime= | tr -d ' ')
            MEM=$(ps -p "$SUPER_PID" -o rss= | awk '{printf "%.1f MB", $1/1024}')
            echo -e "${GREEN}✅ Supervisor: RUNNING${NC}"
            echo -e "   PID:    $SUPER_PID"
            echo -e "   Uptime: $UPTIME"
            echo -e "   Memory: $MEM"
        else
            echo -e "${RED}❌ Supervisor: NOT RUNNING${NC}"
        fi
    else
        echo -e "${RED}❌ Supervisor: NOT RUNNING${NC}"
    fi
    
    echo ""
    echo "Bot Processes:"
    echo "----------------------------------------"
    
    # List bot processes
    BOT_COUNT=$(pgrep -f "main\.py --channel" | wc -l)
    
    if [ "$BOT_COUNT" -eq 0 ]; then
        echo -e "${RED}   No bot processes running${NC}"
    else
        echo -e "${GREEN}   $BOT_COUNT bot(s) running:${NC}"
        echo ""
        
        # Show each bot with details
        ps aux | grep "main\.py --channel" | grep -v grep | while read -r line; do
            PID=$(echo "$line" | awk '{print $2}')
            CHANNEL=$(echo "$line" | grep -oP '(?<=--channel )\S+')
            MEM=$(echo "$line" | awk '{printf "%.1f MB", $6/1024}')
            CPU=$(echo "$line" | awk '{print $3}')
            
            if [ -n "$CHANNEL" ]; then
                echo -e "   ${GREEN}📺 $CHANNEL${NC}"
                echo "      PID: $PID | CPU: $CPU% | Memory: $MEM"
                
                # Show log file size if exists
                if [ -f "$LOG_DIR/${CHANNEL}.log" ]; then
                    LOG_SIZE=$(du -h "$LOG_DIR/${CHANNEL}.log" | awk '{print $1}')
                    LOG_LINES=$(wc -l < "$LOG_DIR/${CHANNEL}.log")
                    echo "      Log: $LOG_SIZE ($LOG_LINES lines)"
                fi
                echo ""
            fi
        done
    fi
    
    echo "========================================================================"
}

# Function to show logs
logs() {
    # Determine which log to show
    CHANNEL="$2"
    
    if [ -z "$CHANNEL" ]; then
        # No channel specified, show supervisor log
        LOG_FILE="$SUPERVISOR_LOG"
        LABEL="Supervisor"
    else
        # Channel specified, show that channel's log
        LOG_FILE="$LOG_DIR/${CHANNEL}.log"
        LABEL="$CHANNEL"
    fi
    
    if [ ! -f "$LOG_FILE" ]; then
        echo -e "${RED}❌ Log file not found: $LOG_FILE${NC}"
        echo ""
        echo "Available logs:"
        echo "  - supervisor    : $SUPERVISOR_LOG"
        if [ -d "$LOG_DIR" ]; then
            for log in "$LOG_DIR"/*.log; do
                if [ -f "$log" ]; then
                    basename "$log" .log | while read channel; do
                        echo "  - $channel"
                    done
                fi
            done
        fi
        return 1
    fi
    
    if [ "$3" = "-f" ] || [ "$3" = "--follow" ]; then
        echo -e "${GREEN}📝 Following $LABEL logs (Ctrl+C to stop)...${NC}"
        tail -f "$LOG_FILE"
    else
        echo -e "${GREEN}📝 Last 50 lines of $LABEL logs:${NC}"
        tail -n 50 "$LOG_FILE"
    fi
}

# Main script
case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    start-channel)
        start_channel "$2"
        ;;
    stop-channel)
        stop_channel "$2"
        ;;
    restart-channel)
        restart_channel "$2"
        ;;
    start-web)
        start_web
        ;;
    stop-web)
        stop_web
        ;;
    restart-web)
        stop_web
        sleep 1
        start_web
        ;;
    start-all)
        echo -e "${GREEN}🚀 Starting full KissBot Stack...${NC}"
        start_web
        start
        echo ""
        echo -e "${GREEN}🎉 Full stack started!${NC}"
        status
        ;;
    stop-all)
        echo -e "${YELLOW}🛑 Stopping full KissBot Stack...${NC}"
        stop
        stop_web
        echo -e "${GREEN}✅ Full stack stopped${NC}"
        ;;
    status)
        status
        ;;
    logs)
        logs "$@"
        ;;
    logs-web)
        if [ "$2" = "-f" ] || [ "$2" = "--follow" ]; then
            echo -e "${GREEN}📝 Following Web Backend logs (Ctrl+C to stop)...${NC}"
            tail -f "$WEB_LOG"
        else
            echo -e "${GREEN}📝 Last 50 lines of Web Backend logs:${NC}"
            tail -n 50 "$WEB_LOG"
        fi
        ;;
    *)
        echo "Usage: $0 {command} [options]"
        echo ""
        echo "🤖 Bot Commands:"
        echo "  start [options]       - Start KissBot Stack (Hub + Supervisor + all bots)"
        echo "  stop                  - Stop KissBot Stack (Hub + Supervisor + all bots)"
        echo "  restart [options]     - Restart KissBot Stack"
        echo "  start-channel <ch>    - Start only one specific bot"
        echo "  stop-channel <ch>     - Stop only one specific bot"
        echo "  restart-channel <ch>  - Restart only one specific bot"
        echo ""
        echo "🌐 Web Dashboard Commands:"
        echo "  start-web             - Start Web Dashboard (OAuth + API)"
        echo "  stop-web              - Stop Web Dashboard"
        echo "  restart-web           - Restart Web Dashboard"
        echo "  logs-web [-f]         - Show Web Dashboard logs"
        echo ""
        echo "📦 Full Stack Commands:"
        echo "  start-all             - Start everything (Web + Bot)"
        echo "  stop-all              - Stop everything"
        echo "  status                - Show status of all components"
        echo ""
        echo "📝 Log Commands:"
        echo "  logs                  - Show supervisor log"
        echo "  logs <channel>        - Show channel log"
        echo "  logs [-f]             - Follow logs in real-time"
        echo "  logs-web [-f]         - Web dashboard logs"
        echo ""
        echo "⚙️  Options:"
        echo "  --use-db              - Use database for OAuth tokens"
        echo "  --rust                - Use Rust supervisor (5MB RAM)"
        echo "  --mono                - Mono-process mode (saves RAM)"
        echo ""
        echo "📌 Examples:"
        echo "  $0 start-all               # Start full stack (Web + Bot)"
        echo "  $0 start --rust --mono     # Bot only, Rust mono-process"
        echo "  $0 start-web               # Web dashboard only"
        echo "  $0 status                  # Check all components"
        echo "  $0 logs-web -f             # Follow web logs"
        echo ""
        echo "🌐 Web Dashboard: http://localhost:${WEB_PORT}"
        exit 1
        ;;
esac

exit 0