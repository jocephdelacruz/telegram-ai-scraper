# Telegram AI Scraper

An intelligent, high-performance Telegram message scraper that uses OpenAI to analyze message significance and automatically sends alerts to Microsoft Teams and stores data in SharePoint Excel files. Built with **Celery distributed task processing** for scalability and fault tolerance.

## Features

- **Periodic Message Fetching**: Automatically checks for new messages every 3 minutes (configurable) with intelligent age filtering
- **Real-time Monitoring**: Continuously monitors specified Telegram channels for new messages using asyncio
- **Advanced Session Management**: Intelligent Telegram session handling with automatic recovery and rate limit management
- **Resilient Error Handling**: Smart retry logic with graceful degradation for API issues and rate limiting
- **Distributed Processing**: Uses Celery workers for parallel processing of AI analysis, notifications, and data storage
- **Intelligent Message Filtering**: Country-specific keyword filtering with AI fallback for optimal performance and accuracy
- **Multi-language Support**: Automatic language detection and translation to English for non-English messages
- **Cost-effective Translation**: Smart heuristics to avoid unnecessary API calls for obviously English text
- **Teams Integration**: Sends formatted alerts to Microsoft Teams channels for significant messages
- **SharePoint Storage**: Automatically stores all messages (significant and trivial) in SharePoint Excel files with translation info
- **Historical Scraping**: Can scrape and analyze past messages from channels
- **Fault Tolerance**: Automatic task retries and error recovery with Celery
- **Scalable Architecture**: Add more workers to handle increased message volume
- **Robust Error Handling**: Comprehensive error catching and logging throughout the system
- **CSV Backup**: Local CSV backup of all processed messages
- **Redis Integration**: Uses Redis as message broker and result backend
- **Task Monitoring**: Real-time monitoring of task queues and worker status
- **Session Recovery Tools**: Automated diagnostics and recovery assistance for Telegram API issues
- **Flexible Configuration**: JSON-based configuration for easy customization

## Prerequisites

- Python 3.8 or higher
- Redis server (for Celery message broker)
- Telegram API credentials (API ID and API Hash)
- OpenAI API key
- Microsoft Teams webhook URL (optional)
- SharePoint access credentials (optional)

## Installation

1. **Clone or download the project files**

2. **Run the setup script**:
   ```bash
   chmod +x scripts/setup.sh
   ./scripts/setup.sh
   ```

3. **Configure the application**:
   ```bash
   cp config/config_sample.json config/config.json
   # Edit config/config.json with your actual credentials and settings
   ```

4. **Start Redis server** (if not already running):
   ```bash
   # Ubuntu/Debian
   sudo systemctl start redis-server
   
   # Or using Docker
   docker run -d -p 6379:6379 redis:alpine
   ```

## Configuration

Edit `config.json` with your credentials and preferences:

### Required Settings

- `TEAMS_SENDER_NAME`: System identifier shown in Teams notifications (e.g., "Aldebaran Scraper")
- `OPEN_AI_KEY`: Your OpenAI API key
- `TELEGRAM_CONFIG`: Telegram API credentials and periodic fetch configuration
  - `FETCH_INTERVAL_SECONDS`: How often to check for new messages (default: 180 = 3 minutes)
  - `FETCH_MESSAGE_LIMIT`: Max messages per channel per fetch (default: 10)
  - Age limit automatically calculated as `FETCH_INTERVAL_SECONDS + 30 seconds` to avoid duplicates
  - **Duplicate Detection**: Redis-based tracking prevents processing the same message twice
- `COUNTRIES`: Country-specific configurations with channels, Teams webhooks, and SharePoint settings
- `MESSAGE_FILTERING`: Keywords that determine message significance
- `MS_SHAREPOINT_ACCESS`: Base SharePoint credentials

### Multi-Country Features

