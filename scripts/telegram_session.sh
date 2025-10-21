#!/bin/bash

# Telegram Session Management - Comprehensive Wrapper Script
# 
# This script provides a unified interface for all Telegram session operations
# with built-in safety protection to prevent account logout or session conflicts.
#
# Usage:
#   ./scripts/telegram_session.sh <command> [options]
#
# Commands:
#   status          - Show session status and age
#   test            - Test session validity (safe)
#   auth            - Authenticate new session
#   renew           - Renew existing session (safe workflow)
#   backup          - Backup current session
#   restore         - Restore session from backup
#   safety-check    - Check session safety (workers, conflicts)
#   diagnostics     - Run comprehensive session diagnostics
#   help            - Show this help message
#
# Examples:
#   ./scripts/telegram_session.sh status
#   ./scripts/telegram_session.sh test
#   ./scripts/telegram_session.sh auth
#   ./scripts/telegram_session.sh renew
#   ./scripts/telegram_session.sh safety-check
#   ./scripts/telegram_session.sh diagnostics

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

print_header() {
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}🔐 $1${NC}"
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

# Function to check prerequisites
check_prerequisites() {
    # Change to project directory
    cd "$PROJECT_DIR" || {
        print_error "Cannot access project directory: $PROJECT_DIR"
        exit 1
    }

    # Check if virtual environment exists
    if [ ! -d "$VENV_DIR" ]; then
        print_error "Virtual environment not found at $VENV_DIR"
        print_error "Please run ./scripts/setup.sh first"
        exit 1
    fi

    # Activate virtual environment
    source "$VENV_DIR/bin/activate" || {
        print_error "Failed to activate virtual environment"
        exit 1
    }

    # Set PYTHONPATH
    export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"

    # Check if config exists
    if [ ! -f "config/config.json" ]; then
        print_warning "config/config.json not found"
        print_info "Some operations may require configuration"
    fi
}

# Function to run Python script safely
run_python_safe() {
    local script="$1"
    shift
    local args="$@"
    
    python3 "scripts/$script" $args
    return $?
}

# Command: status
cmd_status() {
    print_header "Telegram Session Status"
    
    local quiet_mode=""
    if [ "$1" = "--quiet" ] || [ "$1" = "-q" ]; then
        quiet_mode="--quiet"
    fi
    
    run_python_safe "telegram_auth.py" --status $quiet_mode
    local exit_code=$?
    
    echo ""
    if [ $exit_code -eq 0 ]; then
        print_success "Session status retrieved successfully"
    elif [ $exit_code -eq 1 ]; then
        print_info "No session file found (expected for new setup)"
    else
        print_warning "Could not retrieve session status"
    fi
    
    return $exit_code
}

# Command: test
cmd_test() {
    print_header "Testing Session Validity"
    
    # First check session safety
    print_status "Checking session safety before testing..."
    if ! run_python_safe "check_session_safety.py" >/dev/null 2>&1; then
        print_error "Session safety check failed!"
        print_error "Workers may be active or session conflicts detected"
        print_info "Stop workers first: ./scripts/deploy_celery.sh stop"
        print_info "Or check status: ./scripts/telegram_session safety-check"
        return 1
    fi
    
    print_success "Session safety verified - safe to test"
    echo ""
    
    local quiet_mode=""
    if [ "$1" = "--quiet" ] || [ "$1" = "-q" ]; then
        quiet_mode="--quiet"
    fi
    
    run_python_safe "telegram_auth.py" --test $quiet_mode
    local exit_code=$?
    
    echo ""
    case $exit_code in
        0)
            print_success "Session is valid and working!"
            ;;
        1)
            print_warning "Session is invalid or expired"
            print_info "Consider renewal: ./scripts/telegram_session renew"
            ;;
        2)
            print_error "Session test failed due to safety restrictions"
            print_info "Check safety: ./scripts/telegram_session safety-check"
            ;;
        *)
            print_error "Session test encountered an error"
            print_info "Run diagnostics: ./scripts/telegram_session diagnostics"
            ;;
    esac
    
    return $exit_code
}

