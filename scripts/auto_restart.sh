#!/bin/bash

# Auto-restart script for Telegram AI Scraper
# This script monitors and restarts failed workers

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PID_DIR="$PROJECT_DIR/pids"
LOG_DIR="$PROJECT_DIR/logs"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_message() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_DIR/auto_restart.log"
}

check_and_restart() {
    local service_name=$1
    local restart_command=$2
    
    # Check if PID file exists and process is running
    if [ -f "$PID_DIR/$service_name.pid" ]; then
        local pid=$(cat "$PID_DIR/$service_name.pid")
        if ! kill -0 "$pid" 2>/dev/null; then
            log_message "${RED}$service_name is not running (PID $pid not found). Restarting...${NC}"
            
            # Remove stale PID file
            rm -f "$PID_DIR/$service_name.pid"
            
            # Execute restart command
            eval "$restart_command"
            
            sleep 5
            
            # Check if restart was successful
            if [ -f "$PID_DIR/$service_name.pid" ]; then
                local new_pid=$(cat "$PID_DIR/$service_name.pid")
                if kill -0 "$new_pid" 2>/dev/null; then
                    log_message "${GREEN}$service_name restarted successfully (PID $new_pid)${NC}"
                else
                    log_message "${RED}Failed to restart $service_name${NC}"
                fi
            else
                log_message "${RED}Failed to restart $service_name - no PID file created${NC}"
            fi
        else
            log_message "${GREEN}$service_name is running (PID $pid)${NC}"
        fi
    else
        log_message "${YELLOW}$service_name PID file not found. Starting...${NC}"
        eval "$restart_command"
    fi
}

# Main monitoring loop
monitor_services() {
    log_message "Starting service monitoring..."
    
    while true; do
        cd "$PROJECT_DIR" || exit 1
        source "../telegram-ai-scraper_env/bin/activate"
        
        # Check memory usage first
        mem_usage=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
        if [ "$mem_usage" -gt 90 ]; then
            log_message "${RED}High memory usage ($mem_usage%). Skipping restart attempts.${NC}"
            sleep 300  # Wait 5 minutes before next check
            continue
        fi
        
        # Check Redis first
        if ! redis-cli ping >/dev/null 2>&1; then
            log_message "${RED}Redis is not responding. Attempting to restart Redis...${NC}"
            sudo systemctl restart redis-server
            sleep 10
        fi
        
        # Check worker mode and restart accordingly
        if grep -q 'WORKER_MODE="consolidated"' "$SCRIPT_DIR/deploy_celery.sh"; then
            # Consolidated mode - single worker handles all queues
            check_and_restart "celery_all" "$SCRIPT_DIR/deploy_celery.sh start"
        elif grep -q 'WORKER_MODE="split"' "$SCRIPT_DIR/deploy_celery.sh"; then
            # Split mode - 3-tier architecture
            check_and_restart "celery_main_processor" "cd $PROJECT_DIR && $SCRIPT_DIR/deploy_celery.sh main"
            check_and_restart "celery_data_services" "cd $PROJECT_DIR && $SCRIPT_DIR/deploy_celery.sh data_services"
            check_and_restart "celery_maintenance" "cd $PROJECT_DIR && $SCRIPT_DIR/deploy_celery.sh maintenance"
        else
            # Original mode - individual workers per queue type
            check_and_restart "celery_main_processor" "cd $PROJECT_DIR && $SCRIPT_DIR/deploy_celery.sh main"
            check_and_restart "celery_notifications" "cd $PROJECT_DIR && $SCRIPT_DIR/deploy_celery.sh notifications"
            check_and_restart "celery_sharepoint" "cd $PROJECT_DIR && $SCRIPT_DIR/deploy_celery.sh sharepoint"
            check_and_restart "celery_backup" "cd $PROJECT_DIR && $SCRIPT_DIR/deploy_celery.sh backup"
            check_and_restart "celery_maintenance" "cd $PROJECT_DIR && $SCRIPT_DIR/deploy_celery.sh maintenance"
        fi
        
        check_and_restart "celery_beat" "cd $PROJECT_DIR && $SCRIPT_DIR/deploy_celery.sh beat"
        
        log_message "Monitoring cycle completed. Next check in 60 seconds."
        sleep 60
    done
}

case "${1:-monitor}" in
    "start"|"monitor")
        monitor_services
        ;;
    "check")
        # Single check without loop
        cd "$PROJECT_DIR" || exit 1
        source "../telegram-ai-scraper_env/bin/activate"
        
        log_message "Performing single service check..."
        if grep -q 'WORKER_MODE="consolidated"' "$SCRIPT_DIR/deploy_celery.sh"; then
            check_and_restart "celery_all" "$SCRIPT_DIR/deploy_celery.sh start"
        elif grep -q 'WORKER_MODE="split"' "$SCRIPT_DIR/deploy_celery.sh"; then
            # Split mode - check the 3 workers
            check_and_restart "celery_main_processor" "cd $PROJECT_DIR && $SCRIPT_DIR/deploy_celery.sh main"
            check_and_restart "celery_data_services" "cd $PROJECT_DIR && $SCRIPT_DIR/deploy_celery.sh data_services"
            check_and_restart "celery_maintenance" "cd $PROJECT_DIR && $SCRIPT_DIR/deploy_celery.sh maintenance"
        fi
        check_and_restart "celery_beat" "cd $PROJECT_DIR && $SCRIPT_DIR/deploy_celery.sh beat"
        ;;
    *)
        echo "Usage: $0 {start|monitor|check}"
        echo "  start/monitor - Start continuous monitoring"
        echo "  check         - Perform single check"
        ;;
esac