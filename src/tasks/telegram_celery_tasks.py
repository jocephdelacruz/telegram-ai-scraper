import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from celery import Celery
from src.integrations.openai_utils import OpenAIProcessor
from src.integrations.teams_utils import TeamsNotifier
from src.integrations.sharepoint_utils import SharepointProcessor
from src.core import log_handling as lh
from src.core import file_handling as fh
import json
import csv
import asyncio
import concurrent.futures
import threading
from datetime import datetime

# Initialize Celery
celery = Celery('telegram_scraper')
celery.config_from_object('src.tasks.celery_config')

# Use absolute path for logging to avoid path resolution issues in Celery workers
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TELEGRAM_TASKS_LOG = os.path.join(PROJECT_ROOT, "logs", "telegram_tasks.log")
LOGGER = lh.LogHandling(TELEGRAM_TASKS_LOG, "Asia/Manila")


def run_async_in_celery(coro, timeout=300):
    """
    Helper function to run async coroutines in Celery tasks
    Handles event loop issues that can occur in worker threads
    
    Args:
        coro: Coroutine to run
        timeout: Timeout in seconds (default 5 minutes)
    
    Returns:
        Result of the coroutine
    """
    try:
        # Try to get the current event loop
        try:
            loop = asyncio.get_running_loop()
            # If we get here, there's already a running loop
            LOGGER.writeLog("Detected running event loop, creating new thread for async execution")
            
            def run_in_thread():
                # Create a new event loop for this thread
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(coro)
                finally:
                    new_loop.close()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_in_thread)
                return future.result(timeout=timeout)
                
        except RuntimeError:
            # No running loop, we can create one
            LOGGER.writeLog("No running event loop detected, creating new one")
            return asyncio.run(coro)
            
    except Exception as e:
        LOGGER.writeLog(f"Error running async coroutine in Celery: {e}")
        raise

