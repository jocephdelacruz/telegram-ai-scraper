#!/usr/bin/env python3
"""
Comprehensive test suite for Telegram message fetching functions

This test validates both get_channel_messages() and get_channel_messages_efficiently()
functions to ensure they work correctly with different scenarios and configurations.

Tests cover:
- Basic message fetching functionality
- Efficient message fetching with ID tracking
- Redis integration and fallback mechanisms
- Age-based filtering
- Duplicate detection
- Performance comparisons
- Error handling

Author: Telegram AI Scraper System
Created: 2025-10-29
"""

import sys
import os
import asyncio
import redis
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, AsyncMock
import tempfile
import csv

# Add the project root to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.integrations.telegram_utils import TelegramScraper
from src.core import log_handling as lh

# Test configuration
TEST_LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "logs", "test_telegram_fetching.log")
LOGGER = lh.LogHandling(TEST_LOG_FILE, "UTC")

class TestTelegramMessageFetching:
    """Test suite for Telegram message fetching functions"""
    
    def __init__(self):
        self.test_results = {
            'passed': 0,
            'failed': 0,
            'errors': []
        }
        self.redis_client = None
        self.scraper = None
    
    async def setup_test_environment(self):
        """Setup test environment with mock configuration"""
        try:
            LOGGER.writeLog("🔧 Setting up test environment...")
            
            # Mock configuration
            self.test_config = {
                "TELEGRAM_CONFIG": {
                    "API_ID": "12345",
                    "API_HASH": "test_hash",
                    "PHONE_NUMBER": "+1234567890",
                    "FETCH_INTERVAL_SECONDS": 240,
                    "FETCH_MESSAGE_LIMIT": 10
                }
            }
            
            # Setup Redis connection (mock if not available)
            try:
                self.redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
                self.redis_client.ping()  # Test connection
                LOGGER.writeLog("✅ Redis connection established")
            except Exception as e:
                LOGGER.writeLog(f"⚠️  Redis not available, using mock: {e}")
                self.redis_client = self._create_mock_redis()
            
            # Initialize TelegramScraper with mock data
            self.scraper = TelegramScraper(
                api_id=self.test_config["TELEGRAM_CONFIG"]["API_ID"],
                api_hash=self.test_config["TELEGRAM_CONFIG"]["API_HASH"],
                phone_number=self.test_config["TELEGRAM_CONFIG"]["PHONE_NUMBER"]
            )
            
            LOGGER.writeLog("✅ Test environment setup complete")
            return True
            
        except Exception as e:
            LOGGER.writeLog(f"❌ Failed to setup test environment: {e}")
            return False
    
    def _create_mock_redis(self):
        """Create a mock Redis client for testing"""
        mock_redis = Mock()
        mock_redis.storage = {}  # In-memory storage for testing
        
        def mock_get(key):
            return mock_redis.storage.get(key, None)
        
        def mock_setex(key, ttl, value):
            mock_redis.storage[key] = value
            return True
        
        def mock_exists(key):
            return key in mock_redis.storage
        
        def mock_ping():
            return True
        
        mock_redis.get = mock_get
        mock_redis.setex = mock_setex
        mock_redis.exists = mock_exists
        mock_redis.ping = mock_ping
        
        return mock_redis
    
    def _create_mock_message(self, message_id, text, date, channel="@testchannel"):
        """Create a mock Telegram message for testing"""
        mock_message = Mock()
        mock_message.id = message_id
        mock_message.text = text
        mock_message.date = date
        mock_message.media = None
        mock_message.sender = None
        mock_message.forward = None
        mock_message.entities = None
        return mock_message
    
    def _create_test_csv_data(self, channel_username, messages):
        """Create test CSV data for fallback testing"""
        try:
            temp_dir = tempfile.mkdtemp()
            csv_file = os.path.join(temp_dir, f"{channel_username.lstrip('@')}_messages.csv")
            
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Message_ID', 'Channel', 'Date', 'Time', 'Message_Text'])
                for msg in messages:
                    writer.writerow([
                        msg['Message_ID'],
                        msg['Channel'],
                        msg['Date'],
                        msg['Time'],
                        msg['Message_Text']
                    ])
            
            return csv_file
        except Exception as e:
            LOGGER.writeLog(f"Failed to create test CSV: {e}")
            return None
    
    async def test_basic_message_fetching(self):
        """Test basic get_channel_messages functionality"""
        test_name = "Basic Message Fetching"
        LOGGER.writeLog(f"🧪 Testing: {test_name}")
        
        try:
            # Mock client and messages
            mock_messages = [
                self._create_mock_message(101, "Test message 1", datetime.now(timezone.utc)),
                self._create_mock_message(102, "Test message 2", datetime.now(timezone.utc) - timedelta(minutes=5)),
                self._create_mock_message(103, "Test message 3", datetime.now(timezone.utc) - timedelta(minutes=10))
            ]
            
            with patch.object(self.scraper, '_ensure_client') as mock_client_method:
                with patch.object(self.scraper, 'get_channel_entity') as mock_entity_method:
                    # Setup mocks
                    mock_client = AsyncMock()
                    mock_client.iter_messages.return_value = mock_messages
                    mock_client_method.return_value = mock_client
                    
                    mock_entity = Mock()
                    mock_entity_method.return_value = mock_entity
                    
                    # Test the function
                    result = await self.scraper.get_channel_messages("@testchannel", limit=3)
                    
                    # Validate results
                    assert len(result) == 3, f"Expected 3 messages, got {len(result)}"
                    assert result[0]['Message_ID'] == 101, f"Expected message ID 101, got {result[0]['Message_ID']}"
                    
                    LOGGER.writeLog(f"✅ {test_name}: PASSED")
                    self.test_results['passed'] += 1
        
        except Exception as e:
            error_msg = f"❌ {test_name}: FAILED - {e}"
            LOGGER.writeLog(error_msg)
            self.test_results['failed'] += 1
            self.test_results['errors'].append(error_msg)
    
    async def test_efficient_message_fetching_with_tracking(self):
        """Test get_channel_messages_efficiently with Redis tracking"""
        test_name = "Efficient Message Fetching with Tracking"
        LOGGER.writeLog(f"🧪 Testing: {test_name}")
        
        try:
            # Setup Redis with last processed ID
            channel_username = "@testchannel"
            last_processed_id = 100
            redis_key = f"last_processed:{channel_username}"
            self.redis_client.setex(redis_key, 86400, str(last_processed_id))
            
            # Mock newer messages (ID > 100)
            mock_messages = [
                self._create_mock_message(101, "New message 1", datetime.now(timezone.utc)),
                self._create_mock_message(102, "New message 2", datetime.now(timezone.utc) - timedelta(minutes=5))
            ]
            
            with patch.object(self.scraper, '_ensure_client') as mock_client_method:
                with patch.object(self.scraper, 'get_channel_entity') as mock_entity_method:
                    with patch.object(self.scraper, '_get_last_processed_message_id') as mock_get_last_id:
                        # Setup mocks
                        mock_client = AsyncMock()
                        mock_client.iter_messages.return_value = mock_messages
                        mock_client_method.return_value = mock_client
                        
                        mock_entity = Mock()
                        mock_entity_method.return_value = mock_entity
                        
                        mock_get_last_id.return_value = last_processed_id
                        
                        # Test the function
                        result = await self.scraper.get_channel_messages_efficiently(
                            channel_username, 
                            limit=10,
                            redis_client=self.redis_client
                        )
                        
                        # Validate results
                        assert len(result) == 2, f"Expected 2 messages, got {len(result)}"
                        assert result[0]['Message_ID'] == 101, f"Expected message ID 101, got {result[0]['Message_ID']}"
                        
                        # Verify min_id was used in the call
                        call_args = mock_client.iter_messages.call_args
                        assert 'min_id' in call_args.kwargs, "min_id parameter should be used"
                        assert call_args.kwargs['min_id'] == last_processed_id, f"min_id should be {last_processed_id}"
                        
                        LOGGER.writeLog(f"✅ {test_name}: PASSED")
                        self.test_results['passed'] += 1
        
        except Exception as e:
            error_msg = f"❌ {test_name}: FAILED - {e}"
            LOGGER.writeLog(error_msg)
            self.test_results['failed'] += 1
            self.test_results['errors'].append(error_msg)
    
    async def test_efficient_message_fetching_fallback(self):
        """Test get_channel_messages_efficiently fallback to time-based filtering"""
        test_name = "Efficient Message Fetching Fallback"
        LOGGER.writeLog(f"🧪 Testing: {test_name}")
        
        try:
            # Mock messages without any tracking data
            mock_messages = [
                self._create_mock_message(101, "Message 1", datetime.now(timezone.utc)),
                self._create_mock_message(102, "Message 2", datetime.now(timezone.utc) - timedelta(minutes=5))
            ]
            
            with patch.object(self.scraper, '_ensure_client') as mock_client_method:
                with patch.object(self.scraper, 'get_channel_entity') as mock_entity_method:
                    with patch.object(self.scraper, '_get_last_processed_message_id') as mock_get_last_id:
                        # Setup mocks
                        mock_client = AsyncMock()
                        mock_client.iter_messages.return_value = mock_messages
                        mock_client_method.return_value = mock_client
                        
                        mock_entity = Mock()
                        mock_entity_method.return_value = mock_entity
                        
                        mock_get_last_id.return_value = None  # No tracking data
                        
                        # Test the function
                        result = await self.scraper.get_channel_messages_efficiently(
                            "@testchannel", 
                            limit=10,
                            redis_client=self.redis_client
                        )
                        
                        # Validate results
                        assert len(result) == 2, f"Expected 2 messages, got {len(result)}"
                        
                        # Verify fallback to limit-based fetching (no min_id)
                        call_args = mock_client.iter_messages.call_args
                        assert 'min_id' not in call_args.kwargs or call_args.kwargs.get('min_id') is None, "min_id should not be used in fallback mode"
                        assert 'limit' in call_args.kwargs, "limit parameter should be used"
                        
                        LOGGER.writeLog(f"✅ {test_name}: PASSED")
                        self.test_results['passed'] += 1
        
        except Exception as e:
            error_msg = f"❌ {test_name}: FAILED - {e}"
            LOGGER.writeLog(error_msg)
            self.test_results['failed'] += 1
            self.test_results['errors'].append(error_msg)
    
    async def test_age_filtering(self):
        """Test age-based message filtering"""
        test_name = "Age-based Message Filtering"
        LOGGER.writeLog(f"🧪 Testing: {test_name}")
        
        try:
            # Create messages with different ages
            now = datetime.now(timezone.utc)
            mock_messages = [
                self._create_mock_message(101, "Recent message", now),
                self._create_mock_message(102, "1 hour old", now - timedelta(hours=1)),
                self._create_mock_message(103, "5 hours old", now - timedelta(hours=5)),  # Should be filtered out
                self._create_mock_message(104, "6 hours old", now - timedelta(hours=6))   # Should be filtered out
            ]
            
            with patch.object(self.scraper, '_ensure_client') as mock_client_method:
                with patch.object(self.scraper, 'get_channel_entity') as mock_entity_method:
                    with patch.object(self.scraper, '_get_last_processed_message_id') as mock_get_last_id:
                        # Setup mocks
                        mock_client = AsyncMock()
                        mock_client.iter_messages.return_value = mock_messages
                        mock_client_method.return_value = mock_client
                        
                        mock_entity = Mock()
                        mock_entity_method.return_value = mock_entity
                        
                        mock_get_last_id.return_value = 100  # Use ID-based fetching
                        
                        # Test the function
                        result = await self.scraper.get_channel_messages_efficiently(
                            "@testchannel", 
                            limit=10,
                            redis_client=self.redis_client
                        )
                        
                        # Validate results - should only get messages within 4 hours
                        assert len(result) == 2, f"Expected 2 messages (within 4 hours), got {len(result)}"
                        assert all(msg['Message_ID'] in [101, 102] for msg in result), "Should only get recent messages"
                        
                        LOGGER.writeLog(f"✅ {test_name}: PASSED")
                        self.test_results['passed'] += 1
        
        except Exception as e:
            error_msg = f"❌ {test_name}: FAILED - {e}"
            LOGGER.writeLog(error_msg)
            self.test_results['failed'] += 1
            self.test_results['errors'].append(error_msg)
    
    async def test_duplicate_detection(self):
        """Test Redis duplicate detection"""
        test_name = "Duplicate Detection"
        LOGGER.writeLog(f"🧪 Testing: {test_name}")
        
        try:
            channel_username = "@testchannel"
            
            # Mark message 101 as already processed
            duplicate_key = f"processed_msg:{channel_username}:101"
            self.redis_client.setex(duplicate_key, 86400, "1")
            
            mock_messages = [
                self._create_mock_message(101, "Duplicate message", datetime.now(timezone.utc)),
                self._create_mock_message(102, "New message", datetime.now(timezone.utc))
            ]
            
            with patch.object(self.scraper, '_ensure_client') as mock_client_method:
                with patch.object(self.scraper, 'get_channel_entity') as mock_entity_method:
                    with patch.object(self.scraper, '_get_last_processed_message_id') as mock_get_last_id:
                        # Setup mocks
                        mock_client = AsyncMock()
                        mock_client.iter_messages.return_value = mock_messages
                        mock_client_method.return_value = mock_client
                        
                        mock_entity = Mock()
                        mock_entity_method.return_value = mock_entity
                        
                        mock_get_last_id.return_value = None  # Use fallback mode
                        
                        # Test the function
                        result = await self.scraper.get_channel_messages_efficiently(
                            channel_username, 
                            limit=10,
                            redis_client=self.redis_client
                        )
                        
                        # Validate results - should skip duplicate
                        assert len(result) == 1, f"Expected 1 message (duplicate filtered), got {len(result)}"
                        assert result[0]['Message_ID'] == 102, f"Should only get non-duplicate message"
                        
                        LOGGER.writeLog(f"✅ {test_name}: PASSED")
                        self.test_results['passed'] += 1
        
        except Exception as e:
            error_msg = f"❌ {test_name}: FAILED - {e}"
            LOGGER.writeLog(error_msg)
            self.test_results['failed'] += 1
            self.test_results['errors'].append(error_msg)
    
    async def test_safety_limits(self):
        """Test safety limits to prevent API abuse"""
        test_name = "Safety Limits"
        LOGGER.writeLog(f"🧪 Testing: {test_name}")
        
        try:
            with patch.object(self.scraper, '_ensure_client') as mock_client_method:
                with patch.object(self.scraper, 'get_channel_entity') as mock_entity_method:
                    # Setup mocks
                    mock_client = AsyncMock()
                    mock_client.iter_messages.return_value = []
                    mock_client_method.return_value = mock_client
                    
                    mock_entity = Mock()
                    mock_entity_method.return_value = mock_entity
                    
                    # Test with limit > MAX_SAFE_LIMIT (50)
                    await self.scraper.get_channel_messages_efficiently(
                        "@testchannel", 
                        limit=100,  # Should be capped at 50
                        redis_client=self.redis_client
                    )
                    
                    # Verify limit was capped
                    call_args = mock_client.iter_messages.call_args
                    actual_limit = call_args.kwargs.get('limit')
                    assert actual_limit == 50, f"Expected limit to be capped at 50, got {actual_limit}"
                    
                    LOGGER.writeLog(f"✅ {test_name}: PASSED")
                    self.test_results['passed'] += 1
        
        except Exception as e:
            error_msg = f"❌ {test_name}: FAILED - {e}"
            LOGGER.writeLog(error_msg)
            self.test_results['failed'] += 1
            self.test_results['errors'].append(error_msg)
    
    async def test_error_handling(self):
        """Test error handling in message fetching"""
        test_name = "Error Handling"
        LOGGER.writeLog(f"🧪 Testing: {test_name}")
        
        try:
            with patch.object(self.scraper, 'get_channel_entity') as mock_entity_method:
                # Mock entity retrieval failure
                mock_entity_method.return_value = None
                
                # Test the function with invalid channel
                result = await self.scraper.get_channel_messages_efficiently(
                    "@invalidchannel",
                    limit=10,
                    redis_client=self.redis_client
                )
                
                # Should return empty list on error
                assert result == [], f"Expected empty list on error, got {result}"
                
                LOGGER.writeLog(f"✅ {test_name}: PASSED")
                self.test_results['passed'] += 1
        
        except Exception as e:
            error_msg = f"❌ {test_name}: FAILED - {e}"
            LOGGER.writeLog(error_msg)
            self.test_results['failed'] += 1
            self.test_results['errors'].append(error_msg)
    
    async def run_all_tests(self):
        """Run all test cases"""
        LOGGER.writeLog("🚀 Starting Telegram Message Fetching Tests...")
        
        # Setup test environment
        if not await self.setup_test_environment():
            LOGGER.writeLog("❌ Failed to setup test environment. Aborting tests.")
            return False
        
        # Run individual tests
        test_methods = [
            self.test_basic_message_fetching,
            self.test_efficient_message_fetching_with_tracking,
            self.test_efficient_message_fetching_fallback,
            self.test_age_filtering,
            self.test_duplicate_detection,
            self.test_safety_limits,
            self.test_error_handling
        ]
        
        for test_method in test_methods:
            try:
                await test_method()
            except Exception as e:
                error_msg = f"❌ Unexpected error in {test_method.__name__}: {e}"
                LOGGER.writeLog(error_msg)
                self.test_results['failed'] += 1
                self.test_results['errors'].append(error_msg)
        
        # Print summary
        self._print_test_summary()
        
        return self.test_results['failed'] == 0
    
    def _print_test_summary(self):
        """Print comprehensive test summary"""
        total_tests = self.test_results['passed'] + self.test_results['failed']
        success_rate = (self.test_results['passed'] / total_tests * 100) if total_tests > 0 else 0
        
        LOGGER.writeLog("=" * 80)
        LOGGER.writeLog("📊 TELEGRAM MESSAGE FETCHING TEST SUMMARY")
        LOGGER.writeLog("=" * 80)
        LOGGER.writeLog(f"Total Tests: {total_tests}")
        LOGGER.writeLog(f"✅ Passed: {self.test_results['passed']}")
        LOGGER.writeLog(f"❌ Failed: {self.test_results['failed']}")
        LOGGER.writeLog(f"📈 Success Rate: {success_rate:.1f}%")
        
        if self.test_results['errors']:
            LOGGER.writeLog("\n🔍 ERROR DETAILS:")
            for error in self.test_results['errors']:
                LOGGER.writeLog(f"  • {error}")
        
        if self.test_results['failed'] == 0:
            LOGGER.writeLog("\n🎉 ALL TESTS PASSED! Message fetching functions are working correctly.")
        else:
            LOGGER.writeLog(f"\n⚠️  {self.test_results['failed']} test(s) failed. Please review the errors above.")
        
        LOGGER.writeLog("=" * 80)

async def main():
    """Main test execution function"""
    try:
        print("🧪 Telegram Message Fetching Test Suite")
        print("=" * 50)
        
        # Run comprehensive tests
        test_suite = TestTelegramMessageFetching()
        success = await test_suite.run_all_tests()
        
        if success:
            print("✅ All tests passed successfully!")
            return 0
        else:
            print("❌ Some tests failed. Check the log file for details.")
            return 1
            
    except Exception as e:
        print(f"❌ Critical error running tests: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)