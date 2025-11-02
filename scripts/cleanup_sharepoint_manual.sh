#!/bin/bash

# Manual SharePoint Cleanup Script for Telegram AI Scraper
# Allows manual execution of SharePoint cleanup with configurable retention period
# This script runs independently of the scheduled cleanup and allows custom retention settings

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PATH="../telegram-ai-scraper_env"

# Default retention period (can be overridden via command line)
DEFAULT_RETENTION_DAYS=3

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to display usage
show_usage() {
    echo "Manual SharePoint Cleanup Script"
    echo "================================"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -d, --days DAYS     Number of days to keep entries (default: $DEFAULT_RETENTION_DAYS)"
    echo "  -h, --help          Show this help message"
    echo "  --dry-run           Show what would be deleted without actually deleting"
    echo ""
    echo "Examples:"
    echo "  $0                    # Clean entries older than $DEFAULT_RETENTION_DAYS days"
    echo "  $0 -d 5              # Clean entries older than 5 days"
    echo "  $0 --days 10         # Clean entries older than 10 days"
    echo "  $0 --dry-run -d 3    # Show what would be deleted (3 days retention)"
    echo ""
}

# Function to log messages
log_message() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "[$timestamp] $message"
}

# Function to run SharePoint cleanup
run_sharepoint_cleanup() {
    local retention_days="$1"
    local dry_run="$2"
    
    log_message "${BLUE}🧹 Starting manual SharePoint cleanup${NC}"
    log_message "${BLUE}📅 Retention period: ${retention_days} days${NC}"
    
    if [ "$dry_run" = "true" ]; then
        log_message "${YELLOW}🔍 DRY RUN MODE - No actual deletion will occur${NC}"
    fi
    
    # Change to project directory
    cd "$PROJECT_DIR" || {
        log_message "${RED}❌ Failed to change to project directory: $PROJECT_DIR${NC}"
        exit 1
    }
    
    # Activate virtual environment
    if [ -f "$VENV_PATH/bin/activate" ]; then
        source "$VENV_PATH/bin/activate"
        log_message "${GREEN}✓ Virtual environment activated${NC}"
    else
        log_message "${RED}❌ Virtual environment not found at: $VENV_PATH${NC}"
        exit 1
    fi
    
    # Create Python script to run cleanup
    local python_script="/tmp/sharepoint_cleanup_manual_$$.py"
    cat > "$python_script" << EOF
#!/usr/bin/env python3

import sys
import os

# Add project root to Python path
project_root = os.path.abspath('.')
sys.path.insert(0, project_root)

try:
    from src.tasks.sharepoint_cleanup import cleanup_old_sharepoint_entries
    import json
    from datetime import datetime, timedelta
    
    # Run SharePoint cleanup with specified retention days
    retention_days = int(sys.argv[1]) if len(sys.argv) > 1 else $DEFAULT_RETENTION_DAYS
    dry_run = len(sys.argv) > 2 and sys.argv[2] == 'true'
    
    if dry_run:
        print(f"🔍 DRY RUN: Would clean SharePoint entries older than {retention_days} days")
        cutoff_date = (datetime.now() - timedelta(days=retention_days)).strftime('%Y-%m-%d')
        print(f"🔍 DRY RUN: Cutoff date would be: {cutoff_date}")
        print(f"🔍 DRY RUN: Use this script without --dry-run to perform actual cleanup")
        result = {"status": "dry_run", "message": "Dry run completed - no changes made"}
    else:
        print(f"🧹 Running SharePoint cleanup with {retention_days} days retention...")
        result = cleanup_old_sharepoint_entries(days_to_keep=retention_days)
    
    # Display results
    status = result.get('status', 'unknown')
    if status == 'success':
        processed = result.get('processed_files', 0)
        deleted = result.get('total_deleted', 0)
        print(f"✅ SharePoint cleanup completed successfully!")
        print(f"📊 Files processed: {processed}")
        print(f"🗑️  Entries deleted: {deleted}")
        print(f"📅 Cutoff date: {result.get('cutoff_date', 'unknown')}")
    elif status == 'partial_success':
        processed = result.get('processed_files', 0)
        deleted = result.get('total_deleted', 0)
        errors = result.get('errors', [])
        print(f"⚠️  SharePoint cleanup completed with some errors:")
        print(f"📊 Files processed: {processed}")
        print(f"🗑️  Entries deleted: {deleted}")
        print(f"❌ Errors: {len(errors)}")
        for error in errors:
            print(f"   - {error}")
    elif status == 'dry_run':
        print(f"🔍 {result.get('message', 'Dry run completed')}")
    else:
        print(f"❌ SharePoint cleanup failed: {result.get('message', 'Unknown error')}")
        sys.exit(1)

except ImportError as e:
    print(f"❌ Import error: {e}")
    print("💡 Make sure you're running this from the project root directory")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error during SharePoint cleanup: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF
    
    # Run the cleanup
    if python3 "$python_script" "$retention_days" "$dry_run"; then
        log_message "${GREEN}✅ SharePoint cleanup completed successfully${NC}"
        cleanup_exit_code=0
    else
        log_message "${RED}❌ SharePoint cleanup failed${NC}"
        cleanup_exit_code=1
    fi
    
    # Cleanup temp script
    rm -f "$python_script"
    
    # Deactivate virtual environment
    deactivate 2>/dev/null || true
    
    return $cleanup_exit_code
}

# Main execution
main() {
    local retention_days="$DEFAULT_RETENTION_DAYS"
    local dry_run="false"
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -d|--days)
                retention_days="$2"
                if ! [[ "$retention_days" =~ ^[0-9]+$ ]] || [ "$retention_days" -lt 1 ]; then
                    log_message "${RED}❌ Invalid retention days: $retention_days. Must be a positive integer.${NC}"
                    exit 1
                fi
                shift 2
                ;;
            --dry-run)
                dry_run="true"
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                log_message "${RED}❌ Unknown option: $1${NC}"
                show_usage
                exit 1
                ;;
        esac
    done
    
    # Validate retention days
    if ! [[ "$retention_days" =~ ^[0-9]+$ ]] || [ "$retention_days" -lt 1 ]; then
        log_message "${RED}❌ Invalid retention days: $retention_days. Must be a positive integer.${NC}"
        exit 1
    fi
    
    # Check if project directory exists
    if [ ! -d "$PROJECT_DIR" ]; then
        log_message "${RED}❌ Project directory not found: $PROJECT_DIR${NC}"
        exit 1
    fi
    
    # Check if virtual environment exists
    if [ ! -f "$VENV_PATH/bin/activate" ]; then
        log_message "${RED}❌ Virtual environment not found. Please run setup.sh first.${NC}"
        exit 1
    fi
    
    # Run the cleanup
    if run_sharepoint_cleanup "$retention_days" "$dry_run"; then
        log_message "${GREEN}🎉 Manual SharePoint cleanup completed successfully!${NC}"
        exit 0
    else
        log_message "${RED}💥 Manual SharePoint cleanup failed!${NC}"
        exit 1
    fi
}

# Check if running as script (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi