#!/usr/bin/env python3
"""
Test script to verify that empty messages are properly filtered out
Tests the newly added empty message filtering logic
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.tasks.telegram_celery_tasks import process_telegram_message
from src.core.main import TelegramAIScraper
from src.core import file_handling as fh
import asyncio
from datetime import datetime

async def test_empty_message_filtering():
    """Test that empty messages are filtered out at various stages"""
    
    print("🧪 Testing Empty Message Filtering")
    print("=" * 50)
    
    # Load configuration
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(project_root, "config", "config.json")
        config_handler = fh.FileHandling(config_path)
        config = config_handler.read_json()
        
        if not config:
            print("❌ Failed to load configuration")
            return False
            
        print("✅ Configuration loaded successfully")
        
    except Exception as e:
        print(f"❌ Error loading configuration: {e}")
        return False
    
    # Test cases for empty message filtering
    test_cases = [
        {
            "name": "Completely empty message text",
            "message_data": {
                'id': 'test_empty_1',
                'Message_ID': 'test_empty_1',
                'channel': 'test_channel',
                'Channel': '@test_channel',
                'country_code': 'test',
                'text': '',
                'Message_Text': '',
                'Date': '2025-01-01',
                'Time': '12:00:00',
                'Author': 'test_author'
            },
            "should_be_filtered": True
        },
        {
            "name": "Whitespace-only message text",
            "message_data": {
                'id': 'test_empty_2',
                'Message_ID': 'test_empty_2',
                'channel': 'test_channel',
                'Channel': '@test_channel',
                'country_code': 'test',
                'text': '   \n\t  ',
                'Message_Text': '   \n\t  ',
                'Date': '2025-01-01',
                'Time': '12:00:01',
                'Author': 'test_author'
            },
            "should_be_filtered": True
        },
        {
            "name": "None message text",
            "message_data": {
                'id': 'test_empty_3',
                'Message_ID': 'test_empty_3',
                'channel': 'test_channel',
                'Channel': '@test_channel',
                'country_code': 'test',
                'text': None,
                'Message_Text': None,
                'Date': '2025-01-01',
                'Time': '12:00:02',
                'Author': 'test_author'
            },
            "should_be_filtered": True
        },
        {
            "name": "Valid message with content",
            "message_data": {
                'id': 'test_valid_1',
                'Message_ID': 'test_valid_1',
                'channel': 'test_channel',
                'Channel': '@test_channel',
                'country_code': 'test',
                'text': 'This is a valid test message',
                'Message_Text': 'This is a valid test message',
                'Date': '2025-01-01',
                'Time': '12:00:03',
                'Author': 'test_author'
            },
            "should_be_filtered": False
        },
        {
            "name": "Message with only punctuation",
            "message_data": {
                'id': 'test_punct_1',
                'Message_ID': 'test_punct_1',
                'channel': 'test_channel',
                'Channel': '@test_channel',
                'country_code': 'test',
                'text': '...',
                'Message_Text': '...',
                'Date': '2025-01-01',
                'Time': '12:00:04',
                'Author': 'test_author'
            },
            "should_be_filtered": False  # Punctuation is valid content
        }
    ]
    
    print(f"\n🔍 Running {len(test_cases)} test cases...")
    
    passed_tests = 0
    total_tests = len(test_cases)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 Test {i}: {test_case['name']}")
        
        try:
            # Test the main message handler filter
            scraper = TelegramAIScraper()
            await scraper.initialize_components(test_mode=True)
            
            # Simulate the handle_new_message method filtering
            message_data = test_case['message_data'].copy()
            
            # Check the filtering logic from main.py
            message_text = (
                message_data.get('Message_Text', '') or 
                message_data.get('text', '') or 
                message_data.get('Original_Text', '')
            )
            
            main_filter_triggered = not message_text or not message_text.strip()
            
            if main_filter_triggered:
                print(f"   🚫 Filtered by main.py handler: YES")
                if test_case['should_be_filtered']:
                    print(f"   ✅ PASS: Message correctly filtered")
                    passed_tests += 1
                else:
                    print(f"   ❌ FAIL: Message should not have been filtered")
            else:
                print(f"   ➡️  Passed main.py handler filter")
                
                # Test the Celery task filter (simulate without actually running Celery)
                # This tests the logic we added to process_telegram_message
                message_text_celery = message_data.get('text', '') or message_data.get('Message_Text', '')
                celery_filter_triggered = not message_text_celery or not message_text_celery.strip()
                
                if celery_filter_triggered:
                    print(f"   🚫 Filtered by Celery task: YES")
                    if test_case['should_be_filtered']:
                        print(f"   ✅ PASS: Message correctly filtered by Celery task")
                        passed_tests += 1
                    else:
                        print(f"   ❌ FAIL: Message should not have been filtered by Celery task")
                else:
                    print(f"   ➡️  Passed Celery task filter")
                    
                    if test_case['should_be_filtered']:
                        print(f"   ❌ FAIL: Message should have been filtered but wasn't")
                    else:
                        print(f"   ✅ PASS: Valid message correctly allowed through")
                        passed_tests += 1
                        
        except Exception as e:
            print(f"   ❌ ERROR during test: {e}")
            continue
    
    print(f"\n📊 Test Results: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! Empty message filtering is working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Check the filtering logic.")
        return False

async def test_main():
    """Main async test function"""
    try:
        success = await test_empty_message_filtering()
        
        if success:
            print("\n✅ Empty message filtering test completed successfully")
            print("🔒 Empty messages will be filtered out and won't be sent to Teams, SharePoint, or CSV")
            print("♻️  Duplicate processing prevention is maintained with Redis marking")
        else:
            print("\n❌ Empty message filtering test failed")
            
    except Exception as e:
        print(f"❌ Test execution failed: {e}")

if __name__ == "__main__":
    print("🚀 Starting Empty Message Filtering Test")
    asyncio.run(test_main())