#!/usr/bin/env python3
"""
Telegram Authentication Script
Forces interactive Telegram authentication
"""

import asyncio
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from src.core.file_handling import FileHandling
from src.integrations.telegram_utils import TelegramScraper

async def authenticate_telegram():
    """Force Telegram authentication"""
    print("========================================")
    print("Telegram Authentication Setup")
    print("========================================")
    
    try:
        # Load config
        config_path = os.path.join(project_root, 'config', 'config.json')
        config_handler = FileHandling(config_path)
        config = config_handler.read_json()
        
        if not config:
            print("❌ Failed to load configuration")
            print(f"   Looking for: {config_path}")
            return False
        
        # Get Telegram config
        telegram_config = config.get('TELEGRAM_CONFIG', {})
        if not all(key in telegram_config for key in ['API_ID', 'API_HASH', 'PHONE_NUMBER']):
            print("❌ Telegram configuration incomplete")
            print("Required: API_ID, API_HASH, PHONE_NUMBER")
            print("Current config keys:", list(telegram_config.keys()))
            return False
        
        print(f"📱 Phone Number: {telegram_config['PHONE_NUMBER']}")
        print(f"🔑 API ID: {telegram_config['API_ID']}")
        print("🔑 API Hash: [CONFIGURED]")
        print()
        
        # Remove existing session if it exists
        session_file = os.path.join(project_root, 'telegram_session.session')
        if os.path.exists(session_file):
            print("🗑️  Removing existing session file...")
            os.remove(session_file)
        
        print("🚀 Starting Telegram client (this will prompt for authentication)...")
        print("📞 You will need to enter the SMS code sent to your phone")
        print()
        
        # Create Telegram client
        telegram_scraper = TelegramScraper(
            telegram_config['API_ID'],
            telegram_config['API_HASH'], 
            telegram_config['PHONE_NUMBER'],
            'telegram_session'
        )
        
        # This should trigger authentication prompts
        print("📞 Connecting to Telegram servers...")
        success = await telegram_scraper.start_client()
        
        if success:
            print("✅ Telegram authentication successful!")
            print("✅ Session file created: telegram_session.session")
            
            # Test by getting user info
            try:
                client = telegram_scraper.client
                me = await client.get_me()
                print(f"✅ Logged in as: {me.first_name} {me.last_name or ''} (@{me.username or 'no_username'})")
                print(f"✅ Phone: {me.phone}")
            except Exception as e:
                print(f"⚠️  Warning: Could not get user info: {e}")
            
            await telegram_scraper.stop_client()
            return True
        else:
            print("❌ Telegram authentication failed")
            return False
            
    except Exception as e:
        print(f"❌ Error during authentication: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("This script will help you authenticate with Telegram")
    print("Make sure you have your phone nearby to receive SMS verification codes")
    print()
    
    response = input("Continue with authentication? (y/n): ")
    if response.lower() != 'y':
        print("Authentication cancelled")
        sys.exit(0)
    
    result = asyncio.run(authenticate_telegram())
    
    if result:
        print()
        print("🎉 Authentication completed successfully!")
        print("You can now run: ./scripts/run_app.sh test")
    else:
        print()
        print("💥 Authentication failed. Please check your configuration and try again.")
        sys.exit(1)