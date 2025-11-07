#!/bin/bash
# KissBot Supervisor - Start/Stop/Restart Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$SCRIPT_DIR/kissbot-venv"
SUPERVISOR_SCRIPT="$SCRIPT_DIR/supervisor_v1.py"
CONFIG_FILE="$SCRIPT_DIR/config/config.yaml"
DB_FILE="$SCRIPT_DIR/kissbot.db"
PID_DIR="$SCRIPT_DIR/pids"
LOG_DIR="$SCRIPT_DIR/logs"
SUPERVISOR_PID_FILE="$PID_DIR/supervisor.pid"
SUPERVISOR_LOG="$SCRIPT_DIR/supervisor.log"

# Parse --use-db option
USE_DB_FLAG=""
if [ "$2" == "--use-db" ] || [ "$3" == "--use-db" ]; then
    USE_DB_FLAG="--use-db --db $DB_FILE"
fi

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if supervisor is running
is_running() {
    if [ -f "$SUPERVISOR_PID_FILE" ]; then
        PID=$(cat "$SUPERVISOR_PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$SUPERVISOR_PID_FILE"
        fi
    fi
    
    # Check for supervisor_v1.py process
    if pgrep -f "python.*supervisor_v1\.py" > /dev/null 2>&1; then
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
    
    echo -e "${GREEN}🚀 Starting KissBot Supervisor...${NC}"
    
    # Create directories
    mkdir -p "$PID_DIR" "$LOG_DIR"
    
    # Activate venv and start supervisor in background (non-interactive mode)
    cd "$SCRIPT_DIR"
    source "$VENV_PATH/bin/activate"
    nohup python "$SUPERVISOR_SCRIPT" --config "$CONFIG_FILE" --non-interactive $USE_DB_FLAG > "$SUPERVISOR_LOG" 2>&1 &
    
    # Save PID
    SUPERVISOR_PID=$!
    echo $SUPERVISOR_PID > "$SUPERVISOR_PID_FILE"
    
    # Wait a bit and check if it's running
    sleep 3
    if is_running; then
        echo -e "${GREEN}✅ KissBot Supervisor started successfully (PID: $SUPERVISOR_PID)${NC}"
        echo -e "${GREEN}📝 Supervisor log: tail -f $SUPERVISOR_LOG${NC}"
        echo ""
        
        # Show started bots
        sleep 2
        BOT_COUNT=$(pgrep -f "main\.py --channel" | wc -l)
        echo -e "${GREEN}🤖 Started $BOT_COUNT bot processes${NC}"
        
        # List bot processes
        if [ "$BOT_COUNT" -gt 0 ]; then
            echo -e "${GREEN}   Bot processes:${NC}"
            ps aux | grep "main\.py --channel" | grep -v grep | awk '{print "   - PID " $2 ": " $13 " " $14}' || true
        fi
    else
        echo -e "${RED}❌ Failed to start KissBot Supervisor. Check logs: $SUPERVISOR_LOG${NC}"
        rm -f "$SUPERVISOR_PID_FILE"
        return 1
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
    
    if [ -f "$SUPERVISOR_PID_FILE" ]; then
        PID=$(cat "$SUPERVISOR_PID_FILE")
    else
        PID=$(pgrep -f "python.*supervisor_v1\.py" | head -n 1)
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
}

# Function to restart the supervisor
restart() {
    echo -e "${YELLOW}🔄 Restarting KissBot Supervisor...${NC}"
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

# Function to show status
status() {
    echo "========================================================================"
    echo " KissBot Supervisor Status"
    echo "========================================================================"
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
    restart-channel)
        restart_channel "$2"
        ;;
    status)
        status
        ;;
    logs)
        logs "$@"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|restart-channel|status|logs [channel] [-f]} [--use-db]"
        echo ""
        echo "Commands:"
        echo "  start [--use-db]      - Start KissBot Supervisor and all bots"
        echo "  stop                  - Stop KissBot Supervisor and all bots"
        echo "  restart [--use-db]    - Restart KissBot Supervisor and all bots"
        echo "  restart-channel <ch>  - Restart only one specific channel (supervisor keeps running)"
        echo "  status                - Show supervisor and bot status"
        echo "  logs                  - Show last 50 supervisor log lines"
        echo "  logs <channel>        - Show last 50 lines for a specific channel"
        echo "  logs [channel] -f     - Follow logs in real-time"
        echo ""
        echo "Options:"
        echo "  --use-db              - Use database for OAuth tokens (default: YAML)"
        echo ""
        echo "Examples:"
        echo "  $0 start                   # Start with YAML tokens"
        echo "  $0 start --use-db          # Start with database tokens"
        echo "  $0 restart-channel el_serda # Restart only el_serda bot"
        echo "  $0 status"
        echo "  $0 logs"
        echo "  $0 logs ekylybryum"
        echo "  $0 logs pelerin_ -f"
        exit 1
        ;;
esac

exit 0
