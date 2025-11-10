#!/bin/bash

# Log Entry Cleanup Script for Telegram AI Scraper
# Removes log entries older than 4 days from all log files
# Keeps the log files themselves, only removes old entries

# Configuration
LOGS_DIR="/home/ubuntu/TelegramScraper/telegram-ai-scraper/logs"
DAYS_TO_KEEP=3
TEMP_DIR="/tmp/log_cleanup_$$"
SCRIPT_LOG="$LOGS_DIR/cleanup_log_entries.log"
EARLY_TERMINATION_THRESHOLD=5

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

# Function to check if a line has a valid timestamp (supports both LogHandling and Celery formats)
has_valid_timestamp() {
    local line="$1"
    # Check if line starts with [YYYYMMDD_HH:MM:SS]: (LogHandling format)
    if [[ $line =~ ^\[20[0-9]{6}_[0-9]{2}:[0-9]{2}:[0-9]{2}\]: ]]; then
        return 0
    # Check if line starts with [YYYY-MM-DD HH:MM:SS,ms: LEVEL/Process] (Celery format)
    elif [[ $line =~ ^\[20[0-9]{2}-[0-9]{2}-[0-9]{2}\ [0-9]{2}:[0-9]{2}:[0-9]{2},[0-9]{3}:\ [A-Z]+/[^]]+\] ]]; then
        return 0
    else
        return 1
    fi
}

