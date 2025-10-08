# How to Run Telegram AI Scraper in Monitoring Mode

## Complete Step-by-Step Guide

### Prerequisites Check
1. **System Requirements**:
   - Ubuntu/Linux system
   - Python 3.8+
   - Internet connection for API calls
   - Phone access for Telegram SMS verification

### New Streamlined Workflow

The setup process has been streamlined into two main commands:

1. **`./scripts/setup.sh`** - Complete one-time setup (includes Telegram auth)
2. **`./scripts/quick_start.sh`** - Start system (auto-detects auth needs)

### Step 1: Complete Setup (One-time only)

```bash
# Navigate to project directory
cd /home/ubuntu/TelegramScraper/telegram-ai-scraper

# Run comprehensive setup script
chmod +x scripts/setup.sh
./scripts/setup.sh
```

This script will:
- ✅ Create Python virtual environment (`telegram-ai-scraper_env/`)
- ✅ Install all dependencies from `requirements.txt`
- ✅ Install and start Redis server
- ✅ Create necessary directories (`logs/`, `data/`, etc.)
- ✅ Set file permissions
- ✅ **Guide you through configuration setup**
- ✅ **Automatically run Telegram authentication** (SMS verification)

**Interactive Setup Process:**
1. **Dependencies Installation** - Automatic
2. **Configuration Prompt** - You'll be asked to configure API keys
3. **Telegram Authentication** - SMS code verification (if config is ready)

### Step 1.5: Configuration (Guided Setup)

The setup script will guide you through configuration:

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

### Step 2: Start the System (Quick Start)

```bash
# Start everything with one command
chmod +x scripts/quick_start.sh
./scripts/quick_start.sh
```

**What this script does**:
1. ✅ Checks and starts Redis service
2. ✅ Activates virtual environment
3. ✅ **Auto-detects if Telegram authentication needed** (prompts if required)
4. ✅ Starts optimized Celery workers:
   - Main processing workers (memory-optimized)
   - Notification workers
   - SharePoint workers  
   - Backup workers
5. ✅ Starts Flower monitoring web UI at http://localhost:5555
6. ✅ Provides system status and next steps

**Expected Flow**:
- **First run after setup**: Should start immediately (auth already done)
- **After server restart**: Auto-detects everything and starts
- **If auth missing**: Prompts for Telegram SMS verification

### Step 2.5: System Verification (Optional)

```bash
# Test all connections and components
./scripts/run_app.sh test
```

This will test:
- ✅ Telegram API connection
- ✅ OpenAI API connection  
- ✅ Teams webhook connectivity
- ✅ SharePoint access
- ✅ Redis connectivity

### Step 3: Start Monitoring

```bash
# Start real-time monitoring
./scripts/run_app.sh monitor
```

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

## Quick Reference

### Most Common Commands

```bash
# First-time setup (includes Telegram auth)
./scripts/setup.sh

# Start after server restart
./scripts/quick_start.sh

# Check system status
./scripts/status.sh

# Start monitoring
./scripts/run_app.sh monitor

# Test connections
./scripts/run_app.sh test

# Monitor resources
./scripts/monitor_resources.sh
```

### Troubleshooting Commands

```bash
# Verify setup
./scripts/verify_setup.sh

# Manual Telegram authentication (if needed)
python3 scripts/telegram_auth.py

# Stop all services
./scripts/deploy_celery.sh stop

# View logs
tail -f logs/main.log
tail -f logs/celery_main_processor.log
```

## Alternative: Manual Step-by-Step Control

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
# Stop all workers and services (graceful)
./scripts/deploy_celery.sh stop

# Force stop immediately (if needed)
./scripts/deploy_celery.sh stop --force
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