#!/usr/bin/env python3
"""
SharePoint Debug & Maintenance Utilities

Complementary utility for comprehensive SharePoint testing.
Provides debugging tools and maintenance functions for SharePoint integration.
"""

import sys
import os
import json
import requests
from datetime import datetime

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.integrations.sharepoint_utils import SharepointProcessor


class SharePointDebugUtilities:
    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.config = self.load_config()
        
    def load_config(self):
        """Load configuration file"""
        config_path = os.path.join(self.project_root, "config", "config.json")
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Failed to load configuration: {e}")
            return {}
    
    def debug_data_format(self):
        """Debug data format and field mapping"""
        print("🔍 SharePoint Data Format Debug")
        print("=" * 50)
        
        excel_fields = self.config.get('TELEGRAM_EXCEL_FIELDS', [])
        print(f"📊 Excel Fields ({len(excel_fields)}):")
        for i, field in enumerate(excel_fields, 1):
            print(f"  {i:2d}. {field}")
        
        # Sample message data
        sample_message = {
            'Message_ID': 'debug_sample',
            'Channel': '@debug_channel',  # This will test escaping
            'Country': 'Iraq',
            'Date': datetime.now().strftime('%Y-%m-%d'),
            'Time': datetime.now().strftime('%H:%M:%S'),
            'Author': 'Debug User',
            'Message_Text': 'Debug message for format testing',
            'AI_Category': 'Significant',
            'AI_Reasoning': 'Debug classification',
            'Keywords_Matched': 'debug_keyword',
            'Message_Type': 'text',
            'Forward_From': '',
            'Media_Type': 'none',
            'Original_Text': 'Debug message for format testing',
            'Original_Language': 'English',
            'Was_Translated': False,
            'Processed_Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            
            # Extra fields that should be filtered out
            'extra_field_1': 'should_be_removed',
            'extra_field_2': 'should_be_removed'
        }
        
        print(f"\n📝 Raw Message Fields ({len(sample_message)}):")
        for field, value in sample_message.items():
            print(f"  {field}: {value}")
        
        # Filter to expected fields with escaping
        filtered_data = {}
        for field in excel_fields:
            value = sample_message.get(field, '')
            
            # Apply Excel formula escaping
            if field == 'Channel' and isinstance(value, str) and value.startswith('@'):
                value = f"'{value}"
                print(f"\n🛡️  Excel Escaping Applied: Channel '{sample_message['Channel']}' → '{value}'")
                
            filtered_data[field] = value
        
        print(f"\n✅ Filtered Data ({len(filtered_data)}):")
        for field, value in filtered_data.items():
            print(f"  {field}: {value}")
        
        return filtered_data
    
    def debug_range_calculation(self):
        """Debug Excel range calculations"""
        print("\n🎯 Excel Range Calculation Debug")
        print("=" * 50)
        
        excel_fields = self.config.get('TELEGRAM_EXCEL_FIELDS', [])
        field_count = len(excel_fields)
        
        test_rows = [1, 2, 10, 25, 50, 100]
        
        for row in test_rows:
            last_column = chr(ord('A') + field_count - 1)
            range_address = f"A{row}:{last_column}{row}"
            print(f"  Row {row:3d}: {range_address}")
        
        print(f"\n📊 Total Fields: {field_count}")
        print(f"📍 Last Column: {chr(ord('A') + field_count - 1)}")
    
    def check_sharepoint_status(self):
        """Check SharePoint connection and file status"""
        print("\n🔗 SharePoint Connection Status")
        print("=" * 50)
        
        try:
            # Get configuration
            sp_config = self.config.get('MS_SHAREPOINT_ACCESS', {})
            iraq_config = self.config.get('COUNTRIES', {}).get('iraq', {})
            sharepoint_config = iraq_config.get('sharepoint_config', {})
            
            site_name = sharepoint_config.get('site_name', 'ATCSharedFiles')
            folder_path = sharepoint_config.get('folder_path', '/Telegram_Feeds/Iraq/')
            file_name = sharepoint_config.get('file_name', 'Iraq_Telegram_Feeds.xlsx')
            full_file_path = f"{folder_path}{file_name}"
            
            print(f"📂 Site: {site_name}")
            print(f"📁 Path: {full_file_path}")
            
            # Initialize processor
            sp_processor = SharepointProcessor(
                sp_config['ClientID'],
                sp_config['ClientSecret'],
                sp_config['TenantID'],
                sp_config['SharepointSite'],
                site_name,
                full_file_path
            )
            
            print(f"🔑 Token: {'✅ Available' if sp_processor.token else '❌ Missing'}")
            print(f"🏢 Site ID: {sp_processor.siteID[:20] + '...' if sp_processor.siteID else '❌ Missing'}")
            print(f"📄 File ID: {sp_processor.fileID[:20] + '...' if sp_processor.fileID else '❌ Missing'}")
            print(f"🔧 Session: {'✅ Active' if sp_processor.sessionID else '❌ Missing'}")
            
            # Check sheets
            for sheet_name in ['Significant', 'Trivial']:
                try:
                    headers = {
                        "Authorization": f"Bearer {sp_processor.token}",
                        "workbook-session-id": sp_processor.sessionID,
                        "Content-Type": "application/json"
                    }
                    
                    url = f"https://graph.microsoft.com/v1.0/sites/{sp_processor.siteID}/drive/items/{sp_processor.fileID}/workbook/worksheets/{sheet_name}/usedRange"
                    response = requests.get(url, headers=headers)
                    
                    if response.status_code == 200:
                        used_range = response.json()
                        row_count = used_range.get('rowCount', 0)
                        address = used_range.get('address', 'N/A')
                        print(f"📊 {sheet_name}: {row_count} rows, Range: {address}")
                    elif response.status_code == 404:
                        print(f"📊 {sheet_name}: Empty sheet (404)")
                    else:
                        print(f"📊 {sheet_name}: HTTP {response.status_code}")
                        
                except Exception as e:
                    print(f"📊 {sheet_name}: Error - {str(e)}")
            
            # Cleanup
            sp_processor.closeExcelSession()
            print("🧹 Session closed")
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
    
    def run_debug_suite(self):
        """Run complete debug suite"""
        print("🛠️  SharePoint Debug & Maintenance Utilities")
        print(f"📁 Project Root: {self.project_root}")
        print(f"⏰ Debug Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        self.debug_data_format()
        self.debug_range_calculation()
        self.check_sharepoint_status()
        
        print("\n✅ Debug suite completed!")


def main():
    """Main debug execution"""
    debug_utils = SharePointDebugUtilities()
    debug_utils.run_debug_suite()


if __name__ == "__main__":
    main()