@celery.task(bind=True, retry_kwargs={'max_retries': 3, 'countdown': 60})
def process_telegram_message(self, message_data, config):
    """
    Process a Telegram message with AI analysis and notifications
    Handles both significant and trivial messages with country-specific routing
    """
    try:
        message_id = message_data.get('id', 'unknown')
        channel = message_data.get('channel', 'unknown')
        country_code = message_data.get('country_code', 'unknown')
        
        LOGGER.writeLog(f"Processing message {message_id} from {channel} ({country_code})")
        
        # AI Analysis with country-specific filtering (includes translation if needed)
        openai_processor = OpenAIProcessor(config['OPEN_AI_KEY'])
        country_config = config['COUNTRIES'].get(country_code, {}) if country_code else {}
        
        is_significant, matched_keywords, classification_method, translation_info = openai_processor.isMessageSignificant(
            message_data['text'],
            country_config=country_config
        )
        
        # Handle translation - use translated text for storage and alerts
        original_text = message_data['text']
        if not translation_info['is_english'] and translation_info['translated_text']:
            # Use translated text for storage and alerts
            message_data['text'] = translation_info['translated_text']
            message_data['Message_Text'] = translation_info['translated_text']
            # Store original text and language info
            message_data['Original_Text'] = original_text
            message_data['Original_Language'] = translation_info['original_language']
            message_data['Was_Translated'] = True
            LOGGER.writeLog(f"Message {message_id} translated from {translation_info['original_language']} to English")
        else:
            # Mark as not translated
            message_data['Original_Text'] = original_text
            message_data['Original_Language'] = translation_info['original_language']
            message_data['Was_Translated'] = False
        
        # Build analysis result structure
        analysis_result = {
            'is_significant': is_significant,
            'matched_keywords': matched_keywords,
            'classification_method': classification_method,
            'reasoning': f"Classified as {'significant' if is_significant else 'trivial'} using {classification_method}",
            'translation_info': translation_info
        }
        
        # Add analysis results to message data
        message_data['ai_analysis'] = analysis_result
        message_data['is_significant'] = analysis_result.get('is_significant', False)
        message_data['AI_Category'] = "Significant" if message_data['is_significant'] else "Trivial"
        message_data['AI_Reasoning'] = analysis_result.get('reasoning', '')
        message_data['Keywords_Matched'] = ', '.join(analysis_result.get('matched_keywords', []))
        message_data['processed_at'] = datetime.now().isoformat()
        message_data['Processed_Date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Get country-specific configuration
        countries = config.get('COUNTRIES', {})
        country_info = countries.get(country_code, {})
        
        if message_data['is_significant']:
            LOGGER.writeLog(f"Message {message_id} marked as SIGNIFICANT")
            
            # Send Teams notification for significant messages only
            if country_info.get('teams_webhook'):
                teams_task = send_teams_notification.delay(message_data, config, country_code)
                message_data['teams_task_id'] = teams_task.id
            else:
                LOGGER.writeLog(f"No Teams webhook configured for {country_code}")
        else:
            LOGGER.writeLog(f"Message {message_id} marked as TRIVIAL")
            
        # Save ALL messages (both significant and trivial) to SharePoint
        if country_info.get('sharepoint_config'):
            sharepoint_task = save_to_sharepoint.delay(message_data, config, country_code)
            message_data['sharepoint_task_id'] = sharepoint_task.id
        else:
            LOGGER.writeLog(f"No SharePoint config found for {country_code}")
            
        # Always save to local backup
        csv_task = save_to_csv_backup.delay(message_data, config)
        message_data['csv_task_id'] = csv_task.id
        
        # Mark message as processed in Redis AFTER successful processing
        try:
            import redis
            redis_client = redis.Redis(host='localhost', port=6379, db=1)
            channel = message_data.get('channel', message_data.get('Channel', 'unknown'))
            duplicate_key = f"processed_msg:{channel}:{message_id}"
            # Set expiration to 24 hours (longer than fetch interval to prevent reprocessing)
            redis_client.setex(duplicate_key, 86400, "1")  # 24 hours = 86400 seconds
            LOGGER.writeLog(f"Message {message_id} marked as processed in Redis")
        except Exception as redis_error:
            LOGGER.writeLog(f"Warning: Could not mark message {message_id} as processed in Redis: {redis_error}")
            # Don't fail the task if Redis marking fails
        
        LOGGER.writeLog(f"Message {message_id} processing completed - {message_data['AI_Category']}")
        
        return {
            "status": "success", 
            "significant": message_data['is_significant'],
            "message_id": message_id,
            "country": country_code,
            "analysis": analysis_result
        }
        
    except Exception as e:
        LOGGER.writeLog(f"Error processing message {message_data.get('id', 'unknown')}: {e}")
        # Retry the task
        raise self.retry(exc=e)


@celery.task(bind=True, retry_kwargs={'max_retries': 3, 'countdown': 30})
def send_teams_notification(self, message_data, config, country_code):
    """Send Teams notification to country-specific webhook"""
    try:
        message_id = message_data.get('id', 'unknown')
        LOGGER.writeLog(f"Sending Teams notification for message {message_id} ({country_code})")
        
        # Get country-specific Teams configuration
        countries = config.get('COUNTRIES', {})
        country_info = countries.get(country_code, {})
        webhook_url = country_info.get('teams_webhook')
        channel_name = country_info.get('teams_channel_name', f'{country_code.title()} Telegram Alerts')
        
        if not webhook_url:
            raise Exception(f"Teams webhook URL not configured for {country_code}")
            
        teams_sender_name = config.get('TEAMS_SENDER_NAME', 'Aldebaran Scraper')
        teams_notifier = TeamsNotifier(webhook_url, channel_name, teams_sender_name)
        success = teams_notifier.send_message_alert(message_data)
        
        if success:
            LOGGER.writeLog(f"Teams notification sent successfully for message {message_id} to {country_code}")
        else:
            raise Exception("Teams notification failed")
            
        return {
            "status": "success", 
            "message_id": message_id,
            "country": country_code,
            "webhook_used": webhook_url[:50] + "..."
        }
        
    except Exception as e:
        LOGGER.writeLog(f"Teams notification failed for message {message_data.get('id', 'unknown')} ({country_code}): {e}")
        raise self.retry(exc=e)


@celery.task(bind=True, retry_kwargs={'max_retries': 3, 'countdown': 45})
def save_to_sharepoint(self, message_data, config, country_code):
    """Save to country-specific SharePoint file - handles both significant and trivial messages"""
    try:
        message_id = message_data.get('id', 'unknown')
        is_significant = message_data.get('is_significant', False)
        category = "Significant" if is_significant else "Trivial"
        
        LOGGER.writeLog(f"Saving {category} message {message_id} to SharePoint ({country_code})")
        
        # Get country-specific SharePoint configuration
        countries = config.get('COUNTRIES', {})
        country_info = countries.get(country_code, {})
        sharepoint_config = country_info.get('sharepoint_config', {})
        
        if not sharepoint_config:
            raise Exception(f"No SharePoint configuration found for {country_code}")
        
        # Get base SharePoint configuration
        sp_config = config.get('MS_SHAREPOINT_ACCESS', {})
        required_keys = ['ClientID', 'ClientSecret', 'TenantID', 'SharepointSite']
        for key in required_keys:
            if not sp_config.get(key):
                raise Exception(f"SharePoint configuration missing: {key}")
        
        # Build full file path
        site_name = sharepoint_config.get('site_name', 'ATCSharedFiles')
        folder_path = sharepoint_config.get('folder_path', '/Telegram_Feeds/')
        file_name = sharepoint_config.get('file_name', f'{country_code}_Telegram_Feed.xlsx')
        full_file_path = f"{folder_path}{file_name}"
        
        # Initialize SharePoint processor
        sp_processor = SharepointProcessor(
            sp_config['ClientID'], 
            sp_config['ClientSecret'],
            sp_config['TenantID'],
            sp_config['SharepointSite'],
            site_name,
            full_file_path
        )
        
        if not sp_processor.isConnectedToSharepointFile:
            raise Exception("Failed to connect to SharePoint file")
        
        # Determine which sheet to use based on message significance
        if is_significant:
            sheet_name = sharepoint_config.get('significant_sheet', 'Significant')
        else:
            sheet_name = sharepoint_config.get('trivial_sheet', 'Trivial')
        
        # Prepare data for SharePoint
        excel_fields = config.get('TELEGRAM_EXCEL_FIELDS', [])
        sp_data = [message_data]  # Single message
        sp_format_data = sp_processor.convertDictToSPFormat(sp_data, excel_fields)
        
        # Find next available row and save
        try:
            next_row = get_next_available_row(sp_processor, sheet_name)
        except:
            # If sheet doesn't exist or other error, start at row 2 (assuming headers in row 1)
            next_row = 2
            LOGGER.writeLog(f"Using default row 2 for sheet {sheet_name}")
        
        range_address = f"A{next_row}:{chr(ord('A') + len(excel_fields) - 1)}{next_row}"
        
        success = sp_processor.updateRange(sheet_name, range_address, sp_format_data)
        
        # Close the session
        sp_processor.closeExcelSession()
        
        if success:
            LOGGER.writeLog(f"{category} message {message_id} saved to SharePoint sheet '{sheet_name}' successfully ({country_code})")
        else:
            raise Exception("SharePoint update failed")
            
        return {
            "status": "success", 
            "message_id": message_id,
            "country": country_code,
            "sheet": sheet_name,
            "category": category,
            "range": range_address
        }
        
    except Exception as e:
        LOGGER.writeLog(f"SharePoint save failed for message {message_data.get('id', 'unknown')}: {e}")
        raise self.retry(exc=e)


@celery.task(bind=True, retry_kwargs={'max_retries': 2, 'countdown': 10})
def save_to_csv_backup(self, message_data, config):
    """Local CSV backup - should rarely fail"""
    try:
        message_id = message_data.get('id', 'unknown')
        country_code = message_data.get('country_code', 'unknown')
        category = message_data.get('AI_Category', 'Unknown')
        
        LOGGER.writeLog(f"Saving {category} message {message_id} to CSV backup ({country_code})")
        
        # Create country-specific CSV files using absolute path
        data_dir = os.path.join(PROJECT_ROOT, "data")
        os.makedirs(data_dir, exist_ok=True)
        
        # Separate files for significant and trivial messages
        if message_data.get('is_significant', False):
            csv_file = f"{data_dir}/{country_code}_significant_messages.csv"
        else:
            csv_file = f"{data_dir}/{country_code}_trivial_messages.csv"
        
        # Use file handling utility
        file_handler = fh.FileHandling(csv_file)
        excel_fields = config.get('TELEGRAM_EXCEL_FIELDS', [])
        
        success = file_handler.append_to_csv(message_data, excel_fields)
        
        if success:
            LOGGER.writeLog(f"{category} message {message_id} saved to CSV backup successfully ({country_code})")
        else:
            raise Exception("CSV backup write failed")
            
        return {"status": "success", "message_id": message_data.get('id')}
        
    except Exception as e:
        LOGGER.writeLog(f"CSV backup failed for message {message_data.get('id', 'unknown')}: {e}")
        raise self.retry(exc=e)


@celery.task
def cleanup_old_tasks():
    """Periodic task to clean up old task results"""
    try:
        # Clean up task results older than 24 hours
        from celery.result import AsyncResult
        # Implementation depends on your result backend
        LOGGER.writeLog("Cleaning up old task results")
        return {"status": "success"}
    except Exception as e:
        LOGGER.writeLog(f"Task cleanup failed: {e}")
        return {"status": "error", "error": str(e)}


@celery.task(bind=True, retry_kwargs={'max_retries': 3, 'countdown': 60})
def fetch_new_messages_from_all_channels(self):
    """
    Periodic task to fetch new messages from all configured channels
    This runs based on configurable interval and only fetches messages newer than the configured age limit
    """
    try:
        LOGGER.writeLog("Starting periodic message fetch from all channels")
        
        # Load configuration
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
        
        from src.core import file_handling as fh
        from src.integrations.telegram_utils import TelegramScraper
        import asyncio
        
        # Load config
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(project_root, "config", "config.json")
        config_handler = fh.FileHandling(config_path)
        config = config_handler.read_json()
        
        if not config:
            raise Exception("Failed to load configuration")
        
        # Get fetch configuration
        telegram_config = config.get('TELEGRAM_CONFIG', {})
        message_limit = telegram_config.get('FETCH_MESSAGE_LIMIT', 10)
        fetch_interval_seconds = telegram_config.get('FETCH_INTERVAL_SECONDS', 180)
        
        # Calculate age limit based on fetch interval to minimize duplicates while ensuring no missed messages
        # Use fetch interval + 30 seconds buffer to account for processing delays
        age_limit_seconds = fetch_interval_seconds + 30
        age_limit_minutes = age_limit_seconds / 60.0
        
        LOGGER.writeLog(f"Using fetch limit: {message_limit}, fetch interval: {fetch_interval_seconds}s, age limit: {age_limit_seconds}s ({age_limit_minutes:.1f} minutes)")
        
        # Calculate cutoff time for message age filtering
        from datetime import timedelta
        cutoff_time = datetime.now() - timedelta(seconds=age_limit_seconds)
        LOGGER.writeLog(f"Only processing messages newer than: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Get all channels from all countries
        all_channels = []
        countries = config.get('COUNTRIES', {})
        for country_code, country_info in countries.items():
            channels = country_info.get('channels', [])
            for channel in channels:
                all_channels.append({
                    'channel': channel,
                    'country_code': country_code,
                    'country_name': country_info.get('name', country_code)
                })
        
        if not all_channels:
            LOGGER.writeLog("No channels configured for message fetching")
            return {"status": "no_channels", "timestamp": datetime.now().isoformat()}
        
        # Initialize Telegram scraper
        if not all(key in telegram_config for key in ['API_ID', 'API_HASH', 'PHONE_NUMBER']):
            raise Exception("Telegram configuration incomplete")
        
        telegram_scraper = TelegramScraper(
            telegram_config['API_ID'],
            telegram_config['API_HASH'],
            telegram_config['PHONE_NUMBER'],
            telegram_config.get('SESSION_FILE', 'telegram_session')
        )
        
        # Run async message fetching using our Celery-safe helper
        total_messages, skipped_messages = run_async_in_celery(
            fetch_messages_async(telegram_scraper, all_channels, config, cutoff_time, message_limit)
        )
        
        LOGGER.writeLog(f"Periodic message fetch completed. New messages processed: {total_messages}, " +
                       f"skipped (too old): {skipped_messages}")
        
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "channels_checked": len(all_channels),
            "messages_processed": total_messages,
            "messages_skipped": skipped_messages,
            "age_cutoff": cutoff_time.isoformat(),
            "fetch_limit": message_limit
        }
        
    except Exception as e:
        LOGGER.writeLog(f"Error in periodic message fetch: {e}")
        raise self.retry(exc=e)


async def fetch_messages_async(telegram_scraper, all_channels, config, cutoff_time, message_limit):
    """
    Async function to fetch messages from all channels with age filtering
    
    Args:
        telegram_scraper: Telegram scraper instance
        all_channels: List of channel information
        config: Configuration dictionary
        cutoff_time: Only process messages newer than this datetime
        message_limit: Maximum number of messages to fetch per channel
    
    Returns:
        tuple: (processed_messages_count, skipped_messages_count)
    """
    total_messages = 0
    skipped_messages = 0
    
    try:
        # Start Telegram client
        await telegram_scraper.start_client()
        LOGGER.writeLog("Telegram client started for periodic fetch")
        
        # Fetch messages from each channel
        for channel_info in all_channels:
            try:
                channel = channel_info['channel']
                country_code = channel_info['country_code']
                
                # Get recent messages using configured limit
                messages = await telegram_scraper.get_channel_messages(channel, limit=message_limit)
                
                if messages:
                    LOGGER.writeLog(f"Found {len(messages)} recent messages from {channel}")
                    
                    # Process each message with age filtering and duplicate detection
                    for message_data in messages:
                        message_id = message_data.get('Message_ID', '')
                        
                        # Check if message was already processed (duplicate detection using Redis)
                        if message_id:
                            import redis
                            try:
                                redis_client = redis.Redis(host='localhost', port=6379, db=1)  # Use db=1 for tracking
                                duplicate_key = f"processed_msg:{channel}:{message_id}"
                                
                                if redis_client.exists(duplicate_key):
                                    skipped_messages += 1
                                    LOGGER.writeLog(f"Skipping duplicate message from {channel} (ID: {message_id}) - already processed")
                                    continue
                                
                                # DON'T mark as processed yet - wait until after successful AI processing
                                
                            except Exception as redis_error:
                                LOGGER.writeLog(f"Redis duplicate check failed, processing message anyway: {redis_error}")
                                # Continue processing if Redis fails
                        
                        # Parse message date for age filtering
                        message_date_str = message_data.get('Date', '')
                        message_time_str = message_data.get('Time', '')
                        
                        if message_date_str and message_time_str:
                            try:
                                # Combine date and time to create datetime object
                                message_datetime_str = f"{message_date_str} {message_time_str}"
                                message_datetime = datetime.strptime(message_datetime_str, '%Y-%m-%d %H:%M:%S')
                                
                                # Skip messages that are too old
                                if message_datetime < cutoff_time:
                                    skipped_messages += 1
                                    age_diff = cutoff_time - message_datetime
                                    LOGGER.writeLog(f"Skipping old message from {channel} (ID: {message_id}, age: {age_diff}, too old by {age_diff})")
                                    continue
                                    
                            except ValueError as e:
                                LOGGER.writeLog(f"Could not parse message date/time from {channel}: {e}")
                                # If we can't parse the date, process the message anyway
                                pass
                        
                        # Add country information
                        message_data['country_code'] = country_code
                        message_data['Country'] = channel_info['country_name']
                        message_data['text'] = message_data.get('Message_Text', '')
                        message_data['id'] = message_data.get('Message_ID', '')
                        message_data['channel'] = channel
                        
                        # Log first 20 characters of message for visibility
                        message_preview = message_data.get('Message_Text', '')[:20].replace('\n', ' ').strip()
                        message_id = message_data.get('Message_ID', 'N/A')
                        message_date_info = f"({message_date_str} {message_time_str})" if message_date_str and message_time_str else ""
                        
                        if message_preview:
                            LOGGER.writeLog(f"✅ QUEUEING message from {channel}: '{message_preview}...' " + 
                                          f"(ID: {message_id}) {message_date_info} - PASSES all filters")
                        
                        # Queue message for processing (async, non-blocking)
                        task = process_telegram_message.delay(message_data, config)
                        total_messages += 1
                        LOGGER.writeLog(f"Task {task.id} queued for message {message_id} from {channel}")
                        
                        # Small delay to avoid overwhelming the system
                        await asyncio.sleep(0.1)
                else:
                    LOGGER.writeLog(f"No messages found in {channel}")
                    
            except Exception as e:
                LOGGER.writeLog(f"Error fetching from channel {channel_info['channel']}: {e}")
                continue
                
        # Stop Telegram client
        await telegram_scraper.stop_client()
        LOGGER.writeLog("Telegram client stopped after periodic fetch")
        
    except Exception as e:
        LOGGER.writeLog(f"Error in async message fetch: {e}")
        # Ensure client is stopped
        try:
            await telegram_scraper.stop_client()
        except:
            pass
        raise
    
    return total_messages, skipped_messages


@celery.task
def health_check():
    """Health check task for monitoring"""
    try:
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "worker_id": celery.current_task.request.hostname
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


def get_next_available_row(sp_processor, sheet_name):
    """Helper function to find the next available row in SharePoint"""
    try:
        # This is a simplified implementation
        # You might need to implement proper row detection based on your SharePoint structure
        # For now, we'll use a simple incrementing approach
        
        # You could implement logic to:
        # 1. Read current data range
        # 2. Find the last used row
        # 3. Return next row number
        
        # Placeholder implementation - always append to row 2 for now
        # You should implement proper row finding logic based on your needs
        return 2
        
    except Exception as e:
        LOGGER.writeLog(f"Error finding next available row: {e}")
        return 2  # Default fallback


# Dynamic Celery beat schedule for periodic tasks
from celery.schedules import crontab

def load_beat_schedule():
    """Load beat schedule from configuration"""
    try:
        # Load configuration to get fetch interval
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
        
        from src.core import file_handling as fh
        
        # Load config
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(project_root, "config", "config.json")
        config_handler = fh.FileHandling(config_path)
        config = config_handler.read_json()
        
        # Get fetch interval from config (default to 180 seconds = 3 minutes)
        telegram_config = config.get('TELEGRAM_CONFIG', {}) if config else {}
        fetch_interval = telegram_config.get('FETCH_INTERVAL_SECONDS', 180)
        
        print(f"Setting up Celery beat schedule with fetch interval: {fetch_interval} seconds")
        
        return {
            'fetch-telegram-messages': {
                'task': 'src.tasks.telegram_celery_tasks.fetch_new_messages_from_all_channels',
                'schedule': float(fetch_interval),  # Use configurable interval
            },
            'cleanup-old-tasks': {
                'task': 'src.tasks.telegram_celery_tasks.cleanup_old_tasks',
                'schedule': crontab(hour=2, minute=0),  # Run daily at 2 AM
            },
            'health-check': {
                'task': 'src.tasks.telegram_celery_tasks.health_check',
                'schedule': 60.0,  # Run every minute
            },
        }
    except Exception as e:
        print(f"Error loading beat schedule configuration: {e}")
        # Fallback to default schedule
        return {
            'fetch-telegram-messages': {
                'task': 'src.tasks.telegram_celery_tasks.fetch_new_messages_from_all_channels',
                'schedule': 180.0,  # Default: 3 minutes
            },
            'cleanup-old-tasks': {
                'task': 'src.tasks.telegram_celery_tasks.cleanup_old_tasks',
                'schedule': crontab(hour=2, minute=0),
            },
            'health-check': {
                'task': 'src.tasks.telegram_celery_tasks.health_check',
                'schedule': 60.0,
            },
        }

# Set the beat schedule
celery.conf.beat_schedule = load_beat_schedule()
celery.conf.timezone = 'Asia/Manila'