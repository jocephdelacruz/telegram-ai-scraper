#!/bin/bash

# Telegram AI Scraper - Comprehensive Celery Management Script
# This script provides complete management of Celery workers and the main application

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$PROJECT_DIR/../telegram-ai-scraper_env"
LOG_DIR="$PROJECT_DIR/logs"
PID_DIR="$PROJECT_DIR/pids"
DATA_DIR="$PROJECT_DIR/data"

# Worker Configuration - Adjust these values as needed
WORKER_MODE="split"   # values: consolidated | split | original

# Worker concurrency settings per mode
# =====================================

# CONSOLIDATED MODE: Single worker handles all queues
ALL_WORKERS=1              # Used for consolidated mode - handles all queues together

# SPLIT MODE: 3-tier architecture for optimal resource allocation  
MAIN_PROCESSOR_WORKERS=1   # Used for all modes - AI-intensive telegram processing
DATA_SERVICES_WORKERS=1    # Used for split mode - SharePoint/Backup/Teams operations
MAINTENANCE_SPLIT_WORKERS=1 # Used for split mode - Cleanup/Monitoring tasks

# ORIGINAL MODE: Individual workers per queue type
NOTIFICATIONS_WORKERS=1    # Used for original mode - Teams notifications only
SHAREPOINT_WORKERS=1       # Used for original mode - SharePoint operations only  
BACKUP_WORKERS=1           # Used for original mode - Backup operations only
MAINTENANCE_WORKERS=1      # Used for original mode - Maintenance/Monitoring tasks
DEFAULT_LOG_LEVEL=info
MAX_TASKS_PER_CHILD=100
PREFETCH_MULTIPLIER=1
POOL="prefork"   # or "solo" if CPU bound + low throughput
FLOWER_PORT=5555

# Function to print colored output
print_status() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

print_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

echo "=========================================="
echo "Telegram AI Scraper - Celery Management"
echo "=========================================="

# Create necessary directories
mkdir -p "$LOG_DIR"
mkdir -p "$PID_DIR"
mkdir -p "$DATA_DIR"

# Change to project directory
cd "$PROJECT_DIR" || exit 1

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check if virtual environment exists
    if [ ! -d "$VENV_DIR" ]; then
        print_error "Virtual environment not found at $VENV_DIR. Run setup.sh first."
        exit 1
    fi

    # Check if config.json exists
    if [ ! -f "config/config.json" ]; then
        print_error "config/config.json not found. Copy and configure config/config_sample.json first."
        exit 1
    fi

    # Activate virtual environment
    print_status "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"

    # Check Redis connection
    print_status "Checking Redis connection..."
    if ! command -v redis-cli &> /dev/null; then
        print_error "Redis CLI not found. Please install Redis server."
        exit 1
    fi

    if ! redis-cli ping > /dev/null 2>&1; then
        print_warning "Redis server not responding. Attempting to start..."
        sudo systemctl start redis-server
        sleep 2
        if ! redis-cli ping > /dev/null 2>&1; then
            print_error "Cannot connect to Redis server. Please check Redis installation."
            exit 1
        fi
    fi

    print_success "All prerequisites met"
}


# Function to start a worker
start_worker() {
    local worker_name=$1
    local queues=$2
    local concurrency=${3:-1}
    local log_level=${4:-$DEFAULT_LOG_LEVEL}
    local pidfile="$PID_DIR/celery_${worker_name}.pid"
    local logfile="$LOG_DIR/celery_${worker_name}.log"

    print_status "Starting $worker_name (queues: $queues, concurrency: $concurrency)..."
    "$VENV_DIR/bin/celery" -A src.tasks.telegram_celery_tasks.celery worker \
        -n "${worker_name}@%h" \
        -Q "$queues" \
        --concurrency "$concurrency" \
        --loglevel "$log_level" \
        --pidfile "$pidfile" \
        --logfile "$logfile" \
        --max-tasks-per-child "$MAX_TASKS_PER_CHILD" \
        --prefetch-multiplier "$PREFETCH_MULTIPLIER" \
        --pool "$POOL" \
        --heartbeat-interval 10 \
        --without-gossip \
        --without-mingle \
        --detach
    
    # Wait up to 15 seconds for worker to fully initialize (especially data_services)
    local max_wait=15
    local count=0
    
    while [ $count -lt $max_wait ]; do
        if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
            print_success "$worker_name started (PID: $(cat "$pidfile"))"
            return 0
        fi
        sleep 1
        count=$((count + 1))
    done
    
    # Final check - sometimes the process starts but takes time to write PID
    if pgrep -f "celery.*worker.*${worker_name}" > /dev/null; then
        print_success "$worker_name is running (process detected, PID file may be delayed)"
        return 0
    else
        print_error "Failed to start $worker_name after ${max_wait}s. Check logs for details."
        return 1
    fi
}


