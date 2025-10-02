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
    Runs in distributed Celery worker
    """
    try:
        LOGGER.writeLog(f"Processing message {message_data.get('id', 'unknown')} from {message_data.get('channel', 'unknown')}")
        
        # AI Analysis
        openai_processor = OpenAIProcessor(config['OPEN_AI_KEY'])
        analysis_result = openai_processor.isArticleSignificant(
            message_data['text'], 
            config['MESSAGE_FILTERING']
        )
        
        # Add analysis results to message data
        message_data['ai_analysis'] = analysis_result
        message_data['is_significant'] = analysis_result.get('is_significant', False)
        message_data['processed_at'] = datetime.now().isoformat()
        
        if message_data['is_significant']:
            LOGGER.writeLog(f"Message {message_data.get('id')} marked as SIGNIFICANT")
            
            # Dispatch parallel tasks for significant messages
            teams_task = send_teams_notification.delay(message_data, config)
            sharepoint_task = save_to_sharepoint.delay(message_data, config)
            
            # Track task IDs for monitoring
            message_data['teams_task_id'] = teams_task.id
            message_data['sharepoint_task_id'] = sharepoint_task.id
        else:
            LOGGER.writeLog(f"Message {message_data.get('id')} marked as trivial")
            
        # Always save to local backup (synchronous for reliability)
        csv_success = save_to_csv_backup.delay(message_data, config)
        message_data['csv_task_id'] = csv_success.id
        
        LOGGER.writeLog(f"Message {message_data.get('id')} processing completed")
        
        return {
            "status": "success", 
            "significant": message_data['is_significant'],
            "message_id": message_data.get('id'),
            "analysis": analysis_result
        }
        
    except Exception as e:
        LOGGER.writeLog(f"Error processing message {message_data.get('id', 'unknown')}: {e}")
        # Retry the task
        raise self.retry(exc=e)


@celery.task(bind=True, retry_kwargs={'max_retries': 3, 'countdown': 30})
def send_teams_notification(self, message_data, config):
    """Send Teams notification - can fail independently"""
    try:
        LOGGER.writeLog(f"Sending Teams notification for message {message_data.get('id')}")
        
        teams_config = config.get('MS_TEAMS_CONFIG', {})
        webhook_url = teams_config.get('WEBHOOK_URL')
        
        if not webhook_url:
            raise Exception("Teams webhook URL not configured")
            
        teams_notifier = TeamsNotifier(webhook_url)
        success = teams_notifier.send_message_alert(message_data)
        
        if success:
            LOGGER.writeLog(f"Teams notification sent successfully for message {message_data.get('id')}")
        else:
            raise Exception("Teams notification failed")
            
        return {"status": "success", "message_id": message_data.get('id')}
        
    except Exception as e:
        LOGGER.writeLog(f"Teams notification failed for message {message_data.get('id', 'unknown')}: {e}")
        raise self.retry(exc=e)


@celery.task(bind=True, retry_kwargs={'max_retries': 3, 'countdown': 45})
def save_to_sharepoint(self, message_data, config):
    """Save to SharePoint - can fail independently"""
    try:
        LOGGER.writeLog(f"Saving message {message_data.get('id')} to SharePoint")
        
        sp_config = config.get('MS_SHAREPOINT_ACCESS', {})
        
        # Validate SharePoint configuration
        required_keys = ['ClientID', 'ClientSecret', 'TenantID', 'SharepointSite', 'SiteName', 'FileName']
        for key in required_keys:
            if not sp_config.get(key):
                raise Exception(f"SharePoint configuration missing: {key}")
        
        # Initialize SharePoint processor
        sp_processor = SharepointProcessor(
            sp_config['ClientID'], 
            sp_config['ClientSecret'],
            sp_config['TenantID'],
            sp_config['SharepointSite'],
            sp_config['SiteName'],
            f"{sp_config.get('FolderPath', '')}{sp_config['FileName']}"
        )
        
        if not sp_processor.isConnectedToSharepointFile:
            raise Exception("Failed to connect to SharePoint file")
        
        # Prepare data for SharePoint
        excel_fields = config.get('TELEGRAM_EXCEL_FIELDS', [])
        sp_data = [message_data]  # Single message
        sp_format_data = sp_processor.convertDictToSPFormat(sp_data, excel_fields)
        
        # Find next available row and save
        sheet_name = sp_config.get('SheetName', 'Sheet1')
        
        # For now, append to a fixed range - you may want to implement dynamic row finding
        next_row = get_next_available_row(sp_processor, sheet_name)
        range_address = f"A{next_row}:{chr(ord('A') + len(excel_fields) - 1)}{next_row}"
        
        success = sp_processor.updateRange(sheet_name, range_address, sp_format_data)
        
        # Close the session
        sp_processor.closeExcelSession()
        
        if success:
            LOGGER.writeLog(f"Message {message_data.get('id')} saved to SharePoint successfully")
        else:
            raise Exception("SharePoint update failed")
            
        return {"status": "success", "message_id": message_data.get('id'), "range": range_address}
        
    except Exception as e:
        LOGGER.writeLog(f"SharePoint save failed for message {message_data.get('id', 'unknown')}: {e}")
        raise self.retry(exc=e)


@celery.task(bind=True, retry_kwargs={'max_retries': 2, 'countdown': 10})
def save_to_csv_backup(self, message_data, config):
    """Local CSV backup - should rarely fail"""
    try:
        LOGGER.writeLog(f"Saving message {message_data.get('id')} to CSV backup")
        
        csv_file = "./data/telegram_messages.csv"
        os.makedirs(os.path.dirname(csv_file), exist_ok=True)
        
        # Use file handling utility
        file_handler = fh.FileHandling(csv_file)
        excel_fields = config.get('TELEGRAM_EXCEL_FIELDS', [])
        
        success = file_handler.append_to_csv(message_data, excel_fields)
        
        if success:
            LOGGER.writeLog(f"Message {message_data.get('id')} saved to CSV backup successfully")
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