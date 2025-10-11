#!/usr/bin/env python3
"""
Telegram Rate Limit Status Checker
This script checks the current Telegram API status and provides guidance on recovery
"""

import sys
import os
import asyncio
from datetime import datetime, timedelta
import re

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.core import file_handling as fh
from src.integrations.telegram_session_manager import TelegramSessionManager, TelegramRateLimitError, TelegramSessionError, TelegramAuthError

async def check_telegram_status():
    """Check current Telegram API status and rate limiting"""
    
    print("🔍 Telegram API Status Checker")
    print("=" * 50)
    
    # Load configuration
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(project_root, "config", "config.json")
    config_handler = fh.FileHandling(config_path)
    config = config_handler.read_json()
    
    if not config:
        print("❌ Failed to load configuration")
        return
    
    telegram_config = config.get('TELEGRAM_CONFIG', {})
    
    print(f"📱 Phone: {telegram_config.get('PHONE_NUMBER', 'Not configured')}")
    print(f"🔑 API ID: {telegram_config.get('API_ID', 'Not configured')}")
    print(f"📁 Session: {telegram_config.get('SESSION_FILE', 'telegram_session.session')}")
    print()
    
    # Initialize session manager
    try:
        session_manager = TelegramSessionManager(
            telegram_config['API_ID'],
            telegram_config['API_HASH'],
            telegram_config['PHONE_NUMBER'],
            telegram_config.get('SESSION_FILE', 'telegram_session')
        )
        print("✅ TelegramSessionManager initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize TelegramSessionManager: {e}")
        return
    
    # Test connection using session manager
    print("\n🔄 Testing Telegram connection...")
    try:
        # Perform health check
        health_status = await session_manager.health_check()
        
        if health_status['healthy']:
            print("✅ SUCCESS: Telegram session is healthy!")
            print("🎉 No rate limiting detected, system should work normally")
            
            # Show user info if available
            user_info = health_status.get('user_info', {})
            if user_info:
                print(f"👤 Connected as: {user_info.get('name', 'Unknown')} ({user_info.get('phone', 'N/A')})")
        else:
            print("❌ SESSION UNHEALTHY")
            for error in health_status.get('errors', []):
                print(f"⚠️  {error}")
        
        # Clean up
        await session_manager.close()
            
    except TelegramRateLimitError as e:
        error_msg = str(e)
        wait_match = re.search(r'(\d+) seconds', error_msg)
        hours_match = re.search(r'([\d.]+) hours', error_msg)
        
        if wait_match:
            wait_seconds = int(wait_match.group(1))
            wait_hours = wait_seconds / 3600
            wait_until = datetime.now() + timedelta(seconds=wait_seconds)
            
            print("🚫 RATE LIMITED!")
            print(f"⏱️  Wait time: {wait_hours:.1f} hours ({wait_seconds:,} seconds)")
            print(f"🕐 Rate limit expires: {wait_until.strftime('%Y-%m-%d %H:%M:%S')}")
            print()
            print("🔧 RECOMMENDED ACTIONS:")
            print("1. ⏳ WAIT: Unfortunately, you must wait until the rate limit expires")
            print("2. 🛑 STOP: Stop all Celery workers to prevent further attempts:")
            print("   ./scripts/deploy_celery.sh stop")
            print("3. ⏰ SCHEDULE: Set a reminder to restart after the wait time")
            print("4. 🔄 RESTART: After wait time, restart with:")
            print("   ./scripts/quick_start.sh")
        
    except TelegramSessionError as e:
        print("🔐 SESSION AUTHENTICATION ERROR!")
        print(f"❌ Error: {e}")
        print()
        print("🔧 RECOMMENDED ACTIONS:")
        print("1. 🔄 RE-AUTHENTICATE: Run manual authentication:")
        print("   python3 scripts/telegram_auth.py")
        print("2. 🗑️  CLEAN SESSION: If auth fails, delete session file:")
        print("   rm telegram_session.session")
        print("   python3 scripts/telegram_auth.py")
        print("3. 🔍 CHECK NETWORK: Ensure stable internet connection")
        
    except TelegramAuthError as e:
        print("📱 AUTHENTICATION ERROR!")
        print(f"❌ Error: {e}")
        print()
        print("🔧 RECOMMENDED ACTIONS:")
        print("1. ⏳ WAIT: This may also be rate limit related")
        print("2. 🔄 RE-AUTHENTICATE: Try manual auth after waiting:")
        print("   python3 scripts/telegram_auth.py")
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ CONNECTION FAILED: {error_msg}")
        
        if "wait of" in error_msg and "seconds is required" in error_msg:
            wait_match = re.search(r'wait of (\d+) seconds', error_msg)
            if wait_match:
                wait_seconds = int(wait_match.group(1))
                wait_hours = wait_seconds / 3600
                wait_until = datetime.now() + timedelta(seconds=wait_seconds)
                
                print()
                print("🚫 RATE LIMITED!")
                print(f"⏱️  Wait time: {wait_hours:.1f} hours ({wait_seconds:,} seconds)")
                print(f"🕐 Rate limit expires: {wait_until.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print()
            print("🔧 POSSIBLE SOLUTIONS:")
            print("1. 🔍 Check internet connection")
            print("2. 🔄 Try re-authentication: python3 scripts/telegram_auth.py")
            print("3. 🗑️  Clean session: rm telegram_session.session")
    
    print()
    print("📊 CURRENT SYSTEM STATUS:")
    
    # Check if workers are running
    import subprocess
    try:
        result = subprocess.run(['bash', './scripts/status.sh'], 
                              capture_output=True, text=True, cwd=project_root)
        if "All services are down" in result.stdout:
            print("🛑 All Celery workers are stopped (GOOD - prevents more rate limit triggers)")
        else:
            print("⚠️  Some workers may still be running - consider stopping them:")
            print("   ./scripts/deploy_celery.sh stop")
    except:
        print("❓ Could not check worker status")

if __name__ == "__main__":
    asyncio.run(check_telegram_status())