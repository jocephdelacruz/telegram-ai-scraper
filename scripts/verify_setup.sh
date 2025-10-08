#!/bin/bash

# Telegram AI Scraper - Setup Verification Script
# Validates that all prerequisites and configurations are properly set up

echo "============================================"
echo "Telegram AI Scraper - Setup Verification"
echo "============================================"

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track validation results
ERRORS=0
WARNINGS=0

# Function to show status
check_status() {
    if [ $1 -eq 0 ]; then
        echo -e "✓ ${GREEN}$2${NC}"
    else
        echo -e "✗ ${RED}$2${NC}"
        ((ERRORS++))
    fi
}

warn_status() {
    echo -e "⚠ ${YELLOW}$1${NC}"
    ((WARNINGS++))
}

echo "Checking System Prerequisites..."
echo "─────────────────────────────"

# Check if we're in the right directory
if [ ! -f "run.py" ] || [ ! -d "src" ]; then
    echo -e "✗ ${RED}Error: Not in telegram-ai-scraper directory${NC}"
    echo "Please run this script from the telegram-ai-scraper directory"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 --version 2>/dev/null)
if [ $? -eq 0 ]; then
    check_status 0 "Python 3 is installed: $PYTHON_VERSION"
else
    check_status 1 "Python 3 is not installed or not in PATH"
fi

# Check virtual environment
if [ -d "telegram-ai-scraper_env" ]; then
    check_status 0 "Virtual environment exists"
    
    # Check if virtual environment is activated
    if [[ "$VIRTUAL_ENV" == *"telegram-ai-scraper_env"* ]]; then
        check_status 0 "Virtual environment is activated"
    else
        warn_status "Virtual environment exists but not activated. Run: source telegram-ai-scraper_env/bin/activate"
    fi
elif [ -d "../telegram-ai-scraper_env" ]; then
    # Check if virtual environment is in parent directory
    check_status 0 "Virtual environment exists (in parent directory)"
    
    if [[ "$VIRTUAL_ENV" == *"telegram-ai-scraper_env"* ]]; then
        check_status 0 "Virtual environment is activated"
    else
        warn_status "Virtual environment exists but not activated. Run: source ../telegram-ai-scraper_env/bin/activate"
    fi
else
    check_status 1 "Virtual environment not found. Run: ./scripts/setup.sh"
fi

# Check Redis
REDIS_STATUS=$(systemctl is-active redis-server 2>/dev/null)
if [ "$REDIS_STATUS" = "active" ]; then
    check_status 0 "Redis server is running"
    
    # Test Redis connection
    redis-cli ping >/dev/null 2>&1
    check_status $? "Redis connection test"
else
    check_status 1 "Redis server is not running. Try: sudo systemctl start redis-server"
fi

# Check configuration files
echo ""
echo "Checking Configuration Files..."
echo "─────────────────────────────"

if [ -f "config/config.json" ]; then
    check_status 0 "Main configuration file exists"
    
    # Check if config has required sections
    if grep -q '"telegram"' config/config.json && grep -q '"openai"' config/config.json; then
        check_status 0 "Configuration file has required sections"
    else
        check_status 1 "Configuration file missing required sections (telegram, openai)"
    fi
    
    # Check for placeholder values
    if grep -q "YOUR_" config/config.json; then
        warn_status "Configuration file contains placeholder values (YOUR_*). Please update with actual values."
    fi
    
else
    check_status 1 "Configuration file not found. Copy config_sample.json to config.json and edit"
fi

# Check directory structure
echo ""
echo "Checking Directory Structure..."
echo "────────────────────────────"

REQUIRED_DIRS=("src" "config" "logs" "data" "scripts" "pids")
for dir in "${REQUIRED_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        check_status 0 "Directory '$dir' exists"
    else
        check_status 1 "Directory '$dir' missing"
    fi
done

# Check script permissions
echo ""
echo "Checking Script Permissions..."
echo "────────────────────────────"

SCRIPT_FILES=("setup.sh" "quick_start.sh" "deploy_celery.sh" "run_app.sh" "monitor_resources.sh" "status.sh" "stop_celery.sh" "auto_restart.sh")
for script in "${SCRIPT_FILES[@]}"; do
    if [ -f "scripts/$script" ]; then
        if [ -x "scripts/$script" ]; then
            check_status 0 "Script '$script' is executable"
        else
            warn_status "Script '$script' exists but not executable. Run: chmod +x scripts/$script"
        fi
    else
        warn_status "Script '$script' not found"
    fi
done

# Check system resources
echo ""
echo "Checking System Resources..."
echo "──────────────────────────"

# Memory check
TOTAL_MEM=$(free -m | awk 'NR==2{printf "%.0f", $2}')
AVAILABLE_MEM=$(free -m | awk 'NR==2{printf "%.0f", $7}')
SWAP_SIZE=$(free -m | awk 'NR==3{printf "%.0f", $2}')

if [ "$TOTAL_MEM" -gt 1500 ]; then
    check_status 0 "System memory: ${TOTAL_MEM}MB (sufficient)"
else
    warn_status "System memory: ${TOTAL_MEM}MB (recommended: >1.5GB for stable operation)"
fi

if [ "$SWAP_SIZE" -gt 1000 ]; then
    check_status 0 "Swap space: ${SWAP_SIZE}MB (configured)"
else
    warn_status "Swap space: ${SWAP_SIZE}MB (recommended: >1GB for memory-constrained systems)"
fi

# Disk space check
DISK_USAGE=$(df . | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -lt 80 ]; then
    check_status 0 "Disk usage: ${DISK_USAGE}% (sufficient)"
else
    warn_status "Disk usage: ${DISK_USAGE}% (consider cleaning up if >90%)"
fi

# Check Python packages (if virtual env is activated)
if [[ "$VIRTUAL_ENV" == *"telegram-ai-scraper_env"* ]]; then
    echo ""
    echo "Checking Python Dependencies..."
    echo "─────────────────────────────"
    
    REQUIRED_PACKAGES=("celery" "redis" "telethon" "openai" "requests")
    for package in "${REQUIRED_PACKAGES[@]}"; do
        if python -c "import $package" 2>/dev/null; then
            check_status 0 "Python package '$package' is installed"
        else
            check_status 1 "Python package '$package' not found. Run: pip install -r requirements.txt"
        fi
    done
fi

# Final summary
echo ""
echo "============================================"
echo "Verification Summary"
echo "============================================"

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "🎉 ${GREEN}Perfect! Your system is ready to run.${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Update config/config.json with your API keys and settings"
    echo "2. Run: ./scripts/quick_start.sh"
    echo "3. Check status: ./scripts/status.sh"
elif [ $ERRORS -eq 0 ]; then
    echo -e "✅ ${GREEN}System is functional with ${WARNINGS} warning(s).${NC}"
    echo ""
    echo "You can proceed with:"
    echo "1. Address any warnings above (optional but recommended)"
    echo "2. Run: ./scripts/quick_start.sh"
else
    echo -e "❌ ${RED}Found ${ERRORS} error(s) and ${WARNINGS} warning(s).${NC}"
    echo ""
    echo "Please fix the errors above before proceeding."
    echo "For help, see the Troubleshooting section in README.md"
fi

echo ""
echo "Useful commands:"
echo "• Full setup:      ./scripts/setup.sh"
echo "• Start system:    ./scripts/quick_start.sh"
echo "• Check status:    ./scripts/status.sh"
echo "• Monitor system:  ./scripts/monitor_resources.sh"
echo "• View this help:  ./scripts/verify_setup.sh"