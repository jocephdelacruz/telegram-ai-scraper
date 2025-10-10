#!/usr/bin/env python3
"""
Test script to manually trigger the message fetch task
Use this to test the new periodic message fetching functionality
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.tasks.telegram_celery_tasks import fetch_new_messages_from_all_channels

def main():
    print("🔄 Testing periodic message fetch task...")
    print("=" * 50)
    print("This will test the new configurable message fetching with age filtering.")
    print("Check logs/telegram.log for detailed output including:")
    print("- Fetch configuration (interval, limits)")
    print("- Message age filtering")
    print("- Processing vs skipping decisions")
    print("=" * 50)
    
    try:
        # Trigger the task synchronously (for testing)
        result = fetch_new_messages_from_all_channels()
        
        print("✅ Task completed successfully!")
        print(f"Result: {result}")
        
        if 'messages_processed' in result:
            print(f"📊 Messages processed: {result['messages_processed']}")
        if 'messages_skipped' in result:
            print(f"⏭️  Messages skipped (too old): {result['messages_skipped']}")
        if 'fetch_limit' in result:
            print(f"🔄 Fetch limit per channel: {result['fetch_limit']}")
        if 'age_cutoff' in result:
            print(f"⏰ Age cutoff: {result['age_cutoff']}")
        
    except Exception as e:
        print(f"❌ Task failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())