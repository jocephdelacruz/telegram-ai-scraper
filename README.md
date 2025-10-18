# Telegram AI Scraper

An intelligent, high-performance Telegram message scraper that uses OpenAI to analyze message significance and automatically sends alerts to Microsoft Teams and stores data in SharePoint Excel files. Built with **Celery distributed task processing** for scalability and fault tolerance.

## Features

- **🚀 Efficient Message Fetching**: Redis-based tracking with CSV fallback - **80-95% reduction in API calls**
- **Session-Safe Architecture**: Celery Beat scheduler handles all Telegram operations to prevent session conflicts
- **⚡ Smart Message Processing**: Only fetches truly new messages, preventing rate limiting with multiple channels
- **Advanced Session Management**: Intelligent Telegram session handling with automatic recovery and rate limit management
- **Session Safety System**: Prevents session invalidation through concurrent access protection and unified session management
- **Resilient Error Handling**: Smart retry logic with graceful degradation for API issues and rate limiting
- **Distributed Processing**: Uses Celery workers for parallel processing of AI analysis, notifications, and data storage
- **Intelligent Message Filtering**: Country-specific keyword filtering with AI fallback for optimal performance and accuracy
- **AI Exception Filtering**: Advanced AI-powered filtering to reduce false positives from news about other countries
- **Enhanced Language Detection**: Improved Arabic language detection with mixed-content analysis
- **Advanced Translation Architecture**: Modular translation system with Google Translate (free) and OpenAI (paid) backends
- **Smart Translation Control**: Configure whether to translate trivial messages and which translation method to use
- **Optimized Language Detection**: Reuses language detection from message analysis to avoid redundant API calls
- **Teams Integration**: Sends formatted alerts to Microsoft Teams channels for significant messages
- **SharePoint Storage**: Automatically stores all messages (significant and trivial) in SharePoint Excel files with translation info
- **Enhanced SharePoint Reliability**: Advanced session management with validation, multi-attempt initialization, timeout handling, and exponential backoff retry logic
- **Fault Tolerance**: Automatic task retries and error recovery with Celery
- **Scalable Architecture**: Add more workers to handle increased message volume
- **Robust Error Handling**: Comprehensive error catching and logging throughout the system
- **CSV Backup**: Local CSV backup of all processed messages
- **Redis Integration**: Uses Redis as message broker and result backend with intelligent tracking
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

## SharePoint Integration Reliability

The system features **enterprise-grade SharePoint reliability** with comprehensive error handling and session management to prevent data loss and service interruptions.

### Enhanced Session Management
- **Session Validation**: Automatic health checks before each operation
- **Multi-Attempt Initialization**: Up to 3 attempts for session creation with exponential backoff
- **Timeout Handling**: Configurable timeouts (30-45 seconds) for API calls
- **Authentication Recovery**: Automatic token refresh and authentication retry logic
- **Graceful Degradation**: Proper error handling with detailed logging for troubleshooting

### Fault Tolerance Features
- **Exponential Backoff**: Celery tasks retry with 180-second intervals and exponential delays
- **Maximum Retry Logic**: Up to 5 attempts for transient failures
- **Error Classification**: Different handling for authentication vs. network vs. service errors
- **Session Cleanup**: Proper resource cleanup on failures to prevent resource leaks
- **Comprehensive Logging**: Detailed logging of all SharePoint operations for monitoring

### Data Integrity Protection
- **Atomic Operations**: Each Excel update is atomic to prevent partial writes
- **Error Recovery**: Failed operations trigger admin notifications without data loss
- **Backup Integration**: CSV backups ensure no data is lost during SharePoint outages
- **Health Monitoring**: Continuous monitoring with Teams notifications for issues

### Performance Optimization
- **Connection Reuse**: Efficient session management reduces API call overhead
- **Batch Operations**: Optimized for handling high-volume message processing
- **Resource Management**: Proper cleanup prevents memory leaks in long-running processes

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
- `TEAMS_ADMIN_WEBHOOK`: Microsoft Teams webhook URL for admin alerts and system notifications
- `TEAMS_ADMIN_CHANNEL`: Name of the admin Teams channel (e.g., "Admin Alerts")
- `OPEN_AI_KEY`: Your OpenAI API key
- `TELEGRAM_CONFIG`: Telegram API credentials and periodic fetch configuration
  - `FETCH_INTERVAL_SECONDS`: How often to check for new messages (default: 240 = 4 minutes)
  - `FETCH_MESSAGE_LIMIT`: Max messages per channel per fetch (default: 10)
  - Age limit automatically calculated as `FETCH_INTERVAL_SECONDS + 30 seconds` to avoid duplicates
  - **Duplicate Detection**: Redis-based tracking prevents processing the same message twice
- `COUNTRIES`: Country-specific configurations with channels, Teams webhooks, and SharePoint settings
- `MESSAGE_FILTERING`: Keywords that determine message significance
- `MS_SHAREPOINT_ACCESS`: Base SharePoint credentials

### Admin Teams Channel Integration

