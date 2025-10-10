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
        
        # Create a fake message that should pass all filters
        current_time = datetime.now()
        fake_message = {
            'Message_ID': 999999,
            'Channel': '@test_channel',
            'Date': current_time.strftime('%Y-%m-%d'),
            'Time': current_time.strftime('%H:%M:%S'),
            'Author': '@test_user',
            'Message_Text': 'This is a test message for processing احتجاج مظاهرة',
            'text': 'This is a test message for processing احتجاج مظاهرة',
            'id': 999999,
            'channel': '@test_channel',
            'country_code': 'iraq',
            'Country': 'Iraq'
        }
        
        print(f"🧪 Testing message processing pipeline...")
        print(f"Message ID: {fake_message['Message_ID']}")
        print(f"Message Text: {fake_message['Message_Text']}")
        print(f"Date/Time: {fake_message['Date']} {fake_message['Time']}")
        
        # Submit task for processing
        task = process_telegram_message.delay(fake_message, config)
        print(f"✅ Task submitted: {task.id}")
        print(f"📋 Check logs/telegram_tasks.log for processing results")
        print(f"📋 Check Redis: redis-cli -n 1 get 'processed_msg:@test_channel:999999'")
        
        return task.id
        
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