#!/usr/bin/env python3
"""
Comprehensive Admin Teams Connection Test
Tests both global admin notifier functions and direct admin notifier methods
Consolidates functionality from test_admin_teams_connection.py and test_global_admin_notifier.py
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.core.file_handling import FileHandling
from src.integrations.teams_utils import (
    get_admin_notifier,
    send_critical_exception,
    send_service_failure,
    send_celery_failure,
    send_system_startup,
    send_system_shutdown,
    send_configuration_error,
    send_resource_alert
)
import traceback
from datetime import datetime
import time

def load_config():
    """Load configuration from config.json"""
    print("Loading configuration...")
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.json')
    config_handler = FileHandling(config_path)
    config = config_handler.read_json()
    
    if not config:
        print("❌ Failed to load configuration")
        return None
    
    if not config.get('TEAMS_ADMIN_WEBHOOK'):
        print("❌ TEAMS_ADMIN_WEBHOOK not found in configuration")
        return None
    
    print("✅ Configuration loaded successfully")
    return config

def test_global_notifier_imports():
    """Test importing all global admin notification functions"""
    print("\n--- Testing Global Notifier Imports ---")
    try:
        # Test importing the functions - already imported at top
        print("✅ Successfully imported all global admin notification functions")
        print("   - send_critical_exception")
        print("   - send_service_failure") 
        print("   - send_celery_failure")
        print("   - send_system_startup")
        print("   - send_system_shutdown")
        print("   - send_configuration_error")
        print("   - send_resource_alert")
        return True
    except Exception as e:
        print(f"❌ Error importing global functions: {e}")
        traceback.print_exc()
        return False

def test_admin_notifier_creation(config):
    """Test creating the admin notifier using global notifier"""
    print("\n--- Testing Admin Notifier Creation ---")
    try:
        admin_notifier = get_admin_notifier()
        if admin_notifier:
            print("✅ Global admin notifier initialized successfully")
            print(f"   - Webhook URL: {admin_notifier.webhook_url[:50]}...")
            print(f"   - Channel Name: {admin_notifier.channel_name}")
            print(f"   - System Name: {admin_notifier.system_name}")
            return admin_notifier
        else:
            print("⚠️  Admin notifier not configured (TEAMS_ADMIN_WEBHOOK missing)")
            print("   This is normal if admin webhook is not set up")
            return None
    except Exception as e:
        print(f"❌ Error creating admin notifier: {e}")
        traceback.print_exc()
        return None

def test_basic_connection(admin_notifier):
    """Test basic webhook connection"""
    print("\n--- Testing Basic Connection ---")
    try:
        success = admin_notifier.test_admin_connection()
        if success:
            print("✅ Basic connection test passed")
            return True
        else:
            print("❌ Basic connection test failed")
            return False
    except Exception as e:
        print(f"❌ Error in basic connection test: {e}")
        traceback.print_exc()
        return False

def test_critical_exception_notification(admin_notifier):
    """Test critical exception notification"""
    print("\n--- Testing Critical Exception Notification ---")
    try:
        success = admin_notifier.send_critical_exception(
            exception_type="TestException",
            exception_message="This is a test critical exception from the admin Teams test script",
            module_name="test_admin_teams_connection.py",
            stack_trace="Test stack trace:\n  File test.py, line 1, in test_function\n    raise TestException('Test error')",
            additional_context={
                "test_type": "Admin Teams Connection Test",
                "timestamp": datetime.now().isoformat(),
                "severity": "TEST"
            }
        )
        
        if success:
            print("✅ Critical exception notification sent successfully")
            return True
        else:
            print("❌ Critical exception notification failed")
            return False
    except Exception as e:
        print(f"❌ Error sending critical exception notification: {e}")
        traceback.print_exc()
        return False

def test_service_failure_notification(admin_notifier):
    """Test service failure notification"""
    print("\n--- Testing Service Failure Notification ---")
    try:
        success = admin_notifier.send_service_failure(
            service_name="Test Service",
            failure_reason="This is a test service failure notification from the admin Teams test script",
            impact_level="MEDIUM",
            recovery_action="This is a test - no action required"
        )
        
        if success:
            print("✅ Service failure notification sent successfully")
            return True
        else:
            print("❌ Service failure notification failed")
            return False
    except Exception as e:
        print(f"❌ Error sending service failure notification: {e}")
        traceback.print_exc()
        return False

def test_celery_failure_notification(admin_notifier):
    """Test Celery task failure notification"""
    print("\n--- Testing Celery Failure Notification ---")
    try:
        success = admin_notifier.send_celery_failure(
            task_name="test_task",
            task_id="test-task-id-12345",
            failure_reason="This is a test Celery task failure notification from the admin Teams test script",
            retry_count=2,
            max_retries=3
        )
        
        if success:
            print("✅ Celery failure notification sent successfully")
            return True
        else:
            print("❌ Celery failure notification failed")
            return False
    except Exception as e:
        print(f"❌ Error sending Celery failure notification: {e}")
        traceback.print_exc()
        return False

def test_system_startup_notification(admin_notifier):
    """Test system startup notification"""
    print("\n--- Testing System Startup Notification ---")
    try:
        success = admin_notifier.send_system_startup(
            components_started=[
                "Test Component 1",
                "Test Component 2", 
                "Test Component 3",
                "Admin Teams Notifier"
            ],
            startup_time=2.5
        )
        
        if success:
            print("✅ System startup notification sent successfully")
            return True
        else:
            print("❌ System startup notification failed")
            return False
    except Exception as e:
        print(f"❌ Error sending system startup notification: {e}")
        traceback.print_exc()
        return False

def test_configuration_error_notification(admin_notifier):
    """Test configuration error notification"""
    print("\n--- Testing Configuration Error Notification ---")
    try:
        success = admin_notifier.send_configuration_error(
            config_file="test_config.json",
            error_details="This is a test configuration error notification from the admin Teams test script",
            suggested_fix="This is a test - no action required"
        )
        
        if success:
            print("✅ Configuration error notification sent successfully")
            return True
        else:
            print("❌ Configuration error notification failed")
            return False
    except Exception as e:
        print(f"❌ Error sending configuration error notification: {e}")
        traceback.print_exc()
        return False

def test_resource_alert_notification(admin_notifier):
    """Test resource alert notification"""
    print("\n--- Testing Resource Alert Notification ---")
    try:
        success = admin_notifier.send_resource_alert(
            resource_type="CPU",
            current_value=85.5,
            threshold=80.0,
            unit="%"
        )
        
        if success:
            print("✅ Resource alert notification sent successfully")
            return True
        else:
            print("❌ Resource alert notification failed")
            return False
    except Exception as e:
        print(f"❌ Error sending resource alert notification: {e}")
        traceback.print_exc()
        return False

def test_system_shutdown_notification(admin_notifier):
    """Test system shutdown notification"""
    print("\n--- Testing System Shutdown Notification ---")
    try:
        success = admin_notifier.send_system_shutdown(
            reason="Test shutdown notification from admin Teams test script",
            cleanup_performed=True
        )
        
        if success:
            print("✅ System shutdown notification sent successfully")
            return True
        else:
            print("❌ System shutdown notification failed")
            return False
    except Exception as e:
        print(f"❌ Error sending system shutdown notification: {e}")
        traceback.print_exc()
        return False

# Global convenience function tests
def test_global_critical_exception():
    """Test global send_critical_exception function"""
    print("\n--- Testing Global Critical Exception Function ---")
    try:
        success = send_critical_exception(
            "TestGlobalException",
            "This is a test critical exception from the global convenience function",
            "test_admin_teams_connection.py",
            additional_context={"test_type": "Global Function Test", "test_mode": True}
        )
        
        result_text = "SUCCESS" if success else "FAILED"
        print(f"✅ send_critical_exception: {result_text}")
        return success
    except Exception as e:
        print(f"❌ Error in global critical exception test: {e}")
        traceback.print_exc()
        return False

def test_global_service_failure():
    """Test global send_service_failure function"""
    print("\n--- Testing Global Service Failure Function ---")
    try:
        success = send_service_failure(
            "Global Test Service",
            "This is a test service failure notification from global convenience function",
            impact_level="LOW",
            recovery_action="This is just a test"
        )
        
        result_text = "SUCCESS" if success else "FAILED"
        print(f"✅ send_service_failure: {result_text}")
        return success
    except Exception as e:
        print(f"❌ Error in global service failure test: {e}")
        traceback.print_exc()
        return False

def test_global_celery_failure():
    """Test global send_celery_failure function"""
    print("\n--- Testing Global Celery Failure Function ---")
    try:
        success = send_celery_failure(
            task_name="global_test_task",
            task_id="global-test-task-12345",
            failure_reason="This is a test Celery failure from global convenience function",
            retry_count=1,
            max_retries=3
        )
        
        result_text = "SUCCESS" if success else "FAILED"
        print(f"✅ send_celery_failure: {result_text}")
        return success
    except Exception as e:
        print(f"❌ Error in global Celery failure test: {e}")
        traceback.print_exc()
        return False

def test_global_system_startup():
    """Test global send_system_startup function"""
    print("\n--- Testing Global System Startup Function ---")
    try:
        success = send_system_startup([
            "Global Test Component 1", 
            "Global Test Component 2",
            "Global Admin Notifier"
        ])
        
        result_text = "SUCCESS" if success else "FAILED"
        print(f"✅ send_system_startup: {result_text}")
        return success
    except Exception as e:
        print(f"❌ Error in global system startup test: {e}")
        traceback.print_exc()
        return False

def test_global_system_shutdown():
    """Test global send_system_shutdown function"""
    print("\n--- Testing Global System Shutdown Function ---")
    try:
        success = send_system_shutdown(
            reason="Test shutdown from global convenience function",
            cleanup_performed=True
        )
        
        result_text = "SUCCESS" if success else "FAILED"
        print(f"✅ send_system_shutdown: {result_text}")
        return success
    except Exception as e:
        print(f"❌ Error in global system shutdown test: {e}")
        traceback.print_exc()
        return False

def test_global_configuration_error():
    """Test global send_configuration_error function"""
    print("\n--- Testing Global Configuration Error Function ---")
    try:
        success = send_configuration_error(
            "global_test_config.json",
            "This is a test configuration error from global convenience function",
            "This is just a test - no action required"
        )
        
        result_text = "SUCCESS" if success else "FAILED"
        print(f"✅ send_configuration_error: {result_text}")
        return success
    except Exception as e:
        print(f"❌ Error in global configuration error test: {e}")
        traceback.print_exc()
        return False

def test_global_resource_alert():
    """Test global send_resource_alert function"""
    print("\n--- Testing Global Resource Alert Function ---")
    try:
        success = send_resource_alert(
            resource_type="Memory",
            current_value=92.3,
            threshold=90.0,
            unit="%"
        )
        
        result_text = "SUCCESS" if success else "FAILED"
        print(f"✅ send_resource_alert: {result_text}")
        return success
    except Exception as e:
        print(f"❌ Error in global resource alert test: {e}")
        traceback.print_exc()
        return False

def main():
    """Main test function - runs comprehensive admin Teams tests"""
    print("🔧 Comprehensive Admin Teams Connection Test")
    print("=" * 60)
    print("Testing both global convenience functions and direct admin notifier methods")
    print("=" * 60)
    
    # Test 1: Global function imports
    imports_success = test_global_notifier_imports()
    if not imports_success:
        print("\n❌ Global function imports failed - exiting")
        return False
    
    # Load configuration
    config = load_config()
    if not config:
        print("\n❌ Configuration test failed - exiting")
        return False
    
    # Create admin notifier
    admin_notifier = test_admin_notifier_creation(config)
    if not admin_notifier:
        print("\n⚠️  Admin notifier not available - testing global functions only")
        
        # Run global function tests only
        global_tests = [
            ("Global Critical Exception", test_global_critical_exception),
            ("Global Service Failure", test_global_service_failure),
            ("Global Celery Failure", test_global_celery_failure),
            ("Global System Startup", test_global_system_startup),
            ("Global Configuration Error", test_global_configuration_error),
            ("Global Resource Alert", test_global_resource_alert),
            ("Global System Shutdown", test_global_system_shutdown),
        ]
        
        results = [("Global Function Imports", imports_success)]
        
        for test_name, test_func in global_tests:
            try:
                success = test_func()
                results.append((test_name, success))
                time.sleep(0.5)  # Small delay between tests
            except Exception as e:
                print(f"❌ Unexpected error in {test_name} test: {e}")
                results.append((test_name, False))
                traceback.print_exc()
    
    else:
        # Run full test suite with both direct methods and global functions
        print("\n🎯 Running comprehensive test suite...")
        
        # Direct admin notifier tests
        direct_tests = [
            ("Basic Connection", lambda: test_basic_connection(admin_notifier)),
            ("Direct Critical Exception", lambda: test_critical_exception_notification(admin_notifier)),
            ("Direct Service Failure", lambda: test_service_failure_notification(admin_notifier)),
            ("Direct Celery Failure", lambda: test_celery_failure_notification(admin_notifier)),
            ("Direct System Startup", lambda: test_system_startup_notification(admin_notifier)),
            ("Direct Configuration Error", lambda: test_configuration_error_notification(admin_notifier)),
            ("Direct Resource Alert", lambda: test_resource_alert_notification(admin_notifier)),
            ("Direct System Shutdown", lambda: test_system_shutdown_notification(admin_notifier)),
        ]
        
        # Global convenience function tests
        global_tests = [
            ("Global Critical Exception", test_global_critical_exception),
            ("Global Service Failure", test_global_service_failure),
            ("Global Celery Failure", test_global_celery_failure),
            ("Global System Startup", test_global_system_startup),
            ("Global Configuration Error", test_global_configuration_error),
            ("Global Resource Alert", test_global_resource_alert),
            ("Global System Shutdown", test_global_system_shutdown),
        ]
        
        # Combine all tests
        all_tests = [("Global Function Imports", lambda: True)] + direct_tests + global_tests
        results = [("Global Function Imports", imports_success)]
        
        for test_name, test_func in direct_tests + global_tests:
            try:
                success = test_func()
                results.append((test_name, success))
                
                # Add small delay between tests to avoid potential rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                print(f"❌ Unexpected error in {test_name} test: {e}")
                results.append((test_name, False))
                traceback.print_exc()
    
    # Print comprehensive summary
    print("\n" + "=" * 60)
    print("📊 COMPREHENSIVE TEST RESULTS SUMMARY")
    print("=" * 60)
    
    # Categorize results
    setup_tests = [r for r in results if "Import" in r[0] or "Connection" in r[0]]
    direct_tests_results = [r for r in results if "Direct" in r[0]]
    global_tests_results = [r for r in results if "Global" in r[0] and "Import" not in r[0]]
    
    def print_category(category_name, tests):
        if tests:
            print(f"\n{category_name}:")
            for test_name, success in tests:
                status = "✅ PASS" if success else "❌ FAIL"
                print(f"  {test_name:<35} {status}")
    
    print_category("Setup & Connection Tests", setup_tests)
    print_category("Direct Admin Notifier Tests", direct_tests_results)
    print_category("Global Convenience Function Tests", global_tests_results)
    
    # Overall summary
    passed = sum(1 for _, success in results if success)
    failed = len(results) - passed
    
    print("-" * 60)
    print(f"Total Tests: {len(results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {(passed/len(results)*100):.1f}%")
    
    if failed == 0:
        print("\n🎉 All admin Teams tests passed!")
        print("✅ Both direct admin notifier methods and global convenience functions work correctly")
        print("📧 Check your admin Teams channel for test notifications")
        return True
    else:
        print(f"\n⚠️  {failed} test(s) failed.")
        if admin_notifier is None:
            print("💡 Admin notifier not configured - add TEAMS_ADMIN_WEBHOOK to config.json")
        else:
            print("💡 Please check the Teams webhook URL and channel configuration.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)