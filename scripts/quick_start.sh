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

# Step 2: Check system resources
print_status "2. Checking system resources..."
echo ""
./scripts/monitor_resources.sh memory
echo ""

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

# Step 6: Test all connections
print_status "6. Testing API connections and services..."
echo ""
./scripts/run_app.sh test

if [ $? -eq 0 ]; then
    print_success "Connection tests completed"
else
    print_warning "Some connection tests may have failed - check output above"
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
echo "• Start monitoring: ./scripts/run_app.sh monitor"
echo "• View main logs: tail -f logs/main.log"
echo "• View worker logs: tail -f logs/celery_all.log"
echo "• Monitor resources: ./scripts/monitor_resources.sh"
echo ""
echo "🔧 Management Commands:"
echo "• Check status: ./scripts/deploy_celery.sh status"
echo "• Restart services: ./scripts/deploy_celery.sh restart"
echo "• Stop services: ./scripts/deploy_celery.sh stop"
echo "• Test connections: ./scripts/run_app.sh test"
echo ""
echo "📁 Important Directories:"
echo "• Configuration: config/config.json"
echo "• Logs: logs/"
echo "• Data: data/"
echo "• Process IDs: pids/"
echo ""

# Optional: Ask if user wants to start monitoring
echo "Would you like to start real-time monitoring now? (y/n)"
read -r response
if [[ "$response" =~ ^[Yy]$ ]]; then
    echo ""
    print_status "Starting real-time monitoring..."
    echo "Press Ctrl+C to stop monitoring"
    echo ""
    ./scripts/run_app.sh monitor
fi

print_status "Quick start script completed"