# Command: auth
cmd_auth() {
    print_header "Telegram Authentication"
    
    # Check if session already exists
    if [ -f "telegram_session.session" ]; then
        print_warning "Session file already exists"
        echo ""
        read -p "Do you want to create a new session? This will replace the existing one (y/N): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Authentication cancelled"
            return 0
        fi
        
        # Backup existing session
        print_status "Backing up existing session..."
        cmd_backup
    fi
    
    # CRITICAL: Clear any dangerous queued tasks before renewal
    print_status "Clearing potentially dangerous queued tasks..."
    local cleared_tasks=0
    for queue in "telegram_fetch" "telegram_processing"; do
        local count=$(redis-cli llen "$queue" 2>/dev/null || echo "0")
        if [ "$count" -gt 0 ]; then
            redis-cli del "$queue" >/dev/null 2>&1
            print_warning "Cleared $count queued tasks from $queue queue"
            cleared_tasks=$((cleared_tasks + count))
        fi
    done
    
    if [ $cleared_tasks -gt 0 ]; then
        print_warning "Cleared $cleared_tasks total queued tasks to prevent session conflicts"
    else
        print_success "No dangerous queued tasks found"
    fi
    
    # Check session safety
    print_status "Ensuring safe authentication environment..."
    if ! run_python_safe "check_session_safety.py" >/dev/null 2>&1; then
        print_error "Cannot authenticate - session conflicts detected!"
        print_error "Stop all workers before authentication"
        print_info "Run: ./scripts/deploy_celery.sh stop"
        return 1
    fi
    
    print_success "Environment is safe for authentication"
    echo ""
    
    run_python_safe "telegram_auth.py"
    local exit_code=$?
    
    echo ""
    if [ $exit_code -eq 0 ]; then
        print_success "Authentication completed successfully!"
        print_info "Session is ready for use"
    else
        print_error "Authentication failed"
        print_info "Check configuration and try again"
    fi
    
    return $exit_code
}

# Command: refresh  
cmd_refresh() {
    print_header "Session Refresh with Redis Cleanup"
    
    # Check if session exists
    if [ ! -f "telegram_session.session" ]; then
        print_error "No session file found"
        print_info "Use authentication instead: ./scripts/telegram_session auth"
        return 1
    fi
    
    # CRITICAL: Clear any dangerous queued tasks before refresh
    print_status "Clearing potentially dangerous queued tasks..."
    local cleared_tasks=0
    for queue in "telegram_fetch" "telegram_processing"; do
        local count=$(redis-cli llen "$queue" 2>/dev/null || echo "0")
        if [ "$count" -gt 0 ]; then
            redis-cli del "$queue" >/dev/null 2>&1
            print_warning "Cleared $count queued tasks from $queue queue"
            cleared_tasks=$((cleared_tasks + count))
        fi
    done
    
    if [ $cleared_tasks -gt 0 ]; then
        print_warning "Cleared $cleared_tasks total queued tasks to prevent session conflicts"
    else
        print_success "No dangerous queued tasks found"
    fi
    
    # Check session safety
    print_status "Checking session safety before refresh..."
    if ! run_python_safe "check_session_safety.py" >/dev/null 2>&1; then
        print_error "Cannot refresh - session conflicts detected!"
        print_error "Stop all workers before refresh"
        print_info "Run: ./scripts/deploy_celery.sh stop"
        return 1
    fi
    
    print_success "Environment is safe for refresh"
    echo ""
    
    run_python_safe "telegram_auth.py" --refresh
    local exit_code=$?
    
    echo ""
    if [ $exit_code -eq 0 ]; then
        print_success "Session refresh completed successfully!"
        print_info "Session validated and Redis caches cleared"
        
        # Clear any remaining dangerous tasks after refresh
        print_status "Final cleanup of any remaining queued tasks..."
        for queue in "telegram_fetch" "telegram_processing"; do
            redis-cli del "$queue" >/dev/null 2>&1
        done
        print_success "Queue cleanup completed"
    else
        print_error "Session refresh failed"
        print_info "Check session status: ./scripts/telegram_session status"
    fi
    
    return $exit_code
}

