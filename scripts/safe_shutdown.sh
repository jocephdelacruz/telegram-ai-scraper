#!/bin/bash

# Telegram AI Scraper - Safe System Shutdown
# 
# This script performs a comprehensive, safe shutdown of the entire system:
# - Gracefully stops all Celery workers and Beat scheduler
# - Cleans up stale session lock files (preserves actual session)
# - Clears Redis cache of old message IDs based on FETCH_INTERVAL_SECONDS
# - Removes temporary files and process locks
# - Provides system cleanup status and recommendations
#
# Usage:
#   ./scripts/safe_shutdown.sh [--force] [--keep-redis]
#
# Options:
#   --force      Force immediate shutdown without confirmation
#   --keep-redis Keep Redis cache (skip cleanup)
#
# Examples:
#   ./scripts/safe_shutdown.sh                    # Interactive shutdown with full cleanup
#   ./scripts/safe_shutdown.sh --force           # Immediate shutdown with cleanup
#   ./scripts/safe_shutdown.sh --keep-redis      # Shutdown but preserve Redis cache

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$PROJECT_DIR/../telegram-ai-scraper_env"
LOG_DIR="$PROJECT_DIR/logs"
PID_DIR="$PROJECT_DIR/pids"

print_header() {
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}🛑 $1${NC}"
    echo -e "${CYAN}========================================${NC}"
}

print_status() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} ✅ $1"
}

print_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} ❌ $1"
}

print_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} ⚠️  $1"
}

print_info() {
    echo -e "${PURPLE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} ℹ️  $1"
}

print_cleanup() {
    echo -e "${CYAN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} 🧹 $1"
}

# Parse command line arguments
FORCE_MODE=false
KEEP_REDIS=false

for arg in "$@"; do
    case $arg in
        --force)
            FORCE_MODE=true
            shift
            ;;
        --keep-redis)
            KEEP_REDIS=true
            shift
            ;;
        --help|-h)
            echo "Telegram AI Scraper - Safe System Shutdown"
            echo ""
            echo "Usage: $0 [--force] [--keep-redis]"
            echo ""
            echo "Options:"
            echo "  --force      Force immediate shutdown without confirmation"
            echo "  --keep-redis Keep Redis cache (skip cleanup)"
            echo "  --help       Show this help message"
            echo ""
            echo "This script performs comprehensive system cleanup:"
            echo "• Graceful Celery worker shutdown"
            echo "• Session lock file cleanup"
            echo "• Redis cache cleanup (old message IDs)"
            echo "• Temporary file cleanup"
            echo "• System health summary"
            exit 0
            ;;
        *)
            print_error "Unknown option: $arg"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Function to check prerequisites
check_prerequisites() {
    # Change to project directory
    cd "$PROJECT_DIR" || {
        print_error "Cannot change to project directory: $PROJECT_DIR"
        exit 1
    }

    # Check if virtual environment exists
    if [ ! -d "$VENV_DIR" ]; then
        print_error "Virtual environment not found at $VENV_DIR"
        exit 1
    fi

    # Activate virtual environment
    source "$VENV_DIR/bin/activate" || {
        print_error "Failed to activate virtual environment"
        exit 1
    }

    # Create directories if they don't exist
    mkdir -p "$LOG_DIR" "$PID_DIR"
}

