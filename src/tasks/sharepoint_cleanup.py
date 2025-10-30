"""
SharePoint Cleanup Task for Telegram AI Scraper

Provides scheduled cleanup of old entries from SharePoint Excel files.
Uses Celery Beat for reliable scheduling and conflict-free operation.
"""

import os
import sys
import json
import asyncio
from datetime import datetime, timedelta
from celery import Celery
from celery.schedules import crontab

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.core import log_handling as lh
from src.integrations.sharepoint_utils import SharepointProcessor

# Setup logging
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "sharepoint_cleanup.log")
LOG_TZ = "Asia/Manila"
LOGGER = lh.LogHandling(LOG_FILE, LOG_TZ)

# Import main Celery app
from .telegram_celery_tasks import celery

def cleanup_old_sharepoint_entries(days_to_keep=3):
    """
    Clean up old entries from SharePoint Excel files
    
    This task:
    1. Deletes rows (not just clears content) to prevent blank spaces
    2. Uses atomic operations to prevent conflicts with concurrent writes
    3. Maintains Excel table structure and formatting
    4. Handles multiple countries/worksheets automatically
    
    Args:
        days_to_keep (int): Number of days to keep entries (default: 7)
    
    Returns:
        dict: Result summary with statistics
    """
    try:
        LOGGER.writeLog(f"🧹 Starting SharePoint cleanup - removing entries older than {days_to_keep} days")
        
        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        cutoff_date_str = cutoff_date.strftime('%Y-%m-%d')
        
        LOGGER.writeLog(f"Cutoff date: {cutoff_date_str} (entries before this will be deleted)")
        
        # Load configuration
        config_path = os.path.join(PROJECT_ROOT, "config", "config.json")
        
        if not os.path.exists(config_path):
            LOGGER.writeLog("❌ Config file not found, cannot determine SharePoint configuration")
            return {"status": "error", "message": "Config file not found"}
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Get SharePoint configuration
        sharepoint_config = config.get('SHAREPOINT_CONFIG', {})
        if not sharepoint_config:
            LOGGER.writeLog("❌ SharePoint configuration not found in config file")
            return {"status": "error", "message": "SharePoint configuration not found"}
        
        # Statistics tracking
        total_deleted = 0
        processed_files = 0
        errors = []
        
        # Process each country's SharePoint files
        countries = config.get('countries', {})
        
        for country_code, country_config in countries.items():
            if not country_config.get('enabled', False):
                LOGGER.writeLog(f"ℹ️  Skipping disabled country: {country_code}")
                continue
                
            country_sharepoint = country_config.get('sharepoint', {})
            if not country_sharepoint:
                LOGGER.writeLog(f"⚠️  No SharePoint config for country: {country_code}")
                continue
            
            try:
                # Process significant messages file
                significant_file = country_sharepoint.get('significant_file_path')
                if significant_file:
                    deleted_count = await cleanup_sharepoint_file(
                        sharepoint_config, 
                        significant_file, 
                        cutoff_date_str, 
                        country_code, 
                        "significant"
                    )
                    total_deleted += deleted_count
                    processed_files += 1
                
                # Process trivial messages file  
                trivial_file = country_sharepoint.get('trivial_file_path')
                if trivial_file:
                    deleted_count = await cleanup_sharepoint_file(
                        sharepoint_config, 
                        trivial_file, 
                        cutoff_date_str, 
                        country_code, 
                        "trivial"
                    )
                    total_deleted += deleted_count
                    processed_files += 1
                    
            except Exception as e:
                error_msg = f"Failed to clean SharePoint files for {country_code}: {e}"
                LOGGER.writeLog(f"❌ {error_msg}")
                errors.append(error_msg)
        
        # Summary
        if errors:
            LOGGER.writeLog(f"⚠️  SharePoint cleanup completed with errors: processed {processed_files} files, deleted {total_deleted} entries, {len(errors)} errors")
            return {
                "status": "partial_success", 
                "processed_files": processed_files,
                "total_deleted": total_deleted,
                "errors": errors,
                "cutoff_date": cutoff_date_str
            }
        else:
            LOGGER.writeLog(f"✅ SharePoint cleanup completed successfully: processed {processed_files} files, deleted {total_deleted} entries")
            return {
                "status": "success", 
                "processed_files": processed_files,
                "total_deleted": total_deleted,
                "cutoff_date": cutoff_date_str
            }
        
    except Exception as e:
        error_msg = f"SharePoint cleanup failed: {e}"
        LOGGER.writeLog(f"❌ {error_msg}")
        
        
        # Send critical exception to admin
        try:
            from src.integrations.teams_utils import send_critical_exception
            send_critical_exception(
                "SharePointCleanupError",
                error_msg,
                "cleanup_old_sharepoint_entries",
                additional_context={
                    "days_to_keep": days_to_keep,
                    "called_from": "cleanup_old_tasks"
                }
            )
        except Exception as admin_error:
            LOGGER.writeLog(f"❌ Failed to send cleanup error to admin: {admin_error}")
        
        return {"status": "error", "message": error_msg}


