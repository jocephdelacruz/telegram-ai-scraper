# Telegram AI Scraper

An intelligent, high-performance Telegram message scraper that uses OpenAI to analyze message significance and automatically sends alerts to Microsoft Teams and stores data in SharePoint Excel files. Built with **Celery distributed task processing** for scalability and fault tolerance.

## Features

- **Real-time Monitoring**: Continuously monitors specified Telegram channels for new messages using asyncio
- **Distributed Processing**: Uses Celery workers for parallel processing of AI analysis, notifications, and data storage
- **Intelligent Message Filtering**: Country-specific keyword filtering with AI fallback for optimal performance and accuracy
- **Teams Integration**: Sends formatted alerts to Microsoft Teams channels for significant messages
- **SharePoint Storage**: Automatically stores significant messages in SharePoint Excel files
- **Historical Scraping**: Can scrape and analyze past messages from channels
- **Fault Tolerance**: Automatic task retries and error recovery with Celery
- **Scalable Architecture**: Add more workers to handle increased message volume
- **Robust Error Handling**: Comprehensive error catching and logging throughout the system
- **CSV Backup**: Local CSV backup of all processed messages
- **Redis Integration**: Uses Redis as message broker and result backend
- **Task Monitoring**: Real-time monitoring of task queues and worker status
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

- `OPEN_AI_KEY`: Your OpenAI API key
- `TELEGRAM_CONFIG`: Telegram API credentials
- `COUNTRIES`: Country-specific configurations with channels, Teams webhooks, and SharePoint settings
- `MESSAGE_FILTERING`: Keywords that determine message significance
- `MS_SHAREPOINT_ACCESS`: Base SharePoint credentials

### Multi-Country Features

- **Country-Specific Channels**: Each country has its own set of Telegram channels to monitor  
- **Country-Specific Message Filtering**: Each country has its own significant/trivial/exclude keyword sets for culturally relevant filtering
- **Intelligent Keyword Processing**: System first applies keyword filtering, then uses AI analysis for ambiguous cases
- **Separate Teams Notifications**: Different Teams webhooks for each country with country flags
- **Country-Specific SharePoint Files**: Separate Excel files per country with Significant and Trivial sheets
- **Localized CSV Backups**: Country-specific CSV backup files separated by significance
- **Message Routing**: Messages automatically routed based on source channel
- **Cultural Context**: Keywords tailored to local politics, geography, and events for each country

### Basic Configuration Structure

```json
{
   "OPEN_AI_KEY": "your_openai_api_key",
   
   "TELEGRAM_CONFIG": {
      "API_ID": "your_telegram_api_id",
      "API_HASH": "your_telegram_api_hash",
      "PHONE_NUMBER": "your_phone_number",
      "SESSION_FILE": "telegram_session.session"
   },
   
   "COUNTRIES": {
      "country_code": {
         "name": "Country Name",
         "channels": ["@channel1", "@channel2"],
         "teams_webhook": "teams_webhook_url",
         "sharepoint_config": { ... },
         "message_filtering": {
            "significant_keywords": ["urgent", "breaking"],
            "trivial_keywords": ["sports", "weather"],
            "exclude_keywords": ["advertisement", "promo"]
         }
      }
   },
   
   "MS_SHAREPOINT_ACCESS": { ... },
   "TELEGRAM_EXCEL_FIELDS": [ ... ]
}
```

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

### Quick Start (Recommended)
```bash
# 1. First-time setup
chmod +x scripts/setup.sh
./scripts/setup.sh

# 2. Configure your settings
cp config/config_sample.json config/config.json
# Edit config/config.json with your actual API keys and settings

# 3. Start everything with one command
chmod +x scripts/deploy_celery.sh
./scripts/deploy_celery.sh
```

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
# Check service status
./scripts/status.sh

# Monitor task queues and workers (web UI)
celery -A src.tasks.telegram_celery_tasks flower
# View at http://localhost:5555

# Stop all services
./scripts/stop_celery.sh
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

### Message Processing Flow

1. **Message Ingestion**: Main process (asyncio) listens to Telegram channels in real-time
2. **Country Detection**: Determines which country configuration to use based on source channel
3. **Task Queuing**: New messages are immediately queued as Celery tasks (non-blocking)  
4. **Distributed Processing**: Multiple Celery workers process tasks in parallel:
   - **Smart Filtering**: Country-specific keyword filtering for faster classification
   - **AI Analysis**: OpenAI analyzes ambiguous cases with country context
   - **Dual Storage**: ALL messages stored in SharePoint (Significant/Trivial sheets)
   - **Smart Notifications**: Only significant messages trigger Teams alerts
   - **Country Routing**: Messages routed to country-specific Teams/SharePoint
   - **Backup**: Country-specific CSV storage (separate files for significant/trivial)
5. **Error Handling**: Failed tasks automatically retry with exponential backoff
6. **Monitoring**: All activities logged with classification methods and task IDs### Queue Architecture
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
│   │   └── file_handling.py      # File operations
│   ├── integrations/              # External service integrations
│   │   ├── telegram_utils.py     # Telegram API handling
│   │   ├── openai_utils.py       # OpenAI integration and message analysis
│   │   ├── teams_utils.py        # Microsoft Teams notifications
│   │   └── sharepoint_utils.py   # SharePoint Excel integration
│   └── tasks/                     # Celery task definitions
│       ├── telegram_celery_tasks.py # Celery task definitions
│       └── celery_config.py      # Celery configuration
├── config/                        # Configuration files
│   ├── config_sample.json        # Sample configuration template
│   └── config.json              # Your actual configuration (create from sample)
├── scripts/                       # Deployment and management scripts
│   ├── setup.sh                 # Setup script
│   ├── deploy_celery.sh         # Comprehensive Celery management script
│   ├── stop_celery.sh           # Stop all services script
│   └── status.sh                # Service status monitoring script
├── logs/                          # Log files directory
│   ├── main.log
│   ├── telegram.log
│   ├── telegram_tasks.log
│   ├── openai.log
│   ├── teams.log
│   ├── sharepoint.log
│   └── celery_worker.log
├── data/                          # Data storage directory
├── pids/                          # Process ID files
└── telegram-ai-scraper_env/      # Python virtual environment
```

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

## Contributing

This is a custom internal tool. For modifications:

1. Test changes thoroughly
2. Update documentation
3. Maintain error handling standards
4. Follow existing code structure

## License

This project is for internal use only. All rights reserved.

## Changelog

### Version 2.0.0 (Current)
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