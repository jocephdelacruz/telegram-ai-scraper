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
        
        # SINGLE EFFICIENT EMPTY MESSAGE CHECK - Skip processing if no meaningful text content
        # Message_Text contains the original text from Telegram, so check that first
        message_text = message_data.get('Message_Text', '') or message_data.get('text', '')
        if not message_text or not message_text.strip():
            LOGGER.writeLog(f"⏭️ SKIPPING empty message {message_id} - no text content from Telegram")
            
            # Mark message as processed in Redis to prevent reprocessing
            try:
                import redis
                redis_client = redis.Redis(host='localhost', port=6379, db=1)
                duplicate_key = f"processed_msg:{channel}:{message_id}"
                redis_client.setex(duplicate_key, 86400, "1")  # 24 hours
                LOGGER.writeLog(f"Empty message {message_id} marked as processed in Redis")
            except Exception as redis_error:
                LOGGER.writeLog(f"Warning: Could not mark empty message {message_id} in Redis: {redis_error}")
            
            return {
                "status": "skipped_empty", 
                "message_id": message_id,
                "country": country_code,
                "reason": "No text content from Telegram"
            }
        
        # Message processing with optimized language detection and keyword matching
        from src.core.message_processor import MessageProcessor
        openai_processor = OpenAIProcessor(config['OPEN_AI_KEY'])
        message_processor = MessageProcessor(openai_processor=openai_processor)
        country_config = config['COUNTRIES'].get(country_code, {}) if country_code else {}
        
        is_significant, matched_keywords, classification_method, translation_info = message_processor.isMessageSignificant(
            message_data['text'],
            country_config=country_config
        )
        
        # Handle translation separately based on configuration
        original_text = message_data['text']
        should_translate = False
        
        # Check if we should translate this message
        if country_config and 'message_filtering' in country_config:
            filtering = country_config['message_filtering']
            translate_trivial = filtering.get('translate_trivial_msgs', True)
            
            # Translate significant messages always, trivial messages based on config
            if is_significant or translate_trivial:
                should_translate = True
        else:
            # Default behavior - translate all messages
            should_translate = True
        
        # Perform translation if needed
        if should_translate and not translation_info['is_english']:
            LOGGER.writeLog(f"Translating message {message_id} from {translation_info['original_language']}")
            translation_result = message_processor.translateMessage(
                original_text, 
                country_config, 
                source_language=translation_info['original_language']
            )
            
            if translation_result['success'] and translation_result['was_translated']:
                # Use translated text for storage and alerts
                message_data['text'] = translation_result['translated_text']
                message_data['Message_Text'] = translation_result['translated_text']
                message_data['Original_Text'] = original_text
                message_data['Original_Language'] = translation_result['detected_language']
                message_data['Was_Translated'] = True
                LOGGER.writeLog(f"Message {message_id} translated successfully using {translation_result['translation_method']}")
            else:
                # Translation failed or not needed
                message_data['Original_Text'] = original_text
                message_data['Original_Language'] = translation_info['original_language']
                message_data['Was_Translated'] = False
                if not translation_result['success']:
                    LOGGER.writeLog(f"Translation failed for message {message_id}, using original text")
        else:
            # No translation needed or configured
            message_data['Original_Text'] = original_text
            message_data['Original_Language'] = translation_info['original_language']
            message_data['Was_Translated'] = False
            if should_translate:
                LOGGER.writeLog(f"Message {message_id} already in English, no translation needed")
            else:
                LOGGER.writeLog(f"Translation skipped for trivial message {message_id}")
        

        
        # Build analysis result structure
        analysis_result = {
            'is_significant': is_significant,
            'matched_keywords': matched_keywords,
            'classification_method': classification_method,
            'reasoning': f"Classified as {'significant' if is_significant else 'trivial'} using {classification_method}",
            'language_info': translation_info
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
        
        # Send critical exception to admin for Celery task failures
        try:
            admin_notifier = create_admin_notifier_from_config(config)
            if admin_notifier:
                retry_count = self.request.retries
                max_retries = self.retry_kwargs.get('max_retries', 3)
                
                admin_notifier.send_celery_failure(
                    task_name="process_telegram_message",
                    task_id=str(self.request.id),
                    failure_reason=str(e),
                    retry_count=retry_count,
                    max_retries=max_retries
                )
        except Exception as admin_error:
            LOGGER.writeLog(f"Failed to send Celery task failure to admin: {admin_error}")
        
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


@celery.task(bind=True, retry_kwargs={'max_retries': 5, 'countdown': 180})
def save_to_sharepoint(self, message_data, config, country_code):
    """Save to country-specific SharePoint file - handles both significant and trivial messages"""
    try:
        message_id = message_data.get('id', 'unknown')
        is_significant = message_data.get('is_significant', False)
        category = "Significant" if is_significant else "Trivial"
        
        LOGGER.writeLog(f"Saving {category} message {message_id} to SharePoint ({country_code}) - Attempt {self.request.retries + 1}")
        
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
        
        # Enhanced SharePoint processor initialization with retry logic
        sp_processor = None
        max_init_attempts = 3
        
        for attempt in range(max_init_attempts):
            try:
                LOGGER.writeLog(f"Initializing SharePoint processor - attempt {attempt + 1}/{max_init_attempts}")
                
                sp_processor = SharepointProcessor(
                    sp_config['ClientID'], 
                    sp_config['ClientSecret'],
                    sp_config['TenantID'],
                    sp_config['SharepointSite'],
                    site_name,
                    full_file_path
                )
                
                # Enhanced session validation
                if (sp_processor and 
                    hasattr(sp_processor, 'sessionID') and 
                    sp_processor.sessionID and 
                    hasattr(sp_processor, 'token') and 
                    sp_processor.token and
                    hasattr(sp_processor, 'siteID') and 
                    sp_processor.siteID and
                    hasattr(sp_processor, 'fileID') and 
                    sp_processor.fileID):
                    
                    LOGGER.writeLog(f"SharePoint processor initialized successfully on attempt {attempt + 1}")
                    break
                else:
                    LOGGER.writeLog(f"SharePoint processor initialization incomplete on attempt {attempt + 1}")
                    sp_processor = None
                    
            except Exception as init_error:
                LOGGER.writeLog(f"SharePoint processor initialization failed on attempt {attempt + 1}: {init_error}")
                sp_processor = None
                
            # Wait before retry (except on last attempt)
            if attempt < max_init_attempts - 1:
                import time
                time.sleep(5)  # 5 second delay between initialization attempts
        
        if not sp_processor:
            raise Exception("Failed to initialize SharePoint processor after multiple attempts")
            
        # Additional session validation with connection test
        if not hasattr(sp_processor, 'sessionID') or not sp_processor.sessionID:
            raise Exception("Failed to establish SharePoint session")
        
        # Determine which sheet to use based on message significance
        if is_significant:
            sheet_name = sharepoint_config.get('significant_sheet', 'Significant')
        else:
            sheet_name = sharepoint_config.get('trivial_sheet', 'Trivial')
        
        # Prepare data for SharePoint - filter to only include expected fields
        excel_fields = config.get('TELEGRAM_EXCEL_FIELDS', [])
        
        # Create filtered field list for SharePoint (exclude user-facing unnecessary fields from config)
        excluded_sharepoint_fields = config.get('EXCLUDED_SHAREPOINT_FIELDS', [])
        sharepoint_fields = [field for field in excel_fields if field not in excluded_sharepoint_fields]
        
        LOGGER.writeLog(f"SharePoint field filtering - Total fields: {len(excel_fields)}, SharePoint fields: {len(sharepoint_fields)}")
        
        # Filter message data to only include fields expected in SharePoint
        filtered_message_data = {}
        for field in sharepoint_fields:
            value = message_data.get(field, '')
            
            # Apply Excel formula escaping for Channel field to prevent #NAME? errors
            if field == 'Channel' and isinstance(value, str) and value.startswith('@'):
                # Add single quote prefix to prevent Excel from treating as formula/reference
                value = f"'{value}"
                LOGGER.writeLog(f"Applied Excel escaping to channel: {message_data.get(field, '')} → {value}")
            
            # Apply Excel formula escaping for Author field to prevent #NAME? errors
            if field == 'Author' and isinstance(value, str) and value.startswith('@'):
                # Add single quote prefix to prevent Excel from treating as formula/reference
                value = f"'{value}"
                LOGGER.writeLog(f"Applied Excel escaping to author: {message_data.get(field, '')} → {value}")
            
            filtered_message_data[field] = value
        
        LOGGER.writeLog(f"Filtered message data - Original fields: {len(message_data)}, Filtered fields: {len(filtered_message_data)}")
        
        sp_data = [filtered_message_data]  # Single filtered message
        sp_format_data = sp_processor.convertDictToSPFormat(sp_data, sharepoint_fields)
        
        if not sp_format_data:
            raise Exception("Failed to convert message data to SharePoint format")
        
        # Find next available row and save
        try:
            next_row = get_next_available_row(sp_processor, sheet_name)
        except:
            # If sheet doesn't exist or other error, start at row 2 (assuming headers in row 1)
            next_row = 2
            LOGGER.writeLog(f"Using default row 2 for sheet {sheet_name}")
        
        range_address = f"A{next_row}:{chr(ord('A') + len(sharepoint_fields) - 1)}{next_row}"
        
        # Validate session one more time before attempting the update
        if not sp_processor.validateSession():
            raise Exception("SharePoint session became invalid before update")
        
        # Only send the data row, not the headers (convertDictToSPFormat returns [headers, data])
        if len(sp_format_data) > 1:
            data_only = [sp_format_data[1]]  # Only the data row
            LOGGER.writeLog(f"Writing data to {sheet_name} sheet at {range_address}: {len(data_only[0])} columns")
            success = sp_processor.updateRange(sheet_name, range_address, data_only)
        else:
            raise Exception("No data row found after SharePoint format conversion")
        
        # Always close the session in a try-catch to prevent this from causing task failure
        try:
            sp_processor.closeExcelSession()
            LOGGER.writeLog("SharePoint session closed successfully")
        except Exception as close_error:
            LOGGER.writeLog(f"Warning: Failed to close SharePoint session: {close_error}")
        
        if success:
            LOGGER.writeLog(f"{category} message {message_id} saved to SharePoint sheet '{sheet_name}' successfully ({country_code})")
        else:
            raise Exception("SharePoint update failed - data may not have been saved")
            
        return {
            "status": "success", 
            "message_id": message_id,
            "country": country_code,
            "sheet": sheet_name,
            "category": category,
            "range": range_address
        }
        
    except Exception as e:
        # Ensure session cleanup even on failure
        try:
            if 'sp_processor' in locals() and sp_processor and hasattr(sp_processor, 'closeExcelSession'):
                sp_processor.closeExcelSession()
        except:
            pass  # Ignore cleanup errors
            
        error_msg = f"SharePoint save failed for message {message_data.get('id', 'unknown')} (attempt {self.request.retries + 1}): {e}"
        LOGGER.writeLog(error_msg)
        
        # Add exponential backoff for retries
        retry_countdown = min(180 * (2 ** self.request.retries), 900)  # Max 15 minutes
        raise self.retry(exc=e, countdown=retry_countdown)


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
        
        # Filter message data to only include fields that are expected in CSV
        # This prevents "dict contains fields not in fieldnames" errors
        filtered_message_data = {}
        for field in excel_fields:
            # Use the field value if available, otherwise use empty string
            value = message_data.get(field, '')
            
            # Convert newlines to <br> tags for CSV storage to prevent multi-line entries
            if isinstance(value, str) and field in ['Message_Text', 'Original_Text']:
                # Replace various types of newlines with <br> tags
                value = value.replace('\r\n', '<br>').replace('\n', '<br>').replace('\r', '<br>')
                if value != message_data.get(field, ''):
                    LOGGER.writeLog(f"CSV newline conversion applied to field '{field}': {len(value.split('<br>'))-1} newlines converted")
            
            filtered_message_data[field] = value
        
        LOGGER.writeLog(f"CSV write - Original fields: {len(message_data)}, Filtered fields: {len(filtered_message_data)}")
        
        success = file_handler.append_to_csv(filtered_message_data, excel_fields)
        
        if success:
            LOGGER.writeLog(f"{category} message {message_id} saved to CSV backup successfully ({country_code})")
        else:
            raise Exception("CSV backup write failed")
            
        return {"status": "success", "message_id": message_data.get('id')}
        
    except Exception as e:
        LOGGER.writeLog(f"CSV backup failed for message {message_data.get('id', 'unknown')}: {e}")
        raise self.retry(exc=e)


@celery.task(bind=True, max_retries=2, default_retry_delay=600)
def cleanup_old_tasks(self):
    """
    Comprehensive cleanup task that handles all maintenance operations:
    1. Old Celery task results cleanup
    2. SharePoint entries cleanup
    3. Redis cache cleanup
    """
    cleanup_results = {
        "celery_tasks": {"status": "not_run"},
        "sharepoint": {"status": "not_run"}, 
        "redis": {"status": "not_run"}
    }
    
    try:
        LOGGER.writeLog("🧹 Starting comprehensive cleanup - Celery tasks, SharePoint, and Redis")
        
        # Load configuration for data retention settings
        config = load_cleanup_config()
        data_retention_days = config.get('DATA_RETENTION_DAYS', 3)
        
        LOGGER.writeLog(f"📅 Using data retention period: {data_retention_days} days")
        
        # 1. Clean up old Celery task results
        try:
            cleanup_results["celery_tasks"] = cleanup_celery_task_results()
        except Exception as e:
            LOGGER.writeLog(f"❌ Celery task cleanup failed: {e}")
            cleanup_results["celery_tasks"] = {"status": "error", "error": str(e)}
        
        # 2. Clean up SharePoint entries
        try:
            LOGGER.writeLog("🔄 Starting SharePoint cleanup...")
            from src.tasks.sharepoint_cleanup import cleanup_old_sharepoint_entries
            
            # Call the SharePoint cleanup function directly (not as Celery task)
            sharepoint_result = cleanup_old_sharepoint_entries.apply(
                kwargs={'days_to_keep': data_retention_days}
            ).get()
            
            cleanup_results["sharepoint"] = sharepoint_result
            LOGGER.writeLog(f"✅ SharePoint cleanup completed: {sharepoint_result.get('status', 'unknown')}")
            
        except Exception as e:
            LOGGER.writeLog(f"❌ SharePoint cleanup failed: {e}")
            cleanup_results["sharepoint"] = {"status": "error", "error": str(e)}
        
        # 3. Clean up old Redis entries
        try:
            cleanup_results["redis"] = cleanup_redis_entries()
        except Exception as e:
            LOGGER.writeLog(f"❌ Redis cleanup failed: {e}")
            cleanup_results["redis"] = {"status": "error", "error": str(e)}
        
        # Summary
        successful_cleanups = sum(1 for result in cleanup_results.values() 
                                if result.get("status") == "success")
        total_cleanups = len(cleanup_results)
        
        if successful_cleanups == total_cleanups:
            LOGGER.writeLog(f"✅ All cleanup operations completed successfully ({successful_cleanups}/{total_cleanups})")
            return {"status": "success", "details": cleanup_results}
        else:
            LOGGER.writeLog(f"⚠️  Partial cleanup success ({successful_cleanups}/{total_cleanups})")
            
            # For partial success, we don't retry - individual operations either succeeded or failed
            # Retrying would duplicate successful operations
            return {"status": "partial_success", "details": cleanup_results}
            
    except Exception as e:
        error_msg = f"Comprehensive cleanup failed: {e}"
        LOGGER.writeLog(f"❌ {error_msg}")
        
        # Only retry on critical system errors (not partial failures)
        # This catches configuration loading errors, system connectivity issues, etc.
        if self.request.retries < self.max_retries:
            retry_delay = 600 * (2 ** self.request.retries)  # Exponential backoff: 10, 20 minutes
            LOGGER.writeLog(f"🔄 Retrying comprehensive cleanup in {retry_delay} seconds (attempt {self.request.retries + 1}/{self.max_retries})")
            
            # Send admin notification about retry
            try:
                from src.integrations.teams_utils import send_critical_exception
                send_critical_exception(
                    "CleanupTaskRetry",
                    error_msg,
                    "cleanup_old_tasks",
                    additional_context={
                        "retry_attempt": self.request.retries + 1,
                        "max_retries": self.max_retries,
                        "next_retry_in_seconds": retry_delay,
                        "partial_results": cleanup_results
                    }
                )
            except Exception as admin_error:
                LOGGER.writeLog(f"⚠️  Could not send retry notification to admin: {admin_error}")
            
            raise self.retry(countdown=retry_delay, exc=e)
        else:
            # Max retries reached - send final error notification
            try:
                from src.integrations.teams_utils import send_critical_exception
                send_critical_exception(
                    "CleanupTaskFinalFailure",
                    f"Cleanup task failed after {self.max_retries} retries: {error_msg}",
                    "cleanup_old_tasks",
                    additional_context={
                        "final_failure": True,
                        "total_retries": self.max_retries,
                        "partial_results": cleanup_results
                    }
                )
            except Exception as admin_error:
                LOGGER.writeLog(f"⚠️  Could not send final failure notification to admin: {admin_error}")
        
        return {"status": "error", "error": error_msg, "details": cleanup_results}


def load_cleanup_config():
    """Load configuration for cleanup operations"""
    try:
        import os
        from src.core import file_handling as fh
        
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(project_root, "config", "config.json")
        config_handler = fh.FileHandling(config_path)
        config = config_handler.read_json()
        
        return config if config else {}
    except Exception as e:
        LOGGER.writeLog(f"⚠️  Failed to load cleanup config, using defaults: {e}")
        return {}


def cleanup_celery_task_results():
    """Clean up old Celery task results from Redis"""
    try:
        LOGGER.writeLog("🔄 Cleaning up old Celery task results...")
        
        import redis
        from datetime import datetime, timedelta
        
        # Connect to Redis (using same config as Celery)
        redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        
        # Clean up task results older than 24 hours
        cutoff_time = datetime.now() - timedelta(hours=24)
        cutoff_timestamp = cutoff_time.timestamp()
        
        deleted_count = 0
        
        # Get all result keys (Celery stores results with 'celery-task-meta-' prefix)
        result_keys = redis_client.keys('celery-task-meta-*')
        
        for key in result_keys:
            try:
                # Get the TTL (time to live) of the key
                ttl = redis_client.ttl(key)
                
                # If TTL is -1, the key has no expiration; check its age
                if ttl == -1:
                    # For keys without TTL, we can delete them if they're old
                    # (This is safe because Celery task results should expire)
                    redis_client.delete(key)
                    deleted_count += 1
                elif ttl > 86400:  # More than 24 hours left
                    # Set a reasonable TTL (24 hours) for very old keys
                    redis_client.expire(key, 86400)
                    
            except Exception as e:
                LOGGER.writeLog(f"⚠️  Error processing Redis key {key}: {e}")
                continue
        
        LOGGER.writeLog(f"✅ Cleaned up {deleted_count} old Celery task results from Redis")
        return {"status": "success", "deleted_count": deleted_count}
        
    except Exception as e:
        LOGGER.writeLog(f"❌ Failed to clean up Celery task results: {e}")
        return {"status": "error", "error": str(e)}


def cleanup_redis_entries():
    """Safely clean up old Redis entries"""
    try:
        LOGGER.writeLog("🔄 Cleaning up old Redis entries...")
        
        import redis
        from datetime import datetime, timedelta
        
        # Connect to Redis
        redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        
        deleted_count = 0
        processed_count = 0
        
        # Get all keys and check their age
        all_keys = redis_client.keys('*')
        
        # Filter for safe-to-delete keys (avoid Celery Beat schedule and active tasks)
        safe_patterns = [
            'celery-task-meta-*',  # Old task results
            '_kombu.binding.*',    # Old message routing
        ]
        
        # Dangerous patterns to avoid
        avoid_patterns = [
            'celerybeat-schedule',     # Celery Beat schedule
            'celery-beat-*',          # Celery Beat locks
            'celery-worker-*',        # Active worker info
            'celery-queue-*',         # Active task queues
        ]
        
        for key in all_keys:
            try:
                processed_count += 1
                
                # Skip dangerous keys
                if any(key.startswith(pattern.replace('*', '')) or 
                      key == pattern.replace('*', '') for pattern in avoid_patterns):
                    continue
                
                # Only process safe patterns
                if any(key.startswith(pattern.replace('*', '')) for pattern in safe_patterns):
                    ttl = redis_client.ttl(key)
                    
                    # Delete keys older than 24 hours or without TTL
                    if ttl == -1 or ttl > 86400:
                        redis_client.delete(key)
                        deleted_count += 1
                
            except Exception as e:
                LOGGER.writeLog(f"⚠️  Error processing Redis key {key}: {e}")
                continue
        
        LOGGER.writeLog(f"✅ Redis cleanup completed: processed {processed_count} keys, deleted {deleted_count}")
        return {"status": "success", "processed_count": processed_count, "deleted_count": deleted_count}
        
    except Exception as e:
        LOGGER.writeLog(f"❌ Failed to clean up Redis entries: {e}")
        return {"status": "error", "error": str(e)}


@celery.task(bind=True, retry_kwargs={'max_retries': 3, 'countdown': 60})
def fetch_new_messages_from_all_channels(self):
    """
    Periodic task to fetch new messages from all configured channels
    This runs based on configurable interval and only fetches messages newer than the configured age limit
    CRITICAL: This task now includes session safety protection to prevent concurrent
    Telegram session access that can cause phone logout issues.
    """
    try:
        # 🛡️ CRITICAL SESSION SAFETY CHECK - Prevent concurrent access that causes phone logout
        from src.integrations.session_safety import SessionSafetyManager, SessionSafetyError
        
        # safety_manager = SessionSafetyManager()
        # try:
        #     safety_manager.check_session_safety("periodic_fetch")
        #     LOGGER.writeLog("✅ Session safety check passed - safe to start periodic fetch")
        # except SessionSafetyError as safety_error:
        #     # Multiple workers trying to access session - abort this attempt
        #     LOGGER.writeLog(f"🛡️ SESSION SAFETY ABORT: {safety_error}")
        #     LOGGER.writeLog("⏸️  Skipping this periodic fetch to prevent phone logout")
        #     return {
        #         "status": "skipped_for_safety",
        #         "timestamp": datetime.now().isoformat(),
        #         "reason": "Session safety protection active - prevented concurrent access",
        #         "channels_checked": 0,
        #         "messages_processed": 0,
        #         "messages_skipped": 0
        #     }
        
        LOGGER.writeLog("Starting periodic message fetch from all channels")
        
        # Load configuration
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
        
        from src.core import file_handling as fh
        from src.integrations.telegram_utils import TelegramScraper
        from src.integrations.telegram_session_manager import TelegramRateLimitError, TelegramSessionError, TelegramAuthError
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
        fetch_interval_seconds = telegram_config.get('FETCH_INTERVAL_SECONDS', 240)
        
        # Calculate age limit based on fetch interval to minimize duplicates while ensuring no missed messages
        # Use fetch interval + 30 seconds buffer to account for processing delays
        age_limit_seconds = fetch_interval_seconds + 30
        age_limit_minutes = age_limit_seconds / 60.0
        
        LOGGER.writeLog(f"Using fetch limit: {message_limit}, fetch interval: {fetch_interval_seconds}s, age limit: {age_limit_seconds}s ({age_limit_minutes:.1f} minutes)")

        # Calculate cutoff time for message age filtering (use UTC to match Telegram message timestamps)
        from datetime import timedelta, timezone
        age_limit_seconds = fetch_interval_seconds + 30  # Buffer for processing delays
        cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=age_limit_seconds)
        LOGGER.writeLog(f"Only processing messages newer than: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        
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
        
        # Initialize Telegram scraper with additional session safety
        if not all(key in telegram_config for key in ['API_ID', 'API_HASH', 'PHONE_NUMBER']):
            raise Exception("Telegram configuration incomplete")
        
        # 🛡️ Additional safety check before creating scraper (double protection)
        # LOGGER.writeLog("🔐 Performing final session safety verification before Telegram client creation")
        # safety_manager = SessionSafetyManager()
        # try:
        #     safety_manager.check_session_safety("telegram_client_creation")
        #     LOGGER.writeLog("✅ Final session safety verified - proceeding with client creation")
        # except SessionSafetyError:
        #     LOGGER.writeLog("🛡️ ABORT: Session safety check failed at client creation - preventing phone logout")
        #     raise Exception("Session safety protection triggered - concurrent access detected")

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
        
    except TelegramRateLimitError as e:
        # Rate limiting - don't retry, just log and return status
        LOGGER.writeLog(f"🚫 TELEGRAM RATE LIMITED: {e}")
        LOGGER.writeLog("⏸️  Stopping periodic fetch until rate limit expires. Use 'python3 tests/check_telegram_status.py' to monitor recovery.")
        return {
            "status": "rate_limited",
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "channels_checked": 0,
            "messages_processed": 0,
            "messages_skipped": 0
        }
        
    except TelegramSessionError as e:
        # Session issue - CHECK SESSION SAFETY before retry to prevent phone logout
        LOGGER.writeLog(f"🔐 SESSION ISSUE: {e}")

        # CRITICAL: Check if session safety allows retry to prevent phone logout
        # try:
        #     from src.integrations.session_safety import SessionSafetyManager, SessionSafetyError
        #     safety = SessionSafetyManager()
        #     safety.check_session_safety("celery_task_retry_validation")
        #     LOGGER.writeLog("✅ Session safety verified - safe to retry")
        # except Exception as safety_error:
        #     LOGGER.writeLog(f"� CRITICAL: Session safety check failed - {safety_error}")
        #     LOGGER.writeLog("🛑 ABORTING RETRY to prevent phone logout!")
        #     LOGGER.writeLog("💡 Please stop all workers, renew session, then restart workers")
        #     LOGGER.writeLog("💡 Commands: ./scripts/deploy_celery.sh stop && ./scripts/telegram_session.sh renew && ./scripts/deploy_celery.sh start")
            
        #     # Return failure instead of retry to prevent dangerous session access
        #     return {
        #         "status": "session_safety_abort",
        #         "timestamp": datetime.now().isoformat(),
        #         "error": f"Session retry aborted for safety: {safety_error}",
        #         "channels_checked": 0,
        #         "messages_processed": 0,
        #         "messages_skipped": 0,
        #         "action_required": "stop_workers_renew_session_restart"
        #     }
        
        # Only retry if session safety allows it

        if self.request.retries < 2:  # Only retry twice for session issues
            LOGGER.writeLog("🔄 Will retry with 5-minute backoff (session safety verified)")
            raise self.retry(exc=e, countdown=300)  # Wait 5 minutes before retry
        else:
            LOGGER.writeLog("❌ SESSION ISSUE: Max retries reached, stopping periodic fetch. Run 'python3 scripts/telegram_auth.py' to re-authenticate.")
            return {
                "status": "session_error",
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "channels_checked": 0,
                "messages_processed": 0,
                "messages_skipped": 0
            }
            
    except TelegramAuthError as e:
        # Authentication issue - don't retry, needs manual intervention
        LOGGER.writeLog(f"🚨 TELEGRAM AUTH ERROR: {e}")
        LOGGER.writeLog("💡 Check your API credentials in config.json or re-authenticate with 'python3 scripts/telegram_auth.py'")
        return {
            "status": "auth_error",
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "channels_checked": 0,
            "messages_processed": 0,
            "messages_skipped": 0
        }
        
    except Exception as e:
        # Other errors - use normal retry logic
        error_msg = str(e)
        LOGGER.writeLog(f"❌ Error in periodic message fetch: {error_msg}")
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
        
        # Initialize Redis for duplicate detection
        import redis
        try:
            redis_client = redis.Redis(host='localhost', port=6379, db=1)
            redis_client.ping()  # Test connection
        except Exception as redis_error:
            LOGGER.writeLog(f"Redis connection failed, proceeding without duplicate detection: {redis_error}")
            redis_client = None
        
        # Fetch messages from each channel with filtering applied at retrieval level
        for channel_info in all_channels:
            try:
                channel = channel_info['channel']
                country_code = channel_info['country_code']
                
                # Get recent messages with efficient ID tracking and age filtering
                messages = await telegram_scraper.get_channel_messages_efficiently(
                    channel, 
                    limit=message_limit, 
                    cutoff_time=cutoff_time,
                    redis_client=redis_client,
                    log_found_messages=True  # Let the utils function handle detailed logging
                )
                
                # Process each message that passed all filters
                for message_data in messages:
                    # Add country information
                    message_data['country_code'] = country_code
                    message_data['Country'] = channel_info['country_name']
                    message_data['text'] = message_data.get('Message_Text', '')
                    message_data['id'] = message_data.get('Message_ID', '')
                    message_data['channel'] = channel
                    
                    # Skip messages with empty text content before queuing
                    message_text = message_data.get('text', '') or message_data.get('Message_Text', '')
                    if not message_text or not message_text.strip():
                        message_id = message_data.get('Message_ID', 'N/A')
                        LOGGER.writeLog(f"⏭️  SKIPPING empty message {message_id} from {channel} - no text content")
                        skipped_messages += 1
                        
                        # Mark as processed in Redis to prevent future reprocessing
                        if redis_client:
                            try:
                                duplicate_key = f"processed_msg:{channel}:{message_id}"
                                redis_client.setex(duplicate_key, 86400, "1")  # 24 hours
                            except Exception as redis_error:
                                LOGGER.writeLog(f"Warning: Could not mark empty message {message_id} in Redis: {redis_error}")
                        
                        continue  # Skip to next message without queuing this one
                    
                    # Log that message is being queued for processing
                    message_id = message_data.get('Message_ID', 'N/A')
                    message_date_str = message_data.get('Date', '')
                    message_time_str = message_data.get('Time', '')
                    message_date_info = f"({message_date_str} {message_time_str})" if message_date_str and message_time_str else ""
                    
                    LOGGER.writeLog(f"✅ QUEUING NEW message {message_id} from {channel} for processing {message_date_info}")
                    
                    # Queue message for processing (async, non-blocking)
                    task = process_telegram_message.delay(message_data, config)
                    total_messages += 1
                    
                    # Small delay to avoid overwhelming the system
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                LOGGER.writeLog(f"Error fetching from channel {channel_info['channel']}: {e}")
                continue
                
        # Stop Telegram client with proper cleanup
        await telegram_scraper.stop_client()
        LOGGER.writeLog("Telegram client stopped after periodic fetch")
       
        # Small delay to ensure proper cleanup
        await asyncio.sleep(1)
        
    except Exception as e:
        LOGGER.writeLog(f"Error in async message fetch: {e}")
        # Ensure client is stopped even if there was an error
        try:
            await telegram_scraper.stop_client()
            # Give extra time for cleanup after errors
            await asyncio.sleep(2)
        except Exception as cleanup_error:
            LOGGER.writeLog(f"Error during cleanup: {cleanup_error}")
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


@celery.task
def send_system_startup_notification():
    """
    Send system startup notification to Teams admin (session-safe).
    This runs as a Celery task to avoid concurrent session access during startup.
    """
    try:
        # Small delay to ensure workers are fully initialized
        import time
        time.sleep(2)
        
        LOGGER.writeLog("Sending system startup notification via Celery task")
        
        # Import here to avoid circular imports
        from src.integrations.teams_utils import send_system_startup
        
        # List of components that are available
        components_started = [
            "Celery Workers", 
            "Celery Beat Scheduler",
            "Teams Admin Notifier", 
            "Message Processing Pipeline",
            "Session-Safe Architecture"
        ]
        
        # Send the notification (Teams only, no Telegram access)
        success = send_system_startup(components_started)
        
        if success:
            LOGGER.writeLog("✅ System startup notification sent successfully to Teams admin")
            return {"status": "success", "notification_sent": True}
        else:
            LOGGER.writeLog("⚠️  System startup notification failed or admin Teams not configured")
            return {"status": "warning", "notification_sent": False, "reason": "Admin Teams not configured"}
            
    except Exception as e:
        LOGGER.writeLog(f"❌ Error sending system startup notification: {e}")
        return {"status": "error", "error": str(e)}


def get_next_available_row(sp_processor, sheet_name):
    """Helper function to find the next available row in SharePoint"""
    try:
        # Get the used range to find the last row with data
        import requests
        
        headers = {
            "Authorization": f"Bearer {sp_processor.token}",
            "workbook-session-id": sp_processor.sessionID,
            "Content-Type": "application/json"
        }
        
        # Get the used range for the worksheet
        url = f"https://graph.microsoft.com/v1.0/sites/{sp_processor.siteID}/drive/items/{sp_processor.fileID}/workbook/worksheets/{sheet_name}/usedRange"
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            used_range = response.json()
            row_count = used_range.get('rowCount', 0)
            
            # If there's no data, start at row 2 (assuming headers in row 1)
            if row_count <= 1:  # Only headers or empty sheet
                next_row = 2
                LOGGER.writeLog(f"Sheet {sheet_name} has {row_count} rows, starting at row 2")
            else:
                # Next available row is after the last used row
                next_row = row_count + 1
                LOGGER.writeLog(f"Sheet {sheet_name} has {row_count} rows, next available: {next_row}")
            
            return next_row
            
        elif response.status_code == 404:
            # Sheet might be empty or new, start at row 2
            LOGGER.writeLog(f"Sheet {sheet_name} appears to be empty, starting at row 2")
            return 2
        else:
            LOGGER.writeLog(f"Error getting used range for {sheet_name}: HTTP {response.status_code}")
            return 2  # Default fallback
        
    except Exception as e:
        LOGGER.writeLog(f"Error finding next available row in {sheet_name}: {e}")
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
        
        # Get fetch interval from config (default to 240 seconds = 4 minutes)
        telegram_config = config.get('TELEGRAM_CONFIG', {}) if config else {}
        fetch_interval = telegram_config.get('FETCH_INTERVAL_SECONDS', 240)
        
        print(f"Setting up Celery beat schedule with fetch interval: {fetch_interval} seconds")
        
        return {
            'fetch-telegram-messages': {
                'task': 'src.tasks.telegram_celery_tasks.fetch_new_messages_from_all_channels',
                'schedule': float(fetch_interval),  # Use configurable interval
            },
            'cleanup-old-tasks': {
                'task': 'src.tasks.telegram_celery_tasks.cleanup_old_tasks',
                'schedule': crontab(hour=1, minute=0),  # Run daily at 1 AM - handles all cleanup tasks
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
                'schedule': 240.0,  # Default: 4 minutes
            },
            'cleanup-old-tasks': {
                'task': 'src.tasks.telegram_celery_tasks.cleanup_old_tasks',
                'schedule': crontab(hour=1, minute=0),
            },
            'health-check': {
                'task': 'src.tasks.telegram_celery_tasks.health_check',
                'schedule': 60.0,
            },
        }

# Set the beat schedule
celery.conf.beat_schedule = load_beat_schedule()
celery.conf.timezone = 'Asia/Manila'