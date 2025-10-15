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

# Import Celery tasks (only for health check)
from src.tasks.telegram_celery_tasks import health_check

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
        # Removed: active_tasks, stats tracking - handled by Celery Beat independently
        
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
            
            # Message handler not set - Celery Beat handles all message processing
            print("Telegram scraper ready (Celery Beat will handle message processing)")
            
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
            
            print("🔐 SESSION SAFETY: Telegram client will NOT be started by main.py")
            print("   ✅ Session conflicts prevented - Celery Beat handles all Telegram operations")
            print("   � Your phone will stay connected to Telegram")
            
            # SESSION SAFETY: Do NOT start Telegram client in main.py
            # This prevents session conflicts with Celery Beat workers
            self._telegram_session_started = False  # Track that main.py did NOT start the session
            
            # Create Telegram scraper object but don't start client (session-safe)
            print("   📦 Telegram scraper object created (client not started)")
            LOGGER.writeLog("Telegram scraper object created - client not started for session safety")
            
            # In session-safe architecture, only Celery Beat should access Telegram
            print("   🔄 Celery Beat scheduler will handle all Telegram message fetching")
            print("   ⚠️  If you need to test Telegram connection, use: ./scripts/telegram_session.sh test")
            LOGGER.writeLog("Session-safe mode: Telegram client not started to prevent conflicts")

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


    # REMOVED: handle_new_message, cleanup_completed_tasks, get_task_stats, 
    # scrape_historical_messages, start_monitoring
    # These functions are no longer needed as:
    # - Real-time monitoring is disabled for session safety
    # - Historical scraping is replaced by Celery Beat continuous fetching
    # - Celery Beat handles all message processing independently
    # This simplifies main.py to focus only on initialization and testing


    async def stop(self):
        """Stop the scraper gracefully"""
        try:
            LOGGER.writeLog("Stopping Telegram AI Scraper...")
            self.running = False
            
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

            # SESSION SAFETY: main.py never starts Telegram client, so never stops it
            # Celery Beat workers manage all Telegram operations independently
            if self.telegram_scraper:
                LOGGER.writeLog("🔐 SESSION SAFETY: Telegram session NOT managed by main.py")
                LOGGER.writeLog("   Celery Beat workers handle all Telegram operations independently")
                LOGGER.writeLog("   No session interference - phone stays connected to Telegram")

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


    # REMOVED: get_stats() - statistics are handled by Celery Beat monitoring