# Command: renew
cmd_renew() {
    print_header "Session Renewal (Safe Workflow)"
    
    # Check if session exists
    if [ ! -f "telegram_session.session" ]; then
        print_error "No session file found"
        print_info "Use authentication instead: ./scripts/telegram_session auth"
        return 1
    fi
    
    # CRITICAL: Clear any dangerous queued tasks before renewal
    print_status "Clearing potentially dangerous queued tasks..."
    local cleared_tasks=0
    for queue in "telegram_fetch" "telegram_processing"; do
        local count=$(redis-cli llen "$queue" 2>/dev/null || echo "0")
        if [ "$count" -gt 0 ]; then
            redis-cli del "$queue" >/dev/null 2>&1
            print_warning "Cleared $count queued tasks from $queue queue"
            cleared_tasks=$((cleared_tasks + count))
        fi
    done
    
    if [ $cleared_tasks -gt 0 ]; then
        print_warning "Cleared $cleared_tasks total queued tasks to prevent session conflicts"
    else
        print_success "No dangerous queued tasks found"
    fi
    
    # Check session safety
    print_status "Checking session safety before renewal..."
    if ! run_python_safe "check_session_safety.py" >/dev/null 2>&1; then
        print_error "Cannot renew - session conflicts detected!"
        print_error "Stop all workers before renewal"
        print_info "Run: ./scripts/deploy_celery.sh stop"
        return 1
    fi
    
    print_success "Environment is safe for renewal"
    echo ""
    
    run_python_safe "telegram_auth.py" --safe-renew
    local exit_code=$?
    
    echo ""
    if [ $exit_code -eq 0 ]; then
        print_success "Session renewal completed successfully!"
        print_info "Session is refreshed and ready for use"
        
        # Clear any remaining dangerous tasks after renewal
        print_status "Final cleanup of any remaining queued tasks..."
        for queue in "telegram_fetch" "telegram_processing"; do
            redis-cli del "$queue" >/dev/null 2>&1
        done
        print_success "Queue cleanup completed"
    else
        print_error "Session renewal failed"
        print_info "Check session status: ./scripts/telegram_session status"
    fi
    
    return $exit_code
}

# Command: backup
cmd_backup() {
    print_header "Session Backup"
    
    if [ ! -f "telegram_session.session" ]; then
        print_error "No session file found to backup"
        return 1
    fi
    
    run_python_safe "telegram_auth.py" --backup
    local exit_code=$?
    
    echo ""
    if [ $exit_code -eq 0 ]; then
        print_success "Session backup created successfully!"
    else
        print_error "Session backup failed"
    fi
    
    return $exit_code
}

