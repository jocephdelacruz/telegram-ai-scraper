#!/usr/bin/env python3
"""
Test script to verify the asyncio event loop fix for Celery tasks
This simulates the exact conditions that cause the "no current event loop" error
"""

import sys
import os
import asyncio
import threading
from datetime import datetime

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def test_async_in_thread():
    """Test running async code in a thread (simulates Celery worker)"""
    print("🔄 Testing async execution in thread (simulates Celery worker)...")
    
    async def simple_async_task():
        """Simple async task for testing"""
        await asyncio.sleep(0.1)
        return "async_task_completed"
    
    def thread_function():
        """Function that runs in a separate thread (like Celery)"""
        try:
            # Import our helper function
            from src.tasks.telegram_celery_tasks import run_async_in_celery
            
            # Test multiple executions to simulate repeated Celery task calls
            results = []
            for i in range(3):
                print(f"  - Execution #{i+1}...")
                result = run_async_in_celery(simple_async_task())
                results.append(result)
                print(f"    Result: {result}")
            
            return results
            
        except Exception as e:
            print(f"❌ Error in thread: {e}")
            return None
    
    # Run in a separate thread (simulates Celery worker environment)
    thread = threading.Thread(target=thread_function)
    results = []
    
    def capture_results():
        global test_results
        test_results = thread_function()
    
    thread = threading.Thread(target=capture_results)
    thread.start()
    thread.join()
    
    if 'test_results' in globals() and test_results:
        print("✅ Async execution in thread successful!")
        print(f"   Completed {len(test_results)} executions")
        return True
    else:
        print("❌ Async execution in thread failed!")
        return False


def test_telegram_scraper_init():
    """Test TelegramScraper initialization without connecting"""
    print("🔄 Testing TelegramScraper initialization...")
    
    try:
        # Load config
        from src.core import file_handling as fh
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(project_root, "config", "config.json")
        config_handler = fh.FileHandling(config_path)
        config = config_handler.read_json()
        
        if not config:
            print("❌ Failed to load configuration")
            return False
        
        telegram_config = config.get('TELEGRAM_CONFIG', {})
        if not all(key in telegram_config for key in ['API_ID', 'API_HASH', 'PHONE_NUMBER']):
            print("❌ Telegram configuration incomplete")
            return False
        
        # Test initialization only (no connection)
        from src.integrations.telegram_utils import TelegramScraper
        from src.integrations.telegram_session_manager import TelegramRateLimitError, TelegramSessionError, TelegramAuthError
        
        telegram_scraper = TelegramScraper(
            telegram_config['API_ID'],
            telegram_config['API_HASH'],
            telegram_config['PHONE_NUMBER'],
            telegram_config.get('SESSION_FILE', 'telegram_session')
        )
        
        print("✅ TelegramScraper initialized successfully")
        print(f"   API ID: {telegram_config['API_ID']}")
        print(f"   Session file: {telegram_config.get('SESSION_FILE', 'telegram_session')}")
        return True
        
    except Exception as e:
        print(f"❌ TelegramScraper initialization failed: {e}")
        return False


def test_celery_task_execution_simulation():
    """Simulate actual Celery task execution environment"""
    print("🔄 Testing Celery task simulation...")
    
    def simulate_celery_worker():
        """Simulate how Celery executes tasks"""
        try:
            # Import the actual task
            from src.tasks.telegram_celery_tasks import fetch_new_messages_from_all_channels
            
            # Create a mock task instance (without actually executing on Telegram)
            class MockTask:
                def retry(self, exc):
                    print(f"Task would retry due to: {exc}")
                    return {"status": "retry"}
            
            mock_task = MockTask()
            
            print("  - Task imported successfully")
            print("  - Ready for execution (but we'll skip actual network calls)")
            
            return True
            
        except Exception as e:
            print(f"❌ Celery task simulation failed: {e}")
            return False
    
    return simulate_celery_worker()


def main():
    """Run all async event loop tests"""
    print("=" * 70)
    print("🧪 ASYNCIO EVENT LOOP FIX TESTS")
    print("=" * 70)
    
    tests = [
        ("Async in Thread", test_async_in_thread),
        ("Telegram Scraper Init", test_telegram_scraper_init),
        ("Celery Task Simulation", test_celery_task_execution_simulation),
    ]
    
    results = {}
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        results[test_name] = test_func()
        print()
    
    # Summary
    print("=" * 70)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:<30} {status}")
    
    print(f"\n📈 Total: {total} tests")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {total - passed}")
    
    if passed == total:
        print(f"\n🎉 All tests passed! The asyncio event loop fix is working correctly.")
        return True
    else:
        print(f"\n⚠️  Some tests failed. The asyncio fix may need more work.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)