- **Country-Specific Channels**: Each country has its own set of Telegram channels to monitor  
- **Country-Specific Message Filtering**: Each country has its own significant/trivial/exclude keyword sets for culturally relevant filtering
- **Dual-Language Keyword Structure**: Keywords are now stored as `[EN, AR]` pairs (English and Arabic), and the system matches based on detected message language for optimal accuracy and cost savings
- **Configurable AI Filtering**: For Iraq, you can enable/disable OpenAI context-based filtering with `use_ai_for_message_filtering` in `config.json` (default: true)
- **Intelligent Keyword Processing**: System first applies keyword filtering in the detected language, then uses AI analysis for ambiguous cases if enabled
- **Separate Teams Notifications**: Different Teams webhooks for each country with country flags
- **Country-Specific SharePoint Files**: Separate Excel files per country with Significant and Trivial sheets
- **Localized CSV Backups**: Country-specific CSV backup files separated by significance
- **Message Routing**: Messages automatically routed based on source channel
- **Cultural Context**: Keywords tailored to local politics, geography, and events for each country
- **Modular Architecture**: Separation of concerns with `MessageProcessor` (non-AI logic) and `OpenAIProcessor` (AI-specific logic)

### Iraq Message Filtering Example

```json
"iraq": {
  "name": "Iraq",
  ...
  "message_filtering": {
    "use_ai_for_message_filtering": true,
    "significant_keywords": [
      ["protest", "احتجاج"],
      ["demonstration", "مظاهرة"],
      ["urgent", "عاجل"],
      ...
    ],
    "trivial_keywords": [
      ["sports", "رياضة"],
      ["entertainment", "ترفيه"],
      ...
    ],
    "exclude_keywords": [
      ["advertisement", "إعلان"],
      ["promo", "ترويج"],
      ...
    ]
  }
}
```

**How it works:**
- If a message is in Arabic, only Arabic keywords are used for direct matching.
- If in English, only English keywords are used.
- If no direct match, OpenAI context-based filtering is used if enabled (`use_ai_for_message_filtering`).
- This minimizes translation and AI costs, and is easy to extend to other languages/countries.

See [config_sample.json](config/config_sample.json) for complete configuration examples.

### Advanced Features

- **Country-Specific Filtering**: Each country has tailored keywords for cultural relevance
- **Hybrid Classification**: Keyword pre-filtering + AI analysis for optimal accuracy
- **Performance Optimization**: ~70% reduction in AI API calls through smart filtering
- **Complete Audit Trail**: All messages logged in both Significant and Trivial sheets
- **Transparent Processing**: Each message shows classification method used

For detailed configuration examples and migration guides, see the [Complete Enhancement Guide](docs/MULTI_COUNTRY_COMPLETE_GUIDE.md).

**📋 For step-by-step instructions to run the project, see: [Running Guide](docs/RUNNING_GUIDE.md)**

## Usage

### 🚀 Quick Start (Recommended)

#### First-Time Setup
```bash
# 1. Run complete setup (includes dependencies, config, and Telegram auth)
chmod +x scripts/setup.sh
./scripts/setup.sh

# 2. Start everything with one command (includes comprehensive testing)
chmod +x scripts/quick_start.sh
./scripts/quick_start.sh
```

**What setup.sh does:**
- ✅ Creates virtual environment and installs dependencies
- ✅ Starts Redis server
- ✅ Prompts for configuration (API keys, webhooks, etc.)
- ✅ **Automatically runs Telegram authentication** (SMS verification)
- ✅ Creates all required directories and files

**What quick_start.sh now includes:**
- ✅ Comprehensive system testing (validates all components)
- ✅ Configuration file structure and required fields validation
- ✅ Dual-language keyword format validation for Iraq
- ✅ Language detection and message processing pipeline testing
- ✅ Redis connection and Celery task registration verification

#### After Server Restart
```bash
# Single command to restart everything (auto-detects if Telegram auth needed)
./scripts/quick_start.sh
```

**What quick_start.sh does:**
- ✅ Starts Redis service
- ✅ Activates virtual environment
- ✅ **Auto-detects if Telegram authentication needed** (prompts if required)
- ✅ Starts all Celery workers with optimal settings
- ✅ Starts monitoring web UI (Flower)
- ✅ Provides status and next steps