# Function to start Celery Beat (scheduler)
start_beat() {
    print_status "Starting Beat..."
    "$VENV_DIR/bin/celery" -A src.tasks.telegram_celery_tasks.celery beat \
        --loglevel info \
        --pidfile "$PID_DIR/celery_beat.pid" \
        --logfile "$LOG_DIR/celery_beat.log" \
        --detach
    sleep 5
    if [ -f "$PID_DIR/celery_beat.pid" ] && kill -0 "$(cat "$PID_DIR/celery_beat.pid")" 2>/dev/null; then
        print_success "Beat started (PID: $(cat "$PID_DIR/celery_beat.pid"))"
    else
        print_error "Failed to start Beat. Check if process is running manually."
        return 1
    fi
}


# Function to check if workers are running
check_workers() {
    print_status "Checking worker status..."
    celery -A src.tasks.telegram_celery_tasks.celery inspect active > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        print_success "Workers are responding"
        return 0
    else
        print_error "Workers not responding"
        return 1
    fi
}


start_flower() {
    print_status "Starting Flower (port $FLOWER_PORT)..."
    
    # Check if Flower is installed
    if ! "$VENV_DIR/bin/celery" flower --help >/dev/null 2>&1; then
        print_warning "Flower not installed. Installing flower..."
        "$VENV_DIR/bin/pip" install flower==2.0.1
        if [ $? -ne 0 ]; then
            print_error "Failed to install Flower. Skipping web monitoring."
            return 1
        fi
    fi
    
    nohup "$VENV_DIR/bin/celery" -A src.tasks.telegram_celery_tasks.celery flower \
        --port="$FLOWER_PORT" \
        --url_prefix=/ \
        --logging=info \
        --persistent \
        > "$LOG_DIR/flower.log" 2>&1 &
    echo $! > "$PID_DIR/flower.pid"
    sleep 3
    if kill -0 "$(cat "$PID_DIR/flower.pid")" 2>/dev/null; then
        print_success "Flower started (PID: $(cat "$PID_DIR/flower.pid"))"
        print_success "Web monitoring: http://localhost:$FLOWER_PORT"
    else
        print_warning "Flower may not have started. Check flower.log"
        # Show the error from the log
        if [ -f "$LOG_DIR/flower.log" ]; then
            print_warning "Flower error: $(tail -1 "$LOG_DIR/flower.log")"
        fi
    fi
}


