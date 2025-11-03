#!/bin/bash
# KissBot - Start/Stop/Restart Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$SCRIPT_DIR/kissbot-venv"
PYTHON_SCRIPT="$SCRIPT_DIR/main.py"
PID_FILE="$SCRIPT_DIR/.kissbot.pid"
LOG_FILE="$SCRIPT_DIR/bot.log"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if bot is running
is_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$PID_FILE"
            return 1
        fi
    fi
    return 1
}

# Function to start the bot
start() {
    if is_running; then
        echo -e "${YELLOW}⚠️  KissBot is already running (PID: $(cat $PID_FILE))${NC}"
        return 1
    fi
    
    echo -e "${GREEN}🚀 Starting KissBot...${NC}"
    
    # Activate venv and start bot in background
    cd "$SCRIPT_DIR"
    source "$VENV_PATH/bin/activate"
    nohup python3 "$PYTHON_SCRIPT" > "$LOG_FILE" 2>&1 &
    
    # Save PID
    echo $! > "$PID_FILE"
    
    # Wait a bit and check if it's running
    sleep 2
    if is_running; then
        echo -e "${GREEN}✅ KissBot started successfully (PID: $(cat $PID_FILE))${NC}"
        echo -e "${GREEN}📝 Logs: tail -f $LOG_FILE${NC}"
    else
        echo -e "${RED}❌ Failed to start KissBot. Check logs: $LOG_FILE${NC}"
        rm -f "$PID_FILE"
        return 1
    fi
}

# Function to stop the bot
stop() {
    if ! is_running; then
        echo -e "${YELLOW}⚠️  KissBot is not running${NC}"
        return 1
    fi
    
    PID=$(cat "$PID_FILE")
    echo -e "${YELLOW}🛑 Stopping KissBot (PID: $PID)...${NC}"
    
    kill "$PID"
    
    # Wait for process to stop (max 10 seconds)
    for i in {1..10}; do
        if ! ps -p "$PID" > /dev/null 2>&1; then
            break
        fi
        sleep 1
    done
    
    # Force kill if still running
    if ps -p "$PID" > /dev/null 2>&1; then
        echo -e "${RED}⚠️  Force killing...${NC}"
        kill -9 "$PID"
    fi
    
    rm -f "$PID_FILE"
    echo -e "${GREEN}✅ KissBot stopped${NC}"
}

# Function to restart the bot
restart() {
    echo -e "${YELLOW}🔄 Restarting KissBot...${NC}"
    stop
    sleep 2
    start
}

# Function to show status
status() {
    if is_running; then
        PID=$(cat "$PID_FILE")
        echo -e "${GREEN}✅ KissBot is running (PID: $PID)${NC}"
        
        # Show uptime
        UPTIME=$(ps -p "$PID" -o etime= | tr -d ' ')
        echo -e "${GREEN}⏱️  Uptime: $UPTIME${NC}"
        
        # Show memory usage
        MEM=$(ps -p "$PID" -o rss= | awk '{printf "%.1f MB", $1/1024}')
        echo -e "${GREEN}💾 Memory: $MEM${NC}"
    else
        echo -e "${RED}❌ KissBot is not running${NC}"
    fi
}

# Function to show logs
logs() {
    if [ ! -f "$LOG_FILE" ]; then
        echo -e "${RED}❌ Log file not found: $LOG_FILE${NC}"
        return 1
    fi
    
    if [ "$1" = "-f" ] || [ "$1" = "--follow" ]; then
        echo -e "${GREEN}📝 Following logs (Ctrl+C to stop)...${NC}"
        tail -f "$LOG_FILE"
    else
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
    status)
        status
        ;;
    logs)
        logs "$2"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs [-f]}"
        echo ""
        echo "Commands:"
        echo "  start    - Start KissBot"
        echo "  stop     - Stop KissBot"
        echo "  restart  - Restart KissBot"
        echo "  status   - Show bot status"
        echo "  logs     - Show last 50 log lines"
        echo "  logs -f  - Follow logs in real-time"
        exit 1
        ;;
esac

exit 0