# Command: restore
cmd_restore() {
    print_header "Session Restore"
    
    # List available backups
    print_status "Available session backups:"
    local backup_files=(telegram_session_backup_*.session)
    
    if [ ${#backup_files[@]} -eq 0 ] || [ ! -f "${backup_files[0]}" ]; then
        print_error "No backup files found"
        return 1
    fi
    
    echo ""
    local i=1
    for backup in "${backup_files[@]}"; do
        if [ -f "$backup" ]; then
            local backup_date=$(echo "$backup" | sed 's/telegram_session_backup_\(.*\)\.session/\1/')
            echo "$i) $backup (Date: $backup_date)"
            ((i++))
        fi
    done
    
    echo ""
    read -p "Select backup number to restore (or 0 to cancel): " backup_num
    
    if [ "$backup_num" = "0" ]; then
        print_info "Restore cancelled"
        return 0
    fi
    
    if [ "$backup_num" -lt 1 ] || [ "$backup_num" -ge $i ]; then
        print_error "Invalid backup number"
        return 1
    fi
    
    local selected_backup="${backup_files[$((backup_num-1))]}"
    
    # Check session safety
    print_status "Checking session safety before restore..."
    if ! run_python_safe "check_session_safety.py" >/dev/null 2>&1; then
        print_error "Cannot restore - session conflicts detected!"
        print_error "Stop all workers before restore"
        print_info "Run: ./scripts/deploy_celery.sh stop"
        return 1
    fi
    
    # Backup current session if it exists
    if [ -f "telegram_session.session" ]; then
        print_status "Backing up current session before restore..."
        cmd_backup
    fi
    
    # Restore the selected backup
    print_status "Restoring session from: $selected_backup"
    cp "$selected_backup" "telegram_session.session"
    
    if [ $? -eq 0 ]; then
        print_success "Session restored successfully!"
        print_info "Test the restored session: ./scripts/telegram_session test"
    else
        print_error "Session restore failed"
        return 1
    fi
    
    return 0
}

# Command: safety-check
cmd_safety_check() {
    print_header "Session Safety Check"
    
    run_python_safe "check_session_safety.py"
    local exit_code=$?
    
    echo ""
    case $exit_code in
        0)
            print_success "Session environment is SAFE"
            print_info "No conflicts detected - safe to perform session operations"
            ;;
        1)
            print_warning "Session safety issues detected"
            print_info "Check output above for details"
            ;;
        *)
            print_error "Safety check encountered an error"
            ;;
    esac
    
    return $exit_code
}

# Command: diagnostics
cmd_diagnostics() {
    print_header "Comprehensive Session Diagnostics"
    
    run_python_safe "telegram_session_check.py"
    local exit_code=$?

    if [ $exit_code -eq 0 ]; then
        print_success "Diagnostics completed successfully"
    else
        print_warning "Diagnostics completed with issues - see output above"
    fi
    return $exit_code
}

# Command: clear-queues
cmd_clear_queues() {
    print_header "Clear Dangerous Queued Tasks"
    
    print_status "Checking for dangerous queued tasks..."
    
    local total_cleared=0
    for queue in "telegram_fetch" "telegram_processing"; do
        local count=$(redis-cli llen "$queue" 2>/dev/null || echo "0")
        if [ "$count" -gt 0 ]; then
            print_warning "Found $count tasks in $queue queue"
            read -p "Clear these tasks? (y/N): " -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                redis-cli del "$queue" >/dev/null 2>&1
                print_success "Cleared $count tasks from $queue queue"
                total_cleared=$((total_cleared + count))
            else
                print_info "Skipped clearing $queue queue"
            fi
        else
            print_success "No tasks found in $queue queue"
        fi
    done
    
    if [ $total_cleared -gt 0 ]; then
        print_success "Cleared $total_cleared total dangerous tasks"
        print_info "These tasks could have caused session conflicts"
    else
        print_success "No dangerous tasks found - queues are clean"
    fi
    
    return 0
}