The system includes a **global admin Teams channel** for critical system monitoring and alerting. This channel uses a self-contained notification system that automatically loads configuration and sends alerts from anywhere in the codebase without requiring configuration parameter passing.

**Key Features:**
- **Global Admin Notifier**: Automatically loads configuration and provides system-wide admin notifications
- **Convenient Functions**: Simple functions like `send_critical_exception()` and `send_service_failure()` that can be called from any module
- **Intelligent Error Detection**: Automatically detects and reports various types of system issues
- **No Configuration Coupling**: Classes no longer need config parameters just for admin notifications

#### What Gets Reported

- **Critical Exceptions**: All unhandled exceptions from core services and integrations
- **Service Failures**: When key services (Telegram API, SharePoint, OpenAI) fail to operate
- **Celery Task Failures**: When background tasks fail after all retries are exhausted
- **System Startup/Shutdown**: When the system starts or stops, with component status
- **Configuration Errors**: Invalid configuration files or missing settings
- **Resource Alerts**: When system resources (CPU, memory, disk) exceed thresholds

#### Admin Channel Configuration

```json
{
  "TEAMS_ADMIN_WEBHOOK": "https://your-tenant.webhook.office.com/webhookb2/...",
  "TEAMS_ADMIN_CHANNEL": "Admin Alerts"
}
```

#### Usage Examples

```python
# From anywhere in the codebase, simply import and use:
from src.integrations.teams_utils import send_critical_exception, send_service_failure

# Send critical exception alert
send_critical_exception(
    "DatabaseError", 
    "Connection to database failed", 
    "my_module.py"
)

# Send service failure alert
send_service_failure(
    "OpenAI API", 
    "API quota exceeded", 
    impact_level="HIGH"
)
```

#### Benefits of Global Admin Channel

- **Project-Wide Monitoring**: Unlike country-specific channels, this monitors the entire system
- **Simplified Architecture**: No need to pass config objects just for admin notifications
- **Early Problem Detection**: Get notified immediately when issues occur
- **Intelligent Alerting**: Prevents spam by batching similar errors and using thresholds
- **Rich Context**: Detailed error information including stack traces and system context
- **Self-Contained**: Automatically loads configuration when needed

#### Testing Admin Teams Connection

```bash
# Test comprehensive admin Teams connectivity (includes both global functions and direct methods)
python3 tests/test_admin_teams_connection.py

# Or run as part of full test suite
python3 scripts/run_tests.py --admin-teams

# Quick test of specific functions
python3 -c "from src.integrations.teams_utils import send_critical_exception; send_critical_exception('Test', 'Quick test', 'console')"
```

### Multi-Country Features

- **Country-Specific Channels**: Each country has its own set of Telegram channels to monitor  
- **Country-Specific Message Filtering**: Each country has its own significant/trivial/exclude keyword sets for culturally relevant filtering
- **Dual-Language Keyword Structure**: Keywords are now stored as `[EN, AR]` pairs (English and Arabic), and the system matches based on detected message language for optimal accuracy and cost savings
- **Configurable AI Filtering**: For Iraq, you can enable/disable OpenAI context-based filtering with `use_ai_for_message_filtering` in `config.json` (default: true)
- **AI Additional Criteria**: Advanced system to ensure messages are truly relevant to the target country using `use_ai_for_enhanced_filtering` and `additional_ai_criteria`
- **Intelligent Keyword Processing**: System first applies keyword filtering in the detected language, then uses AI analysis for ambiguous cases if enabled
- **Separate Teams Notifications**: Different Teams webhooks for each country with country flags
- **Country-Specific SharePoint Files**: Separate Excel files per country with Significant and Trivial sheets
- **Localized CSV Backups**: Country-specific CSV backup files separated by significance
- **Message Routing**: Messages automatically routed based on source channel
- **Cultural Context**: Keywords tailored to local politics, geography, and events for each country
- **Modular Architecture**: Separation of concerns with `MessageProcessor` (non-AI logic) and `OpenAIProcessor` (AI-specific logic)

### Advanced Translation System

The system now features a **sophisticated translation architecture** that separates message analysis from translation processing:

#### Translation Configuration Options

```json
"message_filtering": {
  "use_ai_for_message_filtering": false,
  "translate_trivial_msgs": true,
  "use_ai_for_translation": false,
  "use_ai_for_enhanced_filtering": false,
  "additional_ai_criteria": [
    "The message discusses news or events that either happened inside Iraq, directly affects or involves Iraq",
    "The message is about Iraqi citizens, Iraqi entities, or Iraqi government actions",
    "The message relates to economic, political, security, or social developments in Iraq",
    "The message has relevance to Iraq's regional relationships or international affairs"
  ]
}
```

- **`translate_trivial_msgs`**: Control whether to translate trivial messages (saves costs)
- **`use_ai_for_translation`**: Choose between Google Translate (free) and OpenAI (paid)
- **`use_ai_for_enhanced_filtering`**: Enable AI-based additional criteria to ensure relevance to target country
- **`additional_ai_criteria`**: List of criteria that must ALL be met for messages to remain significant

#### Translation Methods

