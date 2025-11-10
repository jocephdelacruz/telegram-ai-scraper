#!/usr/bin/env python3
"""
Session Safety Checker
Verifies that it's safe to perform Telegram operations without session conflicts
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from src.integrations.session_safety import SessionSafetyManager, SessionSafetyError


def main():
    """Check session safety status"""
    print("🔍 Telegram Session Safety Check")
    print("=" * 50)
    
    safety = SessionSafetyManager()
    
    # Check Redis connection status
    if safety.redis_client:
        print("✅ Redis connection: ACTIVE")
        print(f"   Lock timeout: {safety.lock_timeout/60:.1f} minutes (calculated from config)")
        print()
        
        # Check for active Redis locks
        try:
            fetch_lock = safety.redis_client.get("telegram_fetch_active")
            if fetch_lock:
                import time
                lock_age = time.time() - float(fetch_lock)
                print("⚠️  REDIS FETCH LOCK DETECTED:")
                print(f"   Lock timestamp: {fetch_lock}")
                print(f"   Lock age: {lock_age/60:.1f} minutes")
                if lock_age > safety.lock_timeout:
                    print(f"   ⚠️  STALE LOCK (older than {safety.lock_timeout/60:.1f} minutes)")
                else:
                    print("   ✅ Lock is still valid")
                print()
            else:
                print("✅ No Redis fetch lock detected")
                print()
        except Exception as e:
            print(f"❌ Error checking Redis lock: {e}")
            print()
    else:
        print("❌ Redis connection: UNAVAILABLE (using fallback mode)")
        print()
    
    # Check fetch safety using new system
    is_safe, fetch_info, state = safety.is_fetch_safe_to_start()
    
    if not is_safe:
        print("⚠️  FETCH STATUS: BLOCKED")
        print(f"   Reason: {state}")
        if fetch_info:
            if state == "fetch_active":
                print("   Active Redis lock prevents concurrent fetches")
            else:
                print(f"   Detected processes: {', '.join(fetch_info)}")
        print()
    else:
        print("✅ FETCH STATUS: SAFE")
        print(f"   State: {state}")
        print()
    
    # Check for session lock
    if os.path.exists(safety.lock_file):
        print("⚠️  SESSION LOCK FILE EXISTS:")
        print(f"   Lock file: {safety.lock_file}")
        try:
            with open(safety.lock_file, 'r') as f:
                content = f.read().strip()
            print(f"   Content: {content}")
        except Exception as e:
            print(f"   Error reading lock: {e}")
        print()
    else:
        print("✅ No session lock file found")
        print()
    
    # Check for process info
    if os.path.exists(safety.process_info_file):
        print("ℹ️  PROCESS INFO FILE EXISTS:")
        print(f"   Info file: {safety.process_info_file}")
        try:
            with open(safety.process_info_file, 'r') as f:
                content = f.read().strip()
            print(f"   Content:\n{content}")
        except Exception as e:
            print(f"   Error reading info: {e}")
        print()
    else:
        print("✅ No process info file found")
        print()
    
    # Test different operation types
    print("🧪 TESTING DIFFERENT OPERATION TYPES:")
    print("-" * 40)
    
    # Test periodic fetch (uses Redis locking)
    print("📅 Testing periodic_fetch operation:")
    try:
        safety.check_session_safety("periodic_fetch")
        print("   ✅ Periodic fetch: SAFE (Redis lock acquired)")
        
        # Try second periodic fetch (should fail)
        try:
            safety2 = SessionSafetyManager()
            safety2.check_session_safety("periodic_fetch")
            print("   ❌ Second periodic fetch: UNEXPECTEDLY ALLOWED")
        except SessionSafetyError:
            print("   ✅ Second periodic fetch: CORRECTLY BLOCKED")
        
        # Release the lock
        safety.release_fetch_lock()
        print("   ✅ Lock released")
        
    except SessionSafetyError as e:
        print("   ❌ Periodic fetch: BLOCKED")
        print(f"   Reason: {str(e).split(chr(10))[0]}")
    
    print()
    
    # Test manual operation (uses fallback process detection)
    print("🔧 Testing manual operation:")
    try:
        safety.check_session_safety("manual_test")
        print("   ✅ Manual operation: SAFE")
    except SessionSafetyError as e:
        print("   ❌ Manual operation: BLOCKED")
        print(f"   Reason: {str(e).split(chr(10))[0]}")
    
    print()
    
    # Overall safety assessment
    try:
        # Use a fresh instance to avoid lock conflicts
        safety_final = SessionSafetyManager()
        safety_final.check_session_safety("safety_check")
        print("🎉 OVERALL STATUS: SAFE")
        print("   ✅ Safe to perform Telegram operations")
        print("   ✅ No session conflicts detected")
        return True
    except SessionSafetyError as e:
        print("🚫 OVERALL STATUS: UNSAFE")
        print("   ❌ Session conflicts detected")
        print("   ❌ Telegram operations may cause session invalidation")
        print()
        print("DETAILS:")
        for line in str(e).split('\n'):
            if line.strip():
                print(f"   {line}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)