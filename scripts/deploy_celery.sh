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
VENV_DIR="$PROJECT_DIR/telegram-ai-scraper_env"
LOG_DIR="$PROJECT_DIR/logs"
PID_DIR="$PROJECT_DIR/pids"
DATA_DIR="$PROJECT_DIR/data"

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
        print_error "Virtual environment not found. Run setup.sh first."
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
    local queue=$2
    local concurrency=${3:-2}
    local log_level=${4:-info}
    
    print_status "Starting $worker_name worker (queue: $queue, concurrency: $concurrency)..."
    
    nohup celery -A src.tasks.telegram_celery_tasks worker \
        --loglevel=$log_level \
        --queues=$queue \
        --concurrency=$concurrency \
        --hostname=$worker_name@%h \
        --logfile="$LOG_DIR/celery_${worker_name}.log" \
        --pidfile="$PID_DIR/celery_${worker_name}.pid" \
        > "$LOG_DIR/celery_${worker_name}_startup.log" 2>&1 &
    
    # Wait a moment for startup
    sleep 2
    
    # Check if worker started successfully
    if [ -f "$PID_DIR/celery_${worker_name}.pid" ]; then
        local pid=$(cat "$PID_DIR/celery_${worker_name}.pid")
        if kill -0 "$pid" 2>/dev/null; then
            print_success "$worker_name worker started successfully (PID: $pid)"
        else
            print_error "$worker_name worker failed to start"
            return 1
        fi
    else
        print_error "$worker_name worker PID file not found"
        return 1
    fi
}

# Function to start Celery Beat (scheduler)
start_beat() {
    print_status "Starting Celery Beat scheduler..."
    
    nohup celery -A src.tasks.telegram_celery_tasks beat \
        --loglevel=info \
        --logfile="$LOG_DIR/celery_beat.log" \
        --pidfile="$PID_DIR/celery_beat.pid" \
        > "$LOG_DIR/celery_beat_startup.log" 2>&1 &
    
    sleep 2
    
    if [ -f "$PID_DIR/celery_beat.pid" ]; then
        local pid=$(cat "$PID_DIR/celery_beat.pid")
        if kill -0 "$pid" 2>/dev/null; then
            print_success "Celery Beat started successfully (PID: $pid)"
        else
            print_error "Celery Beat failed to start"
            return 1
        fi
    else
        print_error "Celery Beat PID file not found"
        return 1
    fi
}

# Function to check if workers are running
check_workers() {
    print_status "Checking worker status..."
    celery -A src.tasks.telegram_celery_tasks inspect active > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        print_success "Workers are responding"
        return 0
    else
        print_error "Workers not responding"
        return 1
    fi
}

# Function to stop all workers
stop_all_workers() {
    print_status "Stopping all Celery workers..."
    
    # Stop all worker processes
    for pidfile in "$PID_DIR"/celery_*.pid; do
        if [ -f "$pidfile" ]; then
            local pid=$(cat "$pidfile")
            local worker_name=$(basename "$pidfile" .pid)
            
            if kill -0 "$pid" 2>/dev/null; then
                print_status "Stopping $worker_name (PID: $pid)..."
                kill -TERM "$pid"
                
                # Wait for graceful shutdown
                local count=0
                while kill -0 "$pid" 2>/dev/null && [ $count -lt 10 ]; do
                    sleep 1
                    count=$((count + 1))
                done
                
                # Force kill if still running
                if kill -0 "$pid" 2>/dev/null; then
                    print_warning "Force killing $worker_name..."
                    kill -KILL "$pid"
                fi
                
                print_success "$worker_name stopped"
            else
                print_warning "$worker_name was not running"
            fi
            
            rm -f "$pidfile"
        fi
    done
    
    print_success "All workers stopped"
}

# Function to show status
show_status() {
    print_status "Checking Celery workers status..."
    
    echo -e "\n${YELLOW}Active Workers:${NC}"
    celery -A src.tasks.telegram_celery_tasks inspect active 2>/dev/null || print_error "Cannot connect to Celery"
    
    echo -e "\n${YELLOW}Registered Tasks:${NC}"
    celery -A src.tasks.telegram_celery_tasks inspect registered 2>/dev/null || print_error "Cannot connect to Celery"
    
    echo -e "\n${YELLOW}Worker Statistics:${NC}"
    celery -A src.tasks.telegram_celery_tasks inspect stats 2>/dev/null || print_error "Cannot connect to Celery"
    
    echo -e "\n${YELLOW}PID Files:${NC}"
    for pidfile in "$PID_DIR"/celery_*.pid; do
        if [ -f "$pidfile" ]; then
            local pid=$(cat "$pidfile")
            local worker_name=$(basename "$pidfile" .pid)
            
            if kill -0 "$pid" 2>/dev/null; then
                echo -e "  ${GREEN}●${NC} $worker_name (PID: $pid) - Running"
            else
                echo -e "  ${RED}●${NC} $worker_name (PID: $pid) - Not running"
            fi
        fi
    done
}