| Method | Cost | Quality | Speed | Best For |
|--------|------|---------|-------|----------|
| **Google Translate** | Free (rate limited) | Good | Fast | High-volume processing |
| **OpenAI Translation** | Paid (API credits) | Excellent | Moderate | Critical messages, quality focus |

#### Key Benefits

- **No Redundant Detection**: Reuses language detection from message significance analysis
- **Flexible Translation Control**: Skip translation for trivial messages to reduce costs
- **Automatic Fallback**: Google Translate failures automatically fall back to OpenAI
- **Optimized Performance**: Eliminates duplicate language detection API calls
- **Modular Design**: Easy to add new translation backends (Azure, DeepL, etc.)

#### Processing Flow

1. **Message Analysis**: Detect language and determine significance using keywords/AI
2. **Translation Decision**: Based on significance and `translate_trivial_msgs` setting
3. **Translation Execution**: Use configured method (Google/OpenAI) with known source language
4. **Storage & Alerts**: Store both original and translated text, send appropriate notifications

### AI Exception Filtering System

The **AI Exception Filtering** system reduces false positives by filtering out messages that match keywords but are not actually relevant to the target country. This is especially useful for international news that mentions significant keywords but relates to other countries.

#### When to Enable

Enable AI exception filtering when you experience:
- News about other countries being classified as significant
- International events appearing as locally relevant
- Foreign political developments being categorized incorrectly
- High volume of false positives from global news sources

#### Configuration

```json
"message_filtering": {
  "use_ai_for_enhanced_filtering": true,
  "additional_ai_criteria": [
    "The message discusses news or events that either happened inside Iraq, directly affects or involves Iraq",
    "The message is about Iraqi citizens, Iraqi entities, or Iraqi government actions",
    "The message relates to economic, political, security, or social developments in Iraq",
    "The message has relevance to Iraq's regional relationships or international affairs"
  ]
}
```

#### How It Works

1. **Keyword Matching**: Message first goes through normal keyword analysis
2. **Additional Criteria Check**: If `use_ai_for_enhanced_filtering` is enabled, AI verifies ALL additional criteria are met
3. **Geographic Relevance**: AI determines if the message truly relates to the target country
4. **Final Classification**: Messages failing any criteria are marked as trivial, ensuring only relevant content

#### Example Scenarios

| Message | Keywords Match | Additional Criteria | Final Result |
|---------|---------------|-------------------|--------------|
| "Breaking: Cyber attack in Syria" | ✅ "Breaking", "Cyber attack" | ❌ Not Iraq-related | Trivial |
| "Urgent: Baghdad airport security breach" | ✅ "Urgent", "security" | ✅ Iraq-specific event | Significant |
| "Iran announces new trade policies" | ✅ "announces" | ❌ Foreign policy only | Trivial |

For detailed configuration and examples, see [AI Criteria Migration Summary](docs/AI_CRITERIA_MIGRATION_SUMMARY.md).

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

### Field Exclusion Configuration

The system now supports **configurable field exclusions** for Teams notifications and SharePoint Excel files, allowing you to customize what information is displayed to end users while preserving complete data in CSV files.

#### Configuration Fields

```json
{
  "TELEGRAM_EXCEL_FIELDS": [
    "Message_ID", "Channel", "Message_URL", "Country", "Date", "Time", "Author", "Message_Text", 
    "Attached_Links", "AI_Category", "AI_Reasoning", "Keywords_Matched", "Message_Type", 
    "Forward_From", "Media_Type", "Original_Text", "Original_Language", 
    "Was_Translated", "Processed_Date"
  ],
  "EXCLUDED_TEAMS_FIELDS": [
    "Country", "AI_Category", "Message_Type", "Forward_From", "Media_Type", 
    "Was_Translated", "Processed_Date", "Author"
  ],
  "EXCLUDED_SHAREPOINT_FIELDS": [
    "Country", "AI_Category", "Message_Type", "Forward_From", "Media_Type", 
    "Was_Translated", "Processed_Date", "Author"
  ]
}
```

#### How It Works

- **TELEGRAM_EXCEL_FIELDS**: Master list of all available fields (19 total)
- **EXCLUDED_TEAMS_FIELDS**: Fields to hide from Teams notifications (configurable)
- **EXCLUDED_SHAREPOINT_FIELDS**: Fields to hide from SharePoint Excel files (configurable)
- **CSV Files**: Always preserve all fields from `TELEGRAM_EXCEL_FIELDS` for complete data integrity

#### Default Exclusions

By default, the following technical fields are excluded from user-facing Teams and SharePoint outputs:
- `Country`: Redundant (shown in title/context)
- `AI_Category`: Internal classification
- `Message_Type`: Technical metadata
- `Forward_From`: Technical forwarding info
- `Media_Type`: Technical media info
- `Was_Translated`: Internal processing flag
- `Processed_Date`: Internal timestamp
- `Author`: Redundant with Channel in Telegram context

#### Customization

To show additional fields in Teams or SharePoint, simply remove them from the excluded fields arrays in `config.json`. For example, to show Country information in Teams notifications:

