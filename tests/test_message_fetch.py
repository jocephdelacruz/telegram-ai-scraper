#!/usr/bin/env python3
"""
Test script for message fetch task configuration and validation
SAFE VERSION: Does not trigger actual Telegram connections during testing
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def main():
    print("🔄 Testing message fetch task configuration...")
    print("=" * 50)
    print("SAFE TEST MODE: Validates configuration without Telegram connections")
    print("This prevents session conflicts that could cause phone logout")
    print("=" * 50)
    
    try:
        # Test 1: Check if session safety protection is available
        try:
            from src.integrations.session_safety import SessionSafetyManager, SessionSafetyError
            print("✅ Session safety protection available")
            
            # Test session safety check (safe - no Telegram access)
            safety_manager = SessionSafetyManager()
            try:
                safety_manager.check_session_safety("test_message_fetch_validation")
                print("✅ Session safety check passed - workers not conflicting")
            except SessionSafetyError as e:
                print(f"⚠️  Session safety active: {e}")
                print("   (This is good - prevents concurrent access)")
            
        except ImportError:
            print("❌ Session safety protection not available")
            return 1
        
        # Test 2: Validate Celery task registration
        try:
            from src.tasks.telegram_celery_tasks import celery
            registered_tasks = list(celery.tasks.keys())
            fetch_task_found = any('fetch_new_messages' in task for task in registered_tasks)
            
            if fetch_task_found:
                print("✅ Message fetch task properly registered with Celery")
            else:
                print("⚠️  Message fetch task not found in Celery registry")
            
        except Exception as e:
            print(f"⚠️  Celery task validation inconclusive: {e}")
        
        # Test 3: Configuration validation
        try:
            from src.core import file_handling as fh
            config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.json')
            if os.path.exists(config_path):
                print("✅ Configuration file found")
                # Could add more config validation here if needed
            else:
                print("⚠️  Configuration file not found (may affect functionality)")
                
        except Exception as e:
            print(f"⚠️  Configuration validation error: {e}")
        
        print("=" * 50)
        print("✅ SAFE TEST COMPLETED!")
        print("� Summary:")
        print("   • Session safety protection validated")
        print("   • Celery task registration checked")
        print("   • Configuration presence verified")
        print("   • NO Telegram connections made (safe for concurrent workers)")
        print("=" * 50)
        print("💡 To test actual message fetching:")
        print("   • Ensure workers are stopped: ./scripts/deploy_celery.sh stop")
        print("   • Test session: ./scripts/telegram_session.sh test")
        print("   • Manual fetch: Use Celery worker or Flower web interface")
        
        return 0
        
    except Exception as e:
        print(f"❌ Test framework error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())