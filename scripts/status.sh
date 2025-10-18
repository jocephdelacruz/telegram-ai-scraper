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

# Auto-detect worker mode based on existing PID files
running_workers=0
total_workers=0

if [ -f "$PID_DIR/celery_all.pid" ]; then
    # Consolidated mode - single worker handling all queues
    echo "Mode: Consolidated Worker"
    total_workers=1
    check_process "Consolidated Worker (all queues)" "$PID_DIR/celery_all.pid" && ((running_workers++))
elif [ -f "$PID_DIR/celery_main_processor.pid" ] && [ -f "$PID_DIR/celery_data_services.pid" ]; then
    # Split mode - main + data services + maintenance workers
    echo "Mode: Split Workers (3-tier)"
    total_workers=3
    check_process "Main Processor Worker (AI/Telegram)" "$PID_DIR/celery_main_processor.pid" && ((running_workers++))
    check_process "Data Services Worker (SharePoint/Backup/Teams)" "$PID_DIR/celery_data_services.pid" && ((running_workers++))
    check_process "Maintenance Worker (Cleanup/Monitoring)" "$PID_DIR/celery_maintenance.pid" && ((running_workers++))
else
    # Original mode - individual workers for each queue
    echo "Mode: Individual Workers"
    total_workers=5
    check_process "Telegram Processing Worker" "$PID_DIR/celery_main_processor.pid" && ((running_workers++))
    check_process "Notifications Worker" "$PID_DIR/celery_notifications.pid" && ((running_workers++))
    check_process "SharePoint Worker" "$PID_DIR/celery_sharepoint.pid" && ((running_workers++))
    check_process "Backup Worker" "$PID_DIR/celery_backup.pid" && ((running_workers++))
    check_process "Maintenance Worker" "$PID_DIR/celery_maintenance.pid" && ((running_workers++))
fi

# Check Beat scheduler
echo ""
echo "Scheduler:"
echo "─────────"
check_process "Celery Beat Scheduler" "$PID_DIR/celery_beat.pid"

echo ""
echo "Monitoring:"
echo "──────────"
check_process "Flower Web UI" "$PID_DIR/flower.pid"

# Check Telegram session status (safe - file-based only)
echo ""
echo "Telegram Session:"
echo "────────────────"
if [ -f "telegram_session.session" ]; then
    # Check session status using enhanced telegram_auth.py (safe operation)
    if python3 scripts/telegram_auth.py --status --quiet 2>/dev/null; then
        # Extract age from status output
        session_age=$(python3 -c "
import os
from datetime import datetime
if os.path.exists('telegram_session.session'):
    stat = os.stat('telegram_session.session')
    modified = datetime.fromtimestamp(stat.st_mtime)
    age_days = (datetime.now() - modified).days
    print(f'{age_days} days old')
else:
    print('No session file')
" 2>/dev/null)
        echo "✓ Session file exists ($session_age)"
        
        # Show recommendation based on age
        age_num=$(echo "$session_age" | grep -o '^[0-9]*')
        if [ -n "$age_num" ]; then
            if [ "$age_num" -gt 30 ]; then
                echo "  ⚠️  Session >30 days old - consider renewal"
                echo "  💡 Renew: ./scripts/telegram_session.sh renew"
            elif [ "$age_num" -gt 14 ]; then
                echo "  💡 Session >2 weeks old - renewal available if needed"
            else
                echo "  ✓ Session age is acceptable"
            fi
        fi
    else
        echo "✓ Session file exists (details unavailable)"
    fi
else
    echo "✗ No Telegram session file"
    echo "  💡 Authenticate: ./scripts/telegram_session.sh auth"
fi

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
    echo "1. ./scripts/deploy_celery.sh stop"
    echo "2. ./scripts/deploy_celery.sh"
fi

echo ""
echo "Useful Commands:"
echo "───────────────"
echo "Start all:      ./scripts/deploy_celery.sh"
echo "Stop all:       ./scripts/deploy_celery.sh stop"
echo "Monitor web:    http://localhost:5555 (if Flower is running)"
echo "View logs:      tail -f logs/celery_*.log"
echo "Test system:    python3 src/core/main.py --mode test"
echo "SharePoint:     ./scripts/sharepoint_health_check.sh"
echo ""
echo "Session Management:"
echo "──────────────────"
echo "Check session: ./scripts/telegram_session.sh status"
echo "Test session:  ./scripts/telegram_session.sh test"
echo "Renew session: ./scripts/telegram_session.sh renew"

# SharePoint Health Check
echo ""
echo "SharePoint Integration Status:"
echo "────────────────────────────"
if [ -f "$LOG_DIR/sharepoint.log" ]; then
    # Check recent successful operations
    recent_success=$(grep "SharePoint response: status=200" "$LOG_DIR/sharepoint.log" | tail -5 | wc -l)
    if [ "$recent_success" -gt 0 ]; then
        echo "✓ SharePoint operations working (last $recent_success successful)"
        latest_op=$(grep "SharePoint response: status=200" "$LOG_DIR/sharepoint.log" | tail -1 | cut -d']' -f1 | tr -d '[')
        if [ -n "$latest_op" ]; then
            echo "  💾 Last successful operation: $latest_op"
        fi
    else
        echo "⚠️  No recent successful SharePoint operations"
    fi
    
    # Check for recent errors
    recent_errors=$(grep -i "error\|failed" "$LOG_DIR/sharepoint.log" | tail -3)
    if [ -n "$recent_errors" ]; then
        echo "  ⚠️  Recent SharePoint issues detected:"
        echo "$recent_errors" | sed 's/^/    /'
    fi
    
    # Check Teams notifications for SharePoint crashes
    if [ -f "$LOG_DIR/teams.log" ]; then
        sharepoint_crashes=$(grep "SharePointInitializationError" "$LOG_DIR/teams.log" | tail -1)
        if [ -n "$sharepoint_crashes" ]; then
            crash_time=$(echo "$sharepoint_crashes" | cut -d']' -f1 | tr -d '[')
            echo "  🚨 Last SharePoint crash alert: $crash_time"
            echo "  💡 Check: tail -20 logs/sharepoint.log"
        fi
    fi
else
    echo "✗ No SharePoint log file found"
fi

# Show recent errors if any
echo ""
echo "Recent System Errors (last 10 lines):"
echo "────────────────────────────────────"
if [ -f "$LOG_DIR/main.log" ]; then
    tail -10 "$LOG_DIR/main.log" | grep -i error || echo "No recent errors in main.log"
else
    echo "No main.log file found"
fi

# SharePoint troubleshooting commands
echo ""
echo "SharePoint Troubleshooting:"
echo "─────────────────────────"
echo "View SharePoint log:    tail -20 logs/sharepoint.log"
echo "Monitor operations:     tail -f logs/sharepoint.log"
echo "Check crash alerts:     grep 'SharePointInitializationError' logs/teams.log"
echo "Test SharePoint:        ./scripts/run_tests.sh --sharepoint"
echo "Restart data services:  ./scripts/deploy_celery.sh restart data_services"