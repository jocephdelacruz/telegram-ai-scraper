#!/usr/bin/env python3
"""
Test script to create a fake recent message and test the processing pipeline
"""

import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def test_message_processing():
    """Test the message processing pipeline with a fake recent message"""
    try:
        from src.tasks.telegram_celery_tasks import process_telegram_message
        from src.core import file_handling as fh
        
        # Load config using absolute path
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(project_root, "config", "config.json")
        config_handler = fh.FileHandling(config_path)
        config = config_handler.read_json()
        
        # Create fake messages for Iraq dual-language keyword tests
        current_time = datetime.now()
        messages = [
            {
                'Message_ID': 999999,
                'Channel': '@test_channel',
                'Date': current_time.strftime('%Y-%m-%d'),
                'Time': current_time.strftime('%H:%M:%S'),
                'Author': '@test_user',
                'Message_Text': 'protest in Baghdad',
                'text': 'protest in Baghdad',
                'id': 999999,
                'channel': '@test_channel',
                'country_code': 'iraq',
                'Country': 'Iraq',
                'desc': 'Iraq English significant keyword'
            },
            {
                'Message_ID': 1000000,
                'Channel': '@test_channel',
                'Date': current_time.strftime('%Y-%m-%d'),
                'Time': current_time.strftime('%H:%M:%S'),
                'Author': '@test_user',
                'Message_Text': 'احتجاج في بغداد',
                'text': 'احتجاج في بغداد',
                'id': 1000000,
                'channel': '@test_channel',
                'country_code': 'iraq',
                'Country': 'Iraq',
                'desc': 'Iraq Arabic significant keyword'
            },
            {
                'Message_ID': 1000001,
                'Channel': '@test_channel',
                'Date': current_time.strftime('%Y-%m-%d'),
                'Time': current_time.strftime('%H:%M:%S'),
                'Author': '@test_user',
                'Message_Text': 'This is a sports update',
                'text': 'This is a sports update',
                'id': 1000001,
                'channel': '@test_channel',
                'country_code': 'iraq',
                'Country': 'Iraq',
                'desc': 'Iraq English trivial keyword'
            },
            {
                'Message_ID': 1000002,
                'Channel': '@test_channel',
                'Date': current_time.strftime('%Y-%m-%d'),
                'Time': current_time.strftime('%H:%M:%S'),
                'Author': '@test_user',
                'Message_Text': 'رياضة اليوم',
                'text': 'رياضة اليوم',
                'id': 1000002,
                'channel': '@test_channel',
                'country_code': 'iraq',
                'Country': 'Iraq',
                'desc': 'Iraq Arabic trivial keyword'
            },
            {
                'Message_ID': 1000003,
                'Channel': '@test_channel',
                'Date': current_time.strftime('%Y-%m-%d'),
                'Time': current_time.strftime('%H:%M:%S'),
                'Author': '@test_user',
                'Message_Text': 'advertisement: buy now!',
                'text': 'advertisement: buy now!',
                'id': 1000003,
                'channel': '@test_channel',
                'country_code': 'iraq',
                'Country': 'Iraq',
                'desc': 'Iraq English exclude keyword'
            },
            {
                'Message_ID': 1000004,
                'Channel': '@test_channel',
                'Date': current_time.strftime('%Y-%m-%d'),
                'Time': current_time.strftime('%H:%M:%S'),
                'Author': '@test_user',
                'Message_Text': 'إعلان هام',
                'text': 'إعلان هام',
                'id': 1000004,
                'channel': '@test_channel',
                'country_code': 'iraq',
                'Country': 'Iraq',
                'desc': 'Iraq Arabic exclude keyword'
            }
        ]

        for msg in messages:
            print(f"\n🧪 Testing message: {msg['desc']}")
            print(f"Message ID: {msg['Message_ID']}")
            print(f"Message Text: {msg['Message_Text']}")
            print(f"Date/Time: {msg['Date']} {msg['Time']}")
            task = process_telegram_message.delay(msg, config)
            print(f"✅ Task submitted: {task.id}")
            print(f"📋 Check logs/telegram_tasks.log for processing results")
            print(f"📋 Check Redis: redis-cli -n 1 get 'processed_msg:@test_channel:{msg['Message_ID']}'")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def main():
    """Run the test"""
    print("=" * 60)
    print("🧪 MESSAGE PROCESSING PIPELINE TEST")
    print("=" * 60)
    
    task_id = test_message_processing()
    
    if task_id:
        print(f"\n✅ Test completed successfully!")
        print(f"Monitor the task execution in logs...")
    else:
        print(f"\n❌ Test failed!")

if __name__ == "__main__":
    main()