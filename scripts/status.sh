#!/bin/bash

# Telegram AI Scraper - Status Monitoring Script

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PID_DIR="$PROJECT_DIR/pids"
LOG_DIR="$PROJECT_DIR/logs"

cd "$PROJECT_DIR"

echo "=========================================="
echo "Telegram AI Scraper - Service Status"
echo "=========================================="

# Function to check if process is running
check_process() {
    local name=$1
    local pid_file=$2
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p $pid > /dev/null; then
            echo "✓ $name is running (PID: $pid)"
            return 0
        else
            echo "✗ $name is not running (stale PID file)"
            rm -f "$pid_file"
            return 1
        fi
    else
        echo "✗ $name is not running (no PID file)"
        return 1
    fi
}

# Check Redis
echo "Infrastructure:"
echo "─────────────"
if redis-cli ping &> /dev/null; then
    echo "✓ Redis server is running"
else
    echo "✗ Redis server is not running"
fi

echo ""
echo "Celery Workers:"
echo "──────────────"

# Check individual workers
running_workers=0
total_workers=4

check_process "Telegram Processing Worker" "$PID_DIR/celery_main_processor.pid" && ((running_workers++))
check_process "Notifications Worker" "$PID_DIR/celery_notifications.pid" && ((running_workers++))
check_process "SharePoint Worker" "$PID_DIR/celery_sharepoint.pid" && ((running_workers++))
check_process "Backup Worker" "$PID_DIR/celery_backup.pid" && ((running_workers++))

echo ""
echo "Monitoring:"
echo "──────────"
check_process "Flower Web UI" "$PID_DIR/flower.pid"

# Overall status
echo ""
echo "Overall Status:"
echo "──────────────"
echo "Workers running: $running_workers/$total_workers"

if [ $running_workers -eq $total_workers ]; then
    echo "✓ All services are operational"
    echo ""
    
    # Show Celery status
    echo "Celery Cluster Status:"
    echo "────────────────────"
    celery -A src.tasks.telegram_celery_tasks inspect active 2>/dev/null | head -20
    
    echo ""
    echo "Queue Status:"
    echo "───────────"
    celery -A src.tasks.telegram_celery_tasks inspect reserved 2>/dev/null | head -10
    
elif [ $running_workers -eq 0 ]; then
    echo "✗ All services are down"
    echo ""
    echo "To start services: ./deploy_celery.sh"
else
    echo "⚠ Some services are down"
    echo ""
    echo "To restart all services:"
    echo "1. ./scripts/stop_celery.sh"
    echo "2. ./scripts/deploy_celery.sh"
fi

echo ""
echo "Useful Commands:"
echo "───────────────"
echo "Start all:     ./scripts/deploy_celery.sh"
echo "Stop all:      ./scripts/stop_celery.sh"
echo "Monitor web:   http://localhost:5555 (if Flower is running)"
echo "View logs:     tail -f logs/celery_*.log"
echo "Test system:   python3 src/core/main.py --mode test"

# Show recent errors if any
echo ""
echo "Recent Errors (last 10 lines):"
echo "─────────────────────────────"
if [ -f "$LOG_DIR/main.log" ]; then
    tail -10 "$LOG_DIR/main.log" | grep -i error || echo "No recent errors in main.log"
else
    echo "No main.log file found"
fi