#!/usr/bin/env python3
"""
Debug script to check recent messages from specific channels
This will help us understand why recent messages aren't being detected as "new"
"""

import sys
import os
import asyncio
from datetime import datetime, timedelta

# Try to import redis, continue without it if not available
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("⚠️  Redis module not available in this environment")

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.core import file_handling as fh
from src.integrations.telegram_utils import TelegramScraper

async def debug_recent_messages():
    """Debug recent messages from channels that should have new content"""
    
    # Load configuration
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(project_root, "config", "config.json")
    config_handler = fh.FileHandling(config_path)
    config = config_handler.read_json()
    
    if not config:
        print("❌ Failed to load configuration")
        return
    
    # Get configuration values
    telegram_config = config.get('TELEGRAM_CONFIG', {})
    fetch_interval_seconds = telegram_config.get('FETCH_INTERVAL_SECONDS', 180)
    age_limit_seconds = fetch_interval_seconds + 30
    
    # Calculate cutoff time
    cutoff_time = datetime.now() - timedelta(seconds=age_limit_seconds)
    
    print(f"🔍 DEBUGGING RECENT MESSAGES")
    print(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Age cutoff: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')} (messages must be newer than this)")
    print(f"Age limit: {age_limit_seconds} seconds ({age_limit_seconds/60:.1f} minutes)")
    print()
    
    # Initialize Redis if available
    redis_client = None
    if REDIS_AVAILABLE:
        try:
            redis_client = redis.Redis(host='localhost', port=6379, db=1)
            redis_client.ping()
            print("✅ Redis connected successfully")
        except Exception as e:
            print(f"⚠️  Redis connection failed: {e}")
            redis_client = None
    else:
        print("⚠️  Redis not available, skipping duplicate checks")
    
    # Initialize Telegram scraper
    try:
        telegram_scraper = TelegramScraper(
            telegram_config['API_ID'],
            telegram_config['API_HASH'],
            telegram_config['PHONE_NUMBER'],
            telegram_config.get('SESSION_FILE', 'telegram_session')
        )
        
        await telegram_scraper.start_client()
        print("✅ Telegram client connected")
    except Exception as e:
        print(f"❌ Failed to connect to Telegram: {e}")
        return
    
    # Channels to debug (those mentioned as having recent messages)
    debug_channels = [
        '@Sabren_News1',
        '@altaifaalmansoora', 
        '@alghadeertv',
        '@wa3ediq',
        '@shafaaqnews'
    ]
    
    try:
        for channel in debug_channels:
            print(f"\n🔍 DEBUGGING CHANNEL: {channel}")
            print("="*60)
            
            # Get recent messages WITHOUT our filtering to see raw data
            messages = await telegram_scraper.get_channel_messages(
                channel, 
                limit=5,  # Just check the 5 most recent
                cutoff_time=None,  # No age filtering
                redis_client=None,  # No duplicate detection
                log_found_messages=False  # Don't pollute logs
            )
            
            if not messages:
                print(f"❌ No messages found in {channel}")
                continue
            
            print(f"📋 Found {len(messages)} messages:")
            
            for i, msg in enumerate(messages, 1):
                msg_id = msg.get('Message_ID', 'N/A')
                msg_date = msg.get('Date', '')
                msg_time = msg.get('Time', '')
                msg_text = (msg.get('Message_Text', '') or '')[:50].replace('\n', ' ')
                
                # Parse message datetime
                if msg_date and msg_time:
                    try:
                        msg_datetime = datetime.strptime(f"{msg_date} {msg_time}", '%Y-%m-%d %H:%M:%S')
                        age_diff = datetime.now() - msg_datetime
                        
                        # Check against cutoff
                        is_new = msg_datetime >= cutoff_time
                        status = "✅ NEW" if is_new else "❌ TOO OLD"
                        
                        print(f"  {i}. ID:{msg_id} | {msg_datetime} | Age: {age_diff} | {status}")
                        print(f"     Text: '{msg_text}...'")
                        
                        # Check Redis duplicate status if available
                        if redis_client and msg_id:
                            try:
                                duplicate_key = f"processed_msg:{channel}:{msg_id}"
                                is_duplicate = redis_client.exists(duplicate_key)
                                if is_duplicate:
                                    print(f"     🔄 DUPLICATE: Already processed in Redis")
                                else:
                                    print(f"     ✨ FRESH: Not in Redis")
                            except Exception as redis_err:
                                print(f"     ⚠️ Redis check failed: {redis_err}")
                        
                    except ValueError as e:
                        print(f"  {i}. ID:{msg_id} | ❌ DATE PARSE ERROR: {e}")
                        print(f"     Raw date: '{msg_date}' Raw time: '{msg_time}'")
                else:
                    print(f"  {i}. ID:{msg_id} | ❌ NO DATE/TIME DATA")
                
                print()
    
    except Exception as e:
        print(f"❌ Error during debugging: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            await telegram_scraper.stop_client()
            print("✅ Telegram client disconnected")
        except:
            pass

if __name__ == "__main__":
    asyncio.run(debug_recent_messages())