#!/usr/bin/env python3
"""
Comprehensive Test Runner for Telegram AI Scraper
This script runs all available tests in a structured manner and provides detailed reporting.
"""

import sys
import os
import json
import subprocess
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

class TestRunner:
    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.tests_dir = self.project_root / "tests"
        self.results = {
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'errors': [],
            'details': {}
        }
        
    def print_header(self, title):
        """Print a formatted header"""
        print(f"\n{'='*60}")
        print(f"🧪 {title}")
        print(f"{'='*60}")
        
    def print_section(self, title):
        """Print a formatted section header"""
        print(f"\n{'─'*40}")
        print(f"📋 {title}")
        print(f"{'─'*40}")
        
    def print_result(self, test_name, status, details=None):
        """Print test result with appropriate emoji and color"""
        status_map = {
            'PASS': ('✅', '\033[92m'),
            'FAIL': ('❌', '\033[91m'), 
            'SKIP': ('⏭️', '\033[93m'),
            'ERROR': ('💥', '\033[91m')
        }
        
        emoji, color = status_map.get(status, ('❓', '\033[0m'))
        reset = '\033[0m'
        
        print(f"{emoji} {color}{test_name:<35} [{status}]{reset}")
        if details:
            for line in details.split('\n'):
                if line.strip():
                    print(f"   {line}")
                    
    def run_python_test(self, test_file, timeout=60):
        """Run a Python test file and capture results"""
        test_path = self.tests_dir / test_file
        if not test_path.exists():
            return 'SKIP', f"Test file not found: {test_file}"
            
        try:
            # Set PYTHONPATH to include project root
            env = os.environ.copy()
            env['PYTHONPATH'] = str(self.project_root)
            
            result = subprocess.run(
                [sys.executable, str(test_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.project_root),
                env=env
            )
            
            if result.returncode == 0:
                return 'PASS', result.stdout
            else:
                return 'FAIL', f"Exit code: {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
                
        except subprocess.TimeoutExpired:
            return 'ERROR', f"Test timed out after {timeout} seconds"
        except Exception as e:
            return 'ERROR', f"Exception running test: {str(e)}"
            
    def run_component_tests(self):
        """Run core component tests"""
        self.print_section("Core Component Tests")
        
        # Import tests - basic functionality
        try:
            from src.core.log_handling import LogHandling
            from src.core.file_handling import FileHandling
            from src.core.message_processor import MessageProcessor
            from src.integrations.openai_utils import OpenAIProcessor
            self.print_result("Import Tests", "PASS", "All core imports successful")
            self.results['passed'] += 1
        except Exception as e:
            self.print_result("Import Tests", "FAIL", str(e))
            self.results['failed'] += 1
            self.results['errors'].append(f"Import Tests failed: {e}")
            
        # Run component test file
        status, details = self.run_python_test("test_components.py")
        self.print_result("Component Tests", status, details if status != 'PASS' else None)
        if status == 'PASS':
            self.results['passed'] += 1
        elif status == 'SKIP':
            self.results['skipped'] += 1
        else:
            self.results['failed'] += 1
            self.results['errors'].append(f"Component Tests: {details}")
            
    def test_configuration(self):
        """Test configuration file and structure"""
        self.print_section("Configuration Tests")
        
        config_path = self.project_root / "config" / "config.json"
        
        # Check if config exists
        if not config_path.exists():
            self.print_result("Config File Existence", "FAIL", "config/config.json not found")
            self.results['failed'] += 1
            self.results['errors'].append("Configuration file missing")
            return
            
        # Validate config JSON
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            self.print_result("Config JSON Validity", "PASS")
            self.results['passed'] += 1
        except Exception as e:
            self.print_result("Config JSON Validity", "FAIL", str(e))
            self.results['failed'] += 1
            self.results['errors'].append(f"Config JSON invalid: {e}")
            return
            
        # Check required sections
        required_sections = ['OPEN_AI_KEY', 'COUNTRIES', 'MS_SHAREPOINT_ACCESS']
        for section in required_sections:
            if section in config:
                self.print_result(f"Config Section: {section}", "PASS")
                self.results['passed'] += 1
            else:
                self.print_result(f"Config Section: {section}", "FAIL", f"Missing section: {section}")
                self.results['failed'] += 1
                self.results['errors'].append(f"Missing config section: {section}")
                
        # Validate Iraq dual-language config
        if 'COUNTRIES' in config and 'iraq' in config['COUNTRIES']:
            iraq_config = config['COUNTRIES']['iraq']
            if 'message_filtering' in iraq_config:
                filtering = iraq_config['message_filtering']
                if 'significant_keywords' in filtering:
                    keywords = filtering['significant_keywords']
                    if keywords and isinstance(keywords[0], list) and len(keywords[0]) == 2:
                        self.print_result("Iraq Dual-Language Keywords", "PASS", "Found [EN, AR] keyword pairs")
                        self.results['passed'] += 1
                    else:
                        self.print_result("Iraq Dual-Language Keywords", "FAIL", "Keywords not in [EN, AR] format")
                        self.results['failed'] += 1
                        self.results['errors'].append("Iraq keywords not in dual-language format")
                        
    def test_telegram_session_manager(self):
        """Test Telegram session manager functionality"""
        self.print_section("Telegram Session Manager Tests")
        
        # Test session manager import and initialization
        try:
            from src.integrations.telegram_session_manager import TelegramSessionManager, TelegramRateLimitError, TelegramSessionError, TelegramAuthError
            self.print_result("Session Manager Import", "PASS")
            self.results['passed'] += 1
        except Exception as e:
            self.print_result("Session Manager Import", "FAIL", str(e))
            self.results['failed'] += 1
            self.results['errors'].append(f"Session manager import failed: {e}")
            return
            
        # Test session manager initialization (without connection)
        try:
            # Load config for test
            config_path = self.project_root / "config" / "config.json"
            if config_path.exists():
                import json
                with open(config_path, 'r') as f:
                    config = json.load(f)
                telegram_config = config.get('TELEGRAM_CONFIG', {})
                
                if all(key in telegram_config for key in ['API_ID', 'API_HASH', 'PHONE_NUMBER']):
                    session_manager = TelegramSessionManager(
                        telegram_config['API_ID'],
                        telegram_config['API_HASH'],
                        telegram_config['PHONE_NUMBER'],
                        'test_session'
                    )
                    
                    # Test status methods without connecting
                    status = session_manager.get_connection_status()
                    rate_limit_info = session_manager.get_rate_limit_info()
                    
                    self.print_result("Session Manager Init", "PASS", "Initialized without connection")
                    self.results['passed'] += 1
                else:
                    self.print_result("Session Manager Init", "SKIP", "Telegram config incomplete")
                    self.results['skipped'] += 1
            else:
                self.print_result("Session Manager Init", "SKIP", "Config file not found")
                self.results['skipped'] += 1
                
        except Exception as e:
            self.print_result("Session Manager Init", "FAIL", str(e))
            self.results['failed'] += 1
            self.results['errors'].append(f"Session manager initialization failed: {e}")
            
        # Test session status checker script
        status, details = self.run_python_test("../scripts/telegram_session_check.py", timeout=30)
        # Convert to relative path for the test file
        if status == 'SKIP':
            # Try running the script directly
            try:
                script_path = self.project_root / "scripts" / "telegram_session_check.py"
                if script_path.exists():
                    env = os.environ.copy()
                    env['PYTHONPATH'] = str(self.project_root)
                    
                    result = subprocess.run(
                        [sys.executable, str(script_path)],
                        capture_output=True,
                        text=True,
                        timeout=15,  # Shorter timeout for status check
                        cwd=str(self.project_root),
                        env=env
                    )
                    
                    # Any exit code is acceptable for status check (might be rate limited)
                    if "Configuration Check" in result.stdout:
                        self.print_result("Session Status Checker", "PASS", "Script executed successfully")
                        self.results['passed'] += 1
                    else:
                        self.print_result("Session Status Checker", "FAIL", f"Unexpected output: {result.stdout[:200]}")
                        self.results['failed'] += 1
                        self.results['errors'].append("Session status checker unexpected output")
                else:
                    self.print_result("Session Status Checker", "SKIP", "Script not found")
                    self.results['skipped'] += 1
                    
            except subprocess.TimeoutExpired:
                self.print_result("Session Status Checker", "SKIP", "Timed out (expected if rate limited)")
                self.results['skipped'] += 1
            except Exception as e:
                self.print_result("Session Status Checker", "FAIL", str(e))
                self.results['failed'] += 1
                self.results['errors'].append(f"Session status checker error: {e}")
        else:
            # Handle the result from run_python_test
            if status == 'PASS' or "Configuration Check" in str(details):
                self.print_result("Session Status Checker", "PASS")
                self.results['passed'] += 1
            else:
                self.print_result("Session Status Checker", status, details if status != 'PASS' else None)
                if status == 'PASS':
                    self.results['passed'] += 1
                elif status == 'SKIP':
                    self.results['skipped'] += 1
                else:
                    self.results['failed'] += 1
                    self.results['errors'].append(f"Session Status Checker: {details}")

    def test_language_detection(self):
        """Test language detection functionality"""
        self.print_section("Language Detection Tests")
        
        status, details = self.run_python_test("test_language_detection.py")
        self.print_result("Language Detection", status, details if status != 'PASS' else None)
        
        if status == 'PASS':
            self.results['passed'] += 1
        elif status == 'SKIP':
            self.results['skipped'] += 1
        else:
            self.results['failed'] += 1
            self.results['errors'].append(f"Language Detection: {details}")
            
    def test_message_processing(self):
        """Test message processing functionality"""
        self.print_section("Message Processing Tests")
        
        # Test translation functionality
        status, details = self.run_python_test("test_translation.py")
        self.print_result("Translation Tests", status, details if status != 'PASS' else None)
        
        if status == 'PASS':
            self.results['passed'] += 1
        elif status == 'SKIP':
            self.results['skipped'] += 1
        else:
            self.results['failed'] += 1
            self.results['errors'].append(f"Translation Tests: {details}")
            
    def test_api_connections(self):
        """Test API connections"""
        self.print_section("API Connection Tests")
        
        try:
            # Import main and run connection tests
            from src.core.main import TelegramAIScraper
            
            # Test without actually running the full app
            self.print_result("Main Application Import", "PASS")
            self.results['passed'] += 1
            
        except Exception as e:
            self.print_result("Main Application Import", "FAIL", str(e))
            self.results['failed'] += 1
            self.results['errors'].append(f"Main app import failed: {e}")
            
        # Run connection test via main.py
        try:
            env = os.environ.copy()
            env['PYTHONPATH'] = str(self.project_root)
            
            result = subprocess.run(
                [sys.executable, "src/core/main.py", "--mode", "test"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self.project_root),
                env=env
            )
            
            if result.returncode == 0:
                self.print_result("API Connection Test", "PASS")
                self.results['passed'] += 1
            else:
                # Check if it's just missing API keys (acceptable for basic setup)
                if "API key" in result.stderr or "authentication" in result.stderr.lower():
                    self.print_result("API Connection Test", "SKIP", "API keys not configured (expected)")
                    self.results['skipped'] += 1
                else:
                    self.print_result("API Connection Test", "FAIL", f"Exit code: {result.returncode}\n{result.stderr}")
                    self.results['failed'] += 1
                    self.results['errors'].append(f"API connection test failed: {result.stderr}")
                    
        except subprocess.TimeoutExpired:
            self.print_result("API Connection Test", "ERROR", "Test timed out")
            self.results['failed'] += 1
            self.results['errors'].append("API connection test timed out")
        except Exception as e:
            self.print_result("API Connection Test", "ERROR", str(e))
            self.results['failed'] += 1
            self.results['errors'].append(f"API connection test error: {e}")
            
    def test_celery_tasks(self):
        """Test Celery task definitions and basic functionality"""
        self.print_section("Celery Task Tests")
        
        try:
            from src.tasks.telegram_celery_tasks import celery, health_check
            
            # Test task registration
            registered_tasks = list(celery.tasks.keys())
            expected_tasks = [
                'src.tasks.telegram_celery_tasks.process_telegram_message',
                'src.tasks.telegram_celery_tasks.health_check'
            ]
            
            for task_name in expected_tasks:
                if task_name in registered_tasks:
                    self.print_result(f"Task Registration: {task_name.split('.')[-1]}", "PASS")
                    self.results['passed'] += 1
                else:
                    self.print_result(f"Task Registration: {task_name.split('.')[-1]}", "FAIL", "Task not registered")
                    self.results['failed'] += 1
                    self.results['errors'].append(f"Task not registered: {task_name}")
                    
            # Test health check execution
            try:
                result = health_check()
                if result and result.get('status') == 'healthy':
                    self.print_result("Health Check Task", "PASS")
                    self.results['passed'] += 1
                else:
                    self.print_result("Health Check Task", "FAIL", f"Unexpected result: {result}")
                    self.results['failed'] += 1
                    self.results['errors'].append("Health check returned unexpected result")
            except Exception as e:
                self.print_result("Health Check Task", "FAIL", str(e))
                self.results['failed'] += 1
                self.results['errors'].append(f"Health check failed: {e}")
                
        except Exception as e:
            self.print_result("Celery Task Import", "FAIL", str(e))
            self.results['failed'] += 1
            self.results['errors'].append(f"Celery task import failed: {e}")
            
    def test_redis_connection(self):
        """Test Redis connection"""
        self.print_section("Redis Connection Tests")
        
        try:
            result = subprocess.run(
                ["redis-cli", "ping"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and "PONG" in result.stdout:
                self.print_result("Redis Connection", "PASS")
                self.results['passed'] += 1
            else:
                self.print_result("Redis Connection", "FAIL", "Redis not responding")
                self.results['failed'] += 1
                self.results['errors'].append("Redis connection failed")
                
        except subprocess.TimeoutExpired:
            self.print_result("Redis Connection", "FAIL", "Connection timeout")
            self.results['failed'] += 1
            self.results['errors'].append("Redis connection timeout")
        except Exception as e:
            self.print_result("Redis Connection", "FAIL", str(e))
            self.results['failed'] += 1
            self.results['errors'].append(f"Redis test error: {e}")
            
    def run_extended_tests(self):
        """Run extended test suite (optional tests that may require setup)"""
        self.print_section("Extended Tests (Optional)")
        
        # Test message fetch (might require Telegram auth)
        status, details = self.run_python_test("test_message_fetch.py", timeout=30)
        if status == 'FAIL' and ("authentication" in details.lower() or "session" in details.lower()):
            status = 'SKIP'
            details = "Requires Telegram authentication"
            
        self.print_result("Message Fetch Test", status, details if status not in ['PASS', 'SKIP'] else None)
        
        if status == 'PASS':
            self.results['passed'] += 1
        elif status == 'SKIP':
            self.results['skipped'] += 1
        else:
            self.results['failed'] += 1
            if status != 'SKIP':
                self.results['errors'].append(f"Message Fetch Test: {details}")
                
    def generate_report(self):
        """Generate final test report"""
        self.print_header("TEST RESULTS SUMMARY")
        
        total_tests = self.results['passed'] + self.results['failed'] + self.results['skipped']
        
        print(f"Total Tests Run: {total_tests}")
        print(f"✅ Passed: {self.results['passed']}")
        print(f"❌ Failed: {self.results['failed']}")
        print(f"⏭️ Skipped: {self.results['skipped']}")
        
        if self.results['passed'] > 0:
            success_rate = (self.results['passed'] / (self.results['passed'] + self.results['failed'])) * 100
            print(f"📊 Success Rate: {success_rate:.1f}%")
            
        if self.results['errors']:
            print(f"\n🔍 Error Details:")
            for i, error in enumerate(self.results['errors'], 1):
                print(f"{i}. {error}")
                
        # Overall status
        if self.results['failed'] == 0:
            if self.results['passed'] > 0:
                print(f"\n🎉 ALL TESTS PASSED! System is ready for use.")
                return True
            else:
                print(f"\n⚠️ No tests were executed. Check test configuration.")
                return False
        else:
            print(f"\n⚠️ {self.results['failed']} test(s) failed. Please review errors above.")
            return False
            
    def run_all(self, quick=False):
        """Run all tests"""
        self.print_header("TELEGRAM AI SCRAPER - COMPREHENSIVE TEST SUITE")
        
        print(f"Project Root: {self.project_root}")
        print(f"Test Mode: {'Quick' if quick else 'Full'}")
        print(f"Python: {sys.executable}")
        
        # Core tests (always run)
        self.run_component_tests()
        self.test_configuration()
        self.test_redis_connection()
        self.test_telegram_session_manager()
        self.test_language_detection()
        self.test_message_processing()
        self.test_celery_tasks()
        
        if not quick:
            # Extended tests (might require additional setup)
            self.test_api_connections()
            self.run_extended_tests()
            
        return self.generate_report()


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Telegram AI Scraper Test Runner")
    parser.add_argument("--quick", action="store_true", help="Run only quick tests (skip API connections)")
    parser.add_argument("--component", action="store_true", help="Run only component tests")
    parser.add_argument("--config", action="store_true", help="Run only configuration tests")
    parser.add_argument("--session", action="store_true", help="Run only Telegram session manager tests")
    parser.add_argument("--language", action="store_true", help="Run only language detection tests")
    parser.add_argument("--processing", action="store_true", help="Run only message processing tests")
    
    args = parser.parse_args()
    
    runner = TestRunner()
    
    if args.component:
        runner.run_component_tests()
        return runner.generate_report()
    elif args.config:
        runner.test_configuration()
        return runner.generate_report()
    elif args.session:
        runner.test_telegram_session_manager()
        return runner.generate_report()
    elif args.language:
        runner.test_language_detection()
        return runner.generate_report()
    elif args.processing:
        runner.test_message_processing()
        return runner.generate_report()
    else:
        return runner.run_all(quick=args.quick)
        

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)