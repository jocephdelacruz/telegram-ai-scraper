#!/bin/bash

# System Resource Monitor for Telegram AI Scraper
# This script helps monitor system resources to prevent crashes

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_DIR="/home/ubuntu/TelegramScraper/telegram-ai-scraper"
PID_DIR="$PROJECT_DIR/pids"

print_header() {
    echo -e "${BLUE}=================================${NC}"
    echo -e "${BLUE} System Resource Monitor${NC}"
    echo -e "${BLUE} $(date)${NC}"
    echo -e "${BLUE}=================================${NC}"
}

check_memory() {
    echo -e "\n${YELLOW}Memory Usage:${NC}"
    free -h
    
    # Get memory percentage
    mem_usage=$(free | awk 'NR==2{printf "%.1f", $3*100/$2}')
    swap_usage=$(free | awk 'NR==3{if($2>0) printf "%.1f", $3*100/$2; else print "0.0"}')
    
    echo -e "\nMemory: ${mem_usage}% used"
    echo -e "Swap: ${swap_usage}% used"
    
    # Warn if high memory usage
    if (( $(echo "$mem_usage > 80" | bc -l) )); then
        echo -e "${RED}⚠️  WARNING: High memory usage (${mem_usage}%)${NC}"
    fi
    
    if (( $(echo "$swap_usage > 50" | bc -l) )); then
        echo -e "${RED}⚠️  WARNING: High swap usage (${swap_usage}%)${NC}"
    fi
}

check_disk() {
    echo -e "\n${YELLOW}Disk Usage:${NC}"
    df -h /
    
    disk_usage=$(df / | awk 'NR==2{print $5}' | sed 's/%//')
    if [ "$disk_usage" -gt 80 ]; then
        echo -e "${RED}⚠️  WARNING: High disk usage (${disk_usage}%)${NC}"
    fi
}

check_processes() {
    echo -e "\n${YELLOW}Celery Processes:${NC}"
    
    # Check PID files
    active_workers=0
    for pidfile in "$PID_DIR"/*.pid; do
        if [ -f "$pidfile" ]; then
            pid=$(cat "$pidfile")
            name=$(basename "$pidfile" .pid)
            
            if kill -0 "$pid" 2>/dev/null; then
                memory_mb=$(ps -o rss= -p "$pid" 2>/dev/null | awk '{print int($1/1024)}')
                echo -e "  ${GREEN}●${NC} $name (PID: $pid) - ${memory_mb}MB"
                active_workers=$((active_workers + 1))
            else
                echo -e "  ${RED}●${NC} $name (PID: $pid) - NOT RUNNING"
            fi
        fi
    done
    
    echo -e "\nActive workers: $active_workers"
    
    # Show top memory consuming Python processes
    echo -e "\n${YELLOW}Top Python Memory Usage:${NC}"
    ps aux --sort=-%mem | grep python | grep -v grep | head -5 | awk '{printf "  PID: %-6s CPU: %-5s MEM: %-5s CMD: %s\n", $2, $3"%", $4"%", $11}'
}

check_redis() {
    echo -e "\n${YELLOW}Redis Status:${NC}"
    if redis-cli ping >/dev/null 2>&1; then
        echo -e "  ${GREEN}●${NC} Redis is running"
        
        # Get Redis memory usage
        redis_memory=$(redis-cli info memory | grep "used_memory_human" | cut -d: -f2 | tr -d '\r')
        redis_peak=$(redis-cli info memory | grep "used_memory_peak_human" | cut -d: -f2 | tr -d '\r')
        
        echo -e "  Memory used: $redis_memory"
        echo -e "  Peak memory: $redis_peak"
    else
        echo -e "  ${RED}●${NC} Redis is NOT running"
    fi
}

check_logs() {
    echo -e "\n${YELLOW}Recent Critical Log Entries:${NC}"
    
    # Check for OOM killer
    oom_count=$(sudo dmesg | grep -i "killed process" | wc -l)
    if [ "$oom_count" -gt 0 ]; then
        echo -e "  ${RED}⚠️  OOM Killer activated $oom_count times${NC}"
        echo -e "  Last OOM event:"
        sudo dmesg | grep -i "killed process" | tail -1 | sed 's/^/    /'
    else
        echo -e "  ${GREEN}●${NC} No OOM killer events"
    fi
    
    # Check for recent errors in Celery logs
    error_count=0
    if [ -d "$PROJECT_DIR/logs" ]; then
        error_count=$(find "$PROJECT_DIR/logs" -name "*.log" -exec grep -l "ERROR\|CRITICAL\|Exception" {} \; 2>/dev/null | wc -l)
    fi
    
    if [ "$error_count" -gt 0 ]; then
        echo -e "  ${YELLOW}⚠️  $error_count log files contain errors${NC}"
    else
        echo -e "  ${GREEN}●${NC} No recent errors in logs"
    fi
}

show_recommendations() {
    echo -e "\n${YELLOW}Recommendations:${NC}"
    
    mem_usage=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
    
    if [ "$mem_usage" -gt 85 ]; then
        echo -e "  ${RED}●${NC} Consider reducing worker concurrency"
        echo -e "  ${RED}●${NC} Consider using 'solo' pool instead of 'prefork'"
    elif [ "$mem_usage" -gt 70 ]; then
        echo -e "  ${YELLOW}●${NC} Monitor memory usage closely"
    else
        echo -e "  ${GREEN}●${NC} Memory usage is healthy"
    fi
    
    active_workers=$(ls "$PID_DIR"/*.pid 2>/dev/null | wc -l)
    if [ "$active_workers" -gt 3 ]; then
        echo -e "  ${YELLOW}●${NC} Consider using consolidated worker mode"
    fi
}

# Main execution
case "${1:-all}" in
    "memory"|"mem")
        check_memory
        ;;
    "processes"|"proc")
        check_processes
        ;;
    "redis")
        check_redis
        ;;
    "logs")
        check_logs
        ;;
    "all"|*)
        print_header
        check_memory
        check_disk
        check_processes
        check_redis
        check_logs
        show_recommendations
        ;;
esac

echo -e "\n${BLUE}=================================${NC}"