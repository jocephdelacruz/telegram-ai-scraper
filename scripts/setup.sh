#!/bin/bash

# Telegram AI Scraper Setup Script
# This script sets up the environment and installs dependencies

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

echo "=========================================="
echo "Telegram AI Scraper Setup"
echo "=========================================="

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

echo "Python 3 found: $(python3 --version)"

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "Error: pip3 is not installed"
    exit 1
fi

echo "pip3 found: $(pip3 --version)"

# Check if Redis is installed and running
echo "Checking Redis server..."
if command -v redis-server &> /dev/null; then
    echo "Redis server found: $(redis-server --version)"
    
    # Check if Redis is running
    if redis-cli ping &> /dev/null; then
        echo "Redis server is running"
    else
        echo "Starting Redis server..."
        if command -v systemctl &> /dev/null; then
            sudo systemctl start redis-server
            sudo systemctl enable redis-server
        else
            echo "Please start Redis server manually: redis-server"
        fi
    fi
else
    echo "Warning: Redis server not found. Installing Redis..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y redis-server
        sudo systemctl start redis-server
        sudo systemctl enable redis-server
    elif command -v yum &> /dev/null; then
        sudo yum install -y redis
        sudo systemctl start redis
        sudo systemctl enable redis
    else
        echo "Please install Redis manually for your system"
        echo "Ubuntu/Debian: sudo apt-get install redis-server"
        echo "CentOS/RHEL: sudo yum install redis"
        echo "macOS: brew install redis"
    fi
fi

# Create virtual environment if it doesn't exist
if [ ! -d "telegram-ai-scraper_env" ]; then
    echo "Creating virtual environment..."
    python3 -m venv telegram-ai-scraper_env
fi

# Activate virtual environment
echo "Activating virtual environment..."
source telegram-ai-scraper_env/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Create necessary directories
echo "Creating required directories..."
mkdir -p logs
mkdir -p data
mkdir -p backups

# Test Redis connection
echo "Testing Redis connection..."
if redis-cli ping | grep -q "PONG"; then
    echo "✓ Redis connection successful"
else
    echo "✗ Redis connection failed - please check Redis installation"
fi

# Create sample configuration if it doesn't exist
if [ ! -f "config/config_sample.json" ]; then
    echo "Creating sample configuration file..."
    cat > config/config_sample.json << 'EOF'
{
   "USERS": {
      "admin": "your_admin_password"
   },
   "OPEN_AI_KEY": "your_openai_api_key_here",
   "TELEGRAM_CONFIG": {
      "API_ID": "your_telegram_api_id",
      "API_HASH": "your_telegram_api_hash",
      "PHONE_NUMBER": "your_phone_number",
      "SESSION_FILE": "telegram_session.session"
   },
   "COUNTRIES": {
      "philippines": {
         "name": "Philippines",
         "channels": ["@philippinesnews", "@rapplerdotcom", "@abscbnnews"],
         "teams_webhook": "your_philippines_teams_webhook_url",
         "teams_channel_name": "Philippines Telegram Alerts",
         "sharepoint_config": {
            "site_name": "ATCSharedFiles",
            "folder_path": "/Telegram_Feeds/Philippines/",
            "file_name": "Philippines_Telegram_Feed.xlsx",
            "significant_sheet": "Significant",
            "trivial_sheet": "Trivial"
         }
      },
      "singapore": {
         "name": "Singapore",
         "channels": ["@channelnewsasia", "@straitstimes", "@todayonlinesg"],
         "teams_webhook": "your_singapore_teams_webhook_url",
         "teams_channel_name": "Singapore Telegram Alerts",
         "sharepoint_config": {
            "site_name": "ATCSharedFiles",
            "folder_path": "/Telegram_Feeds/Singapore/",
            "file_name": "Singapore_Telegram_Feed.xlsx",
            "significant_sheet": "Significant", 
            "trivial_sheet": "Trivial"
         }
      },
      "malaysia": {
         "name": "Malaysia",
         "channels": ["@thestaronline", "@malaymail", "@freemalaysiatoday"],
         "teams_webhook": "your_malaysia_teams_webhook_url",
         "teams_channel_name": "Malaysia Telegram Alerts",
         "sharepoint_config": {
            "site_name": "ATCSharedFiles",
            "folder_path": "/Telegram_Feeds/Malaysia/",
            "file_name": "Malaysia_Telegram_Feed.xlsx",
            "significant_sheet": "Significant",
            "trivial_sheet": "Trivial"
         }
      }
   },
   "MS_SHAREPOINT_ACCESS": {
      "ClientID": "your_sharepoint_client_id",
      "ClientSecret": "your_sharepoint_client_secret",
      "TenantID": "your_tenant_id",
      "SharepointSite": "your_sharepoint_site",
      "StartingCell": "A1",
      "RangeAddressToClear": "A1:Z800"
   },
   "MESSAGE_FILTERING": {
      "SIGNIFICANT_KEYWORDS": [
         "breaking news", "alert", "urgent", "emergency", "crisis", "attack", "security", 
         "cyber", "breach", "hack", "vulnerability", "malware", "ransomware", "phishing",
         "data leak", "incident", "threat", "suspicious", "fraud", "scam", "investigation"
      ],
      "TRIVIAL_KEYWORDS": [
         "weather", "sports", "entertainment", "celebrity", "gossip", "fashion", "food",
         "travel", "lifestyle", "health tips", "recipe", "horoscope", "quiz", "game"
      ],
      "EXCLUDE_KEYWORDS": [
         "advertisement", "promo", "discount", "sale", "buy now", "limited time"
      ]
   },
   "TELEGRAM_EXCEL_FIELDS": [
      "Message_ID", "Channel", "Country", "Date", "Time", "Author", "Message_Text", 
      "AI_Category", "AI_Reasoning", "Keywords_Matched", "Message_Type", "Forward_From", 
      "Media_Type", "Processed_Date"
   ],
   "CELERY_CONFIG": {
      "broker_url": "redis://localhost:6379/0",
      "result_backend": "redis://localhost:6379/0",
      "worker_concurrency": 4,
      "task_time_limit": 300,
      "worker_prefetch_multiplier": 1,
      "result_expires": 3600
   }
}
EOF
fi

