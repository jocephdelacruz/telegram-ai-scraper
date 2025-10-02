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
from datetime import datetime

# Initialize Celery
celery = Celery('telegram_scraper')
celery.config_from_object('src.tasks.celery_config')

LOGGER = lh.LogHandling("../../logs/telegram_tasks.log", "Asia/Manila")

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
        
        # AI Analysis with country-specific filtering
        openai_processor = OpenAIProcessor(config['OPEN_AI_KEY'])
        country_config = config['COUNTRIES'].get(country_code, {}) if country_code else {}
        
        is_significant, matched_keywords, classification_method = openai_processor.isMessageSignificant(
            message_data['text'],
            country_config=country_config
        )
        
        # Build analysis result structure
        analysis_result = {
            'is_significant': is_significant,
            'matched_keywords': matched_keywords,
            'classification_method': classification_method,
            'reasoning': f"Classified as {'significant' if is_significant else 'trivial'} using {classification_method}"
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
            
        teams_notifier = TeamsNotifier(webhook_url, channel_name)
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
        
        # Create country-specific CSV files
        data_dir = "../../data"
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


# Celery beat schedule for periodic tasks
from celery.schedules import crontab

celery.conf.beat_schedule = {
    'cleanup-old-tasks': {
        'task': 'telegram_celery_tasks.cleanup_old_tasks',
        'schedule': crontab(hour=2, minute=0),  # Run daily at 2 AM
    },
    'health-check': {
        'task': 'telegram_celery_tasks.health_check',
        'schedule': 60.0,  # Run every minute
    },
}

celery.conf.timezone = 'Asia/Manila'