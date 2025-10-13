#!/usr/bin/env python3
"""
Telegram AI Scraper - Main Module
Scrapes Telegram channels, analyzes messages with AI, and sends alerts to Teams/SharePoint
"""

import asyncio
import json
import sys
import os
from datetime import datetime, timedelta
import signal
import argparse

# Import custom modules
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core import log_handling as lh
from src.core import file_handling as fh
from src.integrations.telegram_utils import TelegramScraper
from src.integrations.telegram_session_manager import TelegramRateLimitError, TelegramSessionError, TelegramAuthError
from src.integrations.session_safety import SessionSafetyManager, SessionSafetyError
from src.integrations.openai_utils import OpenAIProcessor
from src.integrations.teams_utils import TeamsNotifier
from src.integrations.sharepoint_utils import SharepointProcessor

# Import Celery tasks
from src.tasks.telegram_celery_tasks import process_telegram_message, health_check
from celery.result import AsyncResult

# Logging setup
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "main.log")
LOG_TZ = "Asia/Manila"
LOGGER = lh.LogHandling(LOG_FILE, LOG_TZ)

class TelegramAIScraper:
    def __init__(self, config_file="config.json"):
        """
        Initialize the Telegram AI Scraper
        
        Args:
            config_file: Path to configuration file (relative to project root)
        """
        self.config = None
        self.telegram_scraper = None
        self.openai_processor = None
        self.teams_notifier = None
        self.sharepoint_processor = None
        self.running = False
        self.active_tasks = {}  # Track active Celery tasks
        self.stats = {
            'total_messages': 0,
            'significant_messages': 0,
            'errors': 0,
            'start_time': None,
            'tasks_queued': 0,
            'tasks_completed': 0,
            'tasks_failed': 0
        }
        
        try:
            # Determine project root directory
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
            # Handle relative and absolute paths
            if not os.path.isabs(config_file):
                # If relative, make it relative to project root
                config_path = os.path.join(project_root, "config", config_file)
            else:
                config_path = config_file
            
            # Load configuration
            config_handler = fh.FileHandling(config_path)
            self.config = config_handler.read_json()
            
            if not self.config:
                raise Exception(f"Failed to load configuration from {config_path}")
            
            LOGGER.writeLog(f"Configuration loaded from: {config_path}")
            
            LOGGER.writeLog("TelegramAIScraper initialized successfully")
            
        except Exception as e:
            LOGGER.writeLog(f"Failed to initialize TelegramAIScraper: {e}")
            # Send critical exception to admin if possible
            try:
                from src.integrations.teams_utils import send_critical_exception
                send_critical_exception(
                    "InitializationError",
                    str(e),
                    "TelegramAIScraper.__init__",
                    additional_context={"config_file": config_file}
                )
            except:
                pass  # If admin notification fails, continue
            raise


    def determine_message_country(self, channel_name):
        """Determine which country a channel belongs to"""
        countries = self.config.get('COUNTRIES', {})
        
        for country_code, country_info in countries.items():
            if channel_name in country_info.get('channels', []):
                return country_code, country_info
        
        # Default fallback if channel not found in any country
        return None, None

    async def initialize_components(self, test_mode=False):
        """Initialize all components (Telegram, OpenAI, Teams, SharePoint)"""
        self._test_mode = test_mode  # Store test mode flag
        try:
            print("Initializing OpenAI processor...")
            # Initialize OpenAI processor
            openai_key = self.config.get('OPEN_AI_KEY', '')
            if not openai_key:
                raise Exception("OpenAI API key not found in configuration")
            
            self.openai_processor = OpenAIProcessor(openai_key)
            print("OpenAI processor initialized successfully")
            LOGGER.writeLog("OpenAI processor initialized")

            print("Initializing Telegram scraper...")
            # Initialize Telegram scraper
            telegram_config = self.config.get('TELEGRAM_CONFIG', {})
            if not all(key in telegram_config for key in ['API_ID', 'API_HASH', 'PHONE_NUMBER']):
                raise Exception("Telegram configuration incomplete")
            
            self.telegram_scraper = TelegramScraper(
                telegram_config['API_ID'],
                telegram_config['API_HASH'],
                telegram_config['PHONE_NUMBER'],
                telegram_config.get('SESSION_FILE', 'telegram_session')
            )
            print("Telegram scraper object created")
            
            # Set message handler
            self.telegram_scraper.set_message_handler(self.handle_new_message)
            print("Message handler set")
            
            # Get all channels from all countries
            all_channels = []
            countries = self.config.get('COUNTRIES', {})
            for country_code, country_info in countries.items():
                channels = country_info.get('channels', [])
                all_channels.extend(channels)
                LOGGER.writeLog(f"Added {len(channels)} channels for {country_info.get('name', country_code)}")
            
            if not all_channels:
                raise Exception("No channels configured in any country")
            
            LOGGER.writeLog(f"Total channels to monitor: {len(all_channels)}")
            
            print("Starting Telegram client...")
            # Start Telegram client with enhanced error handling
            try:
                success = await self.telegram_scraper.start_client()
                if success:
                    print("✅ Telegram client started successfully")
                    LOGGER.writeLog("Telegram scraper initialized")
                else:
                    print("❌ Failed to start Telegram client")
                    print("🔧 This usually means authentication is needed")
                    print("🚀 Run: python3 scripts/telegram_auth.py")
                    LOGGER.writeLog("Failed to start Telegram client - authentication likely needed")
                    
                    # In test mode, we can continue without Telegram to test other components
                    if hasattr(self, '_test_mode') and self._test_mode:
                        print("⚠️  Continuing in test mode without Telegram")
                        self.telegram_scraper = None
                    else:
                        # In monitor/historical mode, Telegram is required
                        raise Exception("Telegram client authentication required. Run: python3 scripts/telegram_auth.py")
                        
            except TelegramRateLimitError as e:
                print(f"🚫 TELEGRAM RATE LIMITED: {e}")
                print("⏸️  System must wait for rate limit to expire")
                print("📊 Use 'python3 tests/check_telegram_status.py' to monitor")
                LOGGER.writeLog(f"Telegram rate limited: {e}")
                raise Exception("Telegram API rate limited - system cannot start")
                
            except TelegramSessionError as e:
                print(f"🔐 TELEGRAM SESSION ERROR: {e}")
                print("🔑 Run 'python3 scripts/telegram_auth.py' to re-authenticate")
                LOGGER.writeLog(f"Telegram session error: {e}")
                
                # In test mode, continue without Telegram
                if hasattr(self, '_test_mode') and self._test_mode:
                    print("⚠️  Continuing in test mode without Telegram")
                    self.telegram_scraper = None
                else:
                    raise Exception("Telegram session authentication required. Run: python3 scripts/telegram_auth.py")
                    
            except TelegramAuthError as e:
                print(f"🚨 TELEGRAM AUTH ERROR: {e}")
                print("🔧 Check your API credentials in config.json")
                LOGGER.writeLog(f"Telegram auth error: {e}")
                
                # In test mode, continue without Telegram
                if hasattr(self, '_test_mode') and self._test_mode:
                    print("⚠️  Continuing in test mode without Telegram")
                    self.telegram_scraper = None
                else:
                    raise Exception("Telegram authentication failed - check API credentials")

            print("Initializing Teams notifier...")
            # Initialize Teams notifier - check both old and new config locations
            teams_config = self.config.get('MICROSOFT_TEAMS_CONFIG', {})
            
            # Check if we have country-specific Teams webhooks
            countries = self.config.get('COUNTRIES', {})
            teams_webhook_found = False
            
            for country_code, country_info in countries.items():
                if country_info.get('teams_webhook'):
                    # Use the first available Teams webhook for general notifications
                    teams_sender_name = self.config.get('TEAMS_SENDER_NAME', 'Aldebaran Scraper')
                    self.teams_notifier = TeamsNotifier(
                        country_info['teams_webhook'],
                        country_info.get('teams_channel_name', f'{country_code.title()} Telegram Alerts'),
                        teams_sender_name
                    )
                    teams_webhook_found = True
                    print(f"Teams notifier initialized with {country_code} webhook as '{teams_sender_name}'")
                    LOGGER.writeLog(f"Teams notifier initialized with {country_code} webhook as '{teams_sender_name}'")
                    break
            
            if not teams_webhook_found:
                if teams_config.get('WEBHOOK_URL'):
                    teams_sender_name = self.config.get('TEAMS_SENDER_NAME', 'Aldebaran Scraper')
                    self.teams_notifier = TeamsNotifier(
                        teams_config['WEBHOOK_URL'],
                        teams_config.get('CHANNEL_NAME', 'Telegram Alerts'),
                        teams_sender_name
                    )
                    print(f"Teams notifier initialized with main config webhook as '{teams_sender_name}'")
                    LOGGER.writeLog(f"Teams notifier initialized with main config webhook as '{teams_sender_name}'")
                else:
                    print("No Teams webhook configured, skipping Teams notifications")
                    LOGGER.writeLog("Teams webhook not configured, skipping Teams notifications")

            print("Initializing SharePoint processor...")
            # Initialize SharePoint processor - SharePoint config is country-specific
            sp_config = self.config.get('MS_SHAREPOINT_ACCESS', {})
            if all(key in sp_config for key in ['ClientID', 'ClientSecret', 'TenantID', 'SharepointSite']):
                try:
                    # For test mode, we don't need to initialize SharePoint as it's country-specific
                    # SharePoint will be initialized per-country in the Celery tasks
                    print("SharePoint credentials available - SharePoint will be initialized per-country")
                    LOGGER.writeLog("SharePoint credentials available - SharePoint will be initialized per-country")
                    self.sharepoint_processor = None  # Will be initialized per-country
                except Exception as e:
                    LOGGER.writeLog(f"SharePoint initialization failed: {e}")
                    LOGGER.writeLog("Continuing without SharePoint integration")
            else:
                print("SharePoint not fully configured, skipping SharePoint integration")
                LOGGER.writeLog("SharePoint not configured, skipping SharePoint integration")

            # Send startup notification to admin
            try:
                from src.integrations.teams_utils import send_system_startup
                components_started = []
                if self.openai_processor:
                    components_started.append("OpenAI Processor")
                if self.telegram_scraper:
                    components_started.append("Telegram Scraper")
                if self.teams_notifier:
                    components_started.append("Teams Notifier")
                components_started.append("Admin Notifier")
                
                send_system_startup(components_started)
            except Exception as e:
                LOGGER.writeLog(f"Failed to send startup notification: {e}")

            return True

        except Exception as e:
            LOGGER.writeLog(f"Error initializing components: {e}")
            
            # Send critical exception to admin
            try:
                from src.integrations.teams_utils import send_critical_exception
                send_critical_exception(
                    "ComponentInitializationError",
                    str(e),
                    "TelegramAIScraper.initialize_components",
                    additional_context={"test_mode": test_mode}
                )
            except Exception as admin_error:
                LOGGER.writeLog(f"Failed to send component initialization error to admin: {admin_error}")
            
            return False


    async def handle_new_message(self, message_data):
        """
        Handle a new message from Telegram - WITH CELERY INTEGRATION
        Fast ingestion, heavy processing delegated to workers
        
        Args:
            message_data: Dictionary containing message information
        """
        try:
            self.stats['total_messages'] += 1
            channel_name = message_data.get('Channel', 'unknown')
            LOGGER.writeLog(f"Received message {message_data.get('Message_ID', 'unknown')} from {channel_name}")

            # Skip empty messages
            if not message_data.get('Message_Text', '').strip():
                LOGGER.writeLog("Skipping message with no text content")
                return

            # Determine country for this message
            country_code, country_info = self.determine_message_country(channel_name)
            if not country_code:
                LOGGER.writeLog(f"Warning: Channel {channel_name} not found in any country configuration")
                country_code = "unknown"
                country_info = {"name": "Unknown"}

            # Add processing metadata
            message_data['received_at'] = datetime.now().isoformat()
            message_data['text'] = message_data.get('Message_Text', '')  # Standardize field name for Celery tasks
            message_data['id'] = message_data.get('Message_ID', '')
            message_data['channel'] = channel_name
            message_data['country_code'] = country_code
            message_data['country_name'] = country_info.get('name', country_code)
            message_data['Country'] = country_info.get('name', country_code)  # For Excel field compatibility

            # FAST: Queue the message for processing (non-blocking)
            task = process_telegram_message.delay(message_data, self.config)
            
            self.stats['tasks_queued'] += 1
            LOGGER.writeLog(f"Queued message {message_data.get('Message_ID', 'unknown')} for processing (Task ID: {task.id})")
            
            # Track task for monitoring
            self.active_tasks[task.id] = {
                'message_id': message_data.get('Message_ID'),
                'channel': message_data.get('Channel'),
                'queued_at': datetime.now(),
                'status': 'queued'
            }
            
            # Optionally clean up old completed tasks
            await self.cleanup_completed_tasks()
            
        except Exception as e:
            self.stats['errors'] += 1
            LOGGER.writeLog(f"Error queuing message {message_data.get('Message_ID', 'unknown')}: {e}")
            
            # Send error alert to Teams
            if self.teams_notifier:
                self.teams_notifier.send_system_alert(
                    "ERROR",
                    f"Error queuing message from {message_data.get('Channel', 'Unknown')}: {e}",
                    {"Message_ID": message_data.get('Message_ID', 'Unknown')}
                )
            
            # Send critical exception to admin if it's a serious error
            if self.stats['errors'] % 10 == 0:  # Every 10th error to avoid spam
                try:
                    from src.integrations.teams_utils import send_critical_exception
                    send_critical_exception(
                        "MessageHandlingError",
                        str(e),
                        "TelegramAIScraper.handle_new_message",
                        additional_context={
                            "message_id": message_data.get('Message_ID', 'unknown'),
                            "channel": message_data.get('Channel', 'unknown'),
                            "total_errors": self.stats['errors']
                        }
                    )
                except Exception as admin_error:
                    LOGGER.writeLog(f"Failed to send message handling error to admin: {admin_error}")


    async def cleanup_completed_tasks(self):
        """Clean up completed tasks from active_tasks tracking"""
        try:
            if len(self.active_tasks) < 100:  # Only cleanup when we have many tasks
                return
                
            completed_tasks = []
            for task_id, task_info in self.active_tasks.items():
                try:
                    result = AsyncResult(task_id)
                    if result.ready():
                        completed_tasks.append(task_id)
                        if result.successful():
                            self.stats['tasks_completed'] += 1
                        else:
                            self.stats['tasks_failed'] += 1
                            LOGGER.writeLog(f"Task {task_id} failed: {result.result}")
                except Exception as e:
                    LOGGER.writeLog(f"Error checking task {task_id}: {e}")
                    completed_tasks.append(task_id)  # Remove problematic tasks
            
            # Remove completed tasks
            for task_id in completed_tasks:
                self.active_tasks.pop(task_id, None)
                
            if completed_tasks:
                LOGGER.writeLog(f"Cleaned up {len(completed_tasks)} completed tasks")
                
        except Exception as e:
            LOGGER.writeLog(f"Error during task cleanup: {e}")


    async def get_task_stats(self):
        """Get current task statistics"""
        try:
            active_count = len(self.active_tasks)
            
            # Count tasks by status
            pending_count = 0
            running_count = 0
            
            for task_id in list(self.active_tasks.keys())[:10]:  # Check only first 10 to avoid performance issues
                try:
                    result = AsyncResult(task_id)
                    if result.state == 'PENDING':
                        pending_count += 1
                    elif result.state == 'STARTED':
                        running_count += 1
                except:
                    pass
            
            return {
                'active_tasks': active_count,
                'pending_tasks': pending_count,
                'running_tasks': running_count,
                'tasks_queued': self.stats['tasks_queued'],
                'tasks_completed': self.stats['tasks_completed'],
                'tasks_failed': self.stats['tasks_failed']
            }
        except Exception as e:
            LOGGER.writeLog(f"Error getting task stats: {e}")
            return {}


    async def scrape_historical_messages(self, limit_per_channel=100):
        """Scrape historical messages from configured channels"""
        try:
            if not self.telegram_scraper:
                LOGGER.writeLog("Telegram scraper not initialized")
                return False

            channels = self.config.get('TELEGRAM_CONFIG', {}).get('CHANNELS_TO_MONITOR', [])
            if not channels:
                LOGGER.writeLog("No channels configured for monitoring")
                return False

            LOGGER.writeLog(f"Starting historical scraping of {len(channels)} channels")

            for channel in channels:
                try:
                    LOGGER.writeLog(f"Scraping historical messages from {channel}")
                    messages = await self.telegram_scraper.get_channel_messages(channel, limit_per_channel)
                    
                    LOGGER.writeLog(f"Retrieved {len(messages)} messages from {channel}")
                    
                    # Process each message (will be queued to Celery)
                    for message_data in messages:
                        await self.handle_new_message(message_data)
                        
                        # Add small delay to avoid overwhelming Celery queue
                        await asyncio.sleep(0.05)  # Reduced delay since we're just queuing
                    
                except Exception as e:
                    LOGGER.writeLog(f"Error scraping channel {channel}: {e}")
                    continue

            LOGGER.writeLog("Historical scraping completed")
            return True

        except Exception as e:
            LOGGER.writeLog(f"Error in historical scraping: {e}")
            return False


    async def start_monitoring(self):
        """Start real-time monitoring of Telegram channels"""
        try:
            if not self.telegram_scraper:
                LOGGER.writeLog("Telegram scraper not initialized")
                return False

            channels = self.config.get('TELEGRAM_CONFIG', {}).get('CHANNELS_TO_MONITOR', [])
            if not channels:
                LOGGER.writeLog("No channels configured for monitoring")
                return False

            self.running = True
            self.stats['start_time'] = datetime.now()
            
            # Send startup notification
            if self.teams_notifier:
                self.teams_notifier.send_system_alert(
                    "INFO",
                    f"Telegram AI Scraper started monitoring {len(channels)} channels",
                    {"Channels": ", ".join(channels)}
                )

            LOGGER.writeLog(f"Starting real-time monitoring of {len(channels)} channels")
            
            # Start monitoring (this will run indefinitely)
            await self.telegram_scraper.start_monitoring(channels)

        except Exception as e:
            LOGGER.writeLog(f"Error in monitoring: {e}")
            
            # Send critical exception to admin
            try:
                from src.integrations.teams_utils import send_critical_exception
                send_critical_exception(
                    "MonitoringError",
                    str(e),
                    "TelegramAIScraper.start_monitoring",
                    additional_context={"channels_count": len(channels) if 'channels' in locals() else 0}
                )
            except Exception as admin_error:
                LOGGER.writeLog(f"Failed to send monitoring error to admin: {admin_error}")
            
            return False


    async def stop(self):
        """Stop the scraper gracefully"""
        try:
            LOGGER.writeLog("Stopping Telegram AI Scraper...")
            self.running = False

            # Send shutdown notification
            if self.teams_notifier:
                runtime = datetime.now() - self.stats['start_time'] if self.stats['start_time'] else timedelta(0)
                task_stats = await self.get_task_stats()
                self.teams_notifier.send_system_alert(
                    "INFO",
                    "Telegram AI Scraper shutting down",
                    {
                        "Total Messages Received": self.stats['total_messages'],
                        "Tasks Queued": self.stats['tasks_queued'],
                        "Tasks Completed": self.stats['tasks_completed'],
                        "Tasks Failed": self.stats['tasks_failed'],
                        "Active Tasks": task_stats.get('active_tasks', 0),
                        "Errors": self.stats['errors'],
                        "Runtime": str(runtime)
                    }
                )
            
            # Send admin shutdown notification
            try:
                from src.integrations.teams_utils import send_system_shutdown
                cleanup_performed = True
                if self.sharepoint_processor:
                    self.sharepoint_processor.closeExcelSession()
                
                send_system_shutdown(
                    reason="Graceful shutdown requested",
                    cleanup_performed=cleanup_performed
                )
            except Exception as admin_error:
                LOGGER.writeLog(f"Failed to send shutdown notification to admin: {admin_error}")

            # Close SharePoint session
            if self.sharepoint_processor:
                self.sharepoint_processor.closeExcelSession()

            # Stop Telegram client
            if self.telegram_scraper:
                await self.telegram_scraper.stop_client()

            LOGGER.writeLog("Telegram AI Scraper stopped successfully")

        except Exception as e:
            LOGGER.writeLog(f"Error during shutdown: {e}")
            
            # Send critical exception to admin
            try:
                from src.integrations.teams_utils import send_critical_exception
                send_critical_exception(
                    "ShutdownError",
                    str(e),
                    "TelegramAIScraper.stop"
                )
            except Exception as admin_error:
                LOGGER.writeLog(f"Failed to send shutdown error to admin: {admin_error}")


    def get_stats(self):
        """Get current statistics"""
        return self.stats.copy()



