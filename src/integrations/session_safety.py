"""
Session Safety Module

Prevents concurrent access to Telegram sessions that can cause invalidation.
This module provides utilities to ensure only one process accesses the session at a time.
"""

import os
import fcntl
import subprocess
import time
import redis
from datetime import datetime

# Initialize logger
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SAFETY_LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "telegram_session_safety.log")
SAFETY_LOG_TZ = "Asia/Manila"

# Lazy loading to avoid circular imports
LOGGER = None

def get_logger():
    global LOGGER
    if LOGGER is None:
        from src.core.log_handling import LogHandling
        LOGGER = LogHandling(SAFETY_LOG_FILE, SAFETY_LOG_TZ)
    return LOGGER


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
        
        # Calculate lock timeout from config (2 × FETCH_INTERVAL_SECONDS - 30)
        self.lock_timeout = self._calculate_lock_timeout()
        
        # Initialize Redis client for task tracking
        self.redis_client = None
        try:
            self.redis_client = redis.Redis(host='localhost', port=6379, db=2, decode_responses=True)
            self.redis_client.ping()  # Test connection
        except Exception as e:
            get_logger().writeLog(f"⚠️ Redis not available for session safety, using fallback: {e}")
            self.redis_client = None
    
    def _calculate_lock_timeout(self):
        """Calculate lock timeout from config: 2 × FETCH_INTERVAL_SECONDS - 30"""
        try:
            # Load configuration to get fetch interval
            from src.core import file_handling as fh
            import os
            
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            config_path = os.path.join(project_root, "config", "config.json")
            config_handler = fh.FileHandling(config_path)
            config = config_handler.read_json()
            
            if config and 'TELEGRAM_CONFIG' in config:
                fetch_interval = config['TELEGRAM_CONFIG'].get('FETCH_INTERVAL_SECONDS', 240)
                timeout = (fetch_interval * 2) - 30
                return max(timeout, 210)  # Minimum 3.5 minutes
            else:
                get_logger().writeLog(f"⚠️ Could not load config, using default timeout")
                return 450  # Default: 7.5 minutes
        except Exception as e:
            get_logger().writeLog(f"⚠️ Error calculating timeout: {e}, using default")
            return 450  # Default: 7.5 minutes
    
    def is_fetch_safe_to_start(self):
        """
        Check if a Telegram fetch is currently active using Redis-based tracking
        More accurate and reliable than process detection
        
        Returns:
            tuple: (is_safe, fetch_info, state_description)
        """
        if not self.redis_client:
            get_logger().writeLog("⚠️ Redis unavailable, falling back to process detection")
            return self._fallback_process_check()
        
        try:
            # Check for active fetch lock
            fetch_start_time = self.redis_client.get("telegram_fetch_active")
            
            if fetch_start_time:
                current_time = time.time()
                lock_time = float(fetch_start_time)
                age_seconds = current_time - lock_time
                age_minutes = age_seconds / 60
                
                # Check if the lock is stale (older than 7.5 minutes = 450 seconds)
                if age_seconds > self.lock_timeout:
                    deleted = self.redis_client.delete("telegram_fetch_active")
                    if deleted:
                        get_logger().writeLog(f"✅ Stale lock removed - safe to proceed")
                        return True, [], "stale_lock_removed"
                    else:
                        get_logger().writeLog(f"⚠️ Could not remove stale lock, proceeding anyway")
                        return True, [], "stale_lock_removal_failed"
                else:
                    # Active lock within acceptable time
                    get_logger().writeLog(f"🔒 Active fetch lock detected (age: {age_minutes:.1f} minutes)")
                    return False, ["redis_lock"], "fetch_active"
            else:
                get_logger().writeLog(f"✅ No active fetch lock - safe to proceed")
                return True, [], "no_active_fetch"
                
        except Exception as e:
            get_logger().writeLog(f"❌ Redis fetch check failed: {e}")
            
            # Send critical exception to admin for Redis failures
            try:
                from src.integrations.teams_utils import send_critical_exception
                send_critical_exception(
                    "SessionSafetyRedisError",
                    str(e),
                    "SessionSafetyManager.is_fetch_safe_to_start",
                    additional_context={
                        "session_file": self.session_file,
                        "impact": "Redis-based session safety failed, falling back to process detection",
                        "recommendation": "Check Redis connectivity and configuration"
                    }
                )
            except Exception as admin_error:
                get_logger().writeLog(f"❌ Failed to send Redis error to admin: {admin_error}")
            
            # Fallback to process detection
            return self._fallback_process_check()
    
    def _fallback_process_check(self):
        """
        Fallback process detection when Redis is unavailable
        Simplified version of the old worker detection logic
        """
        try:
            # Check for running Telegram-related Celery processes
            result = subprocess.run([
                'pgrep', '-f', 'celery.*telegram_celery_tasks'
            ], capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                get_logger().writeLog(f"🔍 Fallback: Found {len(pids)} Celery processes")
                
                # Simple check - if processes exist, assume they might be active
                # This is less accurate but safer than the complex inspection logic
                return False, pids, "processes_detected_fallback"
            else:
                get_logger().writeLog(f"✅ Fallback: No Celery processes found")
                return True, [], "no_processes_fallback"
                
        except Exception as e:
            get_logger().writeLog(f"❌ Fallback process check failed: {e}")
            # When in doubt, be safe and allow fetch (better than blocking forever)
            return True, [], "fallback_check_failed"
    
    def acquire_fetch_lock(self):
        """
        Acquire a fetch lock to prevent concurrent fetches
        Uses timeout calculated from config (2 × FETCH_INTERVAL_SECONDS - 30)
        If stale lock detected, terminates stuck processes and acquires new lock
        
        Returns:
            bool: True if lock acquired successfully
        """
        if not self.redis_client:
            get_logger().writeLog("⚠️ Redis unavailable, cannot acquire fetch lock")
            return False
        
        try:
            current_time = time.time()
            # Set lock with current timestamp, expire after calculated timeout, only if not exists
            success = self.redis_client.set("telegram_fetch_active", current_time, ex=self.lock_timeout, nx=True)
            
            if success:
                get_logger().writeLog(f"🔐 Acquired fetch lock for {self.lock_timeout/60:.1f} minutes")
                return True
            else:
                # Check if existing lock is stale and try to clean it up
                existing_time = self.redis_client.get("telegram_fetch_active")
                if existing_time:
                    age = current_time - float(existing_time)
                    get_logger().writeLog(f"❌ Could not acquire fetch lock - existing lock age: {age/60:.1f} minutes")
                    
                    # If the existing lock is stale, clean up stuck processes and force remove it
                    if age > self.lock_timeout:
                        get_logger().writeLog(f"🧹 Stale lock detected (age: {age/60:.1f} minutes > timeout: {self.lock_timeout/60:.1f} minutes)")
                        
                        # Terminate any stuck telegram processes
                        self._terminate_stuck_processes()
                        
                        # Force remove the stale lock
                        self.redis_client.delete("telegram_fetch_active")
                        
                        # Try to acquire again
                        success = self.redis_client.set("telegram_fetch_active", current_time, ex=self.lock_timeout, nx=True)
                        if success:
                            get_logger().writeLog(f"🔐 Acquired fetch lock after cleaning up stale lock and processes")
                            return True
                
                return False
                
        except Exception as e:
            get_logger().writeLog(f"❌ Failed to acquire fetch lock: {e}")
            return False
    
    def _terminate_stuck_processes(self):
        """
        Terminate stuck telegram processes when stale lock is detected
        This prevents concurrent API calls that can cause session expiration
        """
        try:
            import subprocess
            import signal
            
            # Find stuck telegram-related processes
            telegram_pids = []
            
            # Check for celery workers running telegram tasks
            try:
                result = subprocess.run(['pgrep', '-f', 'celery.*worker'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    worker_pids = result.stdout.strip().split('\n')
                    
                    # Check which workers might be stuck on telegram tasks
                    for pid in worker_pids:
                        if pid.strip():
                            try:
                                # Check process command line for telegram indicators
                                with open(f'/proc/{pid.strip()}/cmdline', 'r') as f:
                                    cmdline = f.read()
                                    if 'telegram' in cmdline.lower() or 'fetch_new_messages' in cmdline:
                                        telegram_pids.append(pid.strip())
                            except:
                                continue
            except:
                pass
            
            # Also check for any python processes that might be doing telegram operations
            try:
                result = subprocess.run(['pgrep', '-f', 'python.*telegram'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    py_pids = result.stdout.strip().split('\n')
                    telegram_pids.extend([pid.strip() for pid in py_pids if pid.strip()])
            except:
                pass
            
            # Remove duplicates
            telegram_pids = list(set([pid for pid in telegram_pids if pid]))
            
            if telegram_pids:
                get_logger().writeLog(f"🔪 Found {len(telegram_pids)} potentially stuck telegram processes: {telegram_pids}")
                
                # Try graceful termination first (SIGTERM)
                for pid in telegram_pids:
                    try:
                        get_logger().writeLog(f"🔪 Sending SIGTERM to process {pid}")
                        subprocess.run(['kill', '-TERM', pid], check=False)
                    except Exception as e:
                        get_logger().writeLog(f"⚠️ Could not send SIGTERM to {pid}: {e}")
                
                # Wait a bit for graceful shutdown
                import time
                time.sleep(3)
                
                # Force kill any remaining processes (SIGKILL)
                for pid in telegram_pids:
                    try:
                        # Check if process still exists
                        result = subprocess.run(['kill', '-0', pid], capture_output=True)
                        if result.returncode == 0:  # Process still exists
                            get_logger().writeLog(f"🔪 Force killing stubborn process {pid}")
                            subprocess.run(['kill', '-KILL', pid], check=False)
                    except Exception as e:
                        get_logger().writeLog(f"⚠️ Could not force kill {pid}: {e}")
                
                get_logger().writeLog(f"✅ Process cleanup completed for {len(telegram_pids)} processes")
            else:
                get_logger().writeLog(f"ℹ️ No stuck telegram processes found to terminate")
                
        except Exception as e:
            get_logger().writeLog(f"⚠️ Error during process termination: {e}")
            # Don't fail the entire operation if cleanup fails
    
    def release_fetch_lock(self):
        """
        Release the fetch lock
        
        Returns:
            bool: True if lock released successfully
        """
        if not self.redis_client:
            get_logger().writeLog("⚠️ Redis unavailable, cannot release fetch lock")
            return False
        
        try:
            deleted = self.redis_client.delete("telegram_fetch_active")
            if deleted:
                get_logger().writeLog(f"🔓 Released fetch lock")
                return True
            else:
                get_logger().writeLog(f"⚠️ Fetch lock was already released or expired")
                return True  # Still consider this success
                
        except Exception as e:
            get_logger().writeLog(f"❌ Failed to release fetch lock: {e}")
            return False
    
    def check_session_safety(self, operation_type="test"):
        """
        Check if it's safe to access the Telegram session
        
        This function now uses Redis-based task tracking for accurate fetch detection:
        - Uses Redis locks to track active fetch operations
        - Automatic stale lock cleanup (7.5 minute timeout)
        - Fallback to process detection if Redis unavailable
        
        Args:
            operation_type: Type of operation ("test", "debug", "auth", "periodic_fetch", etc.)
            
        Returns:
            bool: True if safe to proceed
            
        Raises:
            SessionSafetyError: If unsafe to proceed with details
        """
        get_logger().writeLog(f"🛡️ Session safety check for operation: {operation_type}")
        
        # For periodic fetch operations, use Redis-based tracking
        if operation_type.startswith("periodic_fetch"):
            # Try to acquire the Redis lock
            if self.redis_client:
                lock_acquired = self.acquire_fetch_lock()
                if lock_acquired:
                    get_logger().writeLog(f"✅ Periodic fetch lock acquired successfully")
                    return True
                else:
                    error_msg = (f"🔄 Could not acquire Telegram fetch lock (another fetch in progress)\n"
                               f"   This is normal - the system will try again in the next cycle.\n"
                               f"   Lock will auto-expire in {self.lock_timeout/60:.1f} minutes if task gets stuck.")
                    get_logger().writeLog(f"⏭️ BLOCKED: Could not acquire Redis lock")
                    raise SessionSafetyError(error_msg)
            else:
                # Fallback to process detection
                if not self._fallback_process_check():
                    error_msg = (f"🔄 Celery processes detected (Redis fallback mode)\n"
                               f"   This is normal - the system will try again in the next cycle.")
                    get_logger().writeLog(f"⏭️ BLOCKED: Processes detected in fallback mode")
                    raise SessionSafetyError(error_msg)
                else:
                    get_logger().writeLog(f"✅ No processes detected (fallback mode)")
                    return True
        
        # For manual operations (auth, renew, test), use fallback process detection
        # This is more conservative to prevent session conflicts during manual operations
        else:
            is_safe, process_info, state = self._fallback_process_check()
            
            if not is_safe:
                error_msg = (f"🛡️ PROTECTED: Celery processes detected - preventing session conflict\n"
                           f"   Detected PIDs: {', '.join(process_info)}\n"
                           f"   Process state: {state}\n"
                           f"   \n"
                           f"   Running {operation_type} now could cause session invalidation.\n"
                           f"   \n"
                           f"   Solutions:\n"
                           f"   1. Stop workers first: ./scripts/deploy_celery.sh stop\n"
                           f"   2. Run your {operation_type}, then restart: ./scripts/deploy_celery.sh start\n"
                           f"   3. Or wait for workers to finish current tasks\n"
                           f"   \n"
                           f"   Check worker status: ./scripts/status.sh")
                get_logger().writeLog(f"🚫 Blocking {operation_type}: Manual operation blocked due to active processes")
                raise SessionSafetyError(error_msg)
            else:
                get_logger().writeLog(f"✅ Manual operation allowed: {state}")
        
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
    Logs user-friendly messages and exits with appropriate codes
    """
    safety = SessionSafetyManager()
    
    try:
        safety.check_session_safety(operation_type)
        print(f"✅ Safe to proceed with {operation_type}")
        return True
    except SessionSafetyError as e:
        error_msg = str(e)
        get_logger().writeLog(f"🚫 CLI Safety Check Failed: {error_msg}")
        print(error_msg)  # Keep print for CLI user feedback
        return False
    except Exception as e:
        critical_msg = f"❌ CRITICAL ERROR in CLI safety check: {e}"
        get_logger().writeLog(critical_msg)
        print(f"❌ Unexpected error: {e}")
        
        # Send critical exception to admin for CLI safety failures
        try:
            from src.integrations.teams_utils import send_critical_exception
            send_critical_exception(
                "SessionSafetyCLIError",
                str(e),
                "check_session_safety_cli",
                additional_context={
                    "operation_type": operation_type,
                    "impact": "CLI session safety check failed unexpectedly",
                    "recommendation": "Investigate CLI safety check implementation"
                }
            )
        except Exception as admin_error:
            get_logger().writeLog(f"❌ Failed to send CLI safety error to admin: {admin_error}")
        
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
                get_logger().writeLog(f"🛡️  Enforcing session safety for {func.__name__} ({operation_type})")
                safety.check_session_safety(operation_type)
                safety.record_session_access(operation_type, func.__name__)
                
                try:
                    get_logger().writeLog(f"✅ Session safety passed - executing {func.__name__}")
                    result = func(*args, **kwargs)
                    get_logger().writeLog(f"✅ Successfully completed {func.__name__}")
                    return result
                finally:
                    safety.cleanup_session_access()
                    
            except SessionSafetyError as e:
                error_msg = f"🚫 SESSION SAFETY CHECK FAILED for {func.__name__}: {str(e)}"
                get_logger().writeLog(error_msg)
                
                # Keep print for immediate user feedback in decorators
                print(f"\n🚫 SESSION SAFETY CHECK FAILED for {func.__name__}:")
                print(str(e))
                print(f"\n💡 TIP: This safety check prevents session invalidation that")
                print(f"   disconnects your phone's Telegram app.")
                
                # Send to admin for decorator safety failures
                try:
                    from src.integrations.teams_utils import send_critical_exception
                    send_critical_exception(
                        "SessionSafetyDecoratorBlocked",
                        str(e),
                        f"enforce_session_safety.{func.__name__}",
                        additional_context={
                            "operation_type": operation_type,
                            "function_name": func.__name__,
                            "impact": "Function execution blocked to prevent session invalidation",
                            "recommendation": "Ensure workers are stopped before running this operation"
                        }
                    )
                except Exception as admin_error:
                    get_logger().writeLog(f"❌ Failed to send decorator safety error to admin: {admin_error}")
                
                return None
                
            except Exception as e:
                critical_msg = f"❌ CRITICAL ERROR in session safety decorator for {func.__name__}: {e}"
                get_logger().writeLog(critical_msg)
                
                # Send critical exception to admin for decorator failures
                try:
                    from src.integrations.teams_utils import send_critical_exception
                    send_critical_exception(
                        "SessionSafetyDecoratorError",
                        str(e),
                        f"enforce_session_safety.{func.__name__}",
                        additional_context={
                            "operation_type": operation_type,
                            "function_name": func.__name__,
                            "impact": "Session safety decorator failed unexpectedly",
                            "recommendation": "Investigate decorator implementation issues"
                        }
                    )
                except Exception as admin_error:
                    get_logger().writeLog(f"❌ Failed to send decorator error to admin: {admin_error}")
                
                print(f"\n❌ Unexpected error in session safety check for {func.__name__}: {e}")
                return None
                
        return wrapper
    return decorator