```json
"EXCLUDED_TEAMS_FIELDS": [
  "AI_Category", "Message_Type", "Forward_From", "Media_Type", 
  "Was_Translated", "Processed_Date", "Author"
]
```

#### Benefits

- **User-Friendly Display**: Teams and SharePoint show only relevant information
- **Complete Data Preservation**: CSV files maintain all fields for future database migration
- **Easy Customization**: Modify exclusions in config.json without code changes
- **Flexible Architecture**: Different exclusions for Teams vs SharePoint if needed

### Advanced Features

- **Country-Specific Filtering**: Each country has tailored keywords for cultural relevance
- **Hybrid Classification**: Keyword pre-filtering + AI analysis for optimal accuracy
- **Performance Optimization**: ~70% reduction in AI API calls through smart filtering
- **Complete Audit Trail**: All messages logged in both Significant and Trivial sheets
- **Transparent Processing**: Each message shows classification method used

For detailed configuration examples and migration guides, see the [Complete Enhancement Guide](docs/MULTI_COUNTRY_COMPLETE_GUIDE.md).

**📋 For step-by-step instructions to run the project, see: [Running Guide](docs/RUNNING_GUIDE.md)**

## 🚀 Efficient Message Fetching System

The system now features an **intelligent message fetching system** that dramatically reduces Telegram API calls and prevents rate limiting, especially critical when monitoring multiple channels.

### 🎯 Performance Benefits

**Before (Original System)**:
- Always fetches 10 messages per channel per cycle
- Processes many duplicate and old messages
- 24 channels × 10 messages × 360 cycles/day = **86,400 API calls/day**
- High risk of rate limiting with multiple channels

**After (Efficient System)**:
- Only fetches messages newer than last processed ID
- Uses Redis tracking + CSV fallback for reliability  
- 24 channels × ~2 new messages × 360 cycles/day = **17,280 API calls/day**
- **80-95% reduction in API calls!**

### 🔧 How It Works

1. **Redis Tracking**: Stores the last processed message ID for each channel
2. **CSV Fallback**: When Redis is unavailable, checks CSV files for the highest message ID
3. **Conservative Final Fallback**: Uses original `FETCH_INTERVAL_SECONDS` method only when both Redis and CSV fail
4. **4-Hour Age Limit**: Absolute cutoff prevents processing very old messages (configurable via `MAX_MESSAGE_AGE_HOURS`)
5. **Duplicate Prevention**: Redis-based deduplication ensures no message is processed twice

### ⚙️ Configuration

The system works automatically with your existing configuration:

```json
{
  "TELEGRAM_CONFIG": {
    "FETCH_INTERVAL_SECONDS": 240,  // Used for conservative fallback only
    "FETCH_MESSAGE_LIMIT": 10       // Used for conservative fallback only
  }
}
```

### 📊 Monitoring

The system provides detailed logging to show efficiency gains:

```log
🚀 Using EFFICIENT tracking-based fetching (Redis + CSV fallback)
🔍 Found Redis tracking for @channel: 87884
📥 Fetching messages from @channel newer than ID 87884
✅ Retrieved 2 NEW messages (checked 2, skipped 0 too old, 0 already processed)
💾 Updated Redis tracking for @channel: 87891
```

### 🧪 Testing

```bash
# Test the efficient fetching system
python3 tests/test_efficient_fetching.py

# Or run as part of full test suite (includes efficiency validation)
./scripts/run_tests.sh --efficient-fetching
```

### 🔄 Fallback Strategy

1. **Primary**: Redis tracking (most efficient)
2. **Secondary**: CSV file analysis (reliable when Redis unavailable)
3. **Tertiary**: Original time-based method (prevents duplication when both fail)

This triple-fallback system ensures reliability while maximizing efficiency. For detailed technical information, see [EFFICIENT_FETCHING_SYSTEM.md](docs/EFFICIENT_FETCHING_SYSTEM.md).

## Session Safety System 🛡️

The system includes **comprehensive session safety protection** to prevent Telegram session invalidation that disconnects your phone's Telegram app.

### 🔐 Unified Session Management

The system provides a comprehensive **telegram_session.sh** wrapper script that consolidates all session operations with built-in safety protection:

```bash
# All session operations through one unified interface
./scripts/telegram_session.sh status      # Check session status and age
./scripts/telegram_session.sh test        # Test if session works (safe)
./scripts/telegram_session.sh auth        # Authenticate new session
./scripts/telegram_session.sh renew       # Renew existing session (safe)
./scripts/telegram_session.sh backup      # Create session backup
./scripts/telegram_session.sh restore     # Restore from backup
./scripts/telegram_session.sh safety-check # Check for conflicts
./scripts/telegram_session.sh diagnostics # Full session diagnostics
./scripts/telegram_session.sh help        # Show all available options
```

**Key Benefits:**
- ✅ **Unified Interface**: All session operations through one script
- ✅ **Built-in Safety**: Automatic conflict detection and prevention
- ✅ **Interactive Operations**: Guided workflows for authentication and restore
- ✅ **Comprehensive Help**: Built-in documentation and examples
- ✅ **Session Backup/Restore**: Easy backup management with selection interface
- ✅ **Smart Workflows**: Automatic safety checks before any operation
- ✅ **Proper Shell Script**: Clear `.sh` extension for consistency

