#!/usr/bin/env python3
"""
Debug script to check message dates and age filtering
"""

import sys
import os
import asyncio
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

async def debug_message_ages():
    """Check actual message dates from the channel"""
    try:
        # Load config and create scraper
        from src.core import file_handling as fh
        from src.integrations.telegram_utils import TelegramScraper
        
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(project_root, "config", "config.json")
        config_handler = fh.FileHandling(config_path)
        config = config_handler.read_json()
        
        telegram_config = config.get('TELEGRAM_CONFIG', {})
        
        telegram_scraper = TelegramScraper(
            telegram_config['API_ID'],
            telegram_config['API_HASH'],
            telegram_config['PHONE_NUMBER'],
            telegram_config.get('SESSION_FILE', 'telegram_session')
        )
        
        await telegram_scraper.start_client()
        
        # Fetch messages from the problematic channel
        test_channel = "@Mahdiasmr1995"
        messages = await telegram_scraper.get_channel_messages(test_channel, limit=10)
        
        # Calculate current cutoff (same logic as the task)
        fetch_interval_seconds = telegram_config.get('FETCH_INTERVAL_SECONDS', 180)
        age_limit_seconds = fetch_interval_seconds + 30
        cutoff_time = datetime.now() - timedelta(seconds=age_limit_seconds)
        
        print(f"🔍 DEBUGGING MESSAGE AGES FOR {test_channel}")
        print(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Age cutoff: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')} (must be newer than this)")
        print(f"Age limit: {age_limit_seconds} seconds ({age_limit_seconds/60:.1f} minutes)")
        print()
        
        if not messages:
            print("❌ No messages found!")
            return
        
        print(f"📋 FOUND {len(messages)} MESSAGES:")
        print("-" * 80)
        
        newer_than_cutoff = 0
        for i, msg in enumerate(messages, 1):
            msg_date = msg.get('Date', '')
            msg_time = msg.get('Time', '')
            msg_id = msg.get('Message_ID', '')
            msg_text = msg.get('Message_Text', '')[:30].replace('\n', ' ')
            
            print(f"{i:2d}. ID:{msg_id} | {msg_date} {msg_time} | '{msg_text}...'")
            
            # Check if this message passes age filter
            if msg_date and msg_time:
                try:
                    message_datetime_str = f"{msg_date} {msg_time}"
                    message_datetime = datetime.strptime(message_datetime_str, '%Y-%m-%d %H:%M:%S')
                    
                    if message_datetime >= cutoff_time:
                        print(f"    ✅ PASSES age filter (newer than cutoff)")
                        newer_than_cutoff += 1
                    else:
                        age_diff = cutoff_time - message_datetime
                        print(f"    ❌ FAILS age filter (too old by {age_diff})")
                except Exception as e:
                    print(f"    ⚠️  Date parsing error: {e}")
            else:
                print(f"    ⚠️  Missing date/time information")
        
        print("-" * 80)
        print(f"📊 SUMMARY:")
        print(f"   Total messages: {len(messages)}")
        print(f"   Pass age filter: {newer_than_cutoff}")
        print(f"   Fail age filter: {len(messages) - newer_than_cutoff}")
        
        if newer_than_cutoff == 0:
            print(f"\n⚠️  ALL MESSAGES ARE TOO OLD!")
            print(f"   This explains why messages_processed = 0")
            print(f"   The channel might not have posted anything in the last {age_limit_seconds/60:.1f} minutes")
        
        await telegram_scraper.stop_client()
        
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """Run the debug check"""
    from src.tasks.telegram_celery_tasks import run_async_in_celery
    run_async_in_celery(debug_message_ages())

if __name__ == "__main__":
    main()