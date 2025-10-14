#!/bin/bash

# Telegram AI Scraper - Quick Start Script
# Run this after server restart to get everything running quickly

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

echo "=========================================="
echo "🚀 Telegram AI Scraper - Quick Start"
echo "=========================================="

# Change to project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR" || exit 1

print_status "Starting from directory: $PROJECT_DIR"

# Step 1: Check and start Redis
print_status "1. Checking Redis service..."
if systemctl is-active --quiet redis-server; then
    print_success "Redis is already running"
else
    print_status "Starting Redis server..."
    sudo systemctl start redis-server
    sleep 2
    if systemctl is-active --quiet redis-server; then
        print_success "Redis started successfully"
    else
        print_error "Failed to start Redis service"
        echo "Please check Redis installation or start it manually:"
        echo "  sudo systemctl start redis-server"
        exit 1
    fi
fi

# Test Redis connection
if redis-cli ping >/dev/null 2>&1; then
    print_success "Redis connection test passed"
else
    print_error "Redis connection failed"
    exit 1
fi

# Step 2: Check virtual environment
print_status "2. Checking virtual environment..."
VENV_DIR="../telegram-ai-scraper_env"
if [ ! -d "$VENV_DIR" ]; then
    print_error "Virtual environment not found at $VENV_DIR"
    print_error "Please run ./scripts/setup.sh first"
    exit 1
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source "$VENV_DIR/bin/activate"
print_success "Virtual environment activated"

# Step 2.5: Check Telegram authentication
print_status "2.5 Checking Telegram authentication..."
if [ ! -f "telegram_session.session" ]; then
    print_warning "Telegram session file not found"
    
    # Check if config exists and has Telegram config
    if [ -f "config/config.json" ] && grep -q '"TELEGRAM_CONFIG"' config/config.json; then
        print_status "🔐 Telegram authentication required"
        echo ""
        echo "The system needs to authenticate with Telegram for the first time."
        echo "This requires entering an SMS verification code sent to your phone."
        echo ""
        print_warning "⚠️  IMPORTANT: Authentication will be done safely without session conflicts"
        echo ""
        read -p "Run Telegram authentication now? (y/n): " auth_now
        
        if [ "$auth_now" = "y" ] || [ "$auth_now" = "Y" ]; then
            print_status "Starting SAFE Telegram authentication (session conflict protection enabled)..."
            ./scripts/telegram_session.sh auth
            
            if [ $? -eq 0 ]; then
                print_success "Telegram authentication completed safely!"
            else
                print_error "Telegram authentication failed"
                print_error "Please run manually: ./scripts/telegram_session.sh auth"
                exit 1
            fi
        else
            print_warning "Telegram authentication skipped"
            print_warning "Some features may not work without authentication"
            print_warning "Run later with: ./scripts/telegram_session.sh auth"
        fi
    else
        print_warning "config/config.json missing or incomplete"
        print_warning "Please run ./scripts/setup.sh first"
    fi
else
    print_success "Telegram session file found"
fi

# Step 3: Check configuration
print_status "3. Verifying configuration..."
if [ ! -f "config/config.json" ]; then
    print_error "Configuration file not found!"
    echo "Please create config/config.json from config/config_sample.json"
    exit 1
fi
print_success "Configuration file found"

# Step 4: Start Celery workers and services
print_status "4. Starting Celery workers and services..."
echo ""
export CALLED_FROM_QUICK_START=true
./scripts/deploy_celery.sh start

# Check if deploy was successful
if [ $? -eq 0 ]; then
    print_success "Celery services started successfully"
else
    print_error "Failed to start Celery services"
    echo "Check the logs in logs/ directory for details"
    exit 1
fi

# Step 5: Wait for services to initialize
print_status "5. Waiting for services to fully initialize..."
sleep 15

# Step 6: Comprehensive system tests
print_status "6. Running comprehensive system tests..."
echo ""
echo "Running quick system validation tests with session verification..."
./scripts/run_tests.sh --quick

test_exit_code=$?
if [ $test_exit_code -eq 0 ]; then
    print_success "All system tests passed!"
else
    print_warning "Some tests failed or were skipped - check output above"
    echo ""
    read -p "Continue with startup despite test issues? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_error "Startup cancelled due to test failures"
        echo "Fix issues and run ./scripts/quick_start.sh again"
        exit 1
    fi
fi

# Step 7: Show final system status
print_status "7. Checking final system status..."
echo ""
./scripts/deploy_celery.sh status

echo ""
echo "=========================================="
echo "🎉 Quick Start Complete!"
echo "=========================================="
echo ""
echo "📊 Access Points:"
echo "• Flower Monitoring: http://$(curl -s ifconfig.me 2>/dev/null || echo 'YOUR_SERVER_IP'):5555"
echo "• Flower Local: http://localhost:5555"
echo ""
echo "🎯 Next Actions:"
echo "• The system now automatically fetches new messages every 4 minutes!"
echo "• View telegram logs: tail -f logs/telegram.log"
echo "• View worker logs: tail -f logs/celery_*.log"
echo "• Monitor resources: ./scripts/monitor_resources.sh"
echo ""
echo "🔧 Management Commands:"
echo "• Check status: ./scripts/deploy_celery.sh status"
echo "• Restart services: ./scripts/deploy_celery.sh restart"
echo "• Stop services: ./scripts/deploy_celery.sh stop"
echo "• Run comprehensive tests: ./scripts/run_tests.sh"
echo "• Run quick tests: ./scripts/run_tests.sh --quick"
echo "• Test Telegram session: ./scripts/telegram_session.sh test"
echo ""
echo "📁 Important Directories:"
echo "• Configuration: config/config.json"
echo "• Logs: logs/"
echo "• Data: data/"
echo "• Process IDs: pids/"
echo ""

# # Optional: Ask if user wants to start monitoring (only if not already running)
# print_status "Checking if monitoring is already running..."

# # Check if main.py --mode monitor is already running
# if pgrep -f "python3 src/core/main.py --mode monitor" > /dev/null; then
#     print_success "Real-time monitoring is already running"
#     echo "• To view monitoring output: tail -f logs/main.log"
#     echo "• To stop monitoring: pkill -f 'python3 src/core/main.py --mode monitor'"
# else
#     echo ""
#     echo "Would you like to start real-time monitoring now? (y/n)"
#     read -r response
#     if [[ "$response" =~ ^[Yy]$ ]]; then
#         echo ""
#         print_status "Starting real-time monitoring..."
#         echo "Press Ctrl+C to stop monitoring"
#         echo ""
#         # Monitoring now handled by Celery Beat automatically
#     fi
# fi

print_status "Quick start script completed"