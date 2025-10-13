"""
Session Safety Module

Prevents concurrent access to Telegram sessions that can cause invalidation.
This module provides utilities to ensure only one process accesses the session at a time.
"""

import os
import fcntl
import subprocess
import time
from datetime import datetime


class SessionSafetyError(Exception):
    """Raised when session access is unsafe due to concurrent processes"""
    pass


class SessionSafetyManager:
    """Manages safe access to Telegram sessions"""
    
    def __init__(self, session_file="telegram_session"):
        self.session_file = session_file
        self.lock_file = f"{session_file}.lock"
        self.process_info_file = f"{session_file}.process_info"
    
    def is_celery_workers_running(self):
        """Check if Celery workers that use Telegram are currently running"""
        try:
            # Check for specific Celery workers that handle Telegram tasks
            result = subprocess.run([
                'pgrep', '-f', 'celery.*telegram_celery_tasks'
            ], capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                return True, pids
            return False, []
        except Exception:
            return False, []
    
    def check_session_safety(self, operation_type="test"):
        """
        Check if it's safe to access the Telegram session
        
        Args:
            operation_type: Type of operation ("test", "debug", "auth", etc.)
            
        Returns:
            bool: True if safe to proceed
            
        Raises:
            SessionSafetyError: If unsafe to proceed with details
        """
        workers_running, worker_pids = self.is_celery_workers_running()
        
        if workers_running:
            raise SessionSafetyError(
                f"❌ UNSAFE: Celery workers are running and may be using the Telegram session!\n"
                f"   Active worker PIDs: {', '.join(worker_pids)}\n"
                f"   \n"
                f"   This {operation_type} could cause session invalidation.\n"
                f"   \n"
                f"   Solutions:\n"
                f"   1. Stop workers first: ./scripts/deploy_celery.sh stop\n"
                f"   2. Run your {operation_type}, then restart: ./scripts/deploy_celery.sh start\n"
                f"   3. Or wait for workers to finish current tasks (may take a few minutes)\n"
                f"   \n"
                f"   Check worker status: ./scripts/status.sh"
            )
        
        # Check for lock file (additional safety)
        if os.path.exists(self.lock_file):
            try:
                with open(self.lock_file, 'r') as f:
                    lock_content = f.read().strip()
                raise SessionSafetyError(
                    f"❌ UNSAFE: Session lock file exists!\n"
                    f"   Lock file: {self.lock_file}\n"
                    f"   Content: {lock_content}\n"
                    f"   \n"
                    f"   Another process may be using the Telegram session.\n"
                    f"   Wait for it to finish or manually remove the lock file if stuck."
                )
            except (IOError, OSError):
                pass  # Lock file might be in use or temporary
        
        return True
    
    def record_session_access(self, process_type, additional_info=""):
        """Record that this process is accessing the session"""
        try:
            info = {
                'process_type': process_type,
                'pid': os.getpid(),
                'start_time': datetime.now().isoformat(),
                'additional_info': additional_info
            }
            
            with open(self.process_info_file, 'w') as f:
                f.write(f"Process: {process_type}\n")
                f.write(f"PID: {os.getpid()}\n")
                f.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                if additional_info:
                    f.write(f"Info: {additional_info}\n")
        except Exception:
            pass  # Non-critical
    
    def cleanup_session_access(self):
        """Clean up session access records"""
        try:
            if os.path.exists(self.process_info_file):
                os.remove(self.process_info_file)
        except Exception:
            pass  # Non-critical
    
    def safe_session_operation(self, operation_type="operation"):
        """
        Context manager for safe session operations
        
        Usage:
            safety = SessionSafetyManager()
            with safety.safe_session_operation("test"):
                # Your Telegram session code here
                pass
        """
        return SafeSessionContext(self, operation_type)


class SafeSessionContext:
    """Context manager for safe session operations"""
    
    def __init__(self, safety_manager, operation_type):
        self.safety_manager = safety_manager
        self.operation_type = operation_type
    
    def __enter__(self):
        # Check safety before entering
        self.safety_manager.check_session_safety(self.operation_type)
        self.safety_manager.record_session_access(self.operation_type)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Clean up on exit
        self.safety_manager.cleanup_session_access()


def check_session_safety_cli(operation_type="operation"):
    """
    CLI-friendly function to check session safety
    Prints user-friendly messages and exits with appropriate codes
    """
    safety = SessionSafetyManager()
    
    try:
        safety.check_session_safety(operation_type)
        print(f"✅ Safe to proceed with {operation_type}")
        return True
    except SessionSafetyError as e:
        print(str(e))
        return False


def enforce_session_safety(operation_type="operation"):
    """
    Decorator to enforce session safety for functions that use Telegram
    
    Usage:
        @enforce_session_safety("debug_test")
        def my_telegram_function():
            # Your code here
            pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            safety = SessionSafetyManager()
            try:
                safety.check_session_safety(operation_type)
                safety.record_session_access(operation_type, func.__name__)
                try:
                    return func(*args, **kwargs)
                finally:
                    safety.cleanup_session_access()
            except SessionSafetyError as e:
                print(f"\n🚫 SESSION SAFETY CHECK FAILED for {func.__name__}:")
                print(str(e))
                print(f"\n💡 TIP: This safety check prevents session invalidation that")
                print(f"   disconnects your phone's Telegram app.")
                return None
        return wrapper
    return decorator