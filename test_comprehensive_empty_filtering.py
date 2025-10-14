#!/usr/bin/env python3
"""
Test script to validate comprehensive empty message filtering
"""

import asyncio
import os
import sys
import json
from datetime import datetime, timezone

# Add project root to Python path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from src.tasks.telegram_celery_tasks import process_telegram_message
from src.core import file_handling as fh

def load_config():
    """Load configuration from config.json"""
    config_path = os.path.join(PROJECT_ROOT, "config", "config.json")
    config_handler = fh.FileHandling(config_path)
    config = config_handler.read_json()
    if not config:
        raise Exception("Failed to load configuration")
    return config

def create_test_message(message_id, text="", original_text="", message_text=None):
    """Create a test message with specified text fields"""
    # Use explicit None to distinguish between empty string and fallback
    if message_text is None:
        message_text = text
    
    return {
        'Message_ID': message_id,
        'Message_Text': message_text,
        'text': text,
        'Original_Text': original_text,
        'channel': 'test_channel',
        'country_code': 'iraq',
        'Country': 'Iraq',
        'Date': datetime.now().strftime('%Y-%m-%d'),
        'Time': datetime.now().strftime('%H:%M:%S'),
        'id': message_id
    }

async def test_empty_message_filtering():
    """Test all scenarios of empty message filtering"""
    
    print("=" * 60)
    print("COMPREHENSIVE EMPTY MESSAGE FILTERING TEST")
    print("=" * 60)
    
    # Load configuration
    try:
        config = load_config()
        print("✅ Configuration loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load configuration: {e}")
        return
    
    # Test cases for empty message filtering
    test_cases = [
        {
            'name': 'Both text and Message_Text empty',
            'message': create_test_message('empty_001', text="", message_text="", original_text="Valid original"),
            'expected_blocked': True,
            'stage': 'initial_processing'
        },
        {
            'name': 'Only text field empty (Message_Text valid)',
            'message': create_test_message('empty_002', text="", message_text="Valid message", original_text="Valid original"),
            'expected_blocked': False,
            'stage': 'none'
        },
        {
            'name': 'Only Message_Text empty (text valid)',
            'message': create_test_message('empty_003', text="Valid text", message_text="", original_text="Valid original"),
            'expected_blocked': False,
            'stage': 'none'
        },
        {
            'name': 'All text fields empty',
            'message': create_test_message('empty_004', text="", message_text="", original_text=""),
            'expected_blocked': True,
            'stage': 'initial_processing'
        },
        {
            'name': 'Whitespace-only text',
            'message': create_test_message('empty_005', text="   ", message_text="   ", original_text="   "),
            'expected_blocked': True,
            'stage': 'initial_processing'
        },
        {
            'name': 'Real-world scenario: No text from Telegram (Message_Text empty)',
            'message': create_test_message('empty_realworld', text="", message_text="", original_text="Valid but irrelevant"),
            'expected_blocked': True,
            'stage': 'initial_processing'
        },
        {
            'name': 'Valid message with all fields',
            'message': create_test_message('valid_001', text="Valid text content", message_text="Valid message content", original_text="Valid original content"),
            'expected_blocked': False,
            'stage': 'none'
        }
    ]
    
    passed_tests = 0
    total_tests = len(test_cases)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n[{i}/{total_tests}] Testing: {test_case['name']}")
        print(f"Expected to be blocked: {test_case['expected_blocked']}")
        
        try:
            # Import the actual Celery task function
            from src.tasks.telegram_celery_tasks import process_telegram_message as ptm_task
            
            # Create a dummy Celery task instance for testing
            class DummyTask:
                def __init__(self):
                    pass
            
            task = DummyTask()
            
            # Call the process_telegram_message function directly (Celery handles self binding)
            result = ptm_task(test_case['message'], config)
            
            # Check if message was blocked
            was_blocked = result.get('status', '').startswith('skipped_') or result.get('status', '').startswith('blocked_')
            
            if was_blocked == test_case['expected_blocked']:
                print(f"✅ PASS - Status: {result.get('status', 'unknown')}")
                if was_blocked:
                    print(f"   Reason: {result.get('reason', 'N/A')}")
                    empty_fields = result.get('empty_fields', [])
                    if empty_fields:
                        print(f"   Empty fields: {', '.join(empty_fields)}")
                passed_tests += 1
            else:
                print(f"❌ FAIL - Expected blocked={test_case['expected_blocked']}, got blocked={was_blocked}")
                print(f"   Status: {result.get('status', 'unknown')}")
                print(f"   Reason: {result.get('reason', 'N/A')}")
                
        except Exception as e:
            print(f"❌ ERROR during test: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'=' * 60}")
    print(f"TEST RESULTS: {passed_tests}/{total_tests} tests passed")
    print(f"{'=' * 60}")
    
    if passed_tests == total_tests:
        print("🎉 ALL TESTS PASSED! Empty message filtering is working correctly.")
        return True
    else:
        print("⚠️  SOME TESTS FAILED! Empty message filtering needs attention.")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_empty_message_filtering())
    sys.exit(0 if success else 1)