async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Telegram AI Scraper')
    parser.add_argument('--config', default='config.json', help='Configuration file path')
    parser.add_argument('--mode', choices=['monitor', 'historical', 'test', 'test-full'], default='monitor',
                       help='Operation mode: monitor (real-time), historical (scrape past messages), test (API connections only), test-full (comprehensive tests)')
    parser.add_argument('--limit', type=int, default=100, help='Limit for historical scraping per channel')
    
    args = parser.parse_args()

    print(f"Starting Telegram AI Scraper in {args.mode} mode...")
    LOGGER.writeLog(f"Starting in {args.mode} mode with config: {args.config}")

    # Create scraper instance
    print("Creating scraper instance...")
    scraper = TelegramAIScraper(args.config)
    print("Scraper instance created successfully.")
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        LOGGER.writeLog(f"Received signal {signum}, initiating shutdown...")
        asyncio.create_task(scraper.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Initialize components
        print("Initializing components...")
        LOGGER.writeLog("Initializing Telegram AI Scraper...")
        success = await scraper.initialize_components(test_mode=(args.mode == 'test'))
        
        if not success:
            print("Failed to initialize components")
            LOGGER.writeLog("Failed to initialize components, exiting")
            sys.exit(1)
        
        print("Components initialized successfully")

        # Execute based on mode
        if args.mode == 'test-full':
            print("Running comprehensive system tests...")
            LOGGER.writeLog("Running comprehensive system tests...")
            
            # Run the comprehensive test suite
            import subprocess
            result = subprocess.run([
                sys.executable, 'scripts/run_tests.py'
            ], cwd=scraper.config_path.parent)
            
            sys.exit(result.returncode)
            
        elif args.mode == 'test':
            print("Running API connection tests...")
            LOGGER.writeLog("Testing API connections...")
            
            # Session safety check for Telegram tests
            safety = SessionSafetyManager()
            try:
                safety.check_session_safety("main_test_mode")
                print("✅ Session safety check passed for test mode")
                safety.record_session_access("main_test_mode")
            except SessionSafetyError as e:
                print("🚫 SESSION SAFETY WARNING for test mode:")
                print(str(e))
                print("⚠️  Skipping Telegram tests to prevent session invalidation")
                scraper.telegram_scraper = None  # Disable Telegram tests
            
            # Test Teams connection
            if scraper.teams_notifier:
                print("Testing Teams connection...")
                teams_test = scraper.teams_notifier.test_connection()
                print(f"Teams connection test: {'SUCCESS' if teams_test else 'FAILED'}")
                LOGGER.writeLog(f"Teams connection test: {'SUCCESS' if teams_test else 'FAILED'}")
            else:
                print("Teams notifier not configured, skipping test")
            
            # Test Admin Teams connection
            try:
                from src.integrations.teams_utils import get_admin_notifier
                admin_notifier = get_admin_notifier()
                if admin_notifier:
                    print("Testing Admin Teams connection...")
                    admin_test = admin_notifier.test_admin_connection()
                    print(f"Admin Teams connection test: {'SUCCESS' if admin_test else 'FAILED'}")
                    LOGGER.writeLog(f"Admin Teams connection test: {'SUCCESS' if admin_test else 'FAILED'}")
                else:
                    print("Admin Teams notifier not configured, skipping test")
            except Exception as e:
                print(f"Error testing admin Teams connection: {e}")
                LOGGER.writeLog(f"Error testing admin Teams connection: {e}")
            
            # Test Telegram connection
            print("Testing Telegram connection...")
            if scraper.telegram_scraper:
                # Get channels from all countries
                all_channels = []
                countries = scraper.config.get('COUNTRIES', {})
                for country_code, country_info in countries.items():
                    channels = country_info.get('channels', [])
                    all_channels.extend(channels[:1])  # Take first channel from each country
                    
                if all_channels:
                    for channel in all_channels[:1]:  # Test first channel only
                        print(f"Testing channel: {channel}")
                        info = await scraper.telegram_scraper.get_channel_info(channel)
                        if info:
                            print(f"Telegram connection test for {channel}: SUCCESS")
                            print(f"Channel info: {info['title']} ({info['participants_count']} members)")
                            LOGGER.writeLog(f"Telegram connection test for {channel}: SUCCESS")
                            LOGGER.writeLog(f"Channel info: {info['title']} ({info['participants_count']} members)")
                        else:
                            print(f"Telegram connection test for {channel}: FAILED")
                            LOGGER.writeLog(f"Telegram connection test for {channel}: FAILED")
                else:
                    print("No channels configured for testing")
            else:
                print("Telegram client not initialized - skipping Telegram tests")
            
            print("Connection tests completed")
            LOGGER.writeLog("Connection tests completed")
            
            # Clean up session safety record
            try:
                safety.cleanup_session_access()
            except:
                pass
            
        elif args.mode == 'historical':
            # Session safety check for historical mode
            safety = SessionSafetyManager()
            try:
                safety.check_session_safety("main_historical_mode")
                print("✅ Session safety check passed for historical mode")
                safety.record_session_access("main_historical_mode")
                
                LOGGER.writeLog(f"Starting historical scraping (limit: {args.limit} per channel)...")
                await scraper.scrape_historical_messages(args.limit)
                
                # Clean up session safety record
                safety.cleanup_session_access()
            except SessionSafetyError as e:
                print("🚫 SESSION SAFETY ERROR for historical mode:")
                print(str(e))
                print("❌ Cannot run historical scraping - session conflict detected")
                LOGGER.writeLog("Historical scraping aborted due to session safety check")
            
        else:  # monitor mode
            # Session safety check for monitor mode
            safety = SessionSafetyManager()
            try:
                safety.check_session_safety("main_monitor_mode")
                print("✅ Session safety check passed for monitor mode")
                safety.record_session_access("main_monitor_mode")
                
                LOGGER.writeLog("Starting real-time monitoring...")
                await scraper.start_monitoring()
                
                # Clean up session safety record
                safety.cleanup_session_access()
            except SessionSafetyError as e:
                print("🚫 SESSION SAFETY ERROR for monitor mode:")
                print(str(e))
                print("❌ Cannot start monitoring - session conflict detected")
                LOGGER.writeLog("Monitoring aborted due to session safety check")

    except KeyboardInterrupt:
        LOGGER.writeLog("Received keyboard interrupt")
    except Exception as e:
        LOGGER.writeLog(f"Unexpected error in main: {e}")
    finally:
        await scraper.stop()


if __name__ == "__main__":
    # Ensure required directories exist (relative to project root)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.makedirs(os.path.join(project_root, "logs"), exist_ok=True)
    os.makedirs(os.path.join(project_root, "data"), exist_ok=True)
    
    # Run the main function
    asyncio.run(main())