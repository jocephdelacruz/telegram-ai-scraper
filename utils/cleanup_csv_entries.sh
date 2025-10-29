#!/bin/bash

# CSV Entry Cleanup Script for Telegram AI Scraper
# Removes CSV entries older than specified days from all CSV files in data folder
# Uses atomic operations to prevent conflicts with concurrent CSV writes
# Keeps the CSV files themselves, only removes old entries

# Configuration
DATA_DIR="/home/ubuntu/TelegramScraper/telegram-ai-scraper/data"
LOGS_DIR="/home/ubuntu/TelegramScraper/telegram-ai-scraper/logs"
DAYS_TO_KEEP=3  # Keep CSV entries for 3 days by default
TEMP_DIR="/tmp/csv_cleanup_$$"
SCRIPT_LOG="$LOGS_DIR/cleanup_csv_entries.log"

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

# Function to check if a CSV line has a valid date in the Date field
has_valid_date() {
    local csv_line="$1"
    local date_field_index="$2"
    
    # Extract the date field using awk (handles CSV properly)
    local date_value=$(echo "$csv_line" | awk -F',' -v col="$date_field_index" '{print $col}' | tr -d '"')
    
    # Check if date matches YYYY-MM-DD format
    if [[ $date_value =~ ^20[0-9]{2}-[0-1][0-9]-[0-3][0-9]$ ]]; then
        return 0
    else
        return 1
    fi
}

# Function to extract date from CSV line
extract_date() {
    local csv_line="$1"
    local date_field_index="$2"
    
    # Extract the date field using awk
    local date_value=$(echo "$csv_line" | awk -F',' -v col="$date_field_index" '{print $col}' | tr -d '"')
    echo "$date_value"
}

# Function to convert date to epoch
date_to_epoch() {
    local date_str="$1"
    date -d "$date_str" +%s 2>/dev/null
}

# Function to find the Date field index in CSV header
find_date_field_index() {
    local header_line="$1"
    local index=1
    
    # Split header by comma and find 'Date' field
    IFS=',' read -ra FIELDS <<< "$header_line"
    for field in "${FIELDS[@]}"; do
        # Remove quotes and whitespace
        field=$(echo "$field" | tr -d '"' | xargs)
        if [[ "$field" == "Date" ]]; then
            echo "$index"
            return 0
        fi
        ((index++))
    done
    
    echo "0"  # Return 0 if Date field not found
}

# Function to clean a single CSV file with atomic operations
clean_csv_file() {
    local csv_file="$1"
    local temp_file="$TEMP_DIR/$(basename "$csv_file")"
    local lock_file="${csv_file}.cleanup_lock"
    local cutoff_epoch=$(date -d "$DAYS_TO_KEEP days ago" +%s)
    local original_lines=0
    local kept_lines=0
    local removed_lines=0
    local date_field_index=0
    
    # Skip if file doesn't exist or is empty
    if [[ ! -f "$csv_file" ]] || [[ ! -s "$csv_file" ]]; then
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
        log_message "${YELLOW}⚠️  Could not acquire lock for $(basename "$csv_file") after ${lock_timeout}s, skipping${NC}"
        return 1
    fi
    
    # Ensure lock is released on exit
    trap "rm -f '$lock_file'" EXIT
    
    original_lines=$(wc -l < "$csv_file")
    
    # Read the header first to find Date field index
    local header_line=$(head -n 1 "$csv_file")
    date_field_index=$(find_date_field_index "$header_line")
    
    if [[ $date_field_index -eq 0 ]]; then
        log_message "${YELLOW}⚠️  No 'Date' field found in $(basename "$csv_file"), skipping${NC}"
        rm -f "$lock_file"
        return 1
    fi
    
    log_message "Processing $(basename "$csv_file") - Date field at index $date_field_index"
    
    local line_number=0
    
    # Process the CSV file line by line
    while IFS= read -r line || [[ -n "$line" ]]; do
        ((line_number++))
        
        # Always keep the header line
        if [[ $line_number -eq 1 ]]; then
            echo "$line" >> "$temp_file"
            ((kept_lines++))
            continue
        fi
        
        # Skip empty lines
        if [[ -z "$line" ]]; then
            continue
        fi
        
        if has_valid_date "$line" "$date_field_index"; then
            local date_value=$(extract_date "$line" "$date_field_index")
            local line_epoch=$(date_to_epoch "$date_value")
            
            # Keep line if date is valid and within retention period
            if [[ -n "$line_epoch" ]] && [[ $line_epoch -gt $cutoff_epoch ]]; then
                echo "$line" >> "$temp_file"
                ((kept_lines++))
            else
                ((removed_lines++))
            fi
        else
            # Keep lines with invalid dates (might be malformed but important data)
            echo "$line" >> "$temp_file"
            ((kept_lines++))
        fi
    done < "$csv_file"
    
    # Atomically replace original file with cleaned version
    if [[ -f "$temp_file" ]]; then
        # Use mv for atomic operation (same filesystem)
        if mv "$temp_file" "$csv_file"; then
            if [[ $removed_lines -gt 0 ]]; then
                log_message "${GREEN}✅ Cleaned $(basename "$csv_file"): ${original_lines} → ${kept_lines} lines (removed ${removed_lines})${NC}"
            else
                log_message "${BLUE}ℹ️  No old entries to remove from $(basename "$csv_file")${NC}"
            fi
        else
            log_message "${RED}❌ Failed to update $(basename "$csv_file")${NC}"
            rm -f "$temp_file"
        fi
    else
        log_message "${RED}❌ Failed to create temp file for $(basename "$csv_file")${NC}"
    fi
    
    # Release lock
    rm -f "$lock_file"
}

# Main execution
main() {
    log_message "${BLUE}🧹 Starting CSV cleanup - removing entries older than ${DAYS_TO_KEEP} days${NC}"
    
    # Create temporary directory
    mkdir -p "$TEMP_DIR"
    
    # Cleanup trap
    trap "rm -rf '$TEMP_DIR'; find '$DATA_DIR' -name '*.cleanup_lock' -mmin +60 -delete 2>/dev/null" EXIT
    
    # Get cutoff date for logging
    local cutoff_date=$(date -d "$DAYS_TO_KEEP days ago" '+%Y-%m-%d')
    log_message "Cutoff date: $cutoff_date (entries before this date will be removed)"
    
    # Counter for statistics
    local total_files=0
    local processed_files=0
    local failed_files=0
    
    # Process all .csv files in the data directory
    for csv_file in "$DATA_DIR"/*.csv; do
        if [[ -f "$csv_file" ]]; then
            ((total_files++))
            if clean_csv_file "$csv_file"; then
                ((processed_files++))
            else
                ((failed_files++))
            fi
        fi
    done
    
    if [[ $total_files -eq 0 ]]; then
        log_message "${YELLOW}⚠️  No CSV files found in $DATA_DIR${NC}"
    else
        log_message "${GREEN}✅ CSV cleanup completed: processed ${processed_files}/${total_files} files (${failed_files} failed)${NC}"
    fi
    
    # Clean up temp directory and any stale locks
    rm -rf "$TEMP_DIR"
    find "$DATA_DIR" -name "*.cleanup_lock" -mmin +60 -delete 2>/dev/null || true
}

# Check if running as script (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Ensure we're in the right directory
    cd "$(dirname "$0")" || exit 1
    
    # Ensure logs directory exists
    mkdir -p "$LOGS_DIR"
    
    # Run main function
    main "$@"
fi