# Function to extract timestamp from log line (supports both formats)
extract_timestamp() {
    local line="$1"
    # Extract timestamp from [YYYYMMDD_HH:MM:SS]: format (LogHandling)
    if [[ $line =~ ^\[([0-9]{8}_[0-9]{2}:[0-9]{2}:[0-9]{2})\]: ]]; then
        echo "${BASH_REMATCH[1]}"
    # Extract timestamp from [YYYY-MM-DD HH:MM:SS,ms: format (Celery)
    elif [[ $line =~ ^\[([0-9]{4}-[0-9]{2}-[0-9]{2}\ [0-9]{2}:[0-9]{2}:[0-9]{2}),[0-9]{3}: ]]; then
        # Convert Celery format to LogHandling format: 2025-11-07 04:01:39 -> 20251107_04:01:39
        local celery_timestamp="${BASH_REMATCH[1]}"
        local converted_timestamp="${celery_timestamp:0:4}${celery_timestamp:5:2}${celery_timestamp:8:2}_${celery_timestamp:11:8}"
        echo "$converted_timestamp"
    fi
}

# Function to convert timestamp to epoch
timestamp_to_epoch() {
    local timestamp="$1"
    # Convert from YYYYMMDD_HH:MM:SS to YYYY-MM-DD HH:MM:SS
    local formatted_date="${timestamp:0:4}-${timestamp:4:2}-${timestamp:6:2} ${timestamp:9}"
    date -d "$formatted_date" +%s 2>/dev/null
}

# Function to clean a single log file with atomic operations
clean_log_file() {
    local log_file="$1"
    local temp_file="$TEMP_DIR/$(basename "$log_file")"
    local lock_file="${log_file}.cleanup_lock"
    # Calculate cutoff in Manila timezone (UTC+8) to match log timestamps
    # Calculate cutoff at midnight (00:00) of the cutoff date in Manila timezone
    local cutoff_date_only=$(TZ='Asia/Manila' date -d "$DAYS_TO_KEEP days ago" '+%Y-%m-%d')
    local cutoff_epoch=$(TZ='Asia/Manila' date -d "$cutoff_date_only 00:00:00" +%s)
    # Also expose a human-friendly cutoff date for logging/debug
    local cutoff_date_human="$cutoff_date_only 00:00:00 Manila"
    local original_lines=0
    local kept_lines=0
    local removed_lines=0
    
    # Skip if file doesn't exist or is empty
    if [[ ! -f "$log_file" ]] || [[ ! -s "$log_file" ]]; then
        return 0
    fi
    
    # Attempt to acquire lock with timeout (prevent concurrent access)
    local lock_timeout=30
    local lock_acquired=false
    
    for ((i=0; i<lock_timeout; i++)); do
        if (set -C; echo $$ > "$lock_file") 2>/dev/null; then
            lock_acquired=true
            break
        fi
        sleep 1
    done
    
    if [[ "$lock_acquired" != true ]]; then
        log_message "${YELLOW}⚠️  Could not acquire lock for $(basename "$log_file") after ${lock_timeout}s, skipping${NC}"
        return 1
    fi
    
    # Ensure lock is released on exit
    trap "rm -f '$lock_file'" EXIT
    
    original_lines=$(wc -l < "$log_file")
    
    # Early termination optimization variables
    local consecutive_new_entries=0
    local early_terminated=false
    
    # Process the log file line by line
    while IFS= read -r line || [[ -n "$line" ]]; do
        if has_valid_timestamp "$line"; then
            local timestamp=$(extract_timestamp "$line")

            # timestamp format is expected to be YYYYMMDD_HH:MM:SS
            # Extract date and time parts explicitly to avoid fragile slicing
            local entry_date_part="${timestamp:0:8}"
            local entry_time_part="${timestamp:9}"
            local entry_date_formatted="${entry_date_part:0:4}-${entry_date_part:4:2}-${entry_date_part:6:2}"

            # Convert to epoch using Manila timezone to match log timestamp format
            local line_epoch=0
            if line_epoch=$(TZ='Asia/Manila' date -d "${entry_date_formatted} ${entry_time_part}" +%s 2>/dev/null); then
                # Keep line if timestamp is valid and within retention period
                if [[ -n "$line_epoch" ]] && [[ $line_epoch -gt $cutoff_epoch ]]; then
                    echo "$line" >> "$temp_file"
                    ((kept_lines++))
                    
                    # Increment consecutive new entries counter for early termination
                    ((consecutive_new_entries++))
                    
                    # Early termination: if we've seen enough consecutive new entries,
                    # assume the rest of the file is also new (chronological order)
                    if [[ $consecutive_new_entries -ge $EARLY_TERMINATION_THRESHOLD ]]; then
                        early_terminated=true
                        # Copy the rest of the file without processing each line
                        while IFS= read -r remaining_line || [[ -n "$remaining_line" ]]; do
                            echo "$remaining_line" >> "$temp_file"
                            ((kept_lines++))
                        done
                        break
                    fi
                else
                    ((removed_lines++))
                    # Reset consecutive counter when we find an old entry
                    consecutive_new_entries=0
                fi
            else
                # If we cannot parse the date/time properly, treat it as malformed and keep it
                # to avoid accidental data loss
                echo "$line" >> "$temp_file"
                ((kept_lines++))
                # Don't count malformed timestamps toward consecutive new entries
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
            # Don't count non-timestamp lines toward consecutive new entries
        fi
    done < "$log_file"
    
    # Atomically replace original file with cleaned version
    if [[ -f "$temp_file" ]] && [[ -s "$temp_file" ]]; then
        if mv "$temp_file" "$log_file"; then
            local termination_msg=""
            if [[ "$early_terminated" == true ]]; then
                termination_msg=" [fast-forward after ${EARLY_TERMINATION_THRESHOLD} consecutive new entries]"
            fi
            log_message "${GREEN}✅ Cleaned $(basename "$log_file"): ${original_lines} → ${kept_lines} lines (removed ${removed_lines})${termination_msg}${NC}"
        else
            log_message "${RED}❌ Failed to update $(basename "$log_file")${NC}"
            rm -f "$temp_file"
        fi
    elif [[ -f "$temp_file" ]]; then
        # Temp file exists but is empty - all entries were old
        if mv "$temp_file" "$log_file"; then
            log_message "${YELLOW}⚠️  All entries removed from $(basename "$log_file") (${original_lines} lines removed)${NC}"
        else
            log_message "${RED}❌ Failed to update $(basename "$log_file")${NC}"
            rm -f "$temp_file"
        fi
    else
        log_message "${BLUE}ℹ️  No changes needed for $(basename "$log_file")${NC}"
    fi
    
    # Release lock
    rm -f "$lock_file"
}

# Main execution
main() {
    log_message "${BLUE}🧹 Starting log cleanup - removing entries older than ${DAYS_TO_KEEP} days${NC}"
    DAYS_TO_KEEP=$((DAYS_TO_KEEP - 1))      # Adjust to keep logs similar to csv cleanup
    # Create temporary directory
    mkdir -p "$TEMP_DIR"
    
    # Cleanup trap (also clean up any stale locks)
    trap "rm -rf '$TEMP_DIR'; find '$LOGS_DIR' -name '*.cleanup_lock' -mmin +60 -delete 2>/dev/null" EXIT
    
    # Get cutoff date for logging (midnight of the cutoff date in Manila timezone)
    local cutoff_date_only=$(TZ='Asia/Manila' date -d "$DAYS_TO_KEEP days ago" '+%Y-%m-%d')
    log_message "Cutoff date: $cutoff_date_only 00:00:00 Manila (entries before this will be deleted)"
    
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
    
    # Clean up temp directory and any stale locks
    rm -rf "$TEMP_DIR"
    find "$LOGS_DIR" -name "*.cleanup_lock" -mmin +60 -delete 2>/dev/null || true
}

# Check if running as script (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Ensure we're in the right directory
    cd "$(dirname "$0")" || exit 1
    
    # Run main function
    main "$@"
fi