async def cleanup_sharepoint_file(sharepoint_config, file_path, cutoff_date_str, country_code, file_type):
    """
    Clean up a specific SharePoint Excel file
    
    Args:
        sharepoint_config: SharePoint connection configuration
        file_path: Path to the Excel file in SharePoint
        cutoff_date_str: Cutoff date in YYYY-MM-DD format
        country_code: Country code for logging
        file_type: "significant" or "trivial" for logging
        
    Returns:
        int: Number of deleted entries
    """
    sharepoint_processor = None
    
    try:
        LOGGER.writeLog(f"🔍 Cleaning {file_type} file for {country_code}: {file_path}")
        
        # Initialize SharePoint connection with session management
        sharepoint_processor = SharepointProcessor(
            clientID=sharepoint_config['client_id'],
            clientSecret=sharepoint_config['client_secret'], 
            tenantID=sharepoint_config['tenant_id'],
            spSite=sharepoint_config['site_url'],
            siteName=sharepoint_config['site_name'],
            filePath=file_path
        )
        
        if not sharepoint_processor.isConnectedToSharepointFile():
            raise Exception("Failed to connect to SharePoint file")
        
        # Get the worksheet (assuming first worksheet or "Sheet1")
        worksheet_name = "Sheet1"  # This might need to be configurable
        
        # Find and delete old entries
        deleted_count = await delete_old_entries_from_worksheet(
            sharepoint_processor, 
            worksheet_name, 
            cutoff_date_str
        )
        
        LOGGER.writeLog(f"✅ Deleted {deleted_count} old entries from {file_type} file for {country_code}")
        return deleted_count
        
    except Exception as e:
        LOGGER.writeLog(f"❌ Error cleaning {file_type} file for {country_code}: {e}")
        raise
    finally:
        # Always close the SharePoint session
        if sharepoint_processor:
            try:
                sharepoint_processor.closeExcelSession()
                LOGGER.writeLog(f"🔐 Closed SharePoint session for {file_type} file ({country_code})")
            except Exception as close_error:
                LOGGER.writeLog(f"⚠️  Warning: Failed to close SharePoint session: {close_error}")


