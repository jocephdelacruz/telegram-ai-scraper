#!/bin/bash

# Log Entry Cleanup Script for Telegram AI Scraper
# Removes log entries older than 4 days from all log files
# Keeps the log files themselves, only removes old entries

# Configuration
LOGS_DIR="/home/ubuntu/TelegramScraper/telegram-ai-scraper/logs"
DAYS_TO_KEEP=4
TEMP_DIR="/tmp/log_cleanup_$$"
SCRIPT_LOG="$LOGS_DIR/cleanup_log_entries.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log_message() {
    local message="$1"
    local timestamp=$(date '+%Y%m%d_%H:%M:%S')
    echo -e "[$timestamp]: $message" | tee -a "$SCRIPT_LOG"
}

# Function to check if a line has a valid timestamp
has_valid_timestamp() {
    local line="$1"
    # Check if line starts with [YYYYMMDD_HH:MM:SS]
    if [[ $line =~ ^\[20[0-9]{6}_[0-9]{2}:[0-9]{2}:[0-9]{2}\]: ]]; then
        return 0
    else
        return 1
    fi
}

# Function to extract timestamp from log line
extract_timestamp() {
    local line="$1"
    # Extract timestamp from [YYYYMMDD_HH:MM:SS] format
    if [[ $line =~ ^\[([0-9]{8}_[0-9]{2}:[0-9]{2}:[0-9]{2})\]: ]]; then
        echo "${BASH_REMATCH[1]}"
    fi
}

# Function to convert timestamp to epoch
timestamp_to_epoch() {
    local timestamp="$1"
    # Convert from YYYYMMDD_HH:MM:SS to YYYY-MM-DD HH:MM:SS
    local formatted_date="${timestamp:0:4}-${timestamp:4:2}-${timestamp:6:2} ${timestamp:9}"
    date -d "$formatted_date" +%s 2>/dev/null
}

# Function to clean a single log file
clean_log_file() {
    local log_file="$1"
    local temp_file="$TEMP_DIR/$(basename "$log_file")"
    local cutoff_epoch=$(date -d "$DAYS_TO_KEEP days ago" +%s)
    local original_lines=0
    local kept_lines=0
    local removed_lines=0
    
    # Skip if file doesn't exist or is empty
    if [[ ! -f "$log_file" ]] || [[ ! -s "$log_file" ]]; then
        return 0
    fi
    
    original_lines=$(wc -l < "$log_file")
    
    # Process the log file line by line
    while IFS= read -r line || [[ -n "$line" ]]; do
        if has_valid_timestamp "$line"; then
            local timestamp=$(extract_timestamp "$line")
            local line_epoch=$(timestamp_to_epoch "$timestamp")
            
            # Keep line if timestamp is valid and within retention period
            if [[ -n "$line_epoch" ]] && [[ $line_epoch -gt $cutoff_epoch ]]; then
                echo "$line" >> "$temp_file"
                ((kept_lines++))
            else
                ((removed_lines++))
            fi
        else
            # Keep lines without timestamps (might be multi-line entries or stack traces)
            # But only if the previous line was kept (to maintain context)
            if [[ -f "$temp_file" ]] && [[ $(tail -n 1 "$temp_file" 2>/dev/null | wc -l) -gt 0 ]]; then
                echo "$line" >> "$temp_file"
                ((kept_lines++))
            else
                ((removed_lines++))
            fi
        fi
    done < "$log_file"
    
    # Replace original file with cleaned version if temp file exists and has content
    if [[ -f "$temp_file" ]] && [[ -s "$temp_file" ]]; then
        mv "$temp_file" "$log_file"
        log_message "${GREEN}✅ Cleaned $(basename "$log_file"): ${original_lines} → ${kept_lines} lines (removed ${removed_lines})${NC}"
    elif [[ -f "$temp_file" ]]; then
        # Temp file exists but is empty - all entries were old
        mv "$temp_file" "$log_file"
        log_message "${YELLOW}⚠️  All entries removed from $(basename "$log_file") (${original_lines} lines removed)${NC}"
    else
        log_message "${BLUE}ℹ️  No changes needed for $(basename "$log_file")${NC}"
    fi
}

# Main execution
main() {
    log_message "${BLUE}🧹 Starting log cleanup - removing entries older than ${DAYS_TO_KEEP} days${NC}"
    
    # Create temporary directory
    mkdir -p "$TEMP_DIR"
    
    # Cleanup trap
    trap "rm -rf '$TEMP_DIR'" EXIT
    
    # Get cutoff date for logging
    local cutoff_date=$(date -d "$DAYS_TO_KEEP days ago" '+%Y-%m-%d %H:%M:%S')
    log_message "Cutoff date: $cutoff_date"
    
    # Counter for statistics
    local total_files=0
    local processed_files=0
    
    # Process all .log files in the logs directory
    for log_file in "$LOGS_DIR"/*.log; do
        # Skip the cleanup script's own log file to prevent self-modification during execution
        if [[ "$(basename "$log_file")" == "cleanup_log_entries.log" ]]; then
            continue
        fi
        
        if [[ -f "$log_file" ]]; then
            ((total_files++))
            clean_log_file "$log_file"
            ((processed_files++))
        fi
    done
    
    log_message "${GREEN}✅ Cleanup completed: processed ${processed_files}/${total_files} log files${NC}"
    
    # Clean up temp directory
    rm -rf "$TEMP_DIR"
}

# Check if running as script (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Ensure we're in the right directory
    cd "$(dirname "$0")" || exit 1
    
    # Run main function
    main "$@"
fi