# Command: help
cmd_help() {
    print_header "Telegram Session Management Help"
    
    echo ""
    echo "USAGE:"
    echo "  ./scripts/telegram_session.sh <command> [options]"
    echo ""
    echo "COMMANDS:"
    echo ""
    echo "  🔍 INFORMATION & STATUS:"
    echo "    status [--quiet]     Show session status and age"
    echo "    test [--quiet]       Test if session is valid and working"
    echo "    safety-check         Check for session conflicts and safety"
    echo "    diagnostics          Run comprehensive session diagnostics"
    echo ""
    echo "  🔐 AUTHENTICATION & MANAGEMENT:"
    echo "    auth                 Authenticate new session (interactive)"
    echo "    refresh              Refresh session + clear Redis caches (safe, no deletion)"
    echo "    renew                Renew existing session (safe workflow)"
    echo ""
    echo "  💾 BACKUP & RESTORE:"
    echo "    backup               Create session backup"
    echo "    restore              Restore session from backup (interactive)"
    echo ""
    echo "  🧹 MAINTENANCE:"
    echo "    clear-queues         Clear dangerous queued tasks (interactive)"
    echo ""
    echo "  ❓ HELP:"
    echo "    help                 Show this help message"
    echo ""
    echo "EXAMPLES:"
    echo ""
    echo "  # Check session status"
    echo "  ./scripts/telegram_session.sh status"
    echo ""
    echo "  # Test if session works"
    echo "  ./scripts/telegram_session.sh test"
    echo ""
    echo "  # Authenticate new session"
    echo "  ./scripts/telegram_session.sh auth"
    echo ""
    echo "  # Refresh session and clear caches (safe, no deletion)"
    echo "  ./scripts/telegram_session.sh refresh"
    echo ""
    echo "  # Renew existing session safely"
    echo "  ./scripts/telegram_session.sh renew"
    echo ""
    echo "  # Check for session conflicts"
    echo "  ./scripts/telegram_session.sh safety-check"
    echo ""
    echo "  # Clear dangerous queued tasks"
    echo "  ./scripts/telegram_session.sh clear-queues"
    echo ""
    echo "  # Run full diagnostics"
    echo "  ./scripts/telegram_session.sh diagnostics"
    echo ""
    echo "SAFETY FEATURES:"
    echo ""
    echo "  ✅ Automatic session conflict detection"
    echo "  ✅ Worker safety checks before operations"
    echo "  ✅ Automatic session backup before changes"
    echo "  ✅ Safe renewal workflow to prevent logout"
    echo "  ✅ Session file locking protection"
    echo ""
    echo "IMPORTANT NOTES:"
    echo ""
    echo "  • Always stop workers before session operations:"
    echo "    ./scripts/deploy_celery.sh stop"
    echo ""
    echo "  • Check safety before manual session work:"
    echo "    ./scripts/telegram_session.sh safety-check"
    echo ""
    echo "  • Use 'renew' instead of 'auth' for existing sessions"
    echo ""
    echo "  • Keep session backups for emergency recovery"
    echo ""
}

# Main execution
main() {
    local command="$1"
    shift
    
    # Handle no command
    if [ -z "$command" ]; then
        cmd_help
        return 0
    fi
    
    # Check prerequisites for all commands except help
    if [ "$command" != "help" ]; then
        check_prerequisites
    fi
    
    # Execute command
    case "$command" in
        "status")
            cmd_status "$@"
            ;;
        "test")
            cmd_test "$@"
            ;;
        "auth"|"authenticate")
            cmd_auth "$@"
            ;;
        "renew")
            cmd_renew "$@"
            ;;
        "refresh")
            cmd_refresh "$@"
            ;;
        "backup")
            cmd_backup "$@"
            ;;
        "restore")
            cmd_restore "$@"
            ;;
        "safety-check"|"safety"|"check-safety")
            cmd_safety_check "$@"
            ;;
        "clear-queues"|"clear-queue"|"clearqueue")
            cmd_clear_queues "$@"
            ;;
        "diagnostics"|"diag"|"check")
            cmd_diagnostics "$@"
            ;;
        "help"|"--help"|"-h")
            cmd_help "$@"
            ;;
        *)
            print_error "Unknown command: $command"
            echo ""
            print_info "Available commands: status, test, auth, refresh, renew, backup, restore, safety-check, clear-queues, diagnostics, help"
            echo ""
            print_info "Use './scripts/telegram_session help' for detailed usage information"
            return 1
            ;;
    esac
    
    return $?
}

# Execute main function
main "$@"
exit $?