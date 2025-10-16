#!/bin/bash

# Telegram AI Scraper Setup Script
# This script sets up the environment and installs dependencies

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PATH="../telegram-ai-scraper_env"

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
if [ ! -d "$VENV_PATH" ]; then
    echo "Creating virtual environment at $VENV_PATH..."
    python3 -m venv "$VENV_PATH"
else
    echo "Virtual environment already exists at $VENV_PATH"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_PATH/bin/activate"

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

# Test Redis connection
echo "Testing Redis connection..."
if redis-cli ping | grep -q "PONG"; then
    echo "✓ Redis connection successful"
else
    echo "✗ Redis connection failed - please check Redis installation"
fi

# Check if config.json exists and Telegram is configured
CONFIG_EXISTS=false
TELEGRAM_CONFIGURED=false

if [ -f "config/config.json" ]; then
    CONFIG_EXISTS=true
    # Check if Telegram config exists
    if grep -q '"TELEGRAM_CONFIG"' config/config.json && grep -q '"API_ID"' config/config.json; then
        TELEGRAM_CONFIGURED=true
    fi
fi

# Create sample configuration if it doesn't exist
if [ ! -f "config/config_sample.json" ]; then
    echo "Creating sample configuration file..."
    cat > config/config_sample.json << 'EOF'
{
   "USERS": {
      "admin": "your_admin_password"
   },
   "TEAMS_SENDER_NAME": "Aldebaran Scraper",
   "TEAMS_ADMIN_WEBHOOK": "your_admin_teams_webhook_url_here",
   "TEAMS_ADMIN_CHANNEL": "Admin Alerts",
   "OPEN_AI_KEY": "your_openai_api_key_here",
   "TELEGRAM_CONFIG": {
      "API_ID": "your_telegram_api_id",
      "API_HASH": "your_telegram_api_hash",
      "PHONE_NUMBER": "your_phone_number",
      "SESSION_FILE": "telegram_session.session",
      "FETCH_INTERVAL_SECONDS": 240,
      "FETCH_MESSAGE_LIMIT": 10
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
         },
         "message_filtering": {
            "use_ai_for_message_filtering": false,
            "translate_trivial_msgs": true,
            "use_ai_for_translation": false,
            "use_ai_for_enhanced_filtering": false,
            "ai_exception_rules": [
               "news about other countries or regions",
               "international events not affecting Philippines",
               "foreign political developments",
               "overseas incidents or accidents"
            ],
            "significant_keywords": [
               "breaking news", "alert", "urgent", "emergency", "crisis", "attack", "security",
               "cyber", "breach", "hack", "vulnerability", "malware", "ransomware", "phishing"
            ],
            "trivial_keywords": [
               "weather", "sports", "entertainment", "celebrity", "gossip", "fashion", "food"
            ],
            "exclude_keywords": [
               "advertisement", "promo", "discount", "sale", "buy now", "limited time"
            ]
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
         },
         "message_filtering": {
            "use_ai_for_message_filtering": false,
            "translate_trivial_msgs": true,
            "use_ai_for_translation": false,
            "use_ai_for_enhanced_filtering": false,
            "ai_exception_rules": [
               "news about other countries or regions",
               "international events not affecting Singapore",
               "foreign political developments",
               "overseas incidents or accidents"
            ],
            "significant_keywords": [
               "breaking news", "alert", "urgent", "emergency", "crisis", "attack", "security",
               "cyber", "breach", "hack", "vulnerability", "malware", "ransomware", "phishing"
            ],
            "trivial_keywords": [
               "weather", "sports", "entertainment", "celebrity", "gossip", "fashion", "food"
            ],
            "exclude_keywords": [
               "advertisement", "promo", "discount", "sale", "buy now", "limited time"
            ]
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
   "TELEGRAM_EXCEL_FIELDS": [
      "Message_ID", "Channel", "Country", "Date", "Time", "Author", "Message_Text", 
      "AI_Category", "AI_Reasoning", "Keywords_Matched", "Message_Type", "Forward_From", 
      "Media_Type", "Original_Text", "Original_Language", "Was_Translated", "Processed_Date"
   ],
   "EXCLUDED_TEAMS_FIELDS": [
      "Country", "AI_Category", "Message_Type", "Forward_From", "Media_Type", "Was_Translated", "Processed_Date", "Author"
   ],
   "EXCLUDED_SHAREPOINT_FIELDS": [
      "Country", "AI_Category", "Message_Type", "Forward_From", "Media_Type", "Was_Translated", "Processed_Date", "Author"
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

# Prompt for configuration if needed
if [ "$CONFIG_EXISTS" = false ]; then
    echo "⚠️  Configuration Required:"
    echo "1. Copy config/config_sample.json to config/config.json"
    echo "2. Edit config/config.json with your actual API keys and settings"
    echo ""
    echo "🤖 AI Enhanced Filtering Configuration (Optional):"
    echo "   • use_ai_for_enhanced_filtering: Enable AI exception checking"
    echo "   • ai_exception_rules: List of patterns to filter out irrelevant news"
    echo "   • Example: News about other countries, foreign political events"
    echo ""
    read -p "Have you configured config/config.json with your API keys? (y/n): " configured
    
    if [ "$configured" = "y" ] || [ "$configured" = "Y" ]; then
        CONFIG_EXISTS=true
        if grep -q '"TELEGRAM_CONFIG"' config/config.json && grep -q '"API_ID"' config/config.json; then
            TELEGRAM_CONFIGURED=true
        fi
    else
        echo ""
        echo "Please complete configuration first:"
        echo "1. cp config/config_sample.json config/config.json" 
        echo "2. Edit config/config.json with your API keys"
        echo "3. Run this setup script again or proceed to telegram authentication"
        CONFIG_EXISTS=false
    fi
fi

# Run Telegram authentication if configured
if [ "$CONFIG_EXISTS" = true ] && [ "$TELEGRAM_CONFIGURED" = true ]; then
    echo ""
    echo "🔐 TELEGRAM AUTHENTICATION SETUP"
    echo "================================="
    
    # Check if session file already exists
    if [ -f "telegram_session.session" ]; then
        echo "✅ Telegram session file already exists"
        echo "If you need to re-authenticate, run:"
        echo "./scripts/telegram_session.sh auth"
    else
        echo "📱 Telegram authentication required for first-time setup"
        echo "This will prompt you to enter SMS verification code from your phone"
        echo ""
        read -p "Run Telegram authentication now? (y/n): " auth_now
        
        if [ "$auth_now" = "y" ] || [ "$auth_now" = "Y" ]; then
            echo ""
            echo "Starting Telegram authentication..."
            ./scripts/telegram_session.sh auth
            
            if [ $? -eq 0 ]; then
                echo "✅ Telegram authentication completed successfully!"
            else
                echo "❌ Telegram authentication failed"
                echo "You can retry later with: ./scripts/telegram_session.sh auth"
            fi
        else
            echo ""
            echo "⚠️  Telegram authentication skipped"
            echo "Run this command when ready: ./scripts/telegram_session.sh auth"
        fi
    fi
fi

echo ""
echo "NEXT STEPS:"
echo "==========="
if [ "$CONFIG_EXISTS" = false ]; then
    echo "1. Configure your API keys: cp config/config_sample.json config/config.json"
    echo "2. Edit config/config.json with actual values"
    echo "3. Run Telegram authentication: ./scripts/telegram_session.sh auth"
    echo "4. Start the system: ./scripts/quick_start.sh"
elif [ ! -f "telegram_session.session" ]; then
    echo "1. Run Telegram authentication: ./scripts/telegram_session.sh auth"
    echo "2. Start the system: ./scripts/quick_start.sh"
else
    echo "✅ System ready! Start with: ./scripts/quick_start.sh"
    echo ""
    echo "📱 Session Management (available anytime):"
    echo "   • Check session: ./scripts/telegram_session.sh status"
    echo "   • Test session: ./scripts/telegram_session.sh test (no SMS)"
    echo "   • Renew session: ./scripts/telegram_session.sh renew"
fi
echo ""
echo "Manual Deployment:"
echo "1. Start Celery workers in separate terminals:"
echo "   celery -A src.tasks.telegram_celery_tasks worker --queues=telegram_processing --concurrency=2"
echo "   celery -A src.tasks.telegram_celery_tasks worker --queues=notifications --concurrency=1"
echo "   celery -A src.tasks.telegram_celery_tasks worker --queues=sharepoint --concurrency=1"
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