# Function to show logs
show_logs() {
    print_status "Showing recent Celery logs..."
    echo -e "\n${YELLOW}Recent Main Processor Logs:${NC}"
    tail -n 20 "$LOG_DIR/celery_main_processor.log" 2>/dev/null || print_warning "No main processor logs found"
    
    echo -e "\n${YELLOW}Recent Notifications Logs:${NC}"
    tail -n 10 "$LOG_DIR/celery_notifications.log" 2>/dev/null || print_warning "No notifications logs found"
    
    echo -e "\n${YELLOW}Recent SharePoint Logs:${NC}"
    tail -n 10 "$LOG_DIR/celery_sharepoint.log" 2>/dev/null || print_warning "No SharePoint logs found"
}

# Function to start all workers
start_all_workers() {
    print_status "Starting all Celery workers..."
    start_worker "main_processor" "telegram_processing" 4
    start_worker "notifications" "notifications" 2
    start_worker "sharepoint" "sharepoint" 2
    start_worker "backup" "backup" 1
    start_worker "maintenance" "maintenance,monitoring" 1
    start_beat
    print_success "All workers started successfully!"
}

# Main command handler
case "${1:-deploy}" in
    "start"|"all"|"deploy")
        check_prerequisites
        start_all_workers
        
        # Wait for workers to initialize
        print_status "Waiting for workers to initialize..."
        sleep 10
        
        # Check if workers are active
        if check_workers; then
            print_success "All workers started successfully!"
            
            # Option to start Flower monitoring (optional)
            echo ""
            read -p "Start Flower monitoring web UI? (y/n): " -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                print_status "Starting Flower monitoring..."
                nohup celery -A src.tasks.telegram_celery_tasks flower --port=5555 > "$LOG_DIR/flower.log" 2>&1 &
                echo $! > "$PID_DIR/flower.pid"
                print_success "Flower started at http://localhost:5555"
            fi

            # Option to run tests
            echo ""
            read -p "Run connection tests? (y/n): " -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                print_status "Running connection tests..."
                python3 src/core/main.py --mode test
            fi

            # Option to start monitoring
            echo ""
            read -p "Start real-time monitoring? (y/n): " -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                echo ""
                echo "=========================================="
                echo "Starting Telegram AI Scraper Monitoring"
                echo "=========================================="
                echo ""
                print_status "Press Ctrl+C to stop monitoring"
                echo ""
                
                # Start main application
                python3 src/core/main.py --mode monitor
            else
                echo ""
                echo "=========================================="
                echo "Deployment Complete!"
                echo "=========================================="
                echo ""
                print_success "Services running:"
                echo "- Telegram Processing Workers: 4 workers"
                echo "- Notification Workers: 2 workers"
                echo "- SharePoint Workers: 2 workers"
                echo "- Backup Workers: 1 worker"
                echo "- Maintenance Workers: 1 worker"
                echo "- Celery Beat Scheduler: 1 process"
                if [ -f "$PID_DIR/flower.pid" ]; then
                    echo "- Flower Monitoring: http://localhost:5555"
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
            fi
        else
            print_error "Some workers failed to start. Check logs in $LOG_DIR/"
            exit 1
        fi
        ;;
    "stop")
        check_prerequisites
        stop_all_workers
        ;;
    "status")
        check_prerequisites
        show_status
        ;;
    "logs")
        show_logs
        ;;
    "main")
        check_prerequisites
        start_worker "main_processor" "telegram_processing" 4
        ;;
    "notifications")
        check_prerequisites
        start_worker "notifications" "notifications" 2
        ;;
    "sharepoint")
        check_prerequisites
        start_worker "sharepoint" "sharepoint" 2
        ;;
    "backup")
        check_prerequisites
        start_worker "backup" "backup" 1
        ;;
    "maintenance")
        check_prerequisites
        start_worker "maintenance" "maintenance,monitoring" 1
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
        echo "  main          - Start main processing workers only"
        echo "  notifications - Start notifications workers only"
        echo "  sharepoint    - Start SharePoint workers only"
        echo "  backup        - Start backup workers only"
        echo "  maintenance   - Start maintenance workers only"
        echo "  beat          - Start Celery Beat scheduler only"
        echo "  stop          - Stop all workers and beat scheduler"
        echo "  status        - Show workers status and statistics"
        echo "  logs          - Show recent logs"
        echo ""
        echo "Examples:"
        echo "  $0            # Interactive deployment (default)"
        echo "  $0 deploy     # Interactive deployment"
        echo "  $0 start      # Start all workers"
        echo "  $0 stop       # Stop everything"
        echo "  $0 status     # Check status"
        echo "  $0 logs       # View logs"
        ;;
esac

print_status "Script execution completed"