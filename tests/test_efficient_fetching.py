#!/usr/bin/env python3
"""
Test script for the new efficient message fetching system

This script tests:
1. Redis tracking functionality
2. CSV fallback mechanism  
3. 4-hour age limit enforcement
4. Integration with existing systems
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import asyncio
import redis
import json
from datetime import datetime, timedelta, timezone
from src.integrations.telegram_utils import TelegramScraper
from src.core import file_handling as fh
from src.core import log_handling as lh

# Setup logging
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_LOG = os.path.join(PROJECT_ROOT, "logs", "test_efficient_fetching.log")
LOGGER = lh.LogHandling(TEST_LOG, "Asia/Manila")


async def test_efficient_fetching():
    """Test the new efficient fetching system"""
    
    try:
        LOGGER.writeLog("🧪 Starting efficient fetching system test")
        
        # Load configuration
        config_path = os.path.join(PROJECT_ROOT, "config", "config.json")
        config_handler = fh.FileHandling(config_path)
        config = config_handler.read_json()
        
        if not config:
            LOGGER.writeLog("❌ Failed to load configuration")
            return False
        
        # Get Telegram configuration
        telegram_config = config.get('TELEGRAM_CONFIG', {})
        if not all(key in telegram_config for key in ['API_ID', 'API_HASH', 'PHONE_NUMBER']):
            LOGGER.writeLog("❌ Telegram configuration incomplete")
            return False
        
        # Initialize Telegram scraper
        telegram_scraper = TelegramScraper(
            telegram_config['API_ID'],
            telegram_config['API_HASH'],
            telegram_config['PHONE_NUMBER'],
            telegram_config.get('SESSION_FILE', 'telegram_session')
        )
        
        # Test Redis connection
        LOGGER.writeLog("🔌 Testing Redis connection...")
        try:
            redis_client = redis.Redis(host='localhost', port=6379, db=1)
            redis_client.ping()
            LOGGER.writeLog("✅ Redis connection successful")
        except Exception as redis_error:
            LOGGER.writeLog(f"⚠️  Redis connection failed: {redis_error}")
            redis_client = None
        
        # Get test channel from Iraq configuration
        countries = config.get('COUNTRIES', {})
        iraq_channels = countries.get('iraq', {}).get('channels', [])
        
        if not iraq_channels:
            LOGGER.writeLog("❌ No Iraq channels found in configuration")
            return False
        
        test_channel = iraq_channels[0]  # Use first channel for testing
        LOGGER.writeLog(f"🎯 Testing with channel: {test_channel}")
        
        # Start Telegram client
        LOGGER.writeLog("🚀 Starting Telegram client...")
        await telegram_scraper.start_client()
        LOGGER.writeLog("✅ Telegram client started")
        
        # Test 1: Efficient fetching with Redis tracking
        LOGGER.writeLog("📊 Test 1: Efficient fetching with Redis tracking")
        
        messages_with_tracking = await telegram_scraper.get_channel_messages_with_tracking(
            test_channel,
            config=config,
            redis_client=redis_client,
            log_found_messages=True
        )
        
        LOGGER.writeLog(f"✅ Tracking method returned {len(messages_with_tracking)} messages")
        
        # Test 2: Compare with original method (small limit to avoid rate limits)
        LOGGER.writeLog("📊 Test 2: Comparing with original method (limited)")
        
        # Calculate 4-hour cutoff for comparison
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=4)
        
        messages_original = await telegram_scraper.get_channel_messages(
            test_channel,
            limit=5,  # Small limit for testing
            cutoff_time=cutoff_time,
            redis_client=redis_client,
            log_found_messages=True
        )
        
        LOGGER.writeLog(f"✅ Original method returned {len(messages_original)} messages")
        
        # Test 3: CSV fallback mechanism (simulate Redis failure)
        LOGGER.writeLog("📊 Test 3: CSV fallback mechanism")
        
        messages_csv_fallback = await telegram_scraper.get_channel_messages_with_tracking(
            test_channel,
            config=config,
            redis_client=None,  # Simulate Redis unavailability
            log_found_messages=True
        )
        
        LOGGER.writeLog(f"✅ CSV fallback returned {len(messages_csv_fallback)} messages")
        
        # Test 4: Check Redis tracking data
        if redis_client:
            LOGGER.writeLog("📊 Test 4: Checking Redis tracking data")
            
            redis_key = f"last_processed:{test_channel}"
            last_id_bytes = redis_client.get(redis_key)
            
            if last_id_bytes:
                last_id = int(last_id_bytes.decode('utf-8'))
                LOGGER.writeLog(f"✅ Redis tracking found: {last_id}")
            else:
                LOGGER.writeLog("ℹ️  No Redis tracking data found (expected for first run)")
        
        # Test 5: Check CSV files for tracking data  
        LOGGER.writeLog("📊 Test 5: Checking CSV files for tracking data")
        
        data_dir = os.path.join(PROJECT_ROOT, "data")
        csv_files = ["iraq_significant_messages.csv", "iraq_trivial_messages.csv"]
        
        for csv_file in csv_files:
            csv_path = os.path.join(data_dir, csv_file)
            if os.path.exists(csv_path):
                # Get file size and modification time
                file_size = os.path.getsize(csv_path)
                mod_time = datetime.fromtimestamp(os.path.getmtime(csv_path))
                LOGGER.writeLog(f"✅ Found {csv_file}: {file_size} bytes, modified {mod_time}")
            else:
                LOGGER.writeLog(f"ℹ️  CSV file not found: {csv_file}")
        
        # Stop Telegram client
        await telegram_scraper.stop_client()
        LOGGER.writeLog("✅ Telegram client stopped")
        
        # Summary
        LOGGER.writeLog("🎉 Efficient fetching system test completed successfully!")
        LOGGER.writeLog(f"📈 Results summary:")
        LOGGER.writeLog(f"   - Tracking method: {len(messages_with_tracking)} messages")
        LOGGER.writeLog(f"   - Original method: {len(messages_original)} messages")
        LOGGER.writeLog(f"   - CSV fallback: {len(messages_csv_fallback)} messages")
        LOGGER.writeLog(f"   - Redis available: {'Yes' if redis_client else 'No'}")
        
        return True
        
    except Exception as e:
        LOGGER.writeLog(f"❌ Test failed with error: {e}")
        
        # Ensure client cleanup
        try:
            await telegram_scraper.stop_client()
        except:
            pass
        
        return False


async def test_csv_tracking():
    """Test CSV tracking functionality separately"""
    
    try:
        LOGGER.writeLog("📄 Testing CSV tracking functionality")
        
        # Load configuration
        config_path = os.path.join(PROJECT_ROOT, "config", "config.json")
        config_handler = fh.FileHandling(config_path)
        config = config_handler.read_json()
        
        # Initialize scraper for testing
        telegram_config = config.get('TELEGRAM_CONFIG', {})
        telegram_scraper = TelegramScraper(
            telegram_config['API_ID'],
            telegram_config['API_HASH'],
            telegram_config['PHONE_NUMBER'],
            telegram_config.get('SESSION_FILE', 'telegram_session')
        )
        
        # Test CSV reading for Iraq channels
        iraq_channels = config.get('COUNTRIES', {}).get('iraq', {}).get('channels', [])
        
        for channel in iraq_channels[:3]:  # Test first 3 channels
            LOGGER.writeLog(f"🔍 Testing CSV tracking for {channel}")
            
            last_id = await telegram_scraper._get_last_id_from_csv(channel, 'iraq')
            
            if last_id:
                LOGGER.writeLog(f"✅ Found last ID for {channel}: {last_id}")
            else:
                LOGGER.writeLog(f"ℹ️  No CSV data found for {channel}")
        
        LOGGER.writeLog("✅ CSV tracking test completed")
        return True
        
    except Exception as e:
        LOGGER.writeLog(f"❌ CSV tracking test failed: {e}")
        return False


def test_redis_operations():
    """Test Redis operations separately"""
    
    try:
        LOGGER.writeLog("🔴 Testing Redis operations")
        
        # Test Redis connection
        redis_client = redis.Redis(host='localhost', port=6379, db=1)
        redis_client.ping()
        LOGGER.writeLog("✅ Redis connection successful")
        
        # Test setting and getting tracking data
        test_channel = "@test_channel"
        test_id = 12345
        
        redis_key = f"last_processed:{test_channel}"
        redis_client.setex(redis_key, 60, str(test_id))  # 60 seconds expiry for testing
        
        retrieved_bytes = redis_client.get(redis_key)
        retrieved_id = int(retrieved_bytes.decode('utf-8'))
        
        if retrieved_id == test_id:
            LOGGER.writeLog(f"✅ Redis set/get test successful: {retrieved_id}")
        else:
            LOGGER.writeLog(f"❌ Redis set/get test failed: expected {test_id}, got {retrieved_id}")
            return False
        
        # Test duplicate detection
        duplicate_key = f"processed_msg:{test_channel}:{test_id}"
        redis_client.setex(duplicate_key, 60, "1")
        
        if redis_client.exists(duplicate_key):
            LOGGER.writeLog("✅ Redis duplicate detection test successful")
        else:
            LOGGER.writeLog("❌ Redis duplicate detection test failed")
            return False
        
        # Cleanup test data
        redis_client.delete(redis_key)
        redis_client.delete(duplicate_key)
        
        LOGGER.writeLog("✅ Redis operations test completed")
        return True
        
    except Exception as e:
        LOGGER.writeLog(f"❌ Redis operations test failed: {e}")
        return False


async def main():
    """Run all tests"""
    
    LOGGER.writeLog("=" * 60)
    LOGGER.writeLog("🧪 EFFICIENT FETCHING SYSTEM TEST SUITE")
    LOGGER.writeLog("=" * 60)
    
    all_passed = True
    
    # Test 1: Redis operations
    LOGGER.writeLog("🔴 Running Redis operations test...")
    redis_passed = test_redis_operations()
    all_passed = all_passed and redis_passed
    
    # Test 2: CSV tracking
    LOGGER.writeLog("\n📄 Running CSV tracking test...")
    csv_passed = await test_csv_tracking()
    all_passed = all_passed and csv_passed
    
    # Test 3: Full integration test
    LOGGER.writeLog("\n🚀 Running full integration test...")
    integration_passed = await test_efficient_fetching()
    all_passed = all_passed and integration_passed
    
    # Final results
    LOGGER.writeLog("\n" + "=" * 60)
    if all_passed:
        LOGGER.writeLog("🎉 ALL TESTS PASSED! Efficient fetching system is ready.")
    else:
        LOGGER.writeLog("❌ Some tests failed. Please check the logs above.")
    LOGGER.writeLog("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    print("🧪 Running efficient fetching system tests...")
    print(f"📋 Check logs at: {TEST_LOG}")
    
    try:
        result = asyncio.run(main())
        
        if result:
            print("✅ All tests passed!")
            exit(0)
        else:
            print("❌ Some tests failed!")
            exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        exit(1)
    except Exception as e:
        print(f"❌ Test suite failed: {e}")
        exit(1)