#!/usr/bin/env python3
"""
Telegram Configuration Validator and Credential Manager
Comprehensive validation and interactive credential management for Telegram authentication
"""

import sys
import os
import re
import socket
import requests
import json
from datetime import datetime

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from src.core.file_handling import FileHandling

def validate_phone_number(phone):
    """Validate phone number format"""
    # Remove any spaces or dashes
    clean_phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    # Should start with + and have 10-15 digits
    if re.match(r'^\+\d{10,15}$', clean_phone):
        return True, clean_phone
    else:
        return False, "Phone number should be in format +CountryCodeNumber (e.g., +639693532299)"

def validate_api_credentials(api_id, api_hash):
    """Validate API credentials format"""
    errors = []
    
    # Validate API_ID
    try:
        api_id_int = int(api_id)
        if api_id_int <= 0:
            errors.append("API_ID should be a positive integer")
    except (ValueError, TypeError):
        errors.append("API_ID should be a numeric value")
    
    # Validate API_HASH
    if not api_hash or len(api_hash) != 32:
        errors.append("API_HASH should be a 32-character hexadecimal string")
    elif not re.match(r'^[a-fA-F0-9]{32}$', api_hash):
        errors.append("API_HASH should contain only hexadecimal characters (0-9, a-f)")
    
    return len(errors) == 0, errors

def check_network_connectivity():
    """Check if we can reach Telegram servers"""
    telegram_endpoints = [
        ("149.154.175.50", 443),  # Telegram DC2
        ("149.154.167.51", 443),  # Telegram DC4
        ("91.108.56.130", 443),   # Telegram DC5
    ]
    
    accessible_endpoints = 0
    for host, port in telegram_endpoints:
        try:
            sock = socket.create_connection((host, port), timeout=5)
            sock.close()
            accessible_endpoints += 1
        except (socket.timeout, socket.error):
            continue
    
    return accessible_endpoints > 0, f"{accessible_endpoints}/{len(telegram_endpoints)} Telegram endpoints accessible"

def check_telegram_api_status():
    """Check if Telegram API is accessible"""
    try:
        # Try to reach Telegram's web interface
        response = requests.get("https://my.telegram.org", timeout=10)
        return response.status_code == 200, f"Telegram web API status: {response.status_code}"
    except requests.RequestException as e:
        return False, f"Cannot reach Telegram web API: {e}"

def interactive_credential_update(config_path, telegram_config):
    """Interactive credential update functionality"""
    print("=" * 50)
    print("🔄 CREDENTIAL UPDATE (optional)")
    print("If you have new credentials from https://my.telegram.org/apps, enter them below:")
    print("(Press Enter to skip any field)")
    print()
    
    new_api_id = input("New API_ID (or press Enter to keep current): ").strip()
    new_api_hash = input("New API_HASH (or press Enter to keep current): ").strip()
    
    if new_api_id or new_api_hash:
        if new_api_id:
            telegram_config['API_ID'] = new_api_id
            print(f"✅ Updated API_ID to: {new_api_id}")
        
        if new_api_hash:
            telegram_config['API_HASH'] = new_api_hash
            print(f"✅ Updated API_HASH to: {new_api_hash[:8]}...{new_api_hash[-4:]}")
        
        # Save updated config
        try:
            with open(config_path, 'r') as f:
                full_config = json.load(f)
            
            full_config['TELEGRAM_CONFIG'] = telegram_config
            
            with open(config_path, 'w') as f:
                json.dump(full_config, f, indent=3)
            
            print("💾 Configuration updated!")
            print("🚀 Run validation again to test new credentials")
            return True
        except Exception as e:
            print(f"❌ Error saving config: {e}")
            return False
    else:
        print("ℹ️  No changes made.")
        return False

