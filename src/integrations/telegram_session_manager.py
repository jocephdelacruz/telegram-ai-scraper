"""
Advanced Telegram Session Manager

This module provides intelligent session management for Telegram API connections,
including automatic recovery, rate limit handling, and session corruption detection.
"""

import os
import asyncio
import sys
import fcntl
import time
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError, 
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    FloodWaitError,
    ApiIdInvalidError,
    PhoneNumberInvalidError,
    AuthKeyUnregisteredError,
    SessionExpiredError,
    SessionRevokedError
)

# Add project root to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.core import log_handling as lh

# Setup project logging (consistent with telegram_utils.py)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "telegram.log")
LOG_TZ = "Asia/Manila"
LOGGER = lh.LogHandling(LOG_FILE, LOG_TZ)


class TelegramRateLimitError(Exception):
    """Raised when Telegram API rate limiting is detected"""
    pass


class TelegramSessionError(Exception):
    """Raised when session needs manual re-authentication"""
    pass


class TelegramAuthError(Exception):
    """Raised when authentication fails"""
    pass


class TelegramSessionManager:
    """
    Advanced Telegram session manager with automatic recovery capabilities
    
    Features:
    - Automatic session validation and renewal
    - Rate limit detection and handling
    - Session corruption recovery
    - Intelligent error classification
    - Connection state management
    """
    
    def __init__(self, api_id, api_hash, phone_number, session_file="telegram_session"):
        """
        Initialize the session manager
        
        Args:
            api_id (int): Telegram API ID
            api_hash (str): Telegram API hash
            phone_number (str): Phone number for authentication
            session_file (str): Path to session file (without .session extension)
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone_number = phone_number
        self.session_file = session_file
        self.client = None
        self.last_successful_connection = None
        self.rate_limit_until = None
        self.connection_attempts = 0
        self.max_retry_attempts = 2
        self._session_lock = None
        self._lock_file_path = f"{session_file}.lock"
        
        # Session manager initialized - use LOGGER for consistency
        LOGGER.writeLog("TelegramSessionManager initialized with advanced session management")
    
    async def get_client(self, force_reconnect=False):
        """
        Get a working Telegram client with automatic session management
        
        Args:
            force_reconnect (bool): Force a new connection even if one exists
            
        Returns:
            TelegramClient: Active and authenticated client
            
        Raises:
            TelegramRateLimitError: When rate limited
            TelegramSessionError: When session needs re-authentication
            TelegramAuthError: When authentication fails
        """
        
        # Check if we're still rate limited
        if self.rate_limit_until and datetime.now() < self.rate_limit_until:
            remaining = (self.rate_limit_until - datetime.now()).total_seconds()
            raise TelegramRateLimitError(
                f"Still rate limited for {remaining:.0f} more seconds. "
                f"Rate limit expires at {self.rate_limit_until.strftime('%Y-%m-%d %H:%M:%S')}"
            )
        
        # Try to use existing client first
        if not force_reconnect and self.client and self.client.is_connected():
            try:
                # Test the connection with a simple API call
                await self._test_connection()
                return self.client
            except Exception as e:
                LOGGER.writeLog(f"Existing client failed test: {e}")
                await self._cleanup_client()
        
        # Create new client
        return await self._create_new_client()
    
    async def _create_new_client(self):
        """Create and authenticate a new Telegram client with file locking"""
        self.connection_attempts += 1
        
        # Acquire file lock to prevent concurrent session access
        await self._acquire_session_lock()
        
        try:
            self.client = TelegramClient(self.session_file, self.api_id, self.api_hash)
            
            LOGGER.writeLog(f"Attempting to start Telegram client (attempt {self.connection_attempts}) with session lock")
            
            # Start the client with phone authentication
            await self.client.start(phone=self.phone_number)
            
            # Test the connection
            await self._test_connection()
            
            # Success - reset counters and update state
            self.last_successful_connection = datetime.now()
            self.rate_limit_until = None
            self.connection_attempts = 0
            
            LOGGER.writeLog("Telegram client started successfully with session protection")
            return self.client
            
        except FloodWaitError as e:
            # Handle rate limiting
            wait_time = e.seconds
            self.rate_limit_until = datetime.now() + timedelta(seconds=wait_time)
            
            LOGGER.writeLog(f"🚫 Rate limited: must wait {wait_time} seconds until {self.rate_limit_until}")
            
            await self._cleanup_client()
            raise TelegramRateLimitError(
                f"Rate limited: wait {wait_time} seconds until {self.rate_limit_until.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
        except (PhoneCodeInvalidError, PhoneCodeExpiredError, SessionPasswordNeededError, AuthKeyUnregisteredError, SessionExpiredError, SessionRevokedError) as e:
            # Session needs re-authentication - handle gracefully to prevent phone logout
            LOGGER.writeLog(f"🔐 Session authentication required: {e}")
            
            # ENHANCED: Try graceful session renewal instead of complete failure
            if isinstance(e, (SessionExpiredError, SessionRevokedError, AuthKeyUnregisteredError)):
                LOGGER.writeLog("Attempting graceful session renewal to prevent phone logout...")
                try:
                    # Gracefully disconnect current session
                    if self.client and self.client.is_connected():
                        await self.client.disconnect()
                    
                    # Create a fresh client for renewal (without deleting session file)
                    self.client = TelegramClient(self.session_file, self.api_id, self.api_hash)
                    
                    # This will prompt for SMS but should preserve phone session
                    await self.client.start(phone=self.phone_number)
                    
                    # Test the renewed connection
                    await self._test_connection()
                    
                    # Success - update state
                    self.last_successful_connection = datetime.now()
                    self.connection_attempts = 0
                    
                    LOGGER.writeLog("✅ Session renewed successfully without phone logout")
                    return self.client
                    
                except Exception as renewal_error:
                    LOGGER.writeLog(f"❌ Session renewal failed: {renewal_error}")
                    # Fall through to original error handling
            
            await self._handle_session_expiry()
            raise TelegramSessionError(
                f"Session expired or requires re-authentication: {type(e).__name__}. "
                "Run 'python3 scripts/telegram_auth.py' to re-authenticate."
            )
            
        except (ApiIdInvalidError, PhoneNumberInvalidError) as e:
            # Configuration errors
            LOGGER.writeLog(f"🚨 Configuration error: {e}")
            await self._cleanup_client()
            raise TelegramAuthError(
                f"Invalid API credentials: {type(e).__name__}. "
                "Check your API_ID, API_HASH, and PHONE_NUMBER in config.json"
            )
            
        except Exception as e:
            error_msg = str(e)
            LOGGER.writeLog(f"❌ Unexpected error during client creation: {error_msg}")
            
            if "EOF when reading a line" in error_msg:
                # Session file might be corrupted
                await self._handle_corrupted_session()
                raise TelegramSessionError(
                    "Session file corrupted. Backup created. "
                    "Run 'python3 scripts/telegram_auth.py' to re-authenticate."
                )
            elif "Connection to Telegram failed" in error_msg:
                # Network issues
                await self._cleanup_client()
                raise TelegramAuthError(f"Network connection failed: {error_msg}")
            else:
                # Unknown error
                await self._cleanup_client()
                raise TelegramAuthError(f"Unknown authentication error: {error_msg}")
        
        except KeyboardInterrupt:
            # Handle user interruption (Ctrl+C)
            LOGGER.writeLog("⚠️ Client creation interrupted by user")
            await self._cleanup_client()
            raise TelegramAuthError("Authentication interrupted by user")
            
        finally:
            # CRITICAL: Always release session lock regardless of success/failure
            if self._session_lock:
                await self._release_session_lock()
    
    async def _test_connection(self):
        """Test the current connection with a simple API call"""
        if not self.client or not self.client.is_connected():
            raise Exception("Client not connected")
        
        # Simple test - get own user info
        me = await self.client.get_me()
        if not me:
            raise Exception("Failed to retrieve user information")
        
        LOGGER.writeLog(f"✅ Connection test successful - connected as {me.first_name}")
    
    async def _handle_corrupted_session(self):
        """Handle corrupted session by backing up and clearing"""
        try:
            session_path = f"{self.session_file}.session"
            if os.path.exists(session_path):
                # Backup corrupted session
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_name = f"{self.session_file}_corrupted_{timestamp}.session"
                os.rename(session_path, backup_name)
                LOGGER.writeLog(f"📁 Backed up corrupted session to {backup_name}")
        except Exception as e:
            LOGGER.writeLog(f"❌ Failed to backup corrupted session: {e}")
        
        await self._cleanup_client()
    
    async def _handle_session_expiry(self):
        """Handle expired session"""
        LOGGER.writeLog("🔐 Session expired - cleanup required")
        await self._cleanup_client()
    
    async def _cleanup_client(self):
        """Properly cleanup the current client with graceful disconnect"""
        if self.client:
            try:
                # Give the client more time to disconnect gracefully
                await asyncio.wait_for(self.client.disconnect(), timeout=10)
                LOGGER.writeLog("🔌 Client disconnected gracefully")
            except asyncio.TimeoutError:
                LOGGER.writeLog("⚠️ Client disconnect timed out")
            except Exception as e:
                LOGGER.writeLog(f"⚠️ Error during client disconnect: {e}")
            finally:
                self.client = None
        
        # Always release the session lock after cleanup
        await self._release_session_lock()
    
    async def _acquire_session_lock(self):
        """Acquire file lock to prevent concurrent session access"""
        try:
            # Create lock file if it doesn't exist
            if not os.path.exists(self._lock_file_path):
                with open(self._lock_file_path, 'w') as f:
                    f.write(f"Session lock created at {datetime.now().isoformat()}\n")
            
            # Open and lock the file
            self._session_lock = open(self._lock_file_path, 'r+')
            
            # Try to acquire exclusive lock with timeout
            max_wait = 30  # 30 seconds timeout
            wait_time = 0
            while wait_time < max_wait:
                try:
                    fcntl.flock(self._session_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    LOGGER.writeLog(f"🔒 Session lock acquired after {wait_time}s")
                    return
                except BlockingIOError:
                    # Lock is held by another process
                    if wait_time == 0:
                        LOGGER.writeLog("⏳ Session lock held by another process, waiting...")
                    await asyncio.sleep(1)
                    wait_time += 1
            
            # Timeout reached
            LOGGER.writeLog(f"❌ Failed to acquire session lock after {max_wait}s")
            raise Exception("Session lock timeout - another process may be using the session")
            
        except Exception as e:
            if self._session_lock:
                try:
                    self._session_lock.close()
                except:
                    pass
                self._session_lock = None
            raise

    async def _release_session_lock(self):
        """Release the session file lock"""
        if self._session_lock:
            try:
                fcntl.flock(self._session_lock.fileno(), fcntl.LOCK_UN)
                self._session_lock.close()
                LOGGER.writeLog("🔓 Session lock released")
            except Exception as e:
                LOGGER.writeLog(f"⚠️ Error releasing session lock: {e}")
            finally:
                self._session_lock = None

    async def close(self):
        """Properly close the session manager with lock cleanup"""
        await self._cleanup_client()
        await self._release_session_lock()
        LOGGER.writeLog("🔚 Telegram session manager closed with lock cleanup")
    
    def is_rate_limited(self):
        """Check if currently rate limited"""
        return self.rate_limit_until and datetime.now() < self.rate_limit_until
    
    def get_rate_limit_info(self):
        """
        Get rate limit information
        
        Returns:
            dict or None: Rate limit info if currently limited, None otherwise
        """
        if not self.rate_limit_until:
            return None
        
        remaining = (self.rate_limit_until - datetime.now()).total_seconds()
        if remaining <= 0:
            self.rate_limit_until = None
            return None
            
        return {
            'remaining_seconds': remaining,
            'expires_at': self.rate_limit_until.isoformat(),
            'expires_human': self.rate_limit_until.strftime('%Y-%m-%d %H:%M:%S'),
            'expires_timestamp': self.rate_limit_until.timestamp()
        }
    
    def get_connection_status(self):
        """
        Get current connection status information
        
        Returns:
            dict: Status information
        """
        return {
            'is_connected': self.client is not None and self.client.is_connected() if self.client else False,
            'last_successful_connection': self.last_successful_connection.isoformat() if self.last_successful_connection else None,
            'connection_attempts': self.connection_attempts,
            'is_rate_limited': self.is_rate_limited(),
            'rate_limit_info': self.get_rate_limit_info()
        }
    
    async def health_check(self):
        """
        Perform a comprehensive health check
        
        Returns:
            dict: Health check results
        """
        status = {
            'healthy': False,
            'timestamp': datetime.now().isoformat(),
            'connection_status': self.get_connection_status(),
            'errors': []
        }
        
        try:
            # Check rate limiting first
            if self.is_rate_limited():
                rate_info = self.get_rate_limit_info()
                status['errors'].append(f"Rate limited until {rate_info['expires_human']}")
                return status
            
            # Try to get a working client
            client = await self.get_client()
            
            # Test basic functionality
            me = await client.get_me()
            status['user_info'] = {
                'id': me.id,
                'name': me.first_name,
                'phone': me.phone,
                'username': me.username
            }
            
            status['healthy'] = True
            
        except TelegramRateLimitError as e:
            status['errors'].append(f"Rate limited: {e}")
        except TelegramSessionError as e:
            status['errors'].append(f"Session error: {e}")
        except TelegramAuthError as e:
            status['errors'].append(f"Authentication error: {e}")
        except Exception as e:
            status['errors'].append(f"Unexpected error: {e}")
        
        return status