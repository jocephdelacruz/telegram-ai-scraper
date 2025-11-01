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
    
    # Check for running workers
    workers_active, worker_pids, worker_state = safety.is_telegram_workers_active()
    
    if workers_active:
        print("⚠️  TELEGRAM WORKERS DETECTED:")
        print(f"   Active worker PIDs: {', '.join(worker_pids)}")
        print(f"   Worker state: {worker_state}")
        print("   Workers may be using the Telegram session")
        print()
    else:
        print("✅ No Telegram workers detected")
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
    
    # Overall safety assessment
    try:
        safety.check_session_safety("safety_check")
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