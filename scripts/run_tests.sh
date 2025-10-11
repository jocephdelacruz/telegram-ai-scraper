#!/bin/bash

# Telegram AI Scraper - Test Runner Script
# Comprehensive test runner with environment setup

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

print_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

# Change to project directory
cd "$PROJECT_DIR" || exit 1

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    print_error "Virtual environment not found at $VENV_DIR"
    print_error "Please run ./scripts/setup.sh first"
    exit 1
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Check if config exists (warn but don't fail)
if [ ! -f "config/config.json" ]; then
    print_warning "config/config.json not found. Some tests may be skipped."
    print_warning "Create config from config_sample.json for full testing."
fi

# Set PYTHONPATH
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"

# Run the Python test runner with all arguments passed through
python3 scripts/run_tests.py "$@"
exit_code=$?

if [ $exit_code -eq 0 ]; then
    print_success "All tests completed successfully!"
else
    print_warning "Some tests failed. Check output above for details."
fi

exit $exit_code