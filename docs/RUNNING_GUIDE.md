# How to Run Telegram AI Scraper with Session-Safe Architecture

## Complete Step-by-Step Guide

**🔄 Architecture Change Notice**: The system now uses a session-safe Celery Beat architecture where all Telegram operations are handled by the background scheduler. This prevents session conflicts and phone disconnections.

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
   "TEAMS_SENDER_NAME": "Aldebaran Scraper",
   "TEAMS_ADMIN_WEBHOOK": "https://your-admin-teams-webhook-url-here",
   "TEAMS_ADMIN_CHANNEL": "Admin Alerts",
   "OPEN_AI_KEY": "sk-your-actual-openai-key-here",
   "DATA_RETENTION_DAYS": 7,
   
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
5. ✅ **Starts Celery Beat scheduler** (handles all periodic message fetching)
6. ✅ Starts Flower monitoring web UI at http://localhost:5555
7. ✅ Provides system status and next steps

**Expected Flow**:
- **First run after setup**: Should start immediately (auth already done)
- **After server restart**: Auto-detects everything and starts
- **If auth missing**: Prompts for Telegram SMS verification

### Step 2.5: System Verification (Optional)

```bash
# Test all connections and components
./scripts/run_tests.sh --quick
```

This will test:
- ✅ Telegram API connection
- ✅ OpenAI API connection  
- ✅ Teams webhook connectivity
- ✅ SharePoint access
- ✅ Redis connectivity

**Comprehensive Test Suite (Advanced)**:
```bash
# Run complete test suite with all integrations
./scripts/run_tests.sh

# Test specific components
./scripts/run_tests.sh --sharepoint    # SharePoint integration tests (PRODUCTION SAFE)
./scripts/run_tests.sh --csv           # CSV storage tests (PRODUCTION SAFE)  
./scripts/run_tests.sh --admin-teams   # Admin Teams webhook connectivity tests
./scripts/run_tests.sh --config        # Configuration validation
./scripts/run_tests.sh --quick         # Essential tests only
```