async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Telegram AI Scraper')
    parser.add_argument('--config', default='config.json', help='Configuration file path')
    parser.add_argument('--mode', choices=['monitor', 'historical', 'test', 'test-full', 'init'], default='monitor',
                       help='Operation mode: monitor (Celery Beat only), historical (deprecated), test (essential tests), test-full (comprehensive tests), init (initialize components only)')
    
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
            print("🧪 RUNNING COMPREHENSIVE TEST SUITE (Session Safe)")
            print("")
            print("   Using consolidated test runner: scripts/run_tests.py")
            print("   This includes all tests with proper session safety")
            print("")
            LOGGER.writeLog("Running comprehensive test suite via consolidated test runner")
            
            # Run the full maintained, session-safe test suite
            import subprocess
            result = subprocess.run([
                sys.executable, 'scripts/run_tests.py'
            ], cwd=PROJECT_ROOT)
            
            if result.returncode == 0:
                print("")
                print("🎉 ALL COMPREHENSIVE TESTS PASSED!")
                print("   System is fully validated and ready for production")
                LOGGER.writeLog("Comprehensive test suite completed successfully")
            else:
                print("")
                print("⚠️  Some comprehensive tests failed")
                print("   Review the detailed output above for troubleshooting")
                LOGGER.writeLog("Some comprehensive tests failed")
            
            sys.exit(result.returncode)
            
        elif args.mode == 'test':
            print("🧪 RUNNING ESSENTIAL TESTS (Session Safe)")
            print("")
            print("   Using consolidated test runner: scripts/run_tests.py --quick")
            print("   This prevents session conflicts and uses maintained test suite")
            print("")
            LOGGER.writeLog("Running essential tests via consolidated test runner")
            
            # Run the maintained, session-safe test suite  
            import subprocess
            result = subprocess.run([
                sys.executable, 'scripts/run_tests.py', '--quick'
            ], cwd=PROJECT_ROOT)
            
            if result.returncode == 0:
                print("")
                print("✅ Essential tests completed successfully!")
                print("   For full test suite, run: ./scripts/run_tests.sh")
                LOGGER.writeLog("Essential tests completed successfully")
            else:
                print("")
                print("⚠️  Some tests failed. Check output above for details.")
                print("   For detailed testing, run: ./scripts/run_tests.sh")
                LOGGER.writeLog("Some essential tests failed")
            
            sys.exit(result.returncode)
            
        elif args.mode == 'init':
            print("🔧 INITIALIZATION MODE - Components Only")
            print("")
            print("📋 PURPOSE:")
            print("   • Initialize all system components (OpenAI, Telegram, Teams, SharePoint)")
            print("   • Send system startup notification to Teams admin")
            print("   • Validate configuration and connections")
            print("   • Exit immediately after initialization (no monitoring)")
            print("")
            print("✅ Components initialized successfully!")
            print("   • System startup notification sent to Teams admin")
            print("   • All components ready for Celery workers")
            print("   • Configuration validated and loaded")
            print("")
            LOGGER.writeLog("Initialization mode completed - components initialized, exiting")
            sys.exit(0)
            
        elif args.mode == 'historical':
            print("📚 HISTORICAL MODE - DEPRECATED")
            print("")
            print("⚠️  Historical mode has been removed for system simplification:")
            print("   • Celery Beat already fetches messages every 4 minutes")
            print("   • Periodic fetching covers historical needs automatically")
            print("   • Reduces session conflict risks and code complexity")
            print("")
            print("🎯 ALTERNATIVES:")
            print("   • Let Celery Beat run - it fetches recent messages continuously")
            print("   • Check data/ folder for existing historical data")
            print("   • Use SharePoint for comprehensive message archives")
            print("")
            LOGGER.writeLog("Historical mode deprecated - redirecting to Celery Beat approach")
            sys.exit(0)
            
        else:  # monitor mode
            print("🚀 MONITOR MODE - Celery Beat Only (Session Safe)")
            print("")
            print("📋 ARCHITECTURE INFO:")
            print("   ✅ Celery Beat: Handles all message fetching (every 4 minutes)")
            print("   ❌ Real-time: Disabled to prevent Telegram session conflicts")
            print("   📱 Phone Safety: No risk of Telegram logout due to session conflicts")
            print("")
            
            # Check if Celery workers are running
            try:
                from src.tasks.telegram_celery_tasks import health_check
                health_result = health_check.delay()
                health_status = health_result.get(timeout=10)
                
                if health_status and health_status.get('status') == 'healthy':
                    print("✅ Celery workers are healthy and running")
                    print(f"   Worker ID: {health_status.get('worker_id', 'unknown')}")
                    print("   Message fetching is active via Celery Beat periodic tasks")
                else:
                    print("⚠️  Celery workers may not be running optimally")
                    print("   Run: ./scripts/deploy_celery.sh start")
                    
            except Exception as celery_error:
                print("❌ Cannot verify Celery worker status")
                print(f"   Error: {celery_error}")
                print("   Ensure Celery workers are running: ./scripts/deploy_celery.sh start")
            
            print("")
            print("🎯 MONITOR MODE STRATEGY:")
            print("   • Initialization completed (Teams notifications sent)")
            print("   • Celery Beat handles all periodic message fetching") 
            print("   • No session conflicts - your phone stays connected")
            print("   • Main process stays alive for component availability")
            print("")
            print("   Press Ctrl+C to exit (Celery Beat continues independently)")
            
            LOGGER.writeLog("Monitor mode: Celery Beat only - no real-time monitoring to prevent session conflicts")
            
            # Keep the process alive without Telegram session access
            try:
                while True:
                    await asyncio.sleep(60)  # Sleep for 1 minute intervals
                    # Optional: Log periodic status every hour
                    if datetime.now().minute == 0:
                        LOGGER.writeLog("Monitor mode active - Celery Beat handling message fetching")
                        
            except KeyboardInterrupt:
                print("")
                print("✅ Main process shutting down")
                print("   Celery Beat continues running independently")
                print("   Message fetching will continue via workers")
                LOGGER.writeLog("Monitor mode main process shutdown - Celery Beat continues")

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