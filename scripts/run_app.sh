#!/bin/bash

# Telegram AI Scraper - Application Runner
# This script runs the main application with proper environment setup

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$PROJECT_DIR/../telegram-ai-scraper_env"

print_status() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

print_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

echo "=========================================="
echo "Telegram AI Scraper - Application Runner"
echo "=========================================="
echo ""
echo "ℹ️  Session Safety: This script includes automatic"
echo "   session conflict detection to prevent invalidation"
echo ""

# Change to project directory
cd "$PROJECT_DIR" || exit 1

# Activate virtual environment
if [ ! -d "$VENV_DIR" ]; then
    print_error "Virtual environment not found at $VENV_DIR"
    exit 1
fi

print_status "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Check if config exists
if [ ! -f "config/config.json" ]; then
    print_error "config/config.json not found. Please configure the application first."
    exit 1
fi

# Get mode and config from arguments
MODE="${1:-monitor}"
CONFIG="${2:-config.json}"

case "$MODE" in
    test)
        print_status "Running comprehensive system tests..."
        ./scripts/run_tests.sh --quick
        exit $?
        ;;
    test-api)
        print_status "Running API connection tests only..."
        result=$(python3 src/core/main.py --mode test --config "$CONFIG" 2>&1)
        exit_code=$?
        echo "$result"
        
        # Check if Telegram authentication is needed
        if echo "$result" | grep -q "Run: python3 scripts/telegram_auth.py"; then
            echo ""
            echo -e "${YELLOW}🔧 Telegram authentication required!${NC}"
            echo -e "${YELLOW}Run the following command to authenticate:${NC}"
            echo -e "${GREEN}python3 scripts/telegram_auth.py${NC}"
            echo ""
        fi
        
        exit $exit_code
        ;;
    monitor)
        print_status "Starting real-time monitoring..."
        python3 src/core/main.py --mode monitor --config "$CONFIG"
        ;;
    historical)
        LIMIT="${3:-100}"
        print_status "Starting historical scraping (limit: $LIMIT)..."
        python3 src/core/main.py --mode historical --config "$CONFIG" --limit "$LIMIT"
        ;;
    *)
        echo -e "${YELLOW}Usage: $0 {test|test-api|monitor|historical} [config_file] [limit]${NC}"
        echo ""
        echo "Commands:"
        echo "  test        - Run comprehensive system tests (recommended)"
        echo "  test-api    - Test API connections only (legacy mode)"
        echo "  monitor     - Real-time monitoring of Telegram channels"
        echo "  historical  - Scrape historical messages from channels"
        echo ""
        echo "Arguments:"
        echo "  config_file - Configuration file name (default: config.json)"
        echo "  limit       - Messages per channel for historical mode (default: 100)"
        echo ""
        echo "Examples:"
        echo "  $0 test                    # Run comprehensive tests"
        echo "  $0 test-api                # Test API connections only"
        echo "  $0 monitor                 # Start monitoring"
        echo "  $0 historical config.json 50  # Scrape 50 messages per channel"
        ;;
esac