The SharePoint tests now include:
- ✅ Connection & Authentication
- ✅ Excel Formula Escaping (fixes #NAME? errors)
- ✅ Header Creation (in dedicated test sheets)
- ✅ Row Detection & Management  
- ✅ Data Writing with Escaping
- ✅ Celery Task Integration
- ✅ High Row Number Validation
- 🛡️ **Production Data Protection**: Uses `TEST_Significant` and `TEST_Trivial` sheets
- 🧹 **Complete Cleanup**: Test sheets completely deleted after testing (no clutter)

**IMPORTANT**: Both SharePoint and CSV tests are completely safe for production environments. 
- **SharePoint tests** create and use dedicated test sheets (`TEST_Significant`, `TEST_Trivial`) and automatically clean up all test data. Your production data in the `Significant` and `Trivial` sheets will never be modified or deleted.
- **CSV tests** create and use dedicated test CSV files (`TEST_iraq_significant_messages.csv`, `TEST_iraq_trivial_messages.csv`) and automatically delete them after testing. Your production CSV files (`iraq_significant_messages.csv`, `iraq_trivial_messages.csv`) remain untouched.

### Step 3: System is Now Running (Automated)

With the new architecture, **no manual monitoring command is needed**. The system automatically runs in the background via Celery Beat:

```bash
# Check system status to verify everything is running
./scripts/status.sh

# View monitoring interface (if needed)
# Open browser to: http://localhost:5555 (Flower UI)
```

**What's Running Automatically:**
- 🔄 **Celery Beat**: Fetches messages every 3 minutes from all channels
- 👥 **Worker Pool**: Processes messages, sends Teams alerts, stores in SharePoint
- 🌸 **Flower UI**: Monitor tasks and workers at http://localhost:5555

### Step 3.5: Admin Teams Monitoring Setup

The system includes a centralized admin Teams channel for critical alerts and system monitoring. This is separate from country-specific notification channels.

**Admin Teams Channel Benefits**:
- **System-Wide Monitoring**: Monitors the entire application, not just individual countries
- **Critical Exception Alerts**: Get notified immediately when core services encounter errors
- **Service Failure Notifications**: Alerts for Telegram API failures, SharePoint issues, OpenAI errors
- **Celery Task Monitoring**: Notifications when background tasks fail after retries
- **Resource Monitoring**: Alerts when system resources exceed thresholds

**Testing Admin Teams Connection**:
```bash
# Test admin Teams webhook connectivity
python3 tests/test_admin_teams_connection.py

# Or test as part of full suite
python3 scripts/run_tests.py --admin-teams
```

**Expected Admin Notifications**:
- System startup/shutdown messages
- Critical exceptions with stack traces
- Service failures with recovery suggestions
- Celery worker status changes
- Configuration errors
- Resource threshold alerts

### Step 4: Monitor the System

The system now runs automatically in the background. Check status with:

```bash
./scripts/status.sh
```

You'll see output like:
```
==========================================
Telegram AI Scraper - System Status
==========================================

✅ Redis: Running (PID: 1234)
✅ Celery Beat: Running (PID: 5678) - Periodic message fetching
✅ Processing Workers: 4 active
✅ Notification Workers: 2 active  
✅ SharePoint Workers: 2 active
✅ Backup Workers: 1 active
✅ Flower UI: http://localhost:5555

📊 System Health: GOOD
🔄 Last Message Fetch: 2 minutes ago
📨 Messages Processed Today: 127
⚡ Session Status: Active (Age: 5 days)
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

# Test connections and components
./scripts/run_tests.sh --quick

# Or run comprehensive test suite
./scripts/run_tests.sh

# Monitor resources
./scripts/monitor_resources.sh
```

### Troubleshooting Commands

```bash
# Verify setup
./scripts/verify_setup.sh

# 🔐 Session Management (RECOMMENDED - Unified Interface)
./scripts/telegram_session.sh status      # Check session status
./scripts/telegram_session.sh test        # Test session validity
./scripts/telegram_session.sh auth        # Authenticate new session
./scripts/telegram_session.sh renew       # Renew existing session
./scripts/telegram_session.sh safety-check # Check for conflicts
./scripts/telegram_session.sh diagnostics # Full diagnostics
./scripts/telegram_session.sh help        # Show all options

# Telegram credential validation (before session operations)
python3 tests/validate_telegram_config.py
# - Comprehensive validation of API credentials
# - Network connectivity testing
# - Interactive credential updates
# - Environment dependency checking

# Stop all services
./scripts/deploy_celery.sh stop

# View logs
tail -f logs/main.log
tail -f logs/celery_main_processor.log
```

## Alternative: Manual Step-by-Step Control

If you prefer manual control over each component:

#### A. Start Workers and Beat Scheduler Individually
```bash
# Activate environment first
source telegram-ai-scraper_env/bin/activate

# Terminal 1 - Beat scheduler (REQUIRED for message fetching)
celery -A src.tasks.telegram_celery_tasks beat --loglevel=info

# Terminal 2 - Main processing
celery -A src.tasks.telegram_celery_tasks worker --loglevel=info --queues=telegram_processing --concurrency=4 --hostname=main@%h

# Terminal 3 - Notifications  
celery -A src.tasks.telegram_celery_tasks worker --loglevel=info --queues=notifications --concurrency=2 --hostname=notifications@%h

# Terminal 4 - SharePoint
celery -A src.tasks.telegram_celery_tasks worker --loglevel=info --queues=sharepoint --concurrency=2 --hostname=sharepoint@%h

# Terminal 5 - Backup
celery -A src.tasks.telegram_celery_tasks worker --loglevel=info --queues=backup --concurrency=1 --hostname=backup@%h
```

#### B. Test System Components (Optional)
```bash
# Terminal 6 - Test connections and components
python3 src/core/main.py --config config/config.json --mode test

# Or run comprehensive test suite
./scripts/run_tests.sh
```

**Important**: With the new architecture, **main.py no longer handles monitoring**. All message fetching is done by Celery Beat scheduler automatically.

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

#### Telegram API Issues

The system now includes advanced session management with intelligent recovery:

```bash
# Check comprehensive session status with recovery guidance
python3 scripts/telegram_session_check.py

# Check current API rate limits
python3 tests/check_telegram_status.py

# Automated recovery after rate limit expires
python3 tests/telegram_recovery.py

# Manual re-authentication if needed
python3 scripts/telegram_auth.py
```

**Key Improvements:**
- **Smart Session Management**: Sessions now last weeks/months instead of frequent re-authentication
- **Automatic Rate Limit Handling**: System gracefully handles rate limits without crashing
- **Intelligent Recovery**: Automated diagnostics and recovery guidance
- **Prevention**: Enhanced error handling prevents future cascading failures

#### Telegram Authentication Issues
```bash
# STEP 1: Always run validation first
python3 tests/validate_telegram_config.py
# This checks everything: credentials, network, environment

# STEP 2: If you get "ApiIdInvalidError" or credential issues:
# Choose option 3 in the validation tool to update credentials
# Or manually get new credentials from https://my.telegram.org/apps

# STEP 3: After credentials are fixed, authenticate:
python3 scripts/telegram_auth.py

# STEP 4: Clean session if needed:
rm telegram_session.session  # Forces fresh authentication
```

#### Config File Issues
```bash
# Validate JSON syntax
python3 -c "import json; json.load(open('config/config.json'))"
```

### Expected Behavior in Monitoring Mode

When running correctly, you should see:

1. **System Startup**: All workers and Beat scheduler initialize
2. **Periodic Fetching**: Beat scheduler fetches messages every 3 minutes automatically
3. **Message Processing**: New messages trigger distributed Celery tasks
4. **AI Analysis**: Messages analyzed for significance using country-specific filters
5. **Notifications**: Significant messages sent to Teams
6. **Storage**: All messages stored in SharePoint (Significant/Trivial sheets) and CSV backups
7. **Session Safety**: No session conflicts - only Beat scheduler accesses Telegram
8. **Logging**: Detailed logs show processing activity

### Key Log Files to Monitor

- `logs/main.log` - Main application events (testing and initialization only)
- `logs/celery_beat.log` - Periodic message fetching by Beat scheduler
- `logs/celery_main_processor.log` - Message processing tasks
- `logs/celery_notifications.log` - Teams notifications
- `logs/celery_sharepoint.log` - SharePoint operations
- `logs/telegram.log` - Telegram API interactions
- `logs/openai.log` - AI analysis results

The system is designed to run continuously with **session-safe periodic fetching**, processing messages automatically with error recovery and task retries.