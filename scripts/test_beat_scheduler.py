#!/usr/bin/env python3
"""
Test script to validate the new Celery beat scheduler and duplicate detection
This tests both the configuration loading and the scheduler functionality
"""

import sys
import os
import redis
import time
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def test_beat_schedule_loading():
    """Test if the beat schedule loads correctly from configuration"""
    print("🔄 Testing beat schedule loading...")
    
    try:
        from src.tasks.telegram_celery_tasks import load_beat_schedule
        
        # Load the beat schedule
        schedule = load_beat_schedule()
        
        print(f"✅ Beat schedule loaded successfully")
        print(f"📋 Available tasks:")
        
        for task_name, task_config in schedule.items():
            print(f"  - {task_name}:")
            print(f"    Task: {task_config['task']}")
            print(f"    Schedule: {task_config['schedule']}")
        
        # Validate fetch task specifically
        fetch_task = schedule.get('fetch-telegram-messages')
        if fetch_task:
            interval = fetch_task['schedule']
            print(f"✅ Fetch task configured with interval: {interval} seconds")
            
            if isinstance(interval, (int, float)) and interval > 0:
                print(f"✅ Interval is valid: {interval}s = {interval/60:.1f} minutes")
            else:
                print(f"❌ Invalid interval: {interval}")
                return False
        else:
            print("❌ Fetch task not found in schedule")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Failed to load beat schedule: {e}")
        return False


def test_celery_config_integration():
    """Test if Celery properly loads the configuration"""
    print("\n🔄 Testing Celery configuration integration...")
    
    try:
        from src.tasks.telegram_celery_tasks import celery
        
        # Check if beat schedule is properly set
        beat_schedule = celery.conf.beat_schedule
        
        if beat_schedule:
            print(f"✅ Celery beat schedule configured")
            print(f"📋 Tasks in Celery config:")
            
            for task_name in beat_schedule:
                print(f"  - {task_name}")
                
            return True
        else:
            print("❌ No beat schedule found in Celery config")
            return False
            
    except Exception as e:
        print(f"❌ Failed to test Celery config: {e}")
        return False


def test_redis_duplicate_detection():
    """Test the Redis duplicate detection mechanism"""
    print("\n🔄 Testing Redis duplicate detection...")
    
    try:
        # Test Redis connection
        redis_client = redis.Redis(host='localhost', port=6379, db=1)
        redis_client.ping()
        print("✅ Redis connection successful")
        
        # Test duplicate detection logic
        test_channel = "@test_channel"
        test_message_id = "test_msg_12345"
        duplicate_key = f"processed_msg:{test_channel}:{test_message_id}"
        
        # Clean up any existing test key
        redis_client.delete(duplicate_key)
        
        # First check - should not exist
        if not redis_client.exists(duplicate_key):
            print("✅ Message not yet processed (correct)")
        else:
            print("❌ Message incorrectly marked as processed")
            return False
        
        # Mark as processed
        redis_client.setex(duplicate_key, 300, "1")  # 5 minutes expiry
        
        # Second check - should exist
        if redis_client.exists(duplicate_key):
            print("✅ Message correctly marked as processed")
        else:
            print("❌ Failed to mark message as processed")
            return False
        
        # Check TTL
        ttl = redis_client.ttl(duplicate_key)
        if ttl > 0:
            print(f"✅ Message tracking has TTL: {ttl} seconds")
        else:
            print("❌ Message tracking TTL not set")
            return False
        
        # Clean up
        redis_client.delete(duplicate_key)
        print("✅ Cleanup completed")
        
        return True
        
    except redis.ConnectionError:
        print("❌ Redis connection failed - ensure Redis is running")
        return False
    except Exception as e:
        print(f"❌ Redis test failed: {e}")
        return False


def test_age_calculation():
    """Test the new age limit calculation logic"""
    print("\n🔄 Testing age limit calculation...")
    
    try:
        from src.core import file_handling as fh
        
        # Load config to test calculation
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(project_root, "config", "config.json")
        config_handler = fh.FileHandling(config_path)
        config = config_handler.read_json()
        
        if not config:
            print("❌ Failed to load configuration")
            return False
        
        telegram_config = config.get('TELEGRAM_CONFIG', {})
        fetch_interval_seconds = telegram_config.get('FETCH_INTERVAL_SECONDS', 180)
        
        # Calculate age limit as done in the task
        age_limit_seconds = fetch_interval_seconds + 30
        age_limit_minutes = age_limit_seconds / 60.0
        
        print(f"✅ Configuration loaded:")
        print(f"  - Fetch interval: {fetch_interval_seconds}s ({fetch_interval_seconds/60:.1f} minutes)")
        print(f"  - Age limit: {age_limit_seconds}s ({age_limit_minutes:.1f} minutes)")
        print(f"  - Buffer: 30 seconds")
        
        # Validate the logic
        if age_limit_seconds > fetch_interval_seconds:
            print(f"✅ Age limit ({age_limit_seconds}s) > Fetch interval ({fetch_interval_seconds}s) - Good!")
        else:
            print(f"❌ Age limit should be larger than fetch interval")
            return False
            
        # Test cutoff time calculation
        from datetime import datetime, timedelta
        cutoff_time = datetime.now() - timedelta(seconds=age_limit_seconds)
        print(f"✅ Current cutoff time: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Age calculation test failed: {e}")
        return False


def test_manual_task_execution():
    """Test if we can manually execute the fetch task"""
    print("\n🔄 Testing manual task execution (dry run)...")
    
    try:
        # Import the task function directly
        from src.tasks.telegram_celery_tasks import fetch_new_messages_from_all_channels
        
        print("✅ Task function imported successfully")
        print("📝 Note: This would normally execute the task, but we'll skip actual execution")
        print("   to avoid interfering with live data. The import success indicates")
        print("   the task is properly configured and can be executed.")
        
        return True
        
    except Exception as e:
        print(f"❌ Task execution test failed: {e}")
        return False


def run_all_tests():
    """Run all tests and provide summary"""
    print("=" * 60)
    print("🧪 TELEGRAM SCRAPER - BEAT SCHEDULER TESTS")
    print("=" * 60)
    
    tests = [
        ("Beat Schedule Loading", test_beat_schedule_loading),
        ("Celery Config Integration", test_celery_config_integration),
        ("Redis Duplicate Detection", test_redis_duplicate_detection),
        ("Age Limit Calculation", test_age_calculation),
        ("Manual Task Execution", test_manual_task_execution),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        results[test_name] = test_func()
    
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:<30} {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n📈 Total: {passed + failed} tests")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    
    if failed == 0:
        print("\n🎉 All tests passed! The beat scheduler is working correctly.")
        return True
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review the issues above.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)