# Function to stop all workers
stop_all_workers() {
    local force_mode=false
    if [[ "$1" == "--force" ]]; then
        force_mode=true
    fi
    
    if [[ "$force_mode" == "true" ]]; then
        print_status "Force stopping all services immediately..."
    else
        print_status "Gracefully stopping all services..."
        echo ""
        echo "This will stop all Celery workers, Beat scheduler, and Flower monitoring."
        read -p "Continue? (y/n): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_warning "Stop operation cancelled"
            return 0
        fi
    fi
    
    # Stop individual services with detailed reporting
    local stopped_count=0
    local total_services=0
    
    echo ""
    print_status "Stopping individual services..."
    echo "─────────────────────────────────"
    
    for pidfile in "$PID_DIR"/celery_*.pid "$PID_DIR/flower.pid"; do
        [ -f "$pidfile" ] || continue
        
        local pid=$(cat "$pidfile" 2>/dev/null)
        local name=$(basename "$pidfile" .pid)
        total_services=$((total_services + 1))
        
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            print_status "Stopping $name (PID: $pid)..."
            
            if [[ "$force_mode" == "true" ]]; then
                # Force kill immediately
                kill -9 "$pid" 2>/dev/null
                sleep 1
            else
                # Graceful shutdown with extended timeout for Telegram session cleanup
                kill -TERM "$pid" 2>/dev/null
                
                # Wait up to 15 seconds for graceful shutdown (increased for Telegram cleanup)
                local timeout=15
                print_status "Waiting for $name to finish Telegram connections..."
                while [[ $timeout -gt 0 ]] && kill -0 "$pid" 2>/dev/null; do
                    sleep 1
                    timeout=$((timeout - 1))
                    if [[ $timeout -eq 10 ]]; then
                        print_status "Still waiting for $name (Telegram session cleanup)..."
                    fi
                done
                
                # Force kill if still running
                if kill -0 "$pid" 2>/dev/null; then
                    print_warning "Force killing $name (graceful shutdown timeout)"
                    kill -9 "$pid" 2>/dev/null
                    sleep 1
                fi
            fi
            
            # Verify process is stopped
            if kill -0 "$pid" 2>/dev/null; then
                print_error "Failed to stop $name (PID: $pid)"
            else
                print_success "$name stopped successfully"
                stopped_count=$((stopped_count + 1))
            fi
        else
            print_warning "$name was not running"
        fi
        
        # Clean up PID file
        rm -f "$pidfile"
    done
    
    # Nuclear option for any remaining processes
    if [[ "$force_mode" == "true" ]] || [[ $stopped_count -lt $total_services ]]; then
        echo ""
        if [[ "$force_mode" != "true" ]]; then
            read -p "Force kill any remaining celery processes? (y/n): " -n 1 -r
            echo ""
        fi
        
        if [[ "$force_mode" == "true" ]] || [[ $REPLY =~ ^[Yy]$ ]]; then
            print_status "Cleaning up any remaining celery processes..."
            
            # Find and kill any remaining celery processes
            local remaining_pids=$(pgrep -f "celery.*src.tasks.telegram_celery_tasks" 2>/dev/null || true)
            if [[ -n "$remaining_pids" ]]; then
                print_warning "Force killing remaining processes: $remaining_pids"
                pkill -9 -f "celery.*src.tasks.telegram_celery_tasks" 2>/dev/null || true
                sleep 2
            fi
            
            # Clean up any remaining PID files
            rm -f "$PID_DIR"/celery_*.pid "$PID_DIR/flower.pid" 2>/dev/null || true
            print_success "Nuclear cleanup completed"
        fi
    fi
    
    # Session Safety: Clean up stale session lock files after workers are stopped
    print_status "Cleaning up stale session lock files..."
    local lock_files_cleaned=0
    # Use shell nullglob option to handle cases where no .lock files exist
    shopt -s nullglob
    for lock_file in *.lock; do
        if [ -f "$lock_file" ]; then
            # Check if lock is stale (older than 5 minutes)
            if find "$lock_file" -mmin +5 -type f >/dev/null 2>&1; then
                if rm -f "$lock_file" 2>/dev/null; then
                    print_success "Removed stale lock: $lock_file"
                    lock_files_cleaned=$((lock_files_cleaned + 1))
                fi
            fi
        fi
    done
    # Reset nullglob option
    shopt -u nullglob
    
    if [ $lock_files_cleaned -gt 0 ]; then
        print_success "Session safety: Cleaned $lock_files_cleaned stale lock file(s)"
    fi
    
    echo ""
    echo "=========================================="
    if [[ $stopped_count -eq $total_services ]] && [[ $total_services -gt 0 ]]; then
        print_success "All services stopped successfully ($stopped_count/$total_services)"
    elif [[ $total_services -eq 0 ]]; then
        print_warning "No running services found"
    else
        print_warning "Some services may still be running ($stopped_count/$total_services stopped)"
    fi
    echo "=========================================="
    echo ""
    echo "To restart services: ./scripts/deploy_celery.sh start"
}


