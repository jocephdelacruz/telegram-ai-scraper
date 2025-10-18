#!/bin/bash

# SharePoint Health Check Script
# Provides detailed SharePoint integration status and health monitoring

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"

cd "$PROJECT_DIR"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}=========================================="
    echo -e "SharePoint Integration Health Check"
    echo -e "==========================================${NC}"
}

print_section() {
    echo -e "\n${BLUE}$1${NC}"
    echo "$(printf '─%.0s' {1..40})"
}

print_status() {
    local status=$1
    local message=$2
    case $status in
        "OK")
            echo -e "✅ ${GREEN}$message${NC}"
            ;;
        "WARNING")
            echo -e "⚠️  ${YELLOW}$message${NC}"
            ;;
        "ERROR")
            echo -e "❌ ${RED}$message${NC}"
            ;;
        "INFO")
            echo -e "ℹ️  $message"
            ;;
    esac
}

print_header

# Check SharePoint log file existence
print_section "Log File Status"
if [ -f "$LOG_DIR/sharepoint.log" ]; then
    log_size=$(du -h "$LOG_DIR/sharepoint.log" | cut -f1)
    log_lines=$(wc -l < "$LOG_DIR/sharepoint.log")
    print_status "OK" "SharePoint log exists ($log_size, $log_lines lines)"
else
    print_status "ERROR" "SharePoint log file not found"
    exit 1
fi

# Check recent operations
print_section "Recent Operations"
if [ -f "$LOG_DIR/sharepoint.log" ]; then
    # Count successful operations in last hour
    current_time=$(date +%s)
    one_hour_ago=$(date -d '1 hour ago' '+%Y%m%d_%H')
    
    recent_ops=$(grep "SharePoint response: status=200" "$LOG_DIR/sharepoint.log" | tail -10)
    success_count=$(echo "$recent_ops" | wc -l)
    
    if [ "$success_count" -gt 0 ]; then
        print_status "OK" "Found $success_count recent successful operations"
        
        # Show last successful operation
        last_success=$(echo "$recent_ops" | tail -1)
        if [ -n "$last_success" ]; then
            timestamp=$(echo "$last_success" | cut -d']' -f1 | tr -d '[')
            operation=$(echo "$last_success" | grep -o 'worksheet=[^,]*' | cut -d'=' -f2)
            print_status "INFO" "Last success: $timestamp (worksheet: $operation)"
        fi
    else
        print_status "WARNING" "No recent successful operations found"
    fi
    
    # Check for recent errors
    recent_errors=$(grep -i "error\|failed\|exception" "$LOG_DIR/sharepoint.log" | tail -5)
    if [ -n "$recent_errors" ]; then
        error_count=$(echo "$recent_errors" | wc -l)
        print_status "WARNING" "Found $error_count recent errors"
        echo "$recent_errors" | while read -r line; do
            timestamp=$(echo "$line" | cut -d']' -f1 | tr -d '[')
            error_msg=$(echo "$line" | cut -d']' -f2- | sed 's/^[[:space:]]*//')
            print_status "INFO" "  $timestamp: ${error_msg:0:80}..."
        done
    else 
        print_status "OK" "No recent errors found"
    fi
fi

# Check Teams notifications for SharePoint issues
print_section "Teams Notifications"
if [ -f "$LOG_DIR/teams.log" ]; then
    sharepoint_alerts=$(grep "SharePointInitializationError" "$LOG_DIR/teams.log")
    if [ -n "$sharepoint_alerts" ]; then
        alert_count=$(echo "$sharepoint_alerts" | wc -l)
        last_alert=$(echo "$sharepoint_alerts" | tail -1)
        alert_time=$(echo "$last_alert" | cut -d']' -f1 | tr -d '[')
        print_status "WARNING" "Found $alert_count SharePoint crash alerts"
        print_status "INFO" "Last alert: $alert_time"
    else
        print_status "OK" "No SharePoint crash alerts found"
    fi
    
    # Check for recent admin notifications
    recent_admin=$(grep "admin message to Teams" "$LOG_DIR/teams.log" | tail -3)
    if [ -n "$recent_admin" ]; then
        admin_count=$(echo "$recent_admin" | wc -l)
        print_status "INFO" "Recent admin notifications: $admin_count"
    fi
else
    print_status "WARNING" "Teams log file not found"
fi

# Check Celery data services worker (handles SharePoint tasks)
print_section "Data Services Worker"
if [ -f "$PROJECT_DIR/pids/celery_data_services.pid" ]; then
    pid=$(cat "$PROJECT_DIR/pids/celery_data_services.pid")
    if ps -p $pid > /dev/null; then
        print_status "OK" "Data services worker is running (PID: $pid)"
        
        # Check recent task activity
        if [ -f "$LOG_DIR/celery_data_services.log" ]; then
            recent_tasks=$(grep "save_to_sharepoint" "$LOG_DIR/celery_data_services.log" | tail -5)
            if [ -n "$recent_tasks" ]; then
                task_count=$(echo "$recent_tasks" | wc -l)
                print_status "OK" "Recent SharePoint tasks: $task_count"
                
                # Check task success rate
                successful_tasks=$(echo "$recent_tasks" | grep "succeeded" | wc -l)
                failed_tasks=$(echo "$recent_tasks" | grep "failed" | wc -l)
                
                if [ "$failed_tasks" -gt 0 ]; then
                    print_status "WARNING" "Task failures detected: $failed_tasks failed, $successful_tasks succeeded"
                else
                    print_status "OK" "All recent tasks successful: $successful_tasks"
                fi
            else
                print_status "INFO" "No recent SharePoint tasks found"
            fi
        fi
    else
        print_status "ERROR" "Data services worker not running (stale PID)"
        rm -f "$PROJECT_DIR/pids/celery_data_services.pid"
    fi