# Function to get fetch interval from config
get_fetch_interval() {
    local fetch_interval=240  # Default fallback
    
    if [ -f "config/config.json" ]; then
        # Try to extract FETCH_INTERVAL_SECONDS from config
        local config_interval=$(python3 -c "
import json
try:
    with open('config/config.json', 'r') as f:
        config = json.load(f)
    interval = config.get('TELEGRAM_CONFIG', {}).get('FETCH_INTERVAL_SECONDS', 240)
    print(int(interval))
except:
    print(240)
" 2>/dev/null)
        
        if [[ "$config_interval" =~ ^[0-9]+$ ]] && [ "$config_interval" -gt 0 ]; then
            fetch_interval=$config_interval
        fi
    fi
    
    echo $fetch_interval
}

# Function: Stop Celery Services
stop_celery_services() {
    print_status "Stopping Celery services..."
    
    if [ "$FORCE_MODE" = true ]; then
        ./scripts/deploy_celery.sh stop --force
    else
        ./scripts/deploy_celery.sh stop
    fi
    
    local exit_code=$?
    if [ $exit_code -eq 0 ]; then
        print_success "Celery services stopped successfully"
    else
        print_warning "Celery shutdown completed with warnings (exit code: $exit_code)"
    fi
    
    return $exit_code
}

# Function: Clean up session lock files
cleanup_session_locks() {
    print_cleanup "Cleaning up session lock files..."
    
    local cleaned_count=0
    local lock_files=()
    
    # Find all session lock files
    while IFS= read -r -d '' file; do
        lock_files+=("$file")
    done < <(find . -maxdepth 1 -name "*.lock" -type f -print0 2>/dev/null)
    
    if [ ${#lock_files[@]} -eq 0 ]; then
        print_success "No session lock files found (already clean)"
        return 0
    fi
    
    echo ""
    print_info "Found ${#lock_files[@]} lock file(s):"
    
    for lock_file in "${lock_files[@]}"; do
        local filename=$(basename "$lock_file")
        local age_minutes=$(find "$lock_file" -mmin +0 -exec sh -c 'echo $(( ($(date +%s) - $(stat -c %Y "$1")) / 60 ))' _ {} \; 2>/dev/null || echo "unknown")
        
        echo "   📄 $filename (age: ${age_minutes} minutes)"
        
        # Check if it's a session file lock (preserve telegram_session.session)
        if [[ "$filename" == *".session" ]] && [[ "$filename" != *".lock" ]]; then
            print_info "   ➡️  Preserved: $filename (actual session file)"
            continue
        fi
        
        # Remove lock files
        if rm -f "$lock_file" 2>/dev/null; then
            print_cleanup "   ✅ Removed: $filename"
            cleaned_count=$((cleaned_count + 1))
        else
            print_error "   ❌ Failed to remove: $filename"
        fi
    done
    
    echo ""
    if [ $cleaned_count -gt 0 ]; then
        print_success "Cleaned up $cleaned_count session lock file(s)"
    else
        print_success "Session lock cleanup completed"
    fi
}

# Function: Clean up Redis cache
cleanup_redis_cache() {
    if [ "$KEEP_REDIS" = true ]; then
        print_info "Skipping Redis cleanup (--keep-redis specified)"
        return 0
    fi
    
    print_cleanup "Cleaning up Redis cache..."
    
    # Check if Redis is running
    if ! redis-cli ping >/dev/null 2>&1; then
        print_warning "Redis is not running - skipping cache cleanup"
        return 0
    fi
    
    local fetch_interval=$(get_fetch_interval)
    local cleanup_age=$((fetch_interval * 2))  # Clean up entries older than 2x fetch interval
    
    print_info "Using fetch interval: ${fetch_interval}s, cleanup age: ${cleanup_age}s"
    
    # Clean up message ID tracking (used to prevent duplicates)
    local message_keys=$(redis-cli --scan --pattern "telegram_message:*" 2>/dev/null | wc -l)
    
    if [ "$message_keys" -gt 0 ]; then
        print_info "Found $message_keys message tracking entries in Redis"
        
        # Use Python script for precise cleanup
        local cleaned_keys=$(python3 -c "
import redis
import time
import json

try:
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    
    # Get all message tracking keys
    keys = r.keys('telegram_message:*')
    current_time = time.time()
    cleanup_age = $cleanup_age
    cleaned = 0
    
    for key in keys:
        try:
            # Get the timestamp when this message was processed
            ttl = r.ttl(key)
            if ttl == -1:  # No expiration set
                # Try to get creation time from key or set expiration
                r.expire(key, cleanup_age)
            elif ttl == -2:  # Key doesn't exist
                continue
            elif ttl < cleanup_age // 2:  # Old enough to clean
                r.delete(key)
                cleaned += 1
        except:
            continue
    
    print(cleaned)
except Exception as e:
    print(0)
" 2>/dev/null)
        
        if [[ "$cleaned_keys" =~ ^[0-9]+$ ]] && [ "$cleaned_keys" -gt 0 ]; then
            print_success "Cleaned up $cleaned_keys old message tracking entries"
        else
            print_info "No old message tracking entries to clean"
        fi
    else
        print_success "Redis cache is already clean (no message tracking entries)"
    fi
    
    # Clean up any stale Celery result keys
    local celery_keys=$(redis-cli --scan --pattern "celery-task-meta-*" 2>/dev/null | wc -l)
    if [ "$celery_keys" -gt 0 ]; then
        print_info "Found $celery_keys Celery result entries - cleaning stale ones"
        redis-cli --scan --pattern "celery-task-meta-*" | xargs -r redis-cli del >/dev/null 2>&1
        print_success "Cleaned up Celery result cache"
    fi
}

# Function: Clean up temporary files
cleanup_temp_files() {
    print_cleanup "Cleaning up temporary files..."
    
    local cleaned_count=0
    
    # Clean up old log files (keep last 7 days)
    if [ -d "$LOG_DIR" ]; then
        local old_logs=$(find "$LOG_DIR" -name "*.log.*" -mtime +7 -type f 2>/dev/null | wc -l)
        if [ "$old_logs" -gt 0 ]; then
            find "$LOG_DIR" -name "*.log.*" -mtime +7 -type f -delete 2>/dev/null
            print_cleanup "Removed $old_logs old log files (>7 days)"
            cleaned_count=$((cleaned_count + old_logs))
        fi
    fi
    
    # Clean up Python cache files
    local cache_files=$(find . -name "__pycache__" -type d 2>/dev/null | wc -l)
    if [ "$cache_files" -gt 0 ]; then
        find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
        print_cleanup "Removed $cache_files Python cache directories"
        cleaned_count=$((cleaned_count + cache_files))
    fi
    
    # Clean up .pyc files
    local pyc_files=$(find . -name "*.pyc" -type f 2>/dev/null | wc -l)
    if [ "$pyc_files" -gt 0 ]; then
        find . -name "*.pyc" -type f -delete 2>/dev/null || true
        print_cleanup "Removed $pyc_files compiled Python files"
        cleaned_count=$((cleaned_count + pyc_files))
    fi
    
    # Clean up any stale PID files (should be handled by deploy_celery.sh but double-check)
    if [ -d "$PID_DIR" ]; then
        local stale_pids=$(find "$PID_DIR" -name "*.pid" -type f 2>/dev/null | wc -l)
        if [ "$stale_pids" -gt 0 ]; then
            rm -f "$PID_DIR"/*.pid 2>/dev/null || true
            print_cleanup "Removed $stale_pids stale PID files"
            cleaned_count=$((cleaned_count + stale_pids))
        fi
    fi
    
    # Clean up Celery beat schedule file
    if [ -f "logs/celerybeat-schedule" ]; then
        rm -f "logs/celerybeat-schedule" 2>/dev/null || true
        print_cleanup "Removed Celery beat schedule file"
        cleaned_count=$((cleaned_count + 1))
    fi
    
    if [ $cleaned_count -gt 0 ]; then
        print_success "Cleaned up $cleaned_count temporary files"
    else
        print_success "No temporary files to clean (system is tidy)"
    fi
}

# Function: System health summary
show_shutdown_summary() {
    print_header "Shutdown Summary"
    
    echo ""
    print_info "System Status After Shutdown:"
    
    # Check Celery processes
    local celery_procs=$(pgrep -f "celery.*telegram_celery_tasks" | wc -l)
    if [ "$celery_procs" -eq 0 ]; then
        print_success "✅ Celery workers: All stopped"
    else
        print_warning "⚠️  Celery workers: $celery_procs still running"
    fi
    
    # Check Redis
    if redis-cli ping >/dev/null 2>&1; then
        print_info "ℹ️  Redis: Running (preserved for other services)"
    else
        print_info "ℹ️  Redis: Not running"
    fi
    
    # Check session files
    if [ -f "telegram_session.session" ]; then
        local session_age=$(find "telegram_session.session" -mmin +0 -exec sh -c 'echo $(( ($(date +%s) - $(stat -c %Y "$1")) / 86400 ))' _ {} \; 2>/dev/null || echo "unknown")
        print_success "✅ Telegram session: Preserved (age: ${session_age} days)"
    else
        print_warning "⚠️  Telegram session: Not found (may need authentication)"
    fi
    
    # Check lock files
    local remaining_locks=$(find . -maxdepth 1 -name "*.lock" -type f 2>/dev/null | wc -l)
    if [ "$remaining_locks" -eq 0 ]; then
        print_success "✅ Session locks: All cleaned"
    else
        print_warning "⚠️  Session locks: $remaining_locks remaining"
    fi
    
    echo ""
    print_info "Next Steps:"
    echo "   🚀 To restart system: ./scripts/quick_start.sh"
    echo "   📊 To check status: ./scripts/status.sh"
    echo "   🔍 To test session: ./scripts/telegram_session.sh test"
    echo "   📝 View logs: tail -f logs/*.log"
    
    if [ "$KEEP_REDIS" = true ]; then
        echo ""
        print_info "💡 Redis cache was preserved (--keep-redis used)"
        echo "   To clean manually: redis-cli FLUSHDB"
    fi
}

# Main execution
main() {
    print_header "Safe System Shutdown"
    
    # Check prerequisites
    check_prerequisites
    
    # Show what will be done
    echo ""
    print_info "This script will:"
    echo "   🛑 Stop all Celery workers and Beat scheduler"
    echo "   🧹 Clean up session lock files (preserve actual session)"
    if [ "$KEEP_REDIS" = false ]; then
        echo "   🗄️  Clean up old Redis message tracking entries"
    else
        echo "   🗄️  Skip Redis cleanup (--keep-redis specified)"
    fi
    echo "   📁 Clean up temporary files and caches"
    echo "   📊 Provide shutdown summary and next steps"
    
    # Confirmation (unless force mode)
    if [ "$FORCE_MODE" = false ]; then
        echo ""
        read -p "Continue with safe shutdown? (y/n): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_warning "Shutdown cancelled by user"
            exit 0
        fi
    fi
    
    echo ""
    print_status "Starting safe shutdown sequence..."
    
    # Step 1: Stop Celery services
    echo ""
    stop_celery_services
    
    # Step 2: Clean up session locks
    echo ""
    cleanup_session_locks
    
    # Step 3: Clean up Redis cache
    echo ""
    cleanup_redis_cache
    
    # Step 4: Clean up temporary files
    echo ""
    cleanup_temp_files
    
    # Step 5: Show summary
    echo ""
    show_shutdown_summary
    
    echo ""
    print_success "Safe shutdown completed successfully! 🎉"
}

# Execute main function
main "$@"
exit $?