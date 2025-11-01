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
    """
    Manages safe access to Telegram sessions by checking worker processes
    
    Note: This class now primarily uses worker process detection for safety.
    The actual session file locking is handled by TelegramSessionManager using fcntl.
    """
    
    def __init__(self, session_file="telegram_session"):
        self.session_file = session_file
        # Keep these for backward compatibility with check_session_safety.py
        self.lock_file = f"{session_file}.lock"
        self.process_info_file = f"{session_file}.process_info"
    
    def is_telegram_workers_active(self):
        """
        Check if Celery workers that handle Telegram operations are currently active
        This is the primary and most accurate way to determine if session access is safe
        """
        try:
            # Method 1: Check for running Telegram-related Celery processes
            result = subprocess.run([
                'pgrep', '-f', 'celery.*telegram_celery_tasks'
            ], capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                
                # Method 2: For extra accuracy, check if any of these workers are actually
                # processing Telegram fetch tasks (not just idle)
                try:
                    # Try to connect to Celery and check active tasks
                    import subprocess
                    celery_inspect = subprocess.run([
                        'celery', '-A', 'src.tasks.telegram_celery_tasks', 'inspect', 'active'
                    ], capture_output=True, text=True, timeout=5)
                    
                    if celery_inspect.returncode == 0:
                        # Check if any active tasks are Telegram-related
                        active_output = celery_inspect.stdout.lower()
                        telegram_tasks = [
                            'fetch_new_messages_from_all_channels',
                            'fetch_messages_async',
                            'telegram_scraper'
                        ]
                        
                        for task in telegram_tasks:
                            if task.lower() in active_output:
                                return True, pids, "telegram_task_active"
                        
                        # Workers exist but no active Telegram tasks
                        return True, pids, "workers_idle"
                    else:
                        # Can't check active tasks, assume workers are potentially active
                        return True, pids, "workers_unknown_state"
                        
                except Exception:
                    # Celery inspect failed, but processes exist - assume active for safety
                    return True, pids, "workers_assumed_active"
            
            return False, [], "no_workers"
            
        except Exception as e:
            # Error checking - assume safe (no workers) but log the issue
            print(f"Warning: Could not check Telegram worker status: {e}")
            return False, [], "check_failed"
    
    def check_session_safety(self, operation_type="test"):
        """
        Check if it's safe to access the Telegram session
        
        This function now uses a simplified, more accurate approach:
        - Only checks if Telegram-related Celery workers are active
        - Removed problematic lock file checking that was causing continuous failures
        
        Args:
            operation_type: Type of operation ("test", "debug", "auth", "periodic_fetch", etc.)
            
        Returns:
            bool: True if safe to proceed
            
        Raises:
            SessionSafetyError: If unsafe to proceed with details
        """
        workers_active, worker_pids, worker_state = self.is_telegram_workers_active()
        
        # For periodic fetch operations, be more lenient
        if operation_type.startswith("periodic_fetch"):
            if workers_active and worker_state == "telegram_task_active":
                # Another periodic fetch is already running - skip this cycle
                raise SessionSafetyError(
                    f"🔄 Another Telegram fetch is currently in progress\n"
                    f"   Worker PIDs: {', '.join(worker_pids)}\n"
                    f"   This is normal - the system will try again in the next cycle."
                )
            elif workers_active and worker_state == "workers_idle":
                # Workers exist but idle - this is actually safe for periodic fetch
                return True
            elif not workers_active:
                # No workers - safe to proceed
                return True
            else:
                # Workers in unknown state - proceed with caution for periodic tasks
                print(f"⚠️  Warning: Telegram workers in {worker_state} state, proceeding with periodic fetch")
                return True
        
        # For manual operations (auth, renew, test), be more strict
        else:
            if workers_active:
                raise SessionSafetyError(
                    f"🛡️ PROTECTED: Telegram workers are active - preventing session conflict\n"
                    f"   Active worker PIDs: {', '.join(worker_pids)}\n"
                    f"   Worker state: {worker_state}\n"
                    f"   \n"
                    f"   Running {operation_type} now could cause session invalidation.\n"
                    f"   \n"
                    f"   Solutions:\n"
                    f"   1. Stop workers first: ./scripts/deploy_celery.sh stop\n"
                    f"   2. Run your {operation_type}, then restart: ./scripts/deploy_celery.sh start\n"
                    f"   3. Or wait for workers to finish current tasks\n"
                    f"   \n"
                    f"   Check worker status: ./scripts/status.sh"
                )
        
        # All checks passed - safe to proceed
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