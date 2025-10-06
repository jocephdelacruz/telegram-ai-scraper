#!/bin/bash

# Telegram AI Scraper - Stop Celery Workers Script

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PID_DIR="$PROJECT_DIR/pids"

cd "$PROJECT_DIR"

echo "=========================================="
echo "Stopping Telegram AI Scraper Services"
echo "=========================================="

# Function to stop a worker
stop_worker() {
    local queue=$1
    local pid_file="$PID_DIR/celery_${queue}.pid"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p $pid > /dev/null; then
            echo "Stopping $queue worker (PID: $pid)..."
            kill $pid
            sleep 2
            
            # Force kill if still running
            if ps -p $pid > /dev/null; then
                echo "Force killing $queue worker..."
                kill -9 $pid
            fi
            
            rm -f "$pid_file"
            echo "✓ $queue worker stopped"
        else
            echo "! $queue worker not running"
            rm -f "$pid_file"
        fi
    else
        echo "! No PID file found for $queue worker"
    fi
}

# Stop Flower if running
if [ -f "$PID_DIR/flower.pid" ]; then
    local flower_pid=$(cat "$PID_DIR/flower.pid")
    if ps -p $flower_pid > /dev/null; then
        echo "Stopping Flower monitoring..."
        kill $flower_pid
        rm -f "$PID_DIR/flower.pid"
        echo "✓ Flower stopped"
    else
        rm -f "$PID_DIR/flower.pid"
    fi
fi

# Stop all workers
echo ""
echo "Stopping Celery workers..."
echo "─────────────────────────"

stop_worker "main_processor"
stop_worker "notifications"
stop_worker "sharepoint"
stop_worker "backup"
stop_worker "maintenance"

# Alternative: Kill all celery processes (nuclear option)
echo ""
read -p "Force kill all remaining celery processes? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Force killing all celery processes..."
    pkill -f "celery.*src.tasks.telegram_celery_tasks"
    echo "✓ All celery processes terminated"
fi

# Clean up PID directory
if [ -d "$PID_DIR" ]; then
    rm -f "$PID_DIR"/celery_*.pid
    rm -f "$PID_DIR/flower.pid"
fi

echo ""
echo "=========================================="
echo "All services stopped"
echo "=========================================="
echo ""
echo "To restart services:"
echo "./scripts/deploy_celery.sh"