### Session Safety Features

- **Concurrent Access Prevention**: File locking prevents multiple processes from accessing session simultaneously
- **Worker Detection**: Automatically detects running Celery workers before allowing manual session access
- **Safe Testing**: All test and debug scripts include session conflict protection
- **Graceful Shutdown**: Extended shutdown timeout (15s) allows proper Telegram session cleanup
- **Safety Validation**: Built-in session safety checker tool

### Session Safety Tools

```bash
# Check if it's safe to perform Telegram operations
python3 scripts/check_session_safety.py

# Session status and health check
python3 scripts/telegram_session_check.py --quick

# ⭐ RECOMMENDED: Use the unified session management wrapper
./scripts/telegram_session.sh status      # Check session status and age
./scripts/telegram_session.sh test        # Test session validity (safe)
./scripts/telegram_session.sh auth        # Authenticate new session
./scripts/telegram_session.sh renew       # Safe renewal workflow
./scripts/telegram_session.sh backup      # Backup current session
./scripts/telegram_session.sh restore     # Restore from backup
./scripts/telegram_session.sh safety-check # Check for conflicts
./scripts/telegram_session.sh diagnostics # Full diagnostics
./scripts/telegram_session.sh help        # Show all options

# Alternative: Direct Python script access (advanced users)
python3 scripts/telegram_auth.py --status      # Check session age and info
python3 scripts/telegram_auth.py --test        # Test validity (no SMS)
python3 scripts/telegram_auth.py --safe-renew  # Complete safe workflow
python3 scripts/check_session_safety.py        # Check session conflicts  
python3 scripts/telegram_session_check.py      # Full diagnostics
```

### Best Practices

**✅ SAFE Operations:**
- Using `./scripts/deploy_celery.sh stop` (graceful shutdown)
- Running tests only when workers are stopped
- Following guided re-authentication process

**❌ UNSAFE Operations:**
- Running debug scripts while workers are active
- Using `kill -9` on worker processes
- Multiple processes accessing session simultaneously

### Session Safety Warnings

When session conflicts are detected, you'll see clear warnings:
```
🚫 UNSAFE: Celery workers are running and may be using the Telegram session!
   Active worker PIDs: 12345, 67890
   
   Solutions:
   1. Stop workers first: ./scripts/deploy_celery.sh stop
   2. Run your operation, then restart: ./scripts/deploy_celery.sh start
   3. Or wait for workers to finish current tasks
```

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
- ✅ **Session verification** (via comprehensive test suite)
- ✅ Comprehensive system testing (validates all components including sessions)
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
| `deploy_celery.sh` | **Complete Celery management** | Start/stop/restart background services | Memory-optimized workers, graceful/force stop, **session lock cleanup** |
| `safe_shutdown.sh` | **🛑 Comprehensive system shutdown** | **Safe system shutdown** with full cleanup | Session locks, Redis cache, temp files, health summary |
| `telegram_session.sh` | **🔐 Unified session management** | All session operations | `status`, `test`, `auth`, `renew`, `backup`, `restore`, `safety-check`, `diagnostics` |
| `telegram_auth.py` | Session management backend | Direct Python access | `--status`, `--test`, `--renew`, `--safe-renew`, `--backup` with safety protection |
| `monitor_resources.sh` | System resource monitoring | Check performance and memory usage | Real-time stats, alerts |
| `auto_restart.sh` | Automatic service recovery | Background watchdog service | Auto-restart failed services |
| `status.sh` | **Enhanced service status** | Quick health check | Process status, **session age/status**, resource usage, commands |
| `verify_setup.sh` | System setup validation | Before first run, troubleshooting | Comprehensive system check |

