#!/usr/bin/env python3
"""
Telegram Recovery Script
Run this script after the rate limit expires to restore normal operation
"""

import sys
import os
import asyncio
import subprocess
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.core import file_handling as fh
from src.integrations.telegram_session_manager import TelegramSessionManager

async def recover_telegram_system():
    """Recover the Telegram system after rate limit expires"""
    
    print("🔄 Telegram System Recovery")
    print("=" * 40)
    print(f"🕐 Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Load configuration
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(project_root, "config", "config.json")
    config_handler = fh.FileHandling(config_path)
    config = config_handler.read_json()
    
    if not config:
        print("❌ Failed to load configuration")
        return False
    
    telegram_config = config.get('TELEGRAM_CONFIG', {})
    
    print("📋 RECOVERY STEPS:")
    print()
    
    # Step 1: Test Telegram connection
    print("1️⃣  Testing Telegram API connection...")
    try:
        session_manager = TelegramSessionManager(
            telegram_config['API_ID'],
            telegram_config['API_HASH'],
            telegram_config['PHONE_NUMBER'],
            telegram_config.get('SESSION_FILE', 'telegram_session')
        )
        
        # Perform comprehensive health check
        health_status = await session_manager.health_check()
        
        if health_status['healthy']:
            print("   ✅ SUCCESS: Telegram connection restored!")
            user_info = health_status.get('user_info', {})
            if user_info:
                print(f"   👤 Connected as: {user_info.get('name', 'Unknown')}")
        else:
            print("   ❌ CONNECTION STILL HAS ISSUES:")
            for error in health_status.get('errors', []):
                print(f"   ⚠️  {error}")
            await session_manager.close()
            return False
        
        await session_manager.close()
        print("   ✅ Session manager closed cleanly")
        
    except Exception as e:
        error_msg = str(e)
        if "wait of" in error_msg and "seconds is required" in error_msg:
            print(f"   ❌ STILL RATE LIMITED: {error_msg}")
            print("   ⏰ Rate limit has not expired yet. Please wait longer.")
            return False
        else:
            print(f"   ⚠️  CONNECTION ISSUE: {error_msg}")
            print("   💡 May need re-authentication. Try: python3 scripts/telegram_auth.py")
            return False
    
    # Step 2: Check Redis
    print("\n2️⃣  Checking Redis connection...")
    try:
        import redis
        redis_client = redis.Redis(host='localhost', port=6379, db=1)
        redis_client.ping()
        print("   ✅ Redis is working")
    except Exception as e:
        print(f"   ❌ Redis issue: {e}")
        print("   💡 Start Redis: sudo systemctl start redis-server")
        return False
    
    # Step 3: Clean up any stale processes
    print("\n3️⃣  Cleaning up stale processes...")
    try:
        # Stop any existing workers
        result = subprocess.run(['bash', './scripts/deploy_celery.sh', 'stop'], 
                              capture_output=True, text=True, cwd=project_root)
        print("   ✅ Cleaned up any existing workers")
    except:
        print("   ⚠️  Could not clean up processes (may be OK)")
    
    # Step 4: Start system
    print("\n4️⃣  Starting Telegram AI Scraper system...")
    try:
        result = subprocess.run(['bash', './scripts/quick_start.sh'], 
                              cwd=project_root, timeout=60)
        if result.returncode == 0:
            print("   ✅ System started successfully!")
        else:
            print("   ⚠️  System start may have issues. Check manually with:")
            print("      ./scripts/status.sh")
    except subprocess.TimeoutExpired:
        print("   ⚠️  System start took longer than expected, but may be OK")
        print("   🔍 Check status with: ./scripts/status.sh")
    except Exception as e:
        print(f"   ❌ Failed to start system: {e}")
        print("   💡 Try manual start: ./scripts/quick_start.sh")
        return False
    
    # Step 5: Verify operation
    print("\n5️⃣  Verifying system operation...")
    try:
        # Wait a moment for systems to initialize
        await asyncio.sleep(10)
        
        # Check if workers are running
        result = subprocess.run(['bash', './scripts/status.sh'], 
                              capture_output=True, text=True, cwd=project_root)
        
        if "Workers running:" in result.stdout and "0/5" not in result.stdout:
            print("   ✅ Workers are running!")
        else:
            print("   ⚠️  Workers may not be fully started yet")
            print("   💡 Give it a few more minutes, then check: ./scripts/status.sh")
        
    except Exception as e:
        print(f"   ⚠️  Could not verify system status: {e}")
    
    print("\n🎉 RECOVERY COMPLETED!")
    print()
    print("📊 NEXT STEPS:")
    print("1. 🔍 Monitor logs: tail -f logs/telegram.log")
    print("2. 📈 Check status: ./scripts/status.sh")
    print("3. 🌐 Web monitoring: http://localhost:5555 (if Flower is running)")
    print("4. ⏰ Watch for new message processing in the next 3-6 minutes")
    print()
    print("💡 If you see new messages being processed, the system is fully recovered!")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(recover_telegram_system())
    if success:
        print("\n✅ Recovery script completed successfully")
    else:
        print("\n❌ Recovery script encountered issues - manual intervention may be needed")
        sys.exit(1)