# Function to show status
show_status() {
    print_status "Celery status:"
    "$VENV_DIR/bin/celery" -A src.tasks.telegram_celery_tasks.celery inspect ping 2>/dev/null
    echo "Running PIDs:"
    ls "$PID_DIR"/*.pid 2>/dev/null || true
}


# Function to show logs
show_logs() {
    print_status "Showing recent Celery logs..."
    
    # Show logs based on current worker mode
    if [ -f "$LOG_DIR/celery_all.log" ]; then
        echo -e "\n${YELLOW}Recent Consolidated Worker Logs:${NC}"
        tail -n 30 "$LOG_DIR/celery_all.log" 2>/dev/null || print_warning "No consolidated logs found"
    elif [ -f "$LOG_DIR/celery_data_services.log" ]; then
        echo -e "\n${YELLOW}Recent Main Processor Logs (AI/Telegram):${NC}"
        tail -n 20 "$LOG_DIR/celery_main_processor.log" 2>/dev/null || print_warning "No main processor logs found"
        
        echo -e "\n${YELLOW}Recent Data Services Logs (SharePoint/Backup/Teams):${NC}"
        tail -n 15 "$LOG_DIR/celery_data_services.log" 2>/dev/null || print_warning "No data services logs found"
        
        echo -e "\n${YELLOW}Recent Maintenance Logs (Cleanup/Monitoring):${NC}"
        tail -n 10 "$LOG_DIR/celery_maintenance.log" 2>/dev/null || print_warning "No maintenance logs found"
    else
        echo -e "\n${YELLOW}Recent Main Processor Logs:${NC}"
        tail -n 20 "$LOG_DIR/celery_main_processor.log" 2>/dev/null || print_warning "No main processor logs found"
        
        echo -e "\n${YELLOW}Recent Notifications Logs:${NC}"
        tail -n 10 "$LOG_DIR/celery_notifications.log" 2>/dev/null || print_warning "No notifications logs found"
        
        echo -e "\n${YELLOW}Recent SharePoint Logs:${NC}"
        tail -n 10 "$LOG_DIR/celery_sharepoint.log" 2>/dev/null || print_warning "No SharePoint logs found"
    fi
}


# Function to start all workers
start_all_workers() {
    case "$WORKER_MODE" in
        consolidated)
            # Single worker handles all queues
            start_worker "all" "telegram_processing,telegram_fetch,notifications,sharepoint,backup,maintenance,monitoring" $ALL_WORKERS || return 1
            ;;
        split)
            start_worker "main_processor" "telegram_processing,telegram_fetch" $MAIN_PROCESSOR_WORKERS || return 1
            start_worker "data_services" "sharepoint,backup,notifications" $DATA_SERVICES_WORKERS || return 1
            start_worker "maintenance" "maintenance,monitoring" $MAINTENANCE_SPLIT_WORKERS || return 1
            ;;
        original)
            start_worker "main_processor" "telegram_processing,telegram_fetch" $MAIN_PROCESSOR_WORKERS || return 1
            start_worker "notifications" "notifications" $NOTIFICATIONS_WORKERS || return 1
            start_worker "sharepoint" "sharepoint" $SHAREPOINT_WORKERS || return 1
            start_worker "backup" "backup" $BACKUP_WORKERS || return 1
            start_worker "maintenance" "maintenance,monitoring" $MAINTENANCE_WORKERS || return 1
            ;;
    esac
    start_beat || return 1
    #start_flower
}

# Main command handler
case "${1:-deploy}" in
    "start"|"all"|"deploy")
        check_prerequisites
        start_all_workers
        show_status

        # Wait for workers to initialize
        print_status "Waiting for workers to initialize..."
        sleep 10
        
        # Check if workers are active
        if check_workers; then
            print_success "All workers started successfully!"
            
            # Flower is already started in start_all_workers function

            # Option to run tests (only if not called from quick_start.sh)
            echo ""
            if [[ "${CALLED_FROM_QUICK_START:-}" == "true" ]]; then
                print_status "Skipping test prompt (tests already run by quick_start.sh)"
            else
                echo "Note: If you ran quick_start.sh, comprehensive tests were already executed."
                read -p "Run comprehensive system tests? (y/n): " -n 1 -r
                echo ""
                if [[ $REPLY =~ ^[Yy]$ ]]; then
                    print_status "Running comprehensive system tests..."
                    ./scripts/run_tests.sh --quick
                    if [ $? -ne 0 ]; then
                        print_warning "Some tests failed. System may still be functional."
                    fi
                fi
            fi

            # Session safety protection during startup
            echo ""
            print_status "🔐 SESSION SAFETY: Protecting against concurrent Telegram access"
            echo "   ✅ Prevents concurrent Telegram session access"
            echo "   📱 Protects against phone logout during startup"
            echo "   🔄 Workers will initialize Telegram components when needed"
            
            # Send system startup notification via Celery task (session-safe)
            echo ""
            print_status "Sending system startup notification via Celery task..."
            if python3 -c "
import sys, os
sys.path.append('.')
from src.tasks.telegram_celery_tasks import send_system_startup_notification
result = send_system_startup_notification.delay()
try:
    status = result.get(timeout=10)
    if status.get('status') == 'success':
        print('✅ Teams admin startup notification sent successfully!')
    else:
        print('⚠️  Startup notification completed with warnings')
        print(f'   Reason: {status.get(\"reason\", \"Unknown\")}')
except Exception as e:
    print(f'❌ Failed to send startup notification: {e}')
" 2>/dev/null; then
                echo "• System startup Teams notification completed"
            else
                echo "• Startup notification skipped (Teams admin not configured or workers not ready)"
            fi
            
            echo ""
            echo "📋 MONITORING INFO:"
            echo "• Real-time monitoring is handled automatically by Celery Beat"
            echo "• Messages are fetched every 4 minutes without user intervention"  
            echo "• Components initialize on-demand (session-safe architecture)"
            echo ""
            if [ "$CALLED_FROM_QUICK_START" != "true" ]; then
                read -p "Run optional main.py monitor (will block terminal)? (y/n): " -n 1 -r
                echo ""
                if [[ $REPLY =~ ^[Yy]$ ]]; then
                    echo ""
                    echo "=========================================="
                    echo "🔄 Starting Optional Main.py Monitor"  
                    echo "=========================================="
                    echo ""
                    print_status "Monitor running in foreground (blocks terminal)"
                    print_status "Press Ctrl+C to stop and return to prompt"
                    print_status "Note: Celery Beat continues independently"
                    echo ""
                    
                    # Start main application (only if user explicitly wants it)
                    python3 src/core/main.py --mode monitor
                    exit 0  # Exit after monitoring stops
                fi
            fi
            
            # Always show deployment complete
            echo ""
            echo "=========================================="
            echo "Deployment Complete!"
            echo "=========================================="
            echo ""
            print_success "Services running:"
            case "$WORKER_MODE" in
                consolidated)
                    echo "- Consolidated Worker: $ALL_WORKERS worker ($ALL_WORKERS concurrency)"
                    echo "  Queues: telegram_processing,telegram_fetch,notifications,sharepoint,backup,maintenance,monitoring"
                    ;;
                split)
                    echo "- Main Processor: $MAIN_PROCESSOR_WORKERS workers (telegram_processing,telegram_fetch)"
                    echo "- Data Services Worker: $DATA_SERVICES_WORKERS worker (sharepoint,backup,notifications)"
                    echo "- Maintenance Worker: $MAINTENANCE_SPLIT_WORKERS worker (maintenance,monitoring)"
                    ;;
                original)
                    echo "- Telegram Processing/Fetch Workers: $MAIN_PROCESSOR_WORKERS workers"
                    echo "- Notification Workers: $NOTIFICATIONS_WORKERS workers"
                    echo "- SharePoint Workers: $SHAREPOINT_WORKERS workers"
                    echo "- Backup Workers: $BACKUP_WORKERS worker"
                    echo "- Maintenance Workers: $MAINTENANCE_WORKERS worker"
                    ;;
            esac
            echo "- Celery Beat Scheduler: 1 process"
            if [ -f "$PID_DIR/flower.pid" ]; then
                echo "- Flower Monitoring: http://localhost:5555"
            fi
            
            # Show basic session status after deployment
            echo ""
            print_status "Session Status:"
            if [ -f "telegram_session.session" ]; then
                echo "✅ Session file exists"
                echo "   💡 Check status: ./scripts/telegram_session.sh status"
            else
                echo "❌ No session file - authentication needed"
                echo "   💡 Authenticate: ./scripts/telegram_session.sh auth"
            fi
            echo ""
            echo "To start monitoring:"
            echo "python3 src/core/main.py --mode monitor"
            echo ""
            echo "To manage workers:"
            echo "./scripts/deploy_celery.sh stop     # Stop all workers"
            echo "./scripts/deploy_celery.sh status   # Check status"
            echo "./scripts/deploy_celery.sh logs     # View logs"
            echo ""
            echo "Log files: $LOG_DIR/"
            echo "PID files: $PID_DIR/"
        else
            print_error "Some workers failed to start. Check logs in $LOG_DIR/"
            exit 1
        fi
        ;;
    "stop")
        if [[ "$2" == "--force" ]]; then
            stop_all_workers --force
        else
            stop_all_workers
        fi
        ;;
    restart)
        stop_all_workers
        sleep 2
        check_prerequisites
        start_all_workers
        ;;
    "status")
        show_status
        ;;
    "logs")
        show_logs
        ;;
    "main")
        check_prerequisites
        start_worker "main_processor" "telegram_processing" $MAIN_PROCESSOR_WORKERS
        ;;
    "notifications")
        check_prerequisites
        start_worker "notifications" "notifications" $NOTIFICATIONS_WORKERS
        ;;
    "sharepoint")
        check_prerequisites
        start_worker "sharepoint" "sharepoint" $SHAREPOINT_WORKERS
        ;;
    "backup")
        check_prerequisites
        start_worker "backup" "backup" $BACKUP_WORKERS
        ;;
    "maintenance")
        check_prerequisites
        start_worker "maintenance" "maintenance,monitoring" $MAINTENANCE_WORKERS
        ;;
    "data_services")
        check_prerequisites
        start_worker "data_services" "sharepoint,backup,notifications" $DATA_SERVICES_WORKERS
        ;;
    "beat")
        check_prerequisites
        start_beat
        ;;
    *)
        echo -e "${YELLOW}Telegram AI Scraper - Comprehensive Celery Management${NC}"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  deploy        - Start all workers, beat scheduler, and offer main app (default)"
        echo "  start/all     - Same as deploy"
        echo "  main          - Start main processing workers only (AI/Telegram)"
        echo "  data_services - Start data services worker (SharePoint/Backup/Teams)"
        echo "  maintenance   - Start maintenance workers only (Cleanup/Monitoring)"
        echo "  notifications - Start notifications workers only (individual mode)"
        echo "  sharepoint    - Start SharePoint workers only (individual mode)"
        echo "  backup        - Start backup workers only (individual mode)"
        echo "  beat          - Start Celery Beat scheduler only"
        echo "  stop          - Stop all workers and beat scheduler (graceful)"
        echo "  stop --force  - Force stop all services immediately"
        echo "  status        - Show workers status and statistics"
        echo "  logs          - Show recent logs"
        echo ""
        echo "Examples:"
        echo "  $0            # Interactive deployment (default)"
        echo "  $0 deploy     # Interactive deployment"
        echo "  $0 start      # Start all workers"
        echo "  $0 stop       # Stop everything gracefully"
        echo "  $0 stop --force # Force stop immediately"
        echo "  $0 status     # Check status"
        echo "  $0 logs       # View logs"
        echo ""
        echo "Note: If called from quick_start.sh, comprehensive tests are automatically"
        echo "      run by quick_start.sh to avoid redundancy."
        ;;
esac

print_status "Script execution completed"