#### Comprehensive Testing System
| Command | Purpose | When to Use | Key Features |
|---------|---------|-------------|--------------|
| `./scripts/run_tests.sh` | **Complete system validation** | After changes, before deployment | Tests all components, config, language detection, Redis, Celery, **efficient fetching** |
| `./scripts/run_tests.sh --quick` | **Essential tests only** | Regular validation, CI/CD | Skips API connections, focuses on core functionality |
| `./scripts/run_tests.sh --efficient-fetching` | **🚀 Efficient fetching tests** | Validate optimization system | Redis operations, CSV fallback, API call reduction validation |
| `./scripts/run_tests.sh --component` | Component testing only | Development and debugging | Tests imports, log handling, file operations |
| `./scripts/run_tests.sh --config` | Configuration validation | After config changes | Validates JSON structure, required fields, Iraq dual-language format |
| `./scripts/run_tests.sh --session` | **Enhanced session tests** | Session validation | Session status, validity testing (with safety protection), management tools |
| `./scripts/run_tests.sh --telegram-session` | **Comprehensive session tests** | Full session validation | Status checking, validity testing, safety protection, management integration |
| `./scripts/run_tests.sh --language` | Language detection tests | Test heuristic detection | Arabic/English detection without OpenAI calls |
| `./scripts/run_tests.sh --processing` | Message processing tests | Test dual-language logic | Iraq keyword matching, AI toggle, translation |
| `./scripts/run_tests.sh --csv` | **CSV storage tests** | Test CSV storage pipeline | **PRODUCTION SAFE**: Uses dedicated test CSV files (`TEST_iraq_*.csv`), complete validation, automatic cleanup |
| `./scripts/run_tests.sh --sharepoint` | **Enhanced SharePoint storage tests** | Test SharePoint integration with reliability features | **PRODUCTION SAFE**: Uses dedicated test sheets, tests session management, retry logic, timeout handling, Excel formula escaping (#NAME? fix), comprehensive integration testing |
| `python3 tests/test_ai_exception_filtering.py` | **🤖 AI Exception Filtering tests** | Test AI exception rules | Tests message classification with geographic relevance filtering, exception rule validation |

#### Legacy Testing & Validation Tools  
| Script | Purpose | When to Use | Key Features |
|--------|---------|-------------|--------------|
| `tests/validate_telegram_config.py` | **Telegram credential validator** | Before authentication, credential issues | Network tests, credential validation, interactive updates |
| `scripts/telegram_session_check.py` | Session diagnostics backend | Direct Python access | Comprehensive diagnostics with recovery guidance |
| `scripts/check_session_safety.py` | Session safety backend | Direct Python access | Detects session conflicts and provides safe operation guidance |
| `tests/check_telegram_status.py` | API rate limit status checker | Check rate limiting status | Monitors API rate limits and provides recovery timeline |
| `tests/telegram_recovery.py` | Automated recovery script | After rate limit expires | Restores system operation post-rate-limit |
| `tests/test_translation.py` | Translation system testing | Verify OpenAI integration | Test language detection and translation |
| `tests/test_components.py` | Component testing | Development and debugging | Individual component validation |
| `tests/test_message_fetch.py` | **Periodic message fetching test** | Verify 3-minute fetch intervals | Tests new periodic fetching with age filtering |
| `tests/test_language_detection.py` | **Heuristic language detection** | Test without OpenAI | Tests Arabic/English detection using word patterns |

**Most Common Usage:**
- **First time:** `./scripts/setup.sh` (includes config + Telegram auth)
- **After restart:** `./scripts/quick_start.sh` (includes automatic comprehensive testing)
- **Safe shutdown:** `./scripts/safe_shutdown.sh` (comprehensive cleanup and shutdown)
- **Session management:** `./scripts/telegram_session.sh help` (unified session operations)
- **Manual testing:** `./scripts/run_tests.sh --quick` (when needed for validation)
- **Check status:** `./scripts/status.sh`
- **Test specific features:** Use individual `--component`, `--config`, etc. flags

### Manual Deployment

#### 1. Activate Virtual Environment
```bash
source telegram-ai-scraper_env/bin/activate
```

#### 2. Start Celery Workers and Beat Scheduler
```bash
# Use the automated deployment script (recommended)
./scripts/deploy_celery.sh

# Or start manually in separate terminals:
# Terminal 1 - Beat scheduler (periodic message fetching)
celery -A src.tasks.telegram_celery_tasks beat --loglevel=info

# Terminal 2 - Main processing workers
celery -A src.tasks.telegram_celery_tasks worker --loglevel=info --queues=telegram_processing --concurrency=4

# Terminal 3 - Notification workers  
celery -A src.tasks.telegram_celery_tasks worker --loglevel=info --queues=notifications --concurrency=2

# Terminal 4 - SharePoint workers
celery -A src.tasks.telegram_celery_tasks worker --loglevel=info --queues=sharepoint --concurrency=2

# Terminal 5 - Backup workers
celery -A src.tasks.telegram_celery_tasks worker --loglevel=info --queues=backup --concurrency=1
```

#### 3. Test System Components
```bash
# Test all connections and components
python3 src/core/main.py --config config/config.json --mode test

# Or use the comprehensive test suite
./scripts/run_tests.sh
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

# Stop all services (basic)
./scripts/deploy_celery.sh stop

# Stop with comprehensive cleanup (recommended)
./scripts/safe_shutdown.sh
```

### Command Line Options

- `--config`: Configuration file path (default: config.json)
- `--mode`: Operation mode (test only - monitoring is now handled by Celery Beat)
- `--run-tests`: Run the comprehensive test suite to validate all components

## How It Works

### Architecture Overview
The system uses a **session-safe Celery-based architecture** for reliable operation:

- **Celery Beat**: Handles all Telegram message fetching on a periodic schedule (prevents session conflicts)
- **Celery Workers**: Process all heavy tasks (AI analysis, API calls) in distributed workers
- **Redis**: Message broker for task queues and result storage
- **main.py**: Component initialization and testing only (no direct Telegram operations)

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
8. **Monitoring**: All activities logged with classification methods (keyword_significant, keyword_trivial, excluded, ai_significant, ai_trivial) and task IDs### Session-Safe Queue Architecture
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Telegram API   │───▶│  Celery Beat     │───▶│  Redis Queues   │
│   (Periodic)    │    │  (Scheduler)     │    │                 │
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

┌──────────────────┐
│   main.py        │ ← Component initialization and testing only
│ (No Telegram     │   (Session-safe: no concurrent access)
│  operations)     │
└──────────────────┘
```

## File Structure

```
telegram-ai-scraper/
├── run.py                          # Easy entry point script
├── requirements.txt                # Python dependencies
├── README.md                      # This file
├── src/                           # Source code
│   ├── core/                      # Core application modules
│   │   ├── main.py               # Component initialization and testing (session-safe)
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
│   ├── safe_shutdown.sh         # 🛑 **Comprehensive system shutdown** (NEW)
│   ├── monitor_resources.sh     # System resource monitoring
│   ├── telegram_session.sh      # 🔐 **Unified session management wrapper** (RECOMMENDED)
│   ├── telegram_auth.py         # Session management backend
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

### Data Fields and Storage

#### Complete Field List (TELEGRAM_EXCEL_FIELDS)

The system processes 19 fields for each message:

**Core Message Fields:**
- `Message_ID`: Unique Telegram message identifier
- `Channel`: Source Telegram channel (e.g., @channelname)
- `Message_URL`: Direct link to view the message in Telegram (https://t.me/channel/message_id)
- `Date`: Message date (YYYY-MM-DD)
- `Time`: Message time (HH:MM:SS)
- `Author`: Message author (often same as Channel)
- `Message_Text`: Processed message content (translated if needed)
- `Attached_Links`: Comma-separated list of URLs extracted from the message

**Analysis Fields:**
- `AI_Category`: Significance classification (Significant/Trivial)
- `AI_Reasoning`: OpenAI explanation for classification
- `Keywords_Matched`: Matched keywords that triggered classification

**Metadata Fields:**
- `Country`: Country associated with the message
- `Message_Type`: Type of message (text, photo, video, etc.)
- `Forward_From`: Original source if message was forwarded
- `Media_Type`: Type of media attached (if any)
- `Processed_Date`: When the message was processed by the system

**Translation Fields:**
- `Original_Text`: Original message text before translation
- `Original_Language`: Detected language of original message
- `Was_Translated`: Boolean indicating if translation was performed

#### Storage Strategy

- **CSV Files**: Store ALL 19 fields for complete data preservation and future database migration
- **Teams Notifications**: Show 11 user-relevant fields (8 excluded via config) - includes Message_URL and Attached_Links
- **SharePoint Excel**: Show 11 user-relevant fields (8 excluded via config)
- **Configurable**: Easily customize what fields appear in Teams/SharePoint via `config.json`

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

3. **Telegram Session Invalidation (Phone Disconnected)**
   - **Most Common Issue**: Session conflicts between workers and manual operations
   - **Solution**: Use session safety tools before operations
   - **Check conflicts**: `python3 scripts/check_session_safety.py`
   - **Safe workflow**: Stop workers → Perform operation → Restart workers
   - **Emergency**: Use `scripts/telegram_session_check.py --quick` for recovery

4. **Telegram Authentication Failed**
   - Verify API ID and API Hash
   - Ensure phone number is correct
   - Check if 2FA is enabled on your Telegram account

5. **OpenAI API Errors**
   - Verify API key is valid and has sufficient credits
   - Check for rate limiting in worker logs
   - Ensure model access permissions

6. **Teams Notifications Not Working**
   - Verify webhook URL is correct
   - Check Teams channel permissions
   - Test webhook with a simple curl command

7. **SharePoint Connection Issues & Service Crashes**
   - **Symptoms**: Teams alerts showing "SharePointInitializationError", Excel files not updating
   - **Root Causes**: Session management failures, authentication token expiration, network timeouts
   - **Immediate Actions**: 
     - Check `logs/sharepoint.log` for detailed error information
     - Verify client credentials in `config.json`
     - Ensure SharePoint site and Excel file permissions are correct
     - Check network connectivity to Microsoft Graph API endpoints
   - **Enhanced Troubleshooting**: 
     - Monitor `logs/teams.log` for crash notifications
     - Look for "SharePointInitializationError" patterns in admin Teams channel
     - Check Celery data services log: `logs/celery_data_services.log`
   - **Recovery Procedures**:
     - System automatically retries with exponential backoff (up to 5 attempts)
     - Failed tasks send admin notifications without data loss
     - Manual recovery: Restart data services worker: `./scripts/deploy_celery.sh restart data_services`
     - If authentication issues persist: Update SharePoint credentials and restart system

8. **High Memory Usage**
   - Reduce worker concurrency levels
   - Implement task result expiration
   - Monitor with `htop` or similar tools

### SharePoint Health Monitoring

**Quick SharePoint Status Check:**
```bash
# Check recent SharePoint operations
tail -20 logs/sharepoint.log

# Look for successful operations (should show status=200)
grep "SharePoint response: status=200" logs/sharepoint.log | tail -5

# Check for SharePoint errors in Teams notifications
grep "SharePointInitializationError" logs/teams.log | tail -5

# Monitor Celery data services (handles SharePoint tasks)
tail -10 logs/celery_data_services.log
```

**SharePoint Service Recovery:**
```bash
# If SharePoint is failing, restart data services worker
./scripts/deploy_celery.sh stop
./scripts/deploy_celery.sh start

# Check system status after restart
./scripts/status.sh

# Verify SharePoint is working by checking logs
tail -f logs/sharepoint.log  # Watch for new operations
```

### Getting Help

1. **SharePoint Issues**: Check `logs/sharepoint.log` and `logs/teams.log` for crash notifications
2. **General System**: Check the log files in the `logs/` directory
3. **Connection Testing**: Run in test mode: `python3 src/core/main.py --config config/config.json --mode test`
4. **Worker Monitoring**: Monitor Celery workers: `celery -A src.tasks.telegram_celery_tasks inspect stats`
5. **Task Results**: View task results: `celery -A src.tasks.telegram_celery_tasks result <task_id>`
6. **Status Checks**: Use management scripts: `./scripts/status.sh` or `./scripts/deploy_celery.sh status`
7. **SharePoint Testing**: Run SharePoint-specific tests: `./scripts/run_tests.sh --sharepoint`

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

🔗 **[SharePoint Integration Reliability Guide](docs/SHAREPOINT_RELIABILITY_GUIDE.md)**

Comprehensive guide for SharePoint reliability features:
- Enhanced session management and validation
- Retry logic with exponential backoff
- Timeout handling and error recovery
- Health monitoring and troubleshooting procedures
- Best practices for enterprise-grade stability
- Recovery procedures and maintenance schedules

🤖 **[AI Exception Filtering Guide](docs/AI_EXCEPTION_FILTERING_GUIDE.md)**

Advanced filtering system to reduce false positives:
- Configuration and setup for exception rules
- Geographic relevance filtering using AI
- Example scenarios and best practices
- Performance considerations and troubleshooting
- Integration with existing keyword filtering

## Troubleshooting

### Common Issues and Solutions

#### 1. Telegram Session Invalidation (Phone Disconnects) ⚠️ MOST COMMON
**Symptoms:** Phone shows "Telegram Web/Desktop is Online", actual Telegram app gets logged out
**Root Cause:** Multiple processes accessing the same session file simultaneously
**Solutions:**
```bash
# ⭐ Use the unified session management wrapper (RECOMMENDED)
./scripts/telegram_session.sh safety-check    # Check before manual operations
./scripts/telegram_session.sh status          # Shows age, recommendations  
./scripts/telegram_session.sh test            # Tests if session works
./scripts/telegram_session.sh renew           # Safe renewal workflow
./scripts/telegram_session.sh diagnostics     # Emergency recovery and diagnostics

# Alternative: Direct Python access (advanced users)
python3 scripts/check_session_safety.py                # Safety check
python3 scripts/telegram_auth.py --status              # Status check  
python3 scripts/telegram_auth.py --safe-renew          # Safe renewal
python3 scripts/telegram_session_check.py              # Full diagnostics

# Safe workflow for testing/debugging
./scripts/deploy_celery.sh stop      # Stop workers first
python3 your_test_script.py         # Run your operation
./scripts/deploy_celery.sh start    # Restart workers
```

**Prevention Best Practices:**
- ✅ Always use `./scripts/deploy_celery.sh stop` (graceful shutdown)
- ✅ Run tests only when workers are stopped
- ❌ Never use `kill -9` on worker processes
- ❌ Never run debug scripts while workers are active

#### 2. Memory Issues on Small Instances (t3.small, etc.)
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

#### 3. Redis Connection Errors
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

#### 4. Celery Workers Not Starting
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

# Alternative: Test connections and components
./scripts/run_tests.sh --quick
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

### Version 2.3.0 (Current) - SharePoint Reliability Enhancement
- **🔗 Enhanced SharePoint Reliability**: Enterprise-grade session management and error handling
- **Session Validation**: Multi-attempt initialization with health checks and timeout handling
- **Advanced Retry Logic**: Exponential backoff with up to 5 attempts for transient failures
- **Comprehensive Error Handling**: Authentication recovery, network timeout management, and graceful degradation
- **Improved Monitoring**: Detailed logging, health checks, and proactive issue detection
- **Admin Notifications**: Real-time Teams alerts for SharePoint issues with detailed error context
- **Documentation**: Complete SharePoint Reliability Guide with troubleshooting and best practices
- **Enhanced Testing**: Production-safe SharePoint testing with dedicated test sheets

### Version 2.2.0
- **🚀 Efficient Message Fetching System**: Redis-based tracking with CSV fallback - **80-95% reduction in API calls**
- **Smart ID Tracking**: Only fetches messages newer than last processed ID per channel
- **Triple Fallback Strategy**: Redis → CSV analysis → Conservative original method
- **4-Hour Age Limit**: Configurable absolute message age cutoff (`MAX_MESSAGE_AGE_HOURS`)
- **API Call Optimization**: Prevents rate limiting when monitoring multiple channels
- **Enhanced Test Suite**: New `test_efficient_fetching.py` with comprehensive validation
- **Updated Documentation**: Complete guides for the new efficient system

### Version 2.1.0
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