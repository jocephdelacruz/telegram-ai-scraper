# Telegram Scraper - Message Fetching Fix

## Problem Identified

The original system had a critical flaw: **it was not continuously monitoring for new messages**. The Telegram client would start briefly during initialization and then stop, without any mechanism to periodically fetch new messages from the configured channels.

### Issues Found:
1. **No periodic message fetching**: Only cleaned up old tasks and health checks were scheduled
2. **Real-time monitoring stops**: The main.py monitoring mode would run briefly and exit  
3. **Missing scheduled scraping**: No background task to regularly check for new messages

## Solution Implemented

### 1. Added Periodic Message Fetching Task

Created a new Celery task `fetch_new_messages_from_all_channels` that:
- Runs every 5 minutes (configurable)
- Connects to Telegram, fetches recent messages from all configured channels
- Logs message previews (first 20 characters) for visibility
- Queues each new message for AI processing
- Gracefully handles errors and retries

### 2. Enhanced Logging

Updated the system to provide better visibility:
- Shows when new messages are found from each channel
- Displays first 20 characters of each message in logs
- Includes message ID for tracking
- Reports how many messages were processed per fetch cycle

### 3. Updated Worker Configuration

- Added new `telegram_fetch` queue for the periodic task
- Updated Celery configuration to route the new task properly
- Modified deployment scripts to include the new queue in workers

## How It Works Now

### Automatic Operation
1. **Every 3 minutes** (configurable), the `fetch_new_messages_from_all_channels` task runs
2. **Connects to Telegram** using the authenticated session
3. **Fetches recent messages** from each configured channel (up to configured limit)
4. **Filters messages by age** - only processes messages newer than 5 minutes (configurable)
5. **Logs message previews** for visibility (first 20 characters) with timestamps
6. **Queues new messages** for AI processing, Teams notifications, and SharePoint storage
7. **Disconnects from Telegram** to free resources

### Message Processing Flow
```
Periodic Task (Every 3 min - configurable) 
    ↓
Fetch Messages from All Channels
    ↓
Filter by Age (only messages < 5 min old - configurable)
    ↓
Queue New Messages → AI Analysis → Teams Alert (if significant) → SharePoint Storage
```

## Files Modified

### Core Changes
- `src/tasks/telegram_celery_tasks.py` - Added periodic fetch task and enhanced logging
- `src/integrations/telegram_utils.py` - Enhanced message logging with previews
- `src/tasks/celery_config.py` - Added new queue and routing configuration
- `scripts/deploy_celery.sh` - Updated worker configurations to include new queue

### New Files
- `scripts/test_message_fetch.py` - Test script to manually trigger message fetching

## Configuration

### Fetch Configuration
The system now uses **configurable settings** in `config.json`:

```json
"TELEGRAM_CONFIG": {
    "FETCH_INTERVAL_SECONDS": 180,        // 3 minutes between fetches
    "FETCH_MESSAGE_LIMIT": 10             // Max messages per channel per fetch
}
```

To change these settings:
1. Edit `config/config.json`
2. Modify the values in `TELEGRAM_CONFIG`
3. Restart the Celery workers: `./scripts/deploy_celery.sh restart`

### Default Settings
- **Fetch Interval**: 3 minutes (180 seconds)
- **Message Limit**: 10 messages per channel per fetch
- **Age Limit**: Automatically calculated as `FETCH_INTERVAL_SECONDS + 30 seconds` (3.5 minutes for 3-minute intervals)

## Usage Instructions

### 1. Restart the System
After implementing these changes, restart the Celery workers:

```bash
cd /home/ubuntu/TelegramScraper/telegram-ai-scraper

# Stop current workers
./scripts/deploy_celery.sh stop

# Start with new configuration
./scripts/deploy_celery.sh start
```

### 2. Monitor the System
Check that the periodic task is working:

```bash
# View telegram logs to see message fetching
tail -f logs/telegram.log

# View celery logs to see task execution
tail -f logs/celery_main_processor.log

# Check Flower web interface
# http://your-server-ip:5555
```

### 3. Test Manual Fetch
To test the new functionality manually:

```bash
python3 scripts/test_message_fetch.py
```

## Expected Log Output

You should now see logs like this in `telegram.log`:

```
[20251010_16:35:00]: Starting periodic message fetch from all channels
[20251010_16:35:00]: Using fetch limit: 10, fetch interval: 180s, age limit: 210s (3.5 minutes)
[20251010_16:35:00]: Only processing messages newer than: 2025-10-10 16:31:30
[20251010_16:35:01]: Telegram client started for periodic fetch
[20251010_16:35:02]: Found 3 recent messages from @wa3ediq
[20251010_16:35:02]: Processing NEW message from @wa3ediq: 'Breaking: Major event...' (ID: 12345) (2025-10-10 16:34:30)
[20251010_16:35:02]: Skipping duplicate message from @wa3ediq (ID: 12340)
[20251010_16:35:02]: Skipping old message from @wa3ediq (date: 2025-10-10 16:30:15, cutoff: 2025-10-10 16:31:30)
[20251010_16:35:05]: No messages found in @hasklay
[20251010_16:35:06]: Telegram client stopped after periodic fetch
[20251010_16:35:06]: Periodic message fetch completed. New messages processed: 1, skipped (too old): 2
```

## Benefits of This Fix

1. **Continuous Monitoring**: System now actively fetches new messages every 5 minutes
2. **Better Visibility**: Detailed logging shows what messages are being processed
3. **Reliable Operation**: No longer depends on real-time event monitoring that could fail
4. **Resource Efficient**: Connects to Telegram only when needed, then disconnects
5. **Scalable**: Can easily adjust fetch frequency and message limits
6. **Error Resilient**: Handles connection failures and retries automatically

## Troubleshooting

### If No Messages Are Being Fetched
1. Check Celery Beat is running: `./scripts/deploy_celery.sh status`
2. Verify Telegram session is valid: `python3 scripts/run_app.sh test`
3. Check logs for errors: `tail -f logs/celery_beat.log`

### If Tasks Are Not Processing
1. Ensure workers include the `telegram_fetch` queue
2. Check worker logs: `tail -f logs/celery_main_processor.log`
3. Verify Redis is running: `redis-cli ping`

The system should now continuously monitor all configured channels and process new messages automatically!