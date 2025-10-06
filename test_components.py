#!/usr/bin/env python3
"""
Test script to validate that all core components are working correctly
"""

import sys
import os
sys.path.append('.')

def test_imports():
    """Test all critical imports"""
    print("Testing imports...")
    
    try:
        from src.core.log_handling import LogHandling
        print("✓ log_handling import successful")
    except Exception as e:
        print(f"✗ log_handling import failed: {e}")
        return False
    
    try:
        from src.core.file_handling import FileHandling
        print("✓ file_handling import successful")
    except Exception as e:
        print(f"✗ file_handling import failed: {e}")
        return False
    
    try:
        from src.integrations.openai_utils import OpenAIProcessor
        print("✓ openai_utils import successful")
    except Exception as e:
        print(f"✗ openai_utils import failed: {e}")
        return False
    
    try:
        from src.tasks.telegram_celery_tasks import celery
        print("✓ telegram_celery_tasks import successful")
    except Exception as e:
        print(f"✗ telegram_celery_tasks import failed: {e}")
        return False
    
    return True

def test_log_handling():
    """Test logging functionality"""
    print("\nTesting log handling...")
    
    try:
        from src.core.log_handling import LogHandling
        logger = LogHandling("./logs/test_log.log", "Asia/Manila")
        result = logger.writeLog("Test log entry")
        if result:
            print("✓ Log writing successful")
        else:
            print("✗ Log writing failed")
            return False
    except Exception as e:
        print(f"✗ Log handling test failed: {e}")
        return False
    
    return True

def test_file_handling():
    """Test file handling functionality"""
    print("\nTesting file handling...")
    
    try:
        from src.core.file_handling import FileHandling
        file_handler = FileHandling("./logs/test_file.txt")
        
        # Test write
        result = file_handler.write("Test content", overwrite=True)
        if not result:
            print("✗ File writing failed")
            return False
        
        # Test read
        content = file_handler.read()
        if content and "Test content" in content:
            print("✓ File handling successful")
        else:
            print("✗ File reading failed")
            return False
            
    except Exception as e:
        print(f"✗ File handling test failed: {e}")
        return False
    
    return True

def test_celery_tasks():
    """Test Celery task definitions"""
    print("\nTesting Celery tasks...")
    
    try:
        from src.tasks.telegram_celery_tasks import health_check, celery
        
        # Test task registration
        registered_tasks = list(celery.tasks.keys())
        expected_tasks = [
            'src.tasks.telegram_celery_tasks.process_telegram_message',
            'src.tasks.telegram_celery_tasks.send_teams_notification',
            'src.tasks.telegram_celery_tasks.save_to_sharepoint',
            'src.tasks.telegram_celery_tasks.save_to_csv_backup',
            'src.tasks.telegram_celery_tasks.cleanup_old_tasks',
            'src.tasks.telegram_celery_tasks.health_check'
        ]
        
        for task in expected_tasks:
            if task in registered_tasks:
                print(f"✓ {task.split('.')[-1]} task registered")
            else:
                print(f"✗ {task.split('.')[-1]} task not registered")
                return False
        
        # Test health check task execution
        result = health_check()
        if result and result.get('status') == 'healthy':
            print("✓ Health check task execution successful")
        else:
            print("✗ Health check task execution failed")
            return False
            
    except Exception as e:
        print(f"✗ Celery tasks test failed: {e}")
        return False
    
    return True

def main():
    """Run all tests"""
    print("=== Telegram AI Scraper Component Test ===\n")
    
    tests = [
        test_imports,
        test_log_handling,
        test_file_handling,
        test_celery_tasks
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")
            failed += 1
    
    print(f"\n=== Test Results ===")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total: {passed + failed}")
    
    if failed == 0:
        print("\n🎉 All tests passed! Your project is ready to use.")
        return True
    else:
        print(f"\n❌ {failed} test(s) failed. Please check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)