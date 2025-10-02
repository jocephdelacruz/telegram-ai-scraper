# How to Run Telegram AI Scraper in Monitoring Mode

## Complete Step-by-Step Guide

### Prerequisites Check
1. **System Requirements**:
   - Ubuntu/Linux system
   - Python 3.8+
   - Redis server
   - Internet connection for API calls

### Step 1: Initial Setup (One-time only)

```bash
# Navigate to project directory
cd /home/ubuntu/TelegramScraper/telegram-ai-scraper

# Run setup script (installs dependencies, creates virtual env, starts redis)
chmod +x scripts/setup.sh
./scripts/setup.sh
```

This script will:
- ✅ Create Python virtual environment (`telegram-ai-scraper_env/`)
- ✅ Install all dependencies from `requirements.txt`
- ✅ Install and start Redis server
- ✅ Create necessary directories (`logs/`, `data/`, etc.)
- ✅ Set file permissions

### Step 2: Configuration

```bash
# Copy sample configuration
cp config/config_sample.json config/config.json

# Edit with your actual credentials
nano config/config.json  # or use your preferred editor
```

**Required Configuration Updates**:
```json
{
   "OPEN_AI_KEY": "sk-your-actual-openai-key-here",
   
   "TELEGRAM_CONFIG": {
      "API_ID": "your_actual_telegram_api_id",
      "API_HASH": "your_actual_telegram_api_hash",
      "PHONE_NUMBER": "+1234567890",
      "SESSION_FILE": "telegram_session.session"
   },
   
   "COUNTRIES": {
      "philippines": {
         "teams_webhook": "https://your-actual-teams-webhook-url",
         "channels": ["@actual_channel1", "@actual_channel2"]
      }
   },
   
   "MS_SHAREPOINT_ACCESS": {
      "ClientID": "your-actual-sharepoint-client-id",
      "ClientSecret": "your-actual-sharepoint-secret",
      "TenantID": "your-actual-tenant-id",
      "SharepointSite": "your-actual-sharepoint-site-url"
   }
}
```

### Step 3: Start the System (Easy Mode)

```bash
# Start everything with interactive deployment script
chmod +x scripts/deploy_celery.sh
./scripts/deploy_celery.sh
```

**What this script does**:
1. ✅ Checks all prerequisites (Python, Redis, config file)
2. ✅ Activates virtual environment
3. ✅ Starts all Celery workers:
   - Main processing workers (4 workers)
   - Notification workers (2 workers) 
   - SharePoint workers (2 workers)
   - Backup workers (1 worker)
   - Maintenance workers (1 worker)
4. ✅ Starts Celery Beat scheduler
5. ✅ Offers to start Flower monitoring web UI
6. ✅ Offers to run connection tests
7. ✅ **Offers to start monitoring mode** ← This is what you want!

**Interactive Options**:
- When prompted "Start Flower monitoring web UI? (y/n)": Type `y` to enable web monitoring at http://localhost:5555
- When prompted "Run connection tests? (y/n)": Type `y` to test all API connections
- When prompted "Start real-time monitoring? (y/n)": Type `y` to begin monitoring Telegram channels

### Step 4: Monitor the System

Once monitoring starts, you'll see:
```
==========================================
Starting Telegram AI Scraper Monitoring  
==========================================

[2025-10-02 10:30:15] Initializing Telegram AI Scraper...
[2025-10-02 10:30:16] Telegram client initialized
[2025-10-02 10:30:17] OpenAI processor initialized  
[2025-10-02 10:30:18] Teams notifier initialized
[2025-10-02 10:30:19] SharePoint processor initialized
[2025-10-02 10:30:20] Starting real-time monitoring...
[2025-10-02 10:30:21] Monitoring channels: @philippinesnews, @rapplerdotcom, @abscbnnews
[2025-10-02 10:30:22] Listening for new messages... (Press Ctrl+C to stop)
```

### Alternative: Manual Step-by-Step Control

If you prefer manual control over each component:

#### A. Start Workers Individually
```bash
# Activate environment first
source telegram-ai-scraper_env/bin/activate

# Terminal 1 - Main processing
celery -A src.tasks.telegram_celery_tasks worker --loglevel=info --queues=telegram_processing --concurrency=4 --hostname=main@%h

# Terminal 2 - Notifications  
celery -A src.tasks.telegram_celery_tasks worker --loglevel=info --queues=notifications --concurrency=2 --hostname=notifications@%h

# Terminal 3 - SharePoint
celery -A src.tasks.telegram_celery_tasks worker --loglevel=info --queues=sharepoint --concurrency=2 --hostname=sharepoint@%h

# Terminal 4 - Backup
celery -A src.tasks.telegram_celery_tasks worker --loglevel=info --queues=backup --concurrency=1 --hostname=backup@%h

# Terminal 5 - Beat scheduler
celery -A src.tasks.telegram_celery_tasks beat --loglevel=info
```

#### B. Start Main Application
```bash
# Terminal 6 - Test connections first
python3 src/core/main.py --config config/config.json --mode test

# If tests pass, start monitoring
python3 src/core/main.py --config config/config.json --mode monitor
```

### Step 5: Monitoring and Management

#### Check System Status
```bash
# Check all components
./scripts/status.sh

# Or individual checks
celery -A src.tasks.telegram_celery_tasks inspect active
celery -A src.tasks.telegram_celery_tasks inspect stats
```

#### View Logs
```bash
# View recent logs
./scripts/deploy_celery.sh logs

# Or individual log files
tail -f logs/main.log
tail -f logs/telegram_celery_tasks.log
tail -f logs/celery_main_processor.log
```

#### Web Monitoring (if Flower is running)
- Open browser to: http://localhost:5555
- View real-time worker status, task queues, and performance metrics

### Step 6: Stopping the System

```bash
# Stop all workers and services
./scripts/stop_celery.sh

# Or use the management script
./scripts/deploy_celery.sh stop
```

### Troubleshooting Quick Fixes

#### Redis Not Running
```bash
sudo systemctl start redis-server
sudo systemctl status redis-server
redis-cli ping  # Should return "PONG"
```

#### Virtual Environment Issues
```bash
# Recreate virtual environment
rm -rf telegram-ai-scraper_env
python3 -m venv telegram-ai-scraper_env
source telegram-ai-scraper_env/bin/activate
pip install -r requirements.txt
```

#### Permission Issues
```bash
chmod +x scripts/*.sh
chmod +x src/core/main.py
```

#### Config File Issues
```bash
# Validate JSON syntax
python3 -c "import json; json.load(open('config/config.json'))"
```

### Expected Behavior in Monitoring Mode

When running correctly, you should see:

1. **System Startup**: All workers initialize and connect
2. **Channel Monitoring**: System listens to configured Telegram channels
3. **Message Processing**: New messages trigger Celery tasks
4. **AI Analysis**: Messages analyzed for significance using country-specific filters
5. **Notifications**: Significant messages sent to Teams
6. **Storage**: All messages stored in SharePoint (Significant/Trivial sheets) and CSV backups
7. **Logging**: Detailed logs show processing activity

### Key Log Files to Monitor

- `logs/main.log` - Main application events
- `logs/celery_main_processor.log` - Message processing tasks
- `logs/celery_notifications.log` - Teams notifications
- `logs/celery_sharepoint.log` - SharePoint operations
- `logs/telegram.log` - Telegram API interactions
- `logs/openai.log` - AI analysis results

The system is designed to run continuously, processing messages in real-time with automatic error recovery and task retries.