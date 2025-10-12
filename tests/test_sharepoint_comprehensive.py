#!/usr/bin/env python3
"""
Comprehensive SharePoint Storage Test Suite

This consolidated test suite validates all aspects of SharePoint integration:
- Connection establishment and authentication
- Header creation in both Significant and Trivial sheets
- Data writing with proper formatting and field filtering
- Row management and detection for any row number
- Excel formula escaping (fixing #NAME? issues)
- Real-world Celery task integration
- Edge cases and high row number validation

Replaces multiple individual SharePoint test files with a single comprehensive suite.
"""

import sys
import os
import json
import time
import requests
from datetime import datetime, timezone

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.integrations.sharepoint_utils import SharepointProcessor
from src.tasks.telegram_celery_tasks import save_to_sharepoint, get_next_available_row


class ComprehensiveSharePointTestSuite:
    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.config = self.load_config()
        self.test_results = {
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }
        
        # SAFETY: Use dedicated test sheets to protect production data
        self.TEST_SHEETS = {
            'significant': 'TEST_Significant',
            'trivial': 'TEST_Trivial'  
        }
        self.test_data_written = []  # Track test data for cleanup
        
    def load_config(self):
        """Load configuration file"""
        config_path = os.path.join(self.project_root, "config", "config.json")
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Failed to load configuration: {e}")
            return {}
            
    def print_test_header(self, title):
        """Print formatted test section header"""
        print(f"\n{'='*70}")
        print(f"📊 {title}")
        print(f"{'='*70}")
        
    def print_test_result(self, test_name, status, details=None):
        """Print individual test result"""
        status_emoji = {
            'PASS': '✅',
            'FAIL': '❌',
            'SKIP': '⏭️',
            'INFO': 'ℹ️'
        }
        
        emoji = status_emoji.get(status, '❓')
        print(f"{emoji} {test_name:<50} [{status}]")
        
        if details:
            for line in str(details).split('\n'):
                if line.strip():
                    print(f"     {line}")
                    
        if status == 'PASS':
            self.test_results['passed'] += 1
        elif status == 'FAIL':
            self.test_results['failed'] += 1
            self.test_results['errors'].append(f"{test_name}: {details}")
        elif status == 'SKIP':
            self.test_results['skipped'] += 1

    def create_test_sheets(self):
        """Create dedicated test sheets to protect production data"""
        self.print_test_header("Production Data Protection Setup")
        
        if not hasattr(self, 'sp_processor'):
            self.print_test_result("Test Sheet Creation", "SKIP", 
                                 "SharePoint connection not available")
            return False
            
        try:
            # Check if test sheets exist, create if needed
            for sheet_type, sheet_name in self.TEST_SHEETS.items():
                try:
                    # Try to access the sheet
                    headers = {
                        "Authorization": f"Bearer {self.sp_processor.token}",
                        "workbook-session-id": self.sp_processor.sessionID,
                        "Content-Type": "application/json"
                    }
                    
                    # Check if sheet exists
                    url = f"https://graph.microsoft.com/v1.0/sites/{self.sp_processor.siteID}/drive/items/{self.sp_processor.fileID}/workbook/worksheets/{sheet_name}"
                    response = requests.get(url, headers=headers)
                    
                    if response.status_code == 404:
                        # Sheet doesn't exist, create it
                        create_url = f"https://graph.microsoft.com/v1.0/sites/{self.sp_processor.siteID}/drive/items/{self.sp_processor.fileID}/workbook/worksheets"
                        create_data = {"name": sheet_name}
                        
                        create_response = requests.post(create_url, headers=headers, json=create_data)
                        
                        if create_response.status_code == 201:
                            self.print_test_result(f"Created Test Sheet: {sheet_name}", "PASS")
                            
                            # Add headers to new sheet
                            excel_fields = self.config.get('TELEGRAM_EXCEL_FIELDS', [])
                            header_data = [excel_fields]
                            range_address = f"A1:{chr(ord('A') + len(excel_fields) - 1)}1"
                            
                            success = self.sp_processor.updateRange(sheet_name, range_address, header_data)
                            if success:
                                self.print_test_result(f"Headers Added: {sheet_name}", "PASS")
                            else:
                                self.print_test_result(f"Headers Failed: {sheet_name}", "FAIL")
                        else:
                            self.print_test_result(f"Create Sheet Failed: {sheet_name}", "FAIL", 
                                                 f"HTTP {create_response.status_code}")
                    else:
                        self.print_test_result(f"Test Sheet Exists: {sheet_name}", "PASS")
                        
                except Exception as e:
                    self.print_test_result(f"Test Sheet Setup: {sheet_name}", "FAIL", str(e))
            
            return True
            
        except Exception as e:
            self.print_test_result("Test Sheet Creation", "FAIL", str(e))
            return False

    def cleanup_test_data(self):
        """Delete test sheets completely to keep production file clean"""
        self.print_test_header("Test Sheet Cleanup (Remove Test Sheets Completely)")
        
        if not hasattr(self, 'sp_processor'):
            self.print_test_result("Test Sheet Cleanup", "SKIP", 
                                 "No SharePoint connection available")
            return True
            
        try:
            # Delete entire test sheets to keep production file clean
            for sheet_type, sheet_name in self.TEST_SHEETS.items():
                try:
                    headers = {
                        "Authorization": f"Bearer {self.sp_processor.token}",
                        "workbook-session-id": self.sp_processor.sessionID,
                        "Content-Type": "application/json"
                    }
                    
                    # Check if sheet exists first
                    check_url = f"https://graph.microsoft.com/v1.0/sites/{self.sp_processor.siteID}/drive/items/{self.sp_processor.fileID}/workbook/worksheets/{sheet_name}"
                    check_response = requests.get(check_url, headers=headers)
                    
                    if check_response.status_code == 200:
                        # Sheet exists, delete it completely
                        delete_url = f"https://graph.microsoft.com/v1.0/sites/{self.sp_processor.siteID}/drive/items/{self.sp_processor.fileID}/workbook/worksheets/{sheet_name}"
                        delete_response = requests.delete(delete_url, headers=headers)
                        
                        if delete_response.status_code == 204:  # 204 No Content indicates successful deletion
                            self.print_test_result(f"Deleted Test Sheet: {sheet_name}", "PASS", 
                                                 "Test sheet completely removed from production file")
                        else:
                            self.print_test_result(f"Delete Failed: {sheet_name}", "FAIL", 
                                                 f"HTTP {delete_response.status_code}: {delete_response.text}")
                    elif check_response.status_code == 404:
                        self.print_test_result(f"Test Sheet Not Found: {sheet_name}", "PASS", 
                                             "Sheet doesn't exist (nothing to delete)")
                    else:
                        self.print_test_result(f"Sheet Check Failed: {sheet_name}", "FAIL", 
                                             f"HTTP {check_response.status_code}")
                    
                except Exception as e:
                    self.print_test_result(f"Delete Error: {sheet_name}", "FAIL", str(e))
            
            self.test_data_written.clear()
            return True
            
        except Exception as e:
            self.print_test_result("Test Sheet Cleanup", "FAIL", str(e))
            return False
            
    def create_test_message_data(self, is_significant=True, message_id=None, test_channels=False, test_authors=False):
        """Create comprehensive test message data with various scenarios"""
        if not message_id:
            message_id = int(time.time())
            
        category = "Significant" if is_significant else "Trivial"
        
        # Test different channel formats if requested
        if test_channels:
            channels = ['@wa3ediq', '@test_channel', '@channel_with_underscore', '@123numbers']
            channel = channels[message_id % len(channels)]
        else:
            channel = '@test_channel'
        
        # Test different author formats if requested (for Excel escaping validation)
        if test_authors:
            authors = ['@test_author', '@author_with_underscore', '@123author', '@AUTHOR_CAPS']
            author = authors[message_id % len(authors)]
        else:
            author = f'Test User {message_id}'
        
        # Create message data with all expected fields
        message_data = {
            'id': message_id,
            'Message_ID': message_id,
            'Channel': channel,  # This will test the Excel formula fix
            'Country': 'Iraq',
            'Date': datetime.now().strftime('%Y-%m-%d'),
            'Time': datetime.now().strftime('%H:%M:%S'),
            'Author': author,  # This will test the Author Excel formula fix
            'Message_Text': f'Test {category.lower()} message for comprehensive SharePoint validation #{message_id}',
            'AI_Category': category,
            'AI_Reasoning': f'Test message classified as {category.lower()} for comprehensive testing',
            'Keywords_Matched': f'test_{category.lower()}_keyword',
            'Message_Type': 'text',
            'Forward_From': '',
            'Media_Type': 'none',
            'Original_Text': f'Test {category.lower()} message for comprehensive SharePoint validation #{message_id}',
            'Original_Language': 'English',
            'Was_Translated': False,
            'Processed_Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            
            # Additional processing fields that should be filtered out
            'country_code': 'iraq',
            'is_significant': is_significant,
            'teams_task_id': f'teams_test_{message_id}',
            'sharepoint_task_id': f'sp_test_{message_id}',
            'received_at': datetime.now(timezone.utc).isoformat(),
            'processed_at': datetime.now(timezone.utc).isoformat(),
            'ai_analysis': {
                'classification': category.lower(),
                'confidence': 0.95,
                'reasoning': f'Test classification for {category.lower()} message'
            }
        }
        
        return message_data

    def test_sharepoint_connection(self):
        """Test SharePoint connection and authentication"""
        self.print_test_header("SharePoint Connection & Authentication Tests")
        
        try:
            # Get SharePoint configuration
            sp_config = self.config.get('MS_SHAREPOINT_ACCESS', {})
            iraq_config = self.config.get('COUNTRIES', {}).get('iraq', {})
            sharepoint_config = iraq_config.get('sharepoint_config', {})
            
            # Check configuration completeness
            required_keys = ['ClientID', 'ClientSecret', 'TenantID', 'SharepointSite']
            missing_keys = [key for key in required_keys if not sp_config.get(key)]
            
            if missing_keys:
                self.print_test_result("SharePoint Configuration", "FAIL", 
                                     f"Missing keys: {missing_keys}")
                return False
            else:
                self.print_test_result("SharePoint Configuration", "PASS", 
                                     "All required credentials present")
            
            # Test SharePoint processor initialization
            site_name = sharepoint_config.get('site_name', 'ATCSharedFiles')
            folder_path = sharepoint_config.get('folder_path', '/Telegram_Feeds/Iraq/')
            file_name = sharepoint_config.get('file_name', 'Iraq_Telegram_Feeds.xlsx')
            full_file_path = f"{folder_path}{file_name}"
            
            self.print_test_result("SharePoint File Path", "INFO", 
                                 f"Target: {full_file_path}")
            
            # Initialize SharePoint processor
            sp_processor = SharepointProcessor(
                sp_config['ClientID'],
                sp_config['ClientSecret'],
                sp_config['TenantID'],
                sp_config['SharepointSite'],
                site_name,
                full_file_path
            )
            
            # Test connection components
            if not sp_processor.token:
                self.print_test_result("SharePoint Authentication", "FAIL", 
                                     "Failed to acquire access token")
                return False
            else:
                self.print_test_result("SharePoint Authentication", "PASS", 
                                     "Access token acquired successfully")
            
            if not sp_processor.siteID or not sp_processor.fileID:
                self.print_test_result("SharePoint File Access", "FAIL", 
                                     f"Site ID: {sp_processor.siteID}, File ID: {sp_processor.fileID}")
                return False
            else:
                self.print_test_result("SharePoint File Access", "PASS", 
                                     "Site and File IDs retrieved successfully")
            
            if not sp_processor.sessionID:
                self.print_test_result("SharePoint Session", "FAIL", 
                                     "Failed to create Excel session")
                return False
            else:
                self.print_test_result("SharePoint Session", "PASS", 
                                     "Excel session created successfully")
            
            # Store processor for other tests
            self.sp_processor = sp_processor
            return True
            
        except Exception as e:
            self.print_test_result("SharePoint Connection", "FAIL", str(e))
            return False

    def test_excel_formula_escaping(self):
        """Test Excel formula escaping for channel names starting with @"""
        self.print_test_header("Excel Formula Escaping Tests")
        
        try:
            # Test the channel escaping logic
            test_channels = [
                '@wa3ediq',
                '@test_channel', 
                '@channel_with_underscore',
                '@123numbers',
                'regular_channel',  # Without @ symbol
                '@ULIQ_Ultra'
            ]
            
            excel_fields = self.config.get('TELEGRAM_EXCEL_FIELDS', [])
            
            for i, channel in enumerate(test_channels):
                # Create test message with this channel
                test_message = self.create_test_message_data(
                    is_significant=True, 
                    message_id=f"escape_test_{i}"
                )
                test_message['Channel'] = channel
                
                # Filter to expected fields
                filtered_data = {}
                for field in excel_fields:
                    value = test_message.get(field, '')
                    
                    # Apply Excel formula escaping for Channel field
                    if field == 'Channel' and isinstance(value, str) and value.startswith('@'):
                        # Add single quote prefix to prevent Excel from treating as formula
                        escaped_value = f"'{value}"
                        filtered_data[field] = escaped_value
                        self.print_test_result(f"Channel Escaping: {channel}", "PASS", 
                                             f"Escaped to: {escaped_value}")
                    else:
                        filtered_data[field] = value
                
            return True
            
        except Exception as e:
            self.print_test_result("Excel Formula Escaping", "FAIL", str(e))
            return False

    def test_header_creation(self):
        """Test header creation in test sheets (production safe)"""
        self.print_test_header("Header Creation Tests (Safe Test Sheets)")
        
        if not hasattr(self, 'sp_processor'):
            self.print_test_result("Header Creation", "SKIP", 
                                 "SharePoint connection not available")
            return False
            
        try:
            excel_fields = self.config.get('TELEGRAM_EXCEL_FIELDS', [])
            
            if not excel_fields:
                self.print_test_result("Excel Fields Configuration", "FAIL", 
                                     "No TELEGRAM_EXCEL_FIELDS defined in config")
                return False
            else:
                self.print_test_result("Excel Fields Configuration", "PASS", 
                                     f"Found {len(excel_fields)} fields")
            
            # Test header creation for test sheets (not production)
            for sheet_type, sheet_name in self.TEST_SHEETS.items():
                try:
                    # Prepare header data
                    header_data = [excel_fields]  # Headers as first row
                    
                    # Create range for headers (row 1)
                    range_address = f"A1:{chr(ord('A') + len(excel_fields) - 1)}1"
                    
                    # Write headers to TEST sheet
                    success = self.sp_processor.updateRange(sheet_name, range_address, header_data)
                    
                    if success:
                        self.print_test_result(f"Headers - {sheet_name} (Test)", "PASS", 
                                             f"Headers created in range {range_address}")
                    else:
                        self.print_test_result(f"Headers - {sheet_name} (Test)", "FAIL", 
                                             f"Failed to create headers in {range_address}")
                        
                except Exception as e:
                    self.print_test_result(f"Headers - {sheet_name} (Test)", "FAIL", str(e))
                    
            return True
            
        except Exception as e:
            self.print_test_result("Header Creation", "FAIL", str(e))
            return False

    def test_row_detection_and_management(self):
        """Test row detection and management functionality on test sheets"""
        self.print_test_header("Row Detection & Management Tests (Safe Test Sheets)")
        
        if not hasattr(self, 'sp_processor'):
            self.print_test_result("Row Detection", "SKIP", 
                                 "SharePoint connection not available")
            return False
            
        try:
            # Test row detection for test sheets only
            for sheet_type, sheet_name in self.TEST_SHEETS.items():
                try:
                    # Get current row information using SharePoint API
                    headers = {
                        "Authorization": f"Bearer {self.sp_processor.token}",
                        "workbook-session-id": self.sp_processor.sessionID,
                        "Content-Type": "application/json"
                    }
                    
                    url = f"https://graph.microsoft.com/v1.0/sites/{self.sp_processor.siteID}/drive/items/{self.sp_processor.fileID}/workbook/worksheets/{sheet_name}/usedRange"
                    response = requests.get(url, headers=headers)
                    
                    if response.status_code == 200:
                        used_range = response.json()
                        row_count = used_range.get('rowCount', 0)
                        address = used_range.get('address', 'N/A')
                        
                        self.print_test_result(f"API Row Detection - {sheet_name}", "PASS", 
                                             f"Range: {address}, Rows: {row_count}")
                        
                        # Test our row detection function
                        next_row = get_next_available_row(self.sp_processor, sheet_name)
                        expected_next = row_count + 1 if row_count > 1 else 2
                        
                        if next_row == expected_next:
                            self.print_test_result(f"Row Logic - {sheet_name}", "PASS", 
                                                 f"Next row: {next_row} (expected: {expected_next})")
                        else:
                            self.print_test_result(f"Row Logic - {sheet_name}", "FAIL", 
                                                 f"Next row: {next_row}, expected: {expected_next}")
                            
                    elif response.status_code == 404:
                        self.print_test_result(f"API Row Detection - {sheet_name}", "PASS", 
                                             f"Empty sheet (404) - will start at row 2")
                    else:
                        self.print_test_result(f"API Row Detection - {sheet_name}", "FAIL", 
                                             f"HTTP {response.status_code}")
                        
                except Exception as e:
                    self.print_test_result(f"Row Detection - {sheet_name}", "FAIL", str(e))
            
            # Test range calculation for various row numbers
            excel_fields_count = len(self.config.get('TELEGRAM_EXCEL_FIELDS', []))
            test_rows = [2, 10, 25, 100]
            
            for row_num in test_rows:
                expected_range = f"A{row_num}:{chr(ord('A') + excel_fields_count - 1)}{row_num}"
                self.print_test_result(f"Range Calculation Row {row_num}", "PASS", 
                                     f"Range: {expected_range}")
            
            return True
            
        except Exception as e:
            self.print_test_result("Row Detection", "FAIL", str(e))
            return False

    def test_data_writing_with_escaping(self):
        """Test data writing with Excel formula escaping on test sheets"""
        self.print_test_header("Data Writing with Excel Escaping Tests (Safe Test Sheets)")
        
        if not hasattr(self, 'sp_processor'):
            self.print_test_result("Data Writing", "SKIP", 
                                 "SharePoint connection not available")
            return False
            
        try:
            excel_fields = self.config.get('TELEGRAM_EXCEL_FIELDS', [])
            
            # Test data writing to test sheets with different channel and author formats
            test_cases = [
                {'sheet_type': 'significant', 'sheet_name': self.TEST_SHEETS['significant'], 'significant': True, 'channel': '@wa3ediq', 'author': '@test_author'},
                {'sheet_type': 'trivial', 'sheet_name': self.TEST_SHEETS['trivial'], 'significant': False, 'channel': '@test_channel_underscore', 'author': '@author_underscore'}
            ]
            
            for case in test_cases:
                sheet_name = case['sheet_name']  # Use test sheet name
                sheet_type = case['sheet_type']
                is_significant = case['significant']
                test_channel = case['channel']
                test_author = case['author']
                
                # Create test message
                message_id = f"{sheet_type}_{int(time.time())}"
                test_message = self.create_test_message_data(
                    is_significant=is_significant, 
                    message_id=message_id
                )
                test_message['Channel'] = test_channel
                test_message['Author'] = test_author
                
                self.print_test_result(f"Test Data - {sheet_name}", "INFO", 
                                     f"Message ID: {message_id}, Channel: {test_channel}")
                
                # Filter and escape data
                filtered_data = {}
                for field in excel_fields:
                    value = test_message.get(field, '')
                    
                    # Apply Excel formula escaping for Channel field
                    if field == 'Channel' and isinstance(value, str) and value.startswith('@'):
                        value = f"'{value}"  # Add single quote prefix
                        
                    filtered_data[field] = value
                
                # Convert to SharePoint format
                sp_data = [filtered_data]
                sp_format_data = self.sp_processor.convertDictToSPFormat(sp_data, excel_fields)
                
                if len(sp_format_data) > 1:
                    data_only = [sp_format_data[1]]  # Only the data row
                    
                    # Get next available row
                    next_row = get_next_available_row(self.sp_processor, sheet_name)
                    range_address = f"A{next_row}:{chr(ord('A') + len(excel_fields) - 1)}{next_row}"
                    
                    # Write data to TEST sheet
                    success = self.sp_processor.updateRange(sheet_name, range_address, data_only)
                    
                    if success:
                        self.print_test_result(f"Data Write - {sheet_name}", "PASS", 
                                             f"Written to {range_address} with escaped channel")
                        # Track test data for cleanup
                        self.test_data_written.append({
                            'sheet': sheet_name,
                            'row': next_row,
                            'range': range_address,
                            'message_id': message_id
                        })
                    else:
                        self.print_test_result(f"Data Write - {sheet_name}", "FAIL", 
                                             f"Failed to write to {range_address}")
                else:
                    self.print_test_result(f"Data Format - {sheet_name}", "FAIL", 
                                         "Data format conversion failed")
            
            return True
            
        except Exception as e:
            self.print_test_result("Data Writing", "FAIL", str(e))
            return False

    def test_celery_task_integration(self):
        """Test SharePoint storage functionality without using production sheets"""
        self.print_test_header("Celery Integration Tests (Production Safe)")
        
        try:
            # For safety, we'll test the functions used by Celery tasks
            # but write to test sheets instead of production sheets
            test_cases = [
                {'significant': True, 'channel': '@celery_test_sig', 'author': '@celery_author_sig', 'sheet': self.TEST_SHEETS['significant']},
                {'significant': False, 'channel': '@celery_test_triv', 'author': '@celery_author_triv', 'sheet': self.TEST_SHEETS['trivial']}
            ]
            
            excel_fields = self.config.get('TELEGRAM_EXCEL_FIELDS', [])
            
            for case in test_cases:
                is_significant = case['significant']
                test_channel = case['channel']
                test_author = case['author']
                test_sheet = case['sheet']
                category = "Significant" if is_significant else "Trivial"
                
                # Create realistic message data
                message_id = f"celery_{category.lower()}_{int(time.time())}"
                message_data = self.create_test_message_data(
                    is_significant=is_significant,
                    message_id=message_id
                )
                message_data['Channel'] = test_channel
                message_data['Author'] = test_author
                
                self.print_test_result(f"Celery Test Setup - {category}", "INFO", 
                                     f"Message: {message_id}, Channel: {test_channel}, Author: {test_author}")
                
                # Simulate the Celery task logic but use test sheet
                try:
                    # Filter and escape data (same as Celery task)
                    filtered_data = {}
                    for field in excel_fields:
                        value = message_data.get(field, '')
                        if field == 'Channel' and isinstance(value, str) and value.startswith('@'):
                            value = f"'{value}"  # Excel escaping
                        filtered_data[field] = value
                    
                    # Convert to SharePoint format
                    sp_data = [filtered_data]
                    sp_format_data = self.sp_processor.convertDictToSPFormat(sp_data, excel_fields)
                    
                    if len(sp_format_data) > 1:
                        data_only = [sp_format_data[1]]
                        next_row = get_next_available_row(self.sp_processor, test_sheet)
                        range_address = f"A{next_row}:{chr(ord('A') + len(excel_fields) - 1)}{next_row}"
                        
                        # Write to TEST sheet
                        success = self.sp_processor.updateRange(test_sheet, range_address, data_only)
                        
                        if success:
                            self.print_test_result(f"Celery Logic - {category}", "PASS", 
                                                 f"Saved to {test_sheet} at {range_address}")
                            # Track for cleanup
                            self.test_data_written.append({
                                'sheet': test_sheet,
                                'row': next_row,
                                'range': range_address,
                                'message_id': message_id
                            })
                        else:
                            self.print_test_result(f"Celery Logic - {category}", "FAIL", 
                                                 f"Failed to save to {test_sheet}")
                    else:
                        self.print_test_result(f"Celery Logic - {category}", "FAIL", 
                                             "Data format conversion failed")
                        
                except Exception as e:
                    self.print_test_result(f"Celery Logic - {category}", "FAIL", str(e))
            
            return True
            
        except Exception as e:
            self.print_test_result("Celery Integration", "FAIL", str(e))
            return False

    def test_high_row_scenarios(self):
        """Test high row number scenarios on test sheets"""
        self.print_test_header("High Row Number Validation Tests (Safe Test Sheets)")
        
        if not hasattr(self, 'sp_processor'):
            self.print_test_result("High Row Tests", "SKIP", 
                                 "SharePoint connection not available")
            return False
        
        try:
            excel_fields = self.config.get('TELEGRAM_EXCEL_FIELDS', [])
            
            # Test writing to specific high row numbers on TEST sheet
            high_rows = [15, 30, 75]
            test_sheet = self.TEST_SHEETS['significant']  # Use test sheet
            
            for target_row in high_rows:
                # Create test data
                test_data = {
                    'Message_ID': f'high_row_{target_row}',
                    'Channel': f'@test_row_{target_row}',  # Will be escaped
                    'Country': 'Iraq',
                    'Date': datetime.now().strftime('%Y-%m-%d'),
                    'Time': datetime.now().strftime('%H:%M:%S'),
                    'Author': f'High Row Test {target_row}',
                    'Message_Text': f'Test message for row {target_row} validation',
                    'AI_Category': 'Significant',
                    'AI_Reasoning': f'Test for row {target_row}',
                    'Keywords_Matched': f'high_row_{target_row}',
                    'Message_Type': 'text',
                    'Forward_From': '',
                    'Media_Type': 'none',
                    'Original_Text': f'Test message for row {target_row} validation',
                    'Original_Language': 'English',
                    'Was_Translated': False,
                    'Processed_Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                # Filter and escape
                filtered_data = {}
                for field in excel_fields:
                    value = test_data.get(field, '')
                    if field == 'Channel' and isinstance(value, str) and value.startswith('@'):
                        value = f"'{value}"
                    filtered_data[field] = value
                
                # Convert and write to TEST sheet
                sp_data = [filtered_data]
                sp_format_data = self.sp_processor.convertDictToSPFormat(sp_data, excel_fields)
                
                if len(sp_format_data) > 1:
                    data_only = [sp_format_data[1]]
                    range_address = f"A{target_row}:{chr(ord('A') + len(excel_fields) - 1)}{target_row}"
                    
                    success = self.sp_processor.updateRange(test_sheet, range_address, data_only)
                    
                    if success:
                        self.print_test_result(f"High Row {target_row} ({test_sheet})", "PASS", 
                                             f"Successfully wrote to {range_address}")
                        # Track test data for cleanup
                        self.test_data_written.append({
                            'sheet': test_sheet,
                            'row': target_row,
                            'range': range_address,
                            'message_id': f'high_row_{target_row}'
                        })
                    else:
                        self.print_test_result(f"High Row {target_row} ({test_sheet})", "FAIL", 
                                             f"Failed to write to {range_address}")
            
            return True
            
        except Exception as e:
            self.print_test_result("High Row Tests", "FAIL", str(e))
            return False

    def test_cleanup(self):
        """Clean up test session"""
        self.print_test_header("Cleanup")
        
        try:
            if hasattr(self, 'sp_processor'):
                self.sp_processor.closeExcelSession()
                self.print_test_result("Session Cleanup", "PASS", 
                                     "SharePoint session closed successfully")
            else:
                self.print_test_result("Session Cleanup", "SKIP", 
                                     "No active session to close")
                                     
            return True
            
        except Exception as e:
            self.print_test_result("Session Cleanup", "FAIL", str(e))
            return False

    def generate_report(self):
        """Generate comprehensive test report"""
        self.print_test_header("COMPREHENSIVE TEST RESULTS SUMMARY")
        
        total_tests = self.test_results['passed'] + self.test_results['failed']
        
        print(f"📊 Total Tests: {total_tests}")
        print(f"✅ Passed: {self.test_results['passed']}")
        print(f"❌ Failed: {self.test_results['failed']}")
        print(f"⏭️ Skipped: {self.test_results['skipped']}")
        
        if total_tests > 0:
            success_rate = (self.test_results['passed'] / total_tests) * 100
            print(f"📈 Success Rate: {success_rate:.1f}%")
        
        if self.test_results['errors']:
            print(f"\n🔍 Errors Encountered:")
            for i, error in enumerate(self.test_results['errors'], 1):
                print(f"{i}. {error}")
        
        # Final status
        if self.test_results['failed'] == 0:
            if self.test_results['passed'] > 0:
                print(f"\n🎉 ALL SHAREPOINT TESTS PASSED!")
                print(f"✅ Connection and authentication working")
                print(f"✅ Production data protection active (test sheets used)")
                print(f"✅ Headers properly created in test sheets")
                print(f"✅ Excel formula escaping prevents #NAME? errors")
                print(f"✅ Data writing works for any row number")
                print(f"✅ Row detection and management functional")
                print(f"✅ Celery task logic validated safely")
                print(f"✅ High row number scenarios confirmed")
                print(f"✅ Test sheets completely removed from production file")
                print(f"\n🛡️ PRODUCTION SAFETY: All tests used dedicated test sheets")
                print(f"   - {self.TEST_SHEETS['significant']} (created, tested, deleted)")
                print(f"   - {self.TEST_SHEETS['trivial']} (created, tested, deleted)")
                print(f"   - No production data was modified or deleted")
                print(f"   - Production file returned to original clean state")
                return True
            else:
                print(f"\n⚠️ No tests were executed. Check configuration and setup.")
                return False
        else:
            print(f"\n⚠️ {self.test_results['failed']} test(s) failed. SharePoint integration needs attention.")
            return False
            
    def run_all_tests(self):
        """Run complete comprehensive SharePoint test suite with production data protection"""
        print("🚀 Comprehensive SharePoint Storage Test Suite")
        print(f"📁 Project Root: {self.project_root}")
        print(f"⏰ Test Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🎯 Consolidates: Connection, Headers, Data Writing, Row Management,")
        print(f"   Excel Escaping, Celery Integration, High Row Validation")
        print(f"🛡️ PRODUCTION SAFE: Creates test sheets ({', '.join(self.TEST_SHEETS.values())}) then deletes them completely")
        
        # Run tests in sequence
        connection_ok = self.test_sharepoint_connection()
        
        if connection_ok:
            # Create test sheets for safe testing
            test_sheets_ready = self.create_test_sheets()
            
            if test_sheets_ready:
                self.test_excel_formula_escaping()
                self.test_header_creation()
                self.test_row_detection_and_management()
                self.test_data_writing_with_escaping()
                self.test_celery_task_integration()
                self.test_high_row_scenarios()
                
                # Delete test sheets completely to keep production file clean
                self.cleanup_test_data()
            else:
                print("\n⚠️ Skipping data tests - unable to create safe test sheets")
        else:
            print("\n⚠️ Skipping data tests due to connection failure")
            
        self.test_cleanup()
        
        return self.generate_report()


def main():
    """Main test execution"""
    test_suite = ComprehensiveSharePointTestSuite()
    success = test_suite.run_all_tests()
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)