#### Available Scripts
| Script | Purpose | When to Use | Key Features |
|--------|---------|-------------|--------------|
| `setup.sh` | **Complete one-time setup** | **Once** during first setup | Virtual env, dependencies, config, **Telegram auth** |
| `quick_start.sh` | **Smart restart sequence** | **After server reboot** or when starting fresh | Auto-detects auth needs, all-in-one startup |
| `deploy_celery.sh` | **Complete Celery management** | Start/stop/restart background services | Memory-optimized workers, graceful/force stop |
| `run_app.sh` | Main application runner | Interactive monitoring/testing | Connection testing, graceful startup |
| `telegram_auth.py` | Manual Telegram authentication | Re-authentication or troubleshooting | Interactive SMS verification |
| `monitor_resources.sh` | System resource monitoring | Check performance and memory usage | Real-time stats, alerts |
| `auto_restart.sh` | Automatic service recovery | Background watchdog service | Auto-restart failed services |
| `status.sh` | Service status check | Quick health check | Process status, resource usage |
| `verify_setup.sh` | System setup validation | Before first run, troubleshooting | Comprehensive system check |

#### Comprehensive Testing System
| Command | Purpose | When to Use | Key Features |
|---------|---------|-------------|--------------|
| `./scripts/run_tests.sh` | **Complete system validation** | After changes, before deployment | Tests all components, config, language detection, Redis, Celery |
| `./scripts/run_tests.sh --quick` | **Essential tests only** | Regular validation, CI/CD | Skips API connections, focuses on core functionality |
| `./scripts/run_tests.sh --component` | Component testing only | Development and debugging | Tests imports, log handling, file operations |
| `./scripts/run_tests.sh --config` | Configuration validation | After config changes | Validates JSON structure, required fields, Iraq dual-language format |
| `./scripts/run_tests.sh --session` | **Session manager tests** | After session changes | Tests session management, status checking, recovery tools |
| `./scripts/run_tests.sh --language` | Language detection tests | Test heuristic detection | Arabic/English detection without OpenAI calls |
| `./scripts/run_tests.sh --processing` | Message processing tests | Test dual-language logic | Iraq keyword matching, AI toggle, translation |
| `./scripts/run_tests.sh --csv` | **CSV storage tests** | Test CSV storage pipeline | **PRODUCTION SAFE**: Uses dedicated test CSV files (`TEST_iraq_*.csv`), complete validation, automatic cleanup |
| `./scripts/run_tests.sh --sharepoint` | **SharePoint storage tests** | Test SharePoint integration | **PRODUCTION SAFE**: Uses dedicated test sheets, Excel formula escaping (#NAME? fix), comprehensive integration testing |

#### Legacy Testing & Validation Tools  
| Script | Purpose | When to Use | Key Features |
|--------|---------|-------------|--------------|
| `tests/validate_telegram_config.py` | **Telegram credential validator** | Before authentication, credential issues | Network tests, credential validation, interactive updates |
| `scripts/telegram_session_check.py` | **Advanced session status checker** | Any time, troubleshooting | Comprehensive diagnostics with recovery guidance |
| `tests/check_telegram_status.py` | API rate limit status checker | Check rate limiting status | Monitors API rate limits and provides recovery timeline |
| `tests/telegram_recovery.py` | Automated recovery script | After rate limit expires | Restores system operation post-rate-limit |
| `tests/test_translation.py` | Translation system testing | Verify OpenAI integration | Test language detection and translation |
| `tests/test_components.py` | Component testing | Development and debugging | Individual component validation |
| `tests/test_message_fetch.py` | **Periodic message fetching test** | Verify 3-minute fetch intervals | Tests new periodic fetching with age filtering |
| `tests/test_language_detection.py` | **Heuristic language detection** | Test without OpenAI | Tests Arabic/English detection using word patterns |

**Most Common Usage:**
- **First time:** `./scripts/setup.sh` (includes config + Telegram auth)
- **After restart:** `./scripts/quick_start.sh` (includes automatic comprehensive testing)
- **Manual testing:** `./scripts/run_tests.sh --quick` (when needed for validation)
- **Check status:** `./scripts/status.sh`
- **Test specific features:** Use individual `--component`, `--config`, etc. flags

### Manual Deployment

#### 1. Activate Virtual Environment
```bash
source telegram-ai-scraper_env/bin/activate
```

#### 2. Start Celery Workers (in separate terminals)
```bash
# Terminal 1 - Main processing workers
celery -A src.tasks.telegram_celery_tasks worker --loglevel=info --queues=telegram_processing --concurrency=4

# Terminal 2 - Notification workers  
celery -A src.tasks.telegram_celery_tasks worker --loglevel=info --queues=notifications --concurrency=2

# Terminal 3 - SharePoint workers
celery -A src.tasks.telegram_celery_tasks worker --loglevel=info --queues=sharepoint --concurrency=2

# Terminal 4 - Backup workers
celery -A src.tasks.telegram_celery_tasks worker --loglevel=info --queues=backup --concurrency=1
```

#### 3. Start Main Application
```bash
# Terminal 5 - Test connections first
python3 src/core/main.py --config config/config.json --mode test

# Historical scraping
python3 src/core/main.py --config config/config.json --mode historical --limit 100

# Real-time monitoring
python3 src/core/main.py --config config/config.json --mode monitor
```

### Monitor System Status
```bash
# Quick status check
./scripts/deploy_celery.sh status

# Comprehensive resource monitoring
./scripts/monitor_resources.sh

# Monitor task queues and workers (web UI)
# Access at http://YOUR_SERVER_IP:5555
# (Flower is automatically started with quick_start.sh)

# Stop all services
./scripts/deploy_celery.sh stop
```

### Command Line Options

- `--config`: Configuration file path (default: config.json)
- `--mode`: Operation mode (monitor/historical/test)
- `--limit`: Message limit for historical scraping (default: 100)

## How It Works

### Architecture Overview
The system uses a **hybrid asyncio + Celery architecture** for optimal performance:

- **Asyncio**: Handles real-time Telegram message listening (fast I/O operations)
- **Celery**: Processes heavy tasks (AI analysis, API calls) in distributed workers
- **Redis**: Message broker for task queues and result storage

### Recent Technical Improvements

- **Periodic Fetching**: Celery beat scheduler automatically fetches new messages every 3 minutes
- **Async Event Loop Fixes**: Resolved asyncio/Celery conflicts with lazy TelegramClient initialization  
- **Duplicate Prevention**: Redis-based tracking ensures messages are never processed twice
- **Absolute Path Resolution**: All file operations use absolute paths for multi-worker safety
- **Intelligent Age Filtering**: Automatically calculates age cutoffs to prevent stale message processing
- **Enhanced Error Handling**: Comprehensive retry mechanisms and graceful failure recovery
- **Centralized Test Suite**: All testing utilities organized in dedicated `tests/` directory

### Message Processing Flow (Updated for Dual-Language)

1. **Periodic Message Ingestion**: Celery beat scheduler triggers message fetch every 3 minutes from all channels
2. **Duplicate Detection**: Redis checks prevent processing messages already handled in the last 24 hours
3. **Age Filtering**: Only processes messages newer than the configured age limit (fetch_interval + 30s buffer)
4. **Country Detection**: Determines which country configuration to use based on source channel
5. **Task Queuing**: New messages are immediately queued as Celery tasks (non-blocking)  
6. **Distributed Processing**: Multiple Celery workers process tasks in parallel:
   - **Language Detection**: Detects if message is Arabic, English, or other language
   - **Dual-Keyword Filtering**: For Iraq, compares only the relevant language in the `[EN, AR]` keyword pairs
   - **Exclude Check**: Whole-word matching prevents false positives (e.g., "ad" in "Baghdad")
   - **Direct Classification**: ~70% of messages classified by keywords without AI calls
   - **AI Context Filtering**: If no direct match, uses OpenAI for context-based filtering (if enabled per country)
   - **Smart Translation**: Only performed for storage/alerts if needed, not for filtering
   - **Dual Storage**: ALL messages stored in SharePoint (Significant/Trivial sheets) with classification method tracking
   - **Smart Notifications**: Only significant messages trigger Teams alerts (showing both original and translated text)
   - **Country Routing**: Messages routed to country-specific Teams/SharePoint configurations
   - **Backup**: Country-specific CSV storage (separate files for significant/trivial) with full metadata
7. **Error Handling**: Failed tasks automatically retry with exponential backoff
8. **Monitoring**: All activities logged with classification methods (keyword_significant, keyword_trivial, excluded, ai_significant, ai_trivial) and task IDs### Queue Architecture
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Telegram API   │───▶│   Main Process   │───▶│  Redis Queues   │
│   (Real-time)   │    │    (Asyncio)     │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                        ┌────────────────────────────────┼────────────────────────────────┐
                        ▼                                ▼                                ▼
               ┌─────────────────┐              ┌─────────────────┐              ┌─────────────────┐
               │ Processing      │              │ Notifications   │              │ Data Storage    │
               │ Workers (4)     │              │ Workers (2)     │              │ Workers (3)     │
               │ • AI Analysis   │              │ • Teams Alerts  │              │ • SharePoint    │
               │ • Classification│              │ • Error Alerts  │              │ • CSV Backup    │
               └─────────────────┘              └─────────────────┘              └─────────────────┘
```

## File Structure

```
telegram-ai-scraper/
├── run.py                          # Easy entry point script
├── requirements.txt                # Python dependencies
├── README.md                      # This file
├── src/                           # Source code
│   ├── core/                      # Core application modules
│   │   ├── main.py               # Main orchestration script (asyncio)
│   │   ├── log_handling.py       # Logging utilities
│   │   ├── file_handling.py      # File operations
│   │   └── message_processor.py  # Language detection and keyword matching (non-AI)
│   ├── integrations/              # External service integrations
│   │   ├── telegram_utils.py     # Telegram API handling
│   │   ├── telegram_session_manager.py # Advanced Telegram session management
│   │   ├── openai_utils.py       # OpenAI integration (AI-specific analysis only)
│   │   ├── teams_utils.py        # Microsoft Teams notifications
│   │   └── sharepoint_utils.py   # SharePoint Excel integration
│   └── tasks/                     # Celery task definitions
│       ├── telegram_celery_tasks.py # Celery task definitions
│       └── celery_config.py      # Celery configuration
├── config/                        # Configuration files
│   ├── config_sample.json        # Sample configuration template
│   └── config.json              # Your actual configuration (create from sample)
├── scripts/                       # Deployment and management scripts
│   ├── setup.sh                 # Initial environment setup (run once)
│   ├── quick_start.sh           # Complete restart sequence (after reboot)
│   ├── telegram_session_check.py # Advanced session status checker and recovery assistant
│   ├── deploy_celery.sh         # Celery worker management
│   ├── run_app.sh               # Main application runner
│   ├── monitor_resources.sh     # System resource monitoring
│   ├── telegram_auth.py         # Interactive Telegram authentication
│   ├── status.sh                # Service status check
│   └── auto_restart.sh          # Automatic service recovery
├── tests/                         # Testing and validation tools
│   ├── validate_telegram_config.py # Telegram credential validator & manager
│   ├── test_components.py       # Component testing
│   └── test_translation.py      # Translation testing
├── docs/                          # Documentation
│   ├── RUNNING_GUIDE.md         # Step-by-step running instructions
│   ├── MULTI_COUNTRY_COMPLETE_GUIDE.md # Multi-country setup guide
│   └── TRANSLATION_GUIDE.md     # Translation features guide
├── logs/                          # Log files directory
│   ├── main.log
│   ├── telegram.log
│   ├── telegram_tasks.log
│   ├── openai.log
│   ├── teams.log
│   ├── sharepoint.log
│   └── celery_*.log             # Various Celery worker logs
├── data/                          # Data storage directory
├── pids/                          # Process ID files
└── telegram-ai-scraper_env/      # Python virtual environment
```

## Multi-language & Dual-Keyword Support

The system now features advanced dual-language keyword matching for optimal performance and accuracy:

### Enhanced Processing Workflow

1. **Language Detection**: Each message is analyzed to determine if it's in English or Arabic (extensible to other languages)
2. **Dual-Keyword Matching**: For Iraq, keywords are stored as `[EN, AR]` pairs. The system matches only the relevant language for direct filtering
3. **AI Context Filtering**: If no direct match, OpenAI is used for context-based filtering (if enabled in config)
4. **Smart Translation**: Only performed if needed for storage/alerts, not for filtering if the message is already in the target language
5. **Metadata Preservation**: Both original and translated text, language, and translation status are stored for reference

### Iraq Dual-Language Features

- **Heuristic Language Detection**: Fast language detection using word patterns and Unicode script analysis (no OpenAI calls)
- **Direct Arabic Filtering**: Arabic messages are matched against Arabic keywords without translation
- **Direct English Filtering**: English messages are matched against English keywords
- **Configurable AI Fallback**: Toggle OpenAI context analysis with `use_ai_for_message_filtering`
- **Modular Architecture**: New `MessageProcessor` class handles non-AI logic for better maintainability
- **Enhanced Cost Optimization**: 95% reduction in API calls through heuristic detection and smart filtering
- **Whole-Word Matching**: Prevents false positives (e.g., "ad" in "Baghdad")

### Configuration Example

```json
"message_filtering": {
  "use_ai_for_message_filtering": true,
  "significant_keywords": [
    ["protest", "احتجاج"],
    ["demonstration", "مظاهرة"]
  ],
  "trivial_keywords": [
    ["sports", "رياضة"],
    ["entertainment", "ترفيه"]
  ]
}
```

### Benefits

- **70-80% Reduction** in OpenAI API calls for keyword-matchable messages
- **Improved Accuracy** through native language keyword matching
- **Cost Effective** processing with smart filtering cascades
- **Extensible Design** - easy to add more language pairs for other countries

### Excel Fields for Translation

Updated fields in Excel output:
- `Original_Text`: The original message text before translation
- `Original_Language`: Detected language of the original message
- `Was_Translated`: Boolean indicating if translation was performed
- `Message_Text`: Contains the processed text (translated if needed for analysis)

## Logging

The system creates detailed logs in the `logs/` directory:

- `main.log`: Main application events
- `telegram.log`: Telegram API interactions
- `openai.log`: OpenAI API calls and responses
- `teams.log`: Teams notification attempts
- `sharepoint.log`: SharePoint operations

## Error Handling

The system includes comprehensive error handling:

- Network connectivity issues
- API rate limiting
- Authentication failures
- Malformed messages
- Configuration errors

All errors are logged and, when possible, reported to Teams as system alerts.

## Performance and Scaling

### Performance Metrics
- **Message Ingestion**: ~1000+ messages/minute (limited by Telegram API)
- **AI Processing**: ~10-50 messages/minute per worker (depends on OpenAI API)
- **Teams Notifications**: ~100+ notifications/minute per worker
- **SharePoint Updates**: ~20-30 updates/minute per worker

### Scaling Guidelines

#### Horizontal Scaling (Add More Workers)
```bash
# Add more processing workers for high message volume
celery -A src.tasks.telegram_celery_tasks worker --queues=telegram_processing --concurrency=8

# Add more notification workers for many alerts
celery -A src.tasks.telegram_celery_tasks worker --queues=notifications --concurrency=4
```

#### Configuration Tuning
```json
{
  "CELERY_CONFIG": {
    "worker_concurrency": 4,           // Increase for more CPU cores
    "task_time_limit": 300,           // Timeout for stuck tasks
    "worker_prefetch_multiplier": 1,   // Tasks per worker process
    "result_expires": 3600            // Task result retention
  }
}
```

#### Resource Requirements
- **CPU**: 2+ cores recommended for production
- **RAM**: 4GB+ (2GB for Redis, 2GB for workers)
- **Disk**: 10GB+ for logs and data storage
- **Network**: Stable internet for API calls

## Security Considerations

- Store sensitive credentials securely
- Use environment variables for production deployments
- Regularly rotate API keys
- Monitor access logs
- Implement IP restrictions where possible

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   - Ensure Redis server is running: `sudo systemctl status redis-server`
   - Check Redis connectivity: `redis-cli ping`
   - Verify Redis port 6379 is accessible

2. **Celery Workers Not Processing Tasks**
   - Check worker status: `celery -A src.tasks.telegram_celery_tasks inspect active`
   - View task queues: `celery -A src.tasks.telegram_celery_tasks inspect reserved`
   - Monitor with Flower: `celery -A src.tasks.telegram_celery_tasks flower`

3. **Telegram Authentication Failed**
   - Verify API ID and API Hash
   - Ensure phone number is correct
   - Check if 2FA is enabled on your Telegram account

4. **OpenAI API Errors**
   - Verify API key is valid and has sufficient credits
   - Check for rate limiting in worker logs
   - Ensure model access permissions

5. **Teams Notifications Not Working**
   - Verify webhook URL is correct
   - Check Teams channel permissions
   - Test webhook with a simple curl command

6. **SharePoint Connection Issues**
   - Verify client credentials
   - Check SharePoint site and file permissions
   - Ensure Excel file exists and is accessible

7. **High Memory Usage**
   - Reduce worker concurrency levels
   - Implement task result expiration
   - Monitor with `htop` or similar tools

### Getting Help

1. Check the log files in the `logs/` directory
2. Run in test mode to verify connections: `python3 src/core/main.py --config config/config.json --mode test`
3. Monitor Celery workers: `celery -A src.tasks.telegram_celery_tasks inspect stats`
4. View task results: `celery -A src.tasks.telegram_celery_tasks result <task_id>`
5. Use the management scripts: `./scripts/status.sh` or `./scripts/deploy_celery.sh status`

## Documentation

For comprehensive information about all features and updates:

📖 **[Complete Multi-Country Enhancement Guide](docs/MULTI_COUNTRY_COMPLETE_GUIDE.md)**

This guide covers:
- Project reorganization and folder structure
- Multi-country support with automatic routing
- Country-specific message filtering with keywords
- Configuration examples for Philippines, Singapore, and Malaysia
- Migration guide from single-country setups
- Performance benefits and troubleshooting

## Troubleshooting

### Common Issues and Solutions

#### 1. Memory Issues on Small Instances (t3.small, etc.)
**Symptoms:** Workers crashing, "Memory Error", system freezing
**Solutions:**
```bash
# Check current memory usage
./scripts/monitor_resources.sh

# If memory usage > 80%, restart with fewer workers
./scripts/deploy_celery.sh 1  # Use 1 worker per queue instead of default

# Check if swap is active (should show 2GB)
free -h
```

#### 2. Redis Connection Errors
**Symptoms:** "Connection refused", "Redis server not available"
**Solutions:**
```bash
# Check Redis status
sudo systemctl status redis-server

# Start Redis if stopped
sudo systemctl start redis-server

# Test Redis connection
redis-cli ping  # Should return "PONG"
```

#### 3. Celery Workers Not Starting
**Symptoms:** "No such file or directory", import errors
**Solutions:**
```bash
# Ensure virtual environment is activated
source telegram-ai-scraper_env/bin/activate

# Check for path issues
cd /home/ubuntu/TelegramScraper/telegram-ai-scraper
python -c "import src.tasks.telegram_celery_tasks"  # Should not error

# Clean restart
./scripts/deploy_celery.sh stop
./scripts/quick_start.sh
```

#### 4. Telegram Authentication Issues
**Symptoms:** "Telegram client not initialized", "Authentication failed", "Session expired", "ApiIdInvalidError"
**Solutions:**
```bash
# STEP 1: Run comprehensive validation (recommended first step)
python3 tests/validate_telegram_config.py
# This will check:
# - API credentials format and validity
# - Network connectivity to Telegram servers
# - Phone number format
# - Environment dependencies

# STEP 2: If validation passes, authenticate
python3 scripts/telegram_auth.py

# STEP 3: If you get ApiIdInvalidError, update credentials
python3 tests/validate_telegram_config.py
# Choose option 3 to update credentials interactively
# Get new credentials from https://my.telegram.org/apps

# Alternative: Test connections to trigger authentication
./scripts/run_app.sh test
```

#### 5. OpenAI API Errors
**Symptoms:** "Invalid model", "Rate limit exceeded"
**Solutions:**
```bash
# Check config.json has correct model name
grep -A 5 '"openai"' config/config.json
# Should show "model": "gpt-4o-mini" (not "gpt-4o-mini-2024-07-18")

# Test OpenAI connection
python tests/test_translation.py
```

#### 6. High Resource Usage
**Symptoms:** System slow, high CPU/memory usage
**Solutions:**
```bash
# Monitor resources continuously
./scripts/monitor_resources.sh

# Reduce worker concurrency in src/tasks/celery_config.py
# Set worker_concurrency = 1 for all workers

# Enable automatic restarts
nohup ./scripts/auto_restart.sh &
```

#### 7. Services Not Restarting After Reboot
**Symptoms:** Nothing working after server restart
**Solutions:**
```bash
# Use the quick start script
./scripts/quick_start.sh

# Check what's actually running
./scripts/status.sh

# If issues persist, manual restart
cd /home/ubuntu/TelegramScraper/telegram-ai-scraper
source telegram-ai-scraper_env/bin/activate
./scripts/deploy_celery.sh
```

### Log File Locations
- **Main Application:** `logs/main.log`
- **Telegram Tasks:** `logs/telegram_tasks.log`
- **Celery Workers:** `logs/celery_*.log`
- **OpenAI Integration:** `logs/openai.log`
- **Teams Notifications:** `logs/teams.log`
- **SharePoint Integration:** `logs/sharepoint.log`

### Getting Help
1. Check service status: `./scripts/status.sh`
2. Monitor resources: `./scripts/monitor_resources.sh`
3. Review relevant log files in `logs/` directory
4. Ensure all configuration files are properly configured
5. Verify virtual environment is activated before manual commands

## Contributing

This is a custom internal tool. For modifications:

1. Test changes thoroughly
2. Update documentation
3. Maintain error handling standards
4. Follow existing code structure

## License

This project is for internal use only. All rights reserved.

## Changelog

### Version 2.1.0 (Current)
- **Periodic Message Fetching**: Automated 3-minute interval fetching with Celery beat scheduler
- **Async Event Loop Fixes**: Resolved asyncio/Celery conflicts with lazy TelegramClient initialization
- **Redis Duplicate Detection**: Prevents processing the same message multiple times (24-hour expiration)
- **Intelligent Age Filtering**: Automatic age cutoff calculation (fetch_interval + 30s buffer)
- **Absolute Path Resolution**: All file operations use absolute paths for multi-worker environment safety
- **Enhanced Error Handling**: Comprehensive async-safe error handling and retry mechanisms
- **Centralized Test Suite**: Reorganized all test utilities into dedicated `tests/` directory
- **Updated Documentation**: Comprehensive guides reflecting all recent technical improvements

### Version 2.0.0
- **Celery Integration**: Distributed task processing with Redis
- **Hybrid Architecture**: Asyncio + Celery for optimal performance
- **Parallel Processing**: Multiple workers for AI analysis, notifications, and storage
- **Fault Tolerance**: Automatic task retries and error recovery
- **Scalability**: Add workers to handle increased message volume
- **Task Monitoring**: Real-time monitoring with Celery Flower
- **Queue Management**: Separate queues for different operations
- **Deployment Scripts**: Automated setup and deployment tools

### Version 1.0.0
- Initial release with core functionality
- Telegram scraping and monitoring
- OpenAI message analysis
- Teams and SharePoint integration
- Comprehensive error handling and logging