# Set permissions
chmod +x src/core/main.py
chmod +x scripts/setup.sh
chmod +x scripts/deploy_celery.sh
chmod +x scripts/stop_celery.sh
chmod +x scripts/status.sh

# Create systemd service files (optional)
if [ -d "/etc/systemd/system" ] && [ "$EUID" -eq 0 ]; then
    echo "Creating systemd service files..."
    
    cat > /etc/systemd/system/telegram-scraper.service << EOF
[Unit]
Description=Telegram AI Scraper
After=network.target redis.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/telegram-ai-scraper_env/bin
ExecStart=$(pwd)/telegram-ai-scraper_env/bin/python main.py --mode monitor
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    echo "✓ Created systemd service file: /etc/systemd/system/telegram-scraper.service"
    systemctl daemon-reload
fi

echo "=========================================="
echo "Setup completed successfully!"
echo "=========================================="
echo ""
echo "CELERY + REDIS ARCHITECTURE SETUP"
echo ""
echo "Quick Start (Recommended):"
echo "1. Copy config/config_sample.json to config/config.json"
echo "2. Edit config/config.json with your actual API keys and settings"
echo "3. Run './scripts/deploy_celery.sh' to start all services"
echo ""
echo "Manual Deployment:"
echo "1. Start Celery workers in separate terminals:"
echo "   celery -A src.tasks.telegram_celery_tasks worker --queues=telegram_processing --concurrency=4"
echo "   celery -A src.tasks.telegram_celery_tasks worker --queues=notifications --concurrency=2"
echo "   celery -A src.tasks.telegram_celery_tasks worker --queues=sharepoint --concurrency=2"
echo "   celery -A src.tasks.telegram_celery_tasks worker --queues=backup --concurrency=1"
echo ""
echo "2. Start main application:"
echo "   python3 src/core/main.py --mode test      # Test connections"
echo "   python3 src/core/main.py --mode monitor   # Real-time monitoring"
echo ""
echo "Monitoring:"
echo "   celery -A src.tasks.telegram_celery_tasks flower  # Web UI at http://localhost:5555"
echo ""
echo "To activate the virtual environment manually:"
echo "source telegram-ai-scraper_env/bin/activate"
echo ""
echo "For help: python3 src/core/main.py --help"