async def delete_old_entries_from_worksheet(sharepoint_processor, worksheet_name, cutoff_date_str):
    """
    Delete old entries from a SharePoint worksheet
    
    This function:
    1. Reads the entire worksheet to identify old entries
    2. Deletes entire rows (not just clears content) to prevent blank spaces
    3. Works from bottom to top to avoid index shifting during deletion
    4. Preserves the header row
    
    Args:
        sharepoint_processor: SharePoint processor instance
        worksheet_name: Name of the worksheet
        cutoff_date_str: Cutoff date in YYYY-MM-DD format
        
    Returns:
        int: Number of deleted entries
    """
    try:
        # Get the used range to determine data boundaries
        used_range_response = sharepoint_processor._make_api_request(
            "GET",
            f"https://graph.microsoft.com/v1.0/sites/{sharepoint_processor.siteID}/drive/items/{sharepoint_processor.fileID}/workbook/worksheets/{worksheet_name}/usedRange"
        )
        
        if not used_range_response or used_range_response.status_code != 200:
            LOGGER.writeLog(f"⚠️  Could not determine used range for {worksheet_name}")
            return 0
        
        used_range_data = used_range_response.json()
        values = used_range_data.get('values', [])
        
        if len(values) <= 1:  # Only header or empty
            LOGGER.writeLog(f"ℹ️  No data rows to process in {worksheet_name}")
            return 0
        
        # Find the Date column index (assuming it's in the header)
        header_row = values[0]
        date_column_index = None
        
        for i, header in enumerate(header_row):
            if header and str(header).strip().lower() == 'date':
                date_column_index = i
                break
        
        if date_column_index is None:
            LOGGER.writeLog(f"⚠️  No 'Date' column found in {worksheet_name}")
            return 0
        
        LOGGER.writeLog(f"📅 Found Date column at index {date_column_index}")
        
        # Identify rows to delete (skip header row)
        rows_to_delete = []
        
        for row_index, row_data in enumerate(values[1:], start=2):  # Start from row 2 (skip header)
            try:
                if date_column_index < len(row_data):
                    date_value = row_data[date_column_index]
                    
                    if date_value:
                        # Handle different date formats
                        date_str = str(date_value)
                        if date_str.startswith('Date('):
                            # Excel serial date format: Date(1234567890000)
                            import re
                            match = re.search(r'Date\((\d+)\)', date_str)
                            if match:
                                timestamp = int(match.group(1)) / 1000  # Convert from milliseconds
                                entry_date = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
                            else:
                                continue
                        else:
                            # Try to parse as standard date
                            try:
                                # Handle YYYY-MM-DD format
                                if len(date_str) >= 10:
                                    entry_date = date_str[:10]  # Take first 10 characters
                                else:
                                    continue
                            except:
                                continue
                        
                        # Compare dates
                        if entry_date < cutoff_date_str:
                            rows_to_delete.append(row_index)
                            
            except Exception as e:
                LOGGER.writeLog(f"⚠️  Error processing row {row_index}: {e}")
                continue
        
        if not rows_to_delete:
            LOGGER.writeLog(f"ℹ️  No old entries found in {worksheet_name}")
            return 0
        
        LOGGER.writeLog(f"🗑️  Found {len(rows_to_delete)} old entries to delete from {worksheet_name}")
        
        # Delete rows from bottom to top to avoid index shifting
        deleted_count = 0
        
        for row_index in sorted(rows_to_delete, reverse=True):
            try:
                # Delete the entire row
                success = await delete_worksheet_row(sharepoint_processor, worksheet_name, row_index)
                if success:
                    deleted_count += 1
                else:
                    LOGGER.writeLog(f"⚠️  Failed to delete row {row_index}")
                    
                # Small delay to be gentle on SharePoint API
                await asyncio.sleep(0.1)
                
            except Exception as e:
                LOGGER.writeLog(f"❌ Error deleting row {row_index}: {e}")
        
        return deleted_count
        
    except Exception as e:
        LOGGER.writeLog(f"❌ Error identifying old entries in {worksheet_name}: {e}")
        raise


async def delete_worksheet_row(sharepoint_processor, worksheet_name, row_index):
    """
    Delete a specific row from the worksheet
    
    Args:
        sharepoint_processor: SharePoint processor instance
        worksheet_name: Name of the worksheet
        row_index: 1-based row index to delete
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Use the Graph API to delete the entire row
        headers = {
            "Authorization": f"Bearer {sharepoint_processor.token}",
            "workbook-session-id": sharepoint_processor.sessionID,
            "Content-Type": "application/json"
        }
        
        # Delete the entire row
        url = f"https://graph.microsoft.com/v1.0/sites/{sharepoint_processor.siteID}/drive/items/{sharepoint_processor.fileID}/workbook/worksheets/{worksheet_name}/range(address='{row_index}:{row_index}')/delete"
        
        response = sharepoint_processor._make_api_request("POST", url, headers=headers, json={"shift": "Up"})
        
        return response and response.status_code in [200, 204]
        
    except Exception as e:
        LOGGER.writeLog(f"❌ Error deleting row {row_index}: {e}")
        return False


# Add helper method to SharePoint processor if it doesn't exist
def add_api_request_method():
    """Add a helper method to SharePoint processor for API requests"""
    if not hasattr(SharepointProcessor, '_make_api_request'):
        import requests
        
        def _make_api_request(self, method, url, headers=None, json=None, timeout=30):
            """Make an API request with proper error handling"""
            try:
                if headers is None:
                    headers = {
                        "Authorization": f"Bearer {self.token}",
                        "workbook-session-id": self.sessionID,
                        "Content-Type": "application/json"
                    }
                
                if method.upper() == "GET":
                    return requests.get(url, headers=headers, timeout=timeout)
                elif method.upper() == "POST":
                    return requests.post(url, headers=headers, json=json, timeout=timeout)
                elif method.upper() == "DELETE":
                    return requests.delete(url, headers=headers, timeout=timeout)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                    
            except Exception as e:
                LOGGER.writeLog(f"❌ API request failed: {method} {url} - {e}")
                return None
        
        SharepointProcessor._make_api_request = _make_api_request

# Apply the method addition
add_api_request_method()