def run_validation():
    """Run comprehensive Telegram configuration validation"""
    print("🔍 Telegram Configuration Validator")
    print("=" * 50)
    print()
    
    # Load configuration
    CONFIG_PATH = os.path.join(project_root, "config", "config.json")
    if not os.path.exists(CONFIG_PATH):
        print("❌ config.json not found")
        print(f"   Looking for: {CONFIG_PATH}")
        return False
    
    try:
        config_handler = FileHandling(CONFIG_PATH)
        config = config_handler.read_json()
        
        if not config:
            print("❌ Failed to parse config.json")
            return False
            
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return False
    
    # Get Telegram configuration
    telegram_config = config.get('TELEGRAM_CONFIG', {})
    if not telegram_config:
        print("❌ TELEGRAM_CONFIG section missing from config.json")
        return False
    
    api_id = telegram_config.get('API_ID')
    api_hash = telegram_config.get('API_HASH')
    phone_number = telegram_config.get('PHONE_NUMBER')
    
    print("1️⃣ Configuration Validation")
    print("-" * 30)
    
    all_valid = True
    
    # Validate phone number
    if phone_number:
        is_valid, message = validate_phone_number(phone_number)
        if is_valid:
            print(f"✅ Phone number format: {message}")
        else:
            print(f"❌ Phone number issue: {message}")
            all_valid = False
    else:
        print("❌ PHONE_NUMBER missing from config")
        all_valid = False
    
    # Validate API credentials
    if api_id and api_hash:
        is_valid, errors = validate_api_credentials(api_id, api_hash)
        if is_valid:
            print(f"✅ API credentials format valid")
            print(f"   API_ID: {api_id}")
            print(f"   API_HASH: {api_hash[:8]}...{api_hash[-4:]}")
        else:
            print("❌ API credentials issues:")
            for error in errors:
                print(f"   - {error}")
            all_valid = False
    else:
        print("❌ API_ID or API_HASH missing from config")
        all_valid = False
    
    print()
    print("2️⃣ Network Connectivity")
    print("-" * 30)
    
    # Check network connectivity
    can_connect, message = check_network_connectivity()
    if can_connect:
        print(f"✅ Network connectivity: {message}")
    else:
        print(f"❌ Network connectivity: {message}")
        print("   💡 Check firewall, VPN, or network restrictions")
        all_valid = False
    
    # Check Telegram API status
    api_accessible, api_message = check_telegram_api_status()
    if api_accessible:
        print(f"✅ Telegram API accessibility: {api_message}")
    else:
        print(f"❌ Telegram API accessibility: {api_message}")
        print("   💡 Try using a VPN or check if Telegram is blocked in your region")
        all_valid = False
    
    print()
    print("3️⃣ Session File Status")
    print("-" * 30)
    
    session_file = os.path.join(project_root, 'telegram_session.session')
    if os.path.exists(session_file):
        file_size = os.path.getsize(session_file)
        mod_time = datetime.fromtimestamp(os.path.getmtime(session_file))
        print(f"⚠️  Existing session file found")
        print(f"   Size: {file_size} bytes")
        print(f"   Modified: {mod_time}")
        print(f"   💡 Delete if you want to start fresh: rm {session_file}")
    else:
        print("✅ No existing session file (fresh start)")
    
    print()
    print("4️⃣ Environment Check")
    print("-" * 30)
    
    # Check if required packages are installed
    try:
        import telethon
        print(f"✅ Telethon installed: v{telethon.__version__}")
    except ImportError:
        print("❌ Telethon not installed")
        print("   💡 Run: pip install telethon")
        all_valid = False
    
    # Check Python version
    python_version = sys.version_info
    if python_version >= (3, 7):
        print(f"✅ Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
    else:
        print(f"❌ Python version too old: {python_version.major}.{python_version.minor}.{python_version.micro}")
        print("   💡 Telegram requires Python 3.7+")
        all_valid = False
    
    print()
    print("=" * 50)
    
    if all_valid:
        print("🎉 All validations passed!")
        print("✅ Ready to attempt Telegram authentication")
        print()
        print("Next steps:")
        print("1. Run: python3 scripts/telegram_auth.py")
        print("2. Enter the SMS code when prompted")
        print("3. If you have 2FA enabled, enter your password")
        return True, CONFIG_PATH, telegram_config
    else:
        print("❌ Validation failed!")
        print("Please fix the issues above before attempting authentication")
        print()
        print("Common solutions:")
        print("1. Double-check API credentials at https://my.telegram.org/apps")
        print("2. Verify phone number format (+CountryCodeNumber)")
        print("3. Check network/firewall settings")
        print("4. Try using a VPN if Telegram is blocked")
        return False, CONFIG_PATH, telegram_config

def show_current_config():
    """Show current configuration for credential management"""
    CONFIG_PATH = os.path.join(project_root, "config", "config.json")
    
    print("🔍 Current Telegram Configuration")
    print("=" * 50)
    
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        
        telegram_config = config.get('TELEGRAM_CONFIG', {})
        
        if telegram_config:
            print("📱 Current configuration in config.json:")
            print(f"   API_ID: {telegram_config.get('API_ID', 'NOT SET')}")
            print(f"   API_HASH: {telegram_config.get('API_HASH', 'NOT SET')}")
            print(f"   PHONE: {telegram_config.get('PHONE_NUMBER', 'NOT SET')}")
            print()
            
            print("🔧 To update credentials:")
            print("1. Go to: https://my.telegram.org/apps")
            print("2. Check if the API_ID and API_HASH match the values above")
            print("3. If they DON'T match, use the update option below")
            print("4. If there's no app, create a new one with these details:")
            print("   - App title: Iraq News Monitor 2025")
            print("   - Short name: iraq-news-2025") 
            print("   - Platform: Desktop")
            print("   - Description: News monitoring system")
            print()
            
            return CONFIG_PATH, telegram_config
        else:
            print("❌ TELEGRAM_CONFIG section missing from config.json")
            return None, None
            
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return None, None

def main():
    """Main function with interactive menu"""
    print("🎯 Telegram Configuration Validator & Credential Manager")
    print("=" * 60)
    print()
    print("Choose an option:")
    print("1. Run full validation (recommended)")
    print("2. Show current credentials")
    print("3. Update credentials only")
    print("4. Exit")
    print()
    
    try:
        choice = input("Enter your choice (1-4): ").strip()
        
        if choice == "1":
            print()
            success, config_path, telegram_config = run_validation()
            
            if not success and config_path and telegram_config:
                print()
                update_choice = input("🔄 Would you like to update credentials now? (y/n): ").strip().lower()
                if update_choice in ['y', 'yes']:
                    updated = interactive_credential_update(config_path, telegram_config)
                    if updated:
                        print()
                        print("🔁 Re-running validation with new credentials...")
                        print()
                        run_validation()
            
            return success
            
        elif choice == "2":
            print()
            show_current_config()
            return True
            
        elif choice == "3":
            print()
            config_path, telegram_config = show_current_config()
            if config_path and telegram_config:
                print()
                interactive_credential_update(config_path, telegram_config)
            return True
            
        elif choice == "4":
            print("👋 Goodbye!")
            return True
            
        else:
            print("❌ Invalid choice. Please enter 1, 2, 3, or 4.")
            return False
            
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user. Goodbye!")
        return True
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)