else
    print_status "ERROR" "Data services worker not running (no PID file)"
fi

# Performance metrics
print_section "Performance Metrics"
if [ -f "$LOG_DIR/sharepoint.log" ]; then
    # Calculate average response times (if available)
    response_times=$(grep "SharePoint response: status=200" "$LOG_DIR/sharepoint.log" | tail -10)
    if [ -n "$response_times" ]; then
        print_status "OK" "Analyzing recent response times..."
        
        # Simple performance check - look for timeout patterns
        timeout_errors=$(grep -i "timeout" "$LOG_DIR/sharepoint.log" | tail -3)
        if [ -n "$timeout_errors" ]; then
            timeout_count=$(echo "$timeout_errors" | wc -l)
            print_status "WARNING" "Recent timeout errors: $timeout_count"
        else
            print_status "OK" "No recent timeout issues"
        fi
        
        # Check for authentication issues
        auth_errors=$(grep -i "auth\|401\|403" "$LOG_DIR/sharepoint.log" | tail -3)
        if [ -n "$auth_errors" ]; then
            auth_count=$(echo "$auth_errors" | wc -l)
            print_status "WARNING" "Recent authentication issues: $auth_count"
        else
            print_status "OK" "No recent authentication issues"
        fi
    fi
fi

# Configuration check
print_section "Configuration"
if [ -f "$PROJECT_DIR/config/config.json" ]; then
    # Check if SharePoint config exists
    sharepoint_config=$(python3 -c "
import json
try:
    with open('config/config.json') as f:
        config = json.load(f)
    sp_config = config.get('MS_SHAREPOINT_ACCESS', {})
    if sp_config:
        print('SharePoint configuration found')
        required_fields = ['CLIENT_ID', 'CLIENT_SECRET', 'TENANT_ID', 'SITE_URL']
        missing = [f for f in required_fields if not sp_config.get(f)]
        if missing:
            print(f'Missing fields: {missing}')
        else:
            print('All required fields present')
    else:
        print('No SharePoint configuration found')
except Exception as e:
    print(f'Error reading config: {e}')
" 2>/dev/null)
    
    if echo "$sharepoint_config" | grep -q "All required fields present"; then
        print_status "OK" "SharePoint configuration is complete"
    elif echo "$sharepoint_config" | grep -q "Missing fields"; then
        missing_fields=$(echo "$sharepoint_config" | grep "Missing fields" | cut -d':' -f2)
        print_status "ERROR" "Missing SharePoint config fields:$missing_fields"
    else
        print_status "ERROR" "SharePoint configuration not found or invalid"
    fi
else
    print_status "ERROR" "Configuration file not found"
fi

# Recommendations
print_section "Recommendations"
if [ -f "$LOG_DIR/sharepoint.log" ]; then
    # Check log age
    log_age=$(find "$LOG_DIR/sharepoint.log" -mtime +1 | wc -l)
    if [ "$log_age" -gt 0 ]; then
        print_status "WARNING" "SharePoint log is older than 1 day - system may not be active"
        echo "  💡 Check if workers are running: ./scripts/status.sh"
    fi
    
    # Check log size
    log_size_mb=$(du -m "$LOG_DIR/sharepoint.log" | cut -f1)
    if [ "$log_size_mb" -gt 100 ]; then
        print_status "WARNING" "SharePoint log is large (${log_size_mb}MB) - consider rotation"
        echo "  💡 Rotate logs: logrotate or manual cleanup"
    fi
    
    # Generic recommendations
    echo ""
    echo "📋 Maintenance Tips:"
    echo "   • Monitor SharePoint operations: tail -f logs/sharepoint.log"
    echo "   • Test connectivity regularly: ./scripts/run_tests.sh --sharepoint"
    echo "   • Check for alerts: grep 'SharePointInitializationError' logs/teams.log"
    echo "   • Restart if needed: ./scripts/deploy_celery.sh restart data_services"
    echo ""
    echo "🔍 Troubleshooting Commands:"
    echo "   • View detailed log: tail -50 logs/sharepoint.log"  
    echo "   • Monitor real-time: tail -f logs/sharepoint.log | grep -E 'status=|error|failed'"
    echo "   • Check task queue: celery -A src.tasks.telegram_celery_tasks inspect reserved"
    echo "   • Full diagnostics: see docs/SHAREPOINT_RELIABILITY_GUIDE.md"
fi

print_section "Health Check Complete"
echo "For detailed troubleshooting, see: docs/SHAREPOINT_RELIABILITY_GUIDE.md"