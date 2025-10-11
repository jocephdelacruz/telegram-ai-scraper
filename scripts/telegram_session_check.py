#!/usr/bin/env python3
"""
Telegram Session Status Checker and Recovery Assistant

This script provides comprehensive Telegram session diagnostics and recovery guidance.
It uses the advanced TelegramSessionManager to check session health and provide
intelligent recommendations for resolving issues.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import asyncio
from datetime import datetime
from src.core import file_handling as fh
from src.integrations.telegram_session_manager import TelegramSessionManager, TelegramRateLimitError, TelegramSessionError, TelegramAuthError


def load_config():
    """Load configuration"""
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(project_root, "config", "config.json")
        config_handler = fh.FileHandling(config_path)
        return config_handler.read_json()
    except Exception as e:
        print(f"❌ Failed to load configuration: {e}")
        return None


def print_banner():
    """Print the application banner"""
    print(f"{'='*60}")
    print("🔍 Telegram Session Status Checker & Recovery Assistant")
    print(f"{'='*60}")
    print(f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()


def print_config_check(config):
    """Check and display configuration status"""
    print("📋 Configuration Check:")
    
    if not config:
        print("   ❌ Failed to load config.json")
        return False
    
    telegram_config = config.get('TELEGRAM_CONFIG', {})
    
    # Check required fields
    required_fields = ['API_ID', 'API_HASH', 'PHONE_NUMBER']
    missing_fields = []
    
    for field in required_fields:
        if not telegram_config.get(field):
            missing_fields.append(field)
    
    if missing_fields:
        print(f"   ❌ Missing required fields: {', '.join(missing_fields)}")
        return False
    
    print("   ✅ All required configuration fields present")
    print(f"   📱 Phone: {telegram_config['PHONE_NUMBER']}")
    print(f"   🔑 API ID: {telegram_config['API_ID']}")
    print(f"   📁 Session: {telegram_config.get('SESSION_FILE', 'telegram_session')}")
    return True


async def check_session_status(config):
    """Check current Telegram session status using the advanced session manager"""
    print("\n🔍 Session Status Check:")
    
    telegram_config = config.get('TELEGRAM_CONFIG', {})
    
    # Initialize session manager
    session_manager = TelegramSessionManager(
        telegram_config['API_ID'],
        telegram_config['API_HASH'],
        telegram_config['PHONE_NUMBER'],
        telegram_config.get('SESSION_FILE', 'telegram_session')
    )
    
    try:
        # Perform comprehensive health check
        health_status = await session_manager.health_check()
        
        print(f"   📊 Health Check Timestamp: {health_status['timestamp']}")
        
        # Display connection status
        conn_status = health_status['connection_status']
        print(f"   🔗 Connected: {'✅ Yes' if conn_status['is_connected'] else '❌ No'}")
        
        if conn_status['last_successful_connection']:
            print(f"   🕐 Last Success: {conn_status['last_successful_connection']}")
        
        print(f"   🔄 Connection Attempts: {conn_status['connection_attempts']}")
        
        # Check rate limiting
        if conn_status['is_rate_limited']:
            rate_info = conn_status['rate_limit_info']
            if rate_info:
                hours = rate_info['remaining_seconds'] / 3600
                print(f"   🚫 RATE LIMITED: {hours:.1f} hours remaining")
                print(f"   ⏰ Expires: {rate_info['expires_human']}")
                return 'rate_limited', rate_info
        
        # Check if healthy
        if health_status['healthy']:
            print("   ✅ SESSION STATUS: HEALTHY")
            user_info = health_status.get('user_info', {})
            if user_info:
                print(f"   👤 Connected as: {user_info.get('name', 'Unknown')} ({user_info.get('phone', 'N/A')})")
                print(f"   🆔 User ID: {user_info.get('id', 'N/A')}")
            return 'healthy', health_status
        else:
            print("   ❌ SESSION STATUS: UNHEALTHY")
            errors = health_status.get('errors', [])
            
            # Check for rate limiting specifically
            rate_limited = False
            for error in errors:
                if "Rate limited" in error:
                    print(f"   🚫 RATE LIMITED: {error}")
                    rate_limited = True
                else:
                    print(f"   ⚠️  {error}")
            
            if rate_limited:
                return 'rate_limited', health_status
            else:
                return 'unhealthy', health_status
            
    except Exception as e:
        print(f"   ❌ Health check failed: {e}")
        return 'error', str(e)
    finally:
        await session_manager.close()


def provide_recovery_guidance(status_result, details):
    """Provide specific recovery guidance based on status"""
    print(f"\n💡 Recovery Guidance:")
    
    status, data = status_result, details
    
    if status == 'healthy':
        print("   ✅ No action needed - session is working properly")
        print("   🚀 Your Telegram scraper can operate normally")
        print("\n📋 Next Steps:")
        print("   • Start your scraper: ./scripts/quick_start.sh")
        print("   • Monitor status: ./scripts/status.sh")
        
    elif status == 'rate_limited':
        # Extract rate limit info from error messages
        errors = data.get('errors', [])
        rate_limit_text = None
        for error in errors:
            if "Rate limited" in error:
                rate_limit_text = error
                break
        
        if rate_limit_text:
            # Try to extract wait time from the error message
            import re
            seconds_match = re.search(r'wait (\d+) seconds', rate_limit_text)
            time_match = re.search(r'until ([\d-]+ [\d:]+)', rate_limit_text)
            
            if seconds_match:
                wait_seconds = int(seconds_match.group(1))
                hours = wait_seconds / 3600
                print(f"   ⏳ WAIT REQUIRED: {hours:.1f} hours ({wait_seconds:,} seconds)")
                
            if time_match:
                print(f"   📅 Rate limit expires: {time_match.group(1)}")
            else:
                print(f"   📅 Rate limit details: {rate_limit_text}")
        
        print("\n📋 Action Plan:")
        print("   1. ⏸️  Keep all workers stopped (they should be already)")
        print("   2. ⏰ Wait for rate limit to expire")
        print("   3. 🔄 Run recovery script: python3 tests/telegram_recovery.py")
        print("   4. ✅ Start system: ./scripts/quick_start.sh")
        
    elif status == 'unhealthy':
        errors = data.get('errors', [])
        
        # Check for specific error types
        needs_auth = any('Session' in error or 'authentication' in error for error in errors)
        has_config_error = any('Invalid API' in error or 'Configuration' in error for error in errors)
        
        if has_config_error:
            print("   🔧 CONFIGURATION ISSUE DETECTED")
            print("\n📋 Fix Steps:")
            print("   1. 🔑 Verify API credentials in config/config.json")
            print("   2. 📱 Ensure phone number is correct (+country code)")
            print("   3. 🌐 Get new credentials from https://my.telegram.org/apps if needed")
            print("   4. 🔄 Run validation: python3 tests/validate_telegram_config.py")
            
        elif needs_auth:
            print("   🔐 AUTHENTICATION REQUIRED")
            print("\n📋 Fix Steps:")
            print("   1. 🔑 Re-authenticate: python3 scripts/telegram_auth.py")
            print("   2. 📱 Enter SMS code when prompted")
            print("   3. ✅ Test connection: python3 scripts/telegram_session_check.py")
            print("   4. 🚀 Start system: ./scripts/quick_start.sh")
        else:
            print("   🔧 GENERAL TROUBLESHOOTING NEEDED")
            print("\n📋 Troubleshooting Steps:")
            print("   1. 🔍 Check logs: tail -f logs/telegram.log")
            print("   2. 🔄 Restart Redis: sudo systemctl restart redis-server")
            print("   3. 🌐 Check network connectivity")
            print("   4. 📞 Contact support if issues persist")
            
    elif status == 'error':
        print("   ❌ UNEXPECTED ERROR OCCURRED")
        print(f"   📝 Error details: {data}")
        print("\n📋 Troubleshooting Steps:")
        print("   1. 🔍 Check logs: tail -f logs/telegram.log")
        print("   2. 🔧 Verify configuration: python3 tests/validate_telegram_config.py")
        print("   3. 🔄 Try manual authentication: python3 scripts/telegram_auth.py")
        print("   4. 📞 Report issue if problem persists")


def print_monitoring_commands():
    """Print useful monitoring commands"""
    print(f"\n📊 Monitoring Commands:")
    print("   • Check session status: python3 scripts/telegram_session_check.py")
    print("   • Check rate limits: python3 tests/check_telegram_status.py") 
    print("   • System status: ./scripts/status.sh")
    print("   • View logs: tail -f logs/telegram.log")
    print("   • Resource monitor: ./scripts/monitor_resources.sh")


async def main():
    """Main execution function"""
    print_banner()
    
    # Load and check configuration
    config = load_config()
    if not print_config_check(config):
        print("\n❌ Configuration issues prevent session checking")
        print("💡 Fix configuration issues first, then re-run this script")
        return 1
    
    # Check session status
    try:
        status_result, details = await check_session_status(config)
        
        # Provide recovery guidance
        provide_recovery_guidance(status_result, details)
        
        # Show monitoring commands
        print_monitoring_commands()
        
        # Return appropriate exit code
        if status_result == 'healthy':
            print(f"\n✅ SESSION READY - System can operate normally")
            return 0
        else:
            print(f"\n⚠️  SESSION NEEDS ATTENTION - Follow guidance above")
            return 1
            
    except Exception as e:
        print(f"\n❌ Unexpected error during session check: {e}")
        print("💡 Try running with debug logging or check system logs")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Session check cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)