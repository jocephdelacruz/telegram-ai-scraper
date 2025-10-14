#!/usr/bin/env python3
"""
Telegram Authentication Script
Handles Telegram authentication and session management
"""

import asyncio
import sys
import os
import argparse
from datetime import datetime

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from src.core.file_handling import FileHandling
from src.integrations.telegram_utils import TelegramScraper
from src.integrations.telegram_session_manager import TelegramRateLimitError, TelegramSessionError, TelegramAuthError
from src.integrations.session_safety import SessionSafetyManager, SessionSafetyError

def get_session_info():
    """Get information about the current session"""
    session_file = os.path.join(project_root, 'telegram_session.session')
    if not os.path.exists(session_file):
        return None
    
    stat = os.stat(session_file)
    created = datetime.fromtimestamp(stat.st_ctime)
    modified = datetime.fromtimestamp(stat.st_mtime)
    size = stat.st_size
    
    return {
        'file': session_file,
        'created': created,
        'modified': modified,
        'size': size,
        'age_days': (datetime.now() - modified).days
    }

def show_session_status():
    """Display current session status"""
    print("=" * 50)
    print("📱 TELEGRAM SESSION STATUS")
    print("=" * 50)
    
    session_info = get_session_info()
    if not session_info:
        print("❌ No session file found")
        print("   Session file: telegram_session.session")
        print("   Status: Not authenticated")
        return False
    
    print(f"✅ Session file exists: {os.path.basename(session_info['file'])}")
    print(f"📅 Created: {session_info['created'].strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔄 Last modified: {session_info['modified'].strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 Size: {session_info['size']:,} bytes")
    print(f"⏰ Age: {session_info['age_days']} days")
    
    if session_info['age_days'] > 30:
        print("⚠️  Session is over 30 days old - consider renewal soon")
        print("💡 Telegram sessions can expire, renewal recommended")
    elif session_info['age_days'] > 14:
        print("💡 Session is over 2 weeks old - renewal available if desired")
    else:
        print("✅ Session is recent and should be working fine")
    
    return True

async def test_session_validity():
    """Test if the current session is valid without requiring SMS"""
    print("🔍 Testing session validity...")
    
    # Session safety check for testing
    safety = SessionSafetyManager()
    try:
        safety.check_session_safety("telegram_session_test")
        print("✅ Session safety check passed - safe to test")
        safety.record_session_access("telegram_session_test")
    except SessionSafetyError as e:
        print("🛡️ SESSION SAFETY PROTECTION for session test:")
        print(str(e))
        print("✅ Session conflict prevented - your phone stays connected!")
        print("\n💡 To test session safely:")
        print("   1. Stop workers: ./scripts/deploy_celery.sh stop")
        print("   2. Test session: python3 scripts/telegram_auth.py --test")
        print("   3. Start workers: ./scripts/deploy_celery.sh start")
        return False
    
    try:
        # Load config
        config_path = os.path.join(project_root, 'config', 'config.json')
        config_handler = FileHandling(config_path)
        config = config_handler.read_json()
        
        if not config:
            print("❌ Failed to load configuration")
            return False
        
        telegram_config = config.get('TELEGRAM_CONFIG', {})
        if not all(key in telegram_config for key in ['API_ID', 'API_HASH', 'PHONE_NUMBER']):
            print("❌ Telegram configuration incomplete")
            return False
        
        # Create scraper and test connection
        telegram_scraper = TelegramScraper(
            telegram_config['API_ID'],
            telegram_config['API_HASH'], 
            telegram_config['PHONE_NUMBER'],
            'telegram_session'
        )
        
        success = await telegram_scraper.start_client()
        
        if success:
            try:
                client = telegram_scraper.client
                me = await client.get_me()
                print(f"✅ Session is VALID - Connected as: {me.first_name} {me.last_name or ''}")
                print(f"📱 Phone: {me.phone}")
                await telegram_scraper.stop_client()
                return True
            except Exception as e:
                print(f"❌ Session test failed: {e}")
                await telegram_scraper.stop_client()
                return False
        else:
            print("❌ Session is INVALID - authentication required")
            return False
            
    except TelegramRateLimitError as e:
        print(f"🚫 RATE LIMITED: {e}")
        return False
    except (TelegramSessionError, TelegramAuthError) as e:
        print(f"❌ Session is INVALID: {e}")
        return False
    except Exception as e:
        print(f"❌ Session test error: {e}")
        return False
    finally:
        # Always clean up session safety records
        try:
            safety.cleanup_session_access()
        except:
            pass

async def authenticate_telegram(force_renewal=False):
    """Perform Telegram authentication with optional forced renewal"""
    print("=" * 50)
    if force_renewal:
        print("🔄 TELEGRAM SESSION RENEWAL")
    else:
        print("🚀 TELEGRAM AUTHENTICATION SETUP")
    print("=" * 50)
    
    # SAFETY CHECK: Prevent session conflicts during authentication
    from src.integrations.session_safety import SessionSafetyManager, SessionSafetyError
    
    safety = SessionSafetyManager()
    try:
        safety.check_session_safety("telegram_authentication")
        print("✅ Session safety check passed - safe to authenticate")
        safety.record_session_access("telegram_authentication")
    except SessionSafetyError as e:
        print(str(e))
        print("\n💡 IMPORTANT: Authentication while workers are running")
        print("   can cause session invalidation and disconnect your phone!")
        return False
    
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
        
        # Backup existing session if renewal
        session_file = os.path.join(project_root, 'telegram_session.session')
        if os.path.exists(session_file):
            if force_renewal:
                # Create backup before removal
                try:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    backup_file = os.path.join(project_root, f'telegram_session_backup_{timestamp}.session')
                    import shutil
                    shutil.copy2(session_file, backup_file)
                    print(f"💾 Session backed up to: {os.path.basename(backup_file)}")
                except Exception as e:
                    print(f"⚠️  Warning: Could not backup session: {e}")
                
                print("🗑️  Removing existing session for renewal...")
            else:
                print("🗑️  Removing existing session file...")
            
            os.remove(session_file)
            
            # Also remove journal file if it exists
            journal_file = session_file + '-journal'
            if os.path.exists(journal_file):
                os.remove(journal_file)
        
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
        
        try:
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
                
        except TelegramRateLimitError as e:
            print(f"🚫 RATE LIMITED: {e}")
            print("⏰ You must wait for the rate limit to expire before authenticating")
            print("💡 Use 'python3 tests/check_telegram_status.py' to monitor the rate limit")
            return False
            
        except TelegramSessionError as e:
            print(f"🔐 SESSION ERROR: {e}")
            print("💡 This is normal during first-time authentication - please continue")
            return False
            
        except TelegramAuthError as e:
            print(f"🚨 AUTHENTICATION ERROR: {e}")
            
            error_msg = str(e)
            if "Invalid API" in error_msg:
                print("🔧 Issue: Invalid API credentials")
                print("💡 Solution: Double-check API_ID and API_HASH from https://my.telegram.org/apps")
            elif "phone number" in error_msg.lower():
                print("🔧 Issue: Invalid phone number format")
                print("💡 Solution: Ensure phone number includes country code (e.g., +639693532299)")
            else:
                print("💡 Check your API credentials and network connection")
            
            return False
            
        except Exception as auth_error:
            print(f"❌ Detailed authentication error: {auth_error}")
            print(f"❌ Error type: {type(auth_error).__name__}")
            
            # Common error scenarios for legacy errors
            error_str = str(auth_error)
            if "PHONE_NUMBER_INVALID" in error_str:
                print("🔧 Issue: Invalid phone number format")
                print("💡 Solution: Ensure phone number includes country code (e.g., +639693532299)")
            elif "API_ID_INVALID" in error_str:
                print("🔧 Issue: Invalid API_ID")
                print("💡 Solution: Double-check API_ID from https://my.telegram.org/apps")
            elif "API_HASH_INVALID" in error_str:
                print("🔧 Issue: Invalid API_HASH")
                print("💡 Solution: Double-check API_HASH from https://my.telegram.org/apps")
            elif "PHONE_CODE_EXPIRED" in error_str:
                print("🔧 Issue: SMS verification code expired")
                print("💡 Solution: Request a new code and try again quickly")
            elif "PHONE_CODE_INVALID" in error_str:
                print("🔧 Issue: Invalid SMS verification code")
                print("💡 Solution: Double-check the code from your SMS")
            elif "ConnectionError" in error_str or "TimeoutError" in error_str:
                print("🔧 Issue: Network connectivity problem")
                print("💡 Solution: Check internet connection and firewall settings")
            else:
                print("💡 General troubleshooting:")
                print("   - Verify API credentials at https://my.telegram.org/apps")
                print("   - Ensure phone number format is correct (+country_code_number)")
                print("   - Check if your IP is blocked by Telegram")
                print("   - Try using a VPN if in a restricted region")
            
            return False
            
    except Exception as e:
        print(f"❌ Error during authentication: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Always clean up session safety records
        try:
            safety.cleanup_session_access()
        except:
            pass

def safe_worker_stop():
    """Stop workers safely for session operations"""
    import subprocess
    try:
        result = subprocess.run(['./scripts/deploy_celery.sh', 'stop'], 
                              capture_output=True, text=True, cwd=project_root)
        return result.returncode == 0
    except Exception:
        return False

def safe_worker_start():
    """Start workers after session operations"""
    import subprocess
    try:
        result = subprocess.run(['./scripts/deploy_celery.sh', 'start'], 
                              capture_output=True, text=True, cwd=project_root)
        return result.returncode == 0
    except Exception:
        return False

def backup_session():
    """Create a backup of the current session"""
    session_file = os.path.join(project_root, 'telegram_session.session')
    if os.path.exists(session_file):
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = os.path.join(project_root, f'telegram_session_backup_{timestamp}.session')
            import shutil
            shutil.copy2(session_file, backup_file)
            print(f"💾 Session backed up to: {os.path.basename(backup_file)}")
            return backup_file
        except Exception as e:
            print(f"⚠️  Warning: Could not backup session: {e}")
            return None
    else:
        print("❌ No session file found to backup")
        return None

def main():
    parser = argparse.ArgumentParser(
        description='Telegram Authentication and Session Management',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/telegram_auth.py              # Original authentication (SMS required)
  python3 scripts/telegram_auth.py --status     # Check session status and age  
  python3 scripts/telegram_auth.py --test       # Test current session (no SMS)
  python3 scripts/telegram_auth.py --renew      # Safe session renewal (stops workers, SMS required)
  python3 scripts/telegram_auth.py --renew -y   # Renew without confirmation
  python3 scripts/telegram_auth.py --backup     # Backup current session
  python3 scripts/telegram_auth.py --safe-renew # Complete safe renewal workflow

Session Safety:
  All operations include session safety checks to prevent phone disconnection.
  Operations that could conflict with workers will be blocked with clear guidance.
        """
    )
    
    parser.add_argument('--status', action='store_true',
                       help='Show current session status and exit')
    parser.add_argument('--test', action='store_true',
                       help='Test current session validity and exit (no SMS needed)')
    parser.add_argument('--renew', action='store_true',
                       help='Force session renewal (removes existing session, SMS required)')
    parser.add_argument('--safe-renew', action='store_true',
                       help='Complete safe renewal workflow (stops workers, renews, restarts)')
    parser.add_argument('--backup', action='store_true',
                       help='Backup current session file and exit')
    parser.add_argument('-y', '--yes', action='store_true',
                       help='Skip confirmation prompts')
    parser.add_argument('--quiet', action='store_true',
                       help='Minimal output (for scripting)')
    
    args = parser.parse_args()
    
    # Handle backup
    if args.backup:
        backup_file = backup_session()
        return 0 if backup_file else 1
    
    # Handle status check
    if args.status:
        has_session = show_session_status()
        return 0 if has_session else 1
    
    # Handle session test
    if args.test:
        if not args.quiet:
            print("Testing Telegram session validity...")
        
        try:
            result = asyncio.run(test_session_validity())
            if result:
                if not args.quiet:
                    print("\n✅ Session is valid and working!")
                return 0
            else:
                if not args.quiet:
                    print("\n❌ Session is invalid - renewal required")
                return 1
        except Exception as e:
            if not args.quiet:
                print(f"\n❌ Session test failed: {e}")
            return 1
    
    # Handle safe renewal workflow
    if args.safe_renew:
        if not args.quiet:
            print("🛡️ Safe Session Renewal Workflow")
            print("================================")
            print("This will:")
            print("1. Stop Celery workers safely")
            print("2. Backup existing session")
            print("3. Renew session (SMS required)")
            print("4. Restart workers")
            print()
        
        # Check current session
        session_info = get_session_info()
        if session_info and not args.quiet:
            print(f"Current session age: {session_info['age_days']} days")
            print(f"Created: {session_info['created'].strftime('%Y-%m-%d %H:%M:%S')}")
            print()
        
        if not args.yes and not args.quiet:
            response = input("Proceed with safe renewal workflow? (y/n): ")
            if response.lower() != 'y':
                print("Safe renewal cancelled")
                return 0
        
        # Step 1: Stop workers
        if not args.quiet:
            print("1️⃣  Stopping Celery workers...")
        if not safe_worker_stop():
            if not args.quiet:
                print("⚠️  Warning: Could not stop workers cleanly")
                print("   Continuing with renewal anyway...")
        elif not args.quiet:
            print("✅ Workers stopped successfully")
        
        # Step 2: Perform renewal
        if not args.quiet:
            print("\n2️⃣  Starting session renewal...")
        
        try:
            result = asyncio.run(authenticate_telegram(force_renewal=True))
            
            if result:
                if not args.quiet:
                    print("✅ Session renewal completed!")
                
                # Step 3: Restart workers
                if not args.quiet:
                    print("\n3️⃣  Restarting Celery workers...")
                
                if safe_worker_start():
                    if not args.quiet:
                        print("✅ Workers restarted successfully")
                        print("\n🎉 Safe renewal workflow completed!")
                        print("✅ Your scraper is running with a fresh session")
                    return 0
                else:
                    if not args.quiet:
                        print("⚠️  Session renewed but failed to restart workers")
                        print("💡 Manually run: ./scripts/deploy_celery.sh start")
                    return 1
            else:
                if not args.quiet:
                    print("❌ Session renewal failed")
                    print("💡 Workers may still be stopped - check with: ./scripts/status.sh")
                return 1
        except Exception as e:
            if not args.quiet:
                print(f"❌ Safe renewal failed: {e}")
                print("💡 Workers may still be stopped - check with: ./scripts/status.sh")
            return 1
    
    # Handle renewal or initial authentication
    if args.renew:
        if not args.quiet:
            print("🔄 Telegram Session Renewal")
            print("This will invalidate your current session and create a new one.")
            print("⚠️  SMS verification code will be required!")
            print()
        
        # Check if session exists
        session_info = get_session_info()
        if session_info and not args.quiet:
            print(f"Current session age: {session_info['age_days']} days")
            print(f"Created: {session_info['created'].strftime('%Y-%m-%d %H:%M:%S')}")
            print()
        
        if not args.yes and not args.quiet:
            response = input("Proceed with session renewal? (y/n): ")
            if response.lower() != 'y':
                print("Session renewal cancelled")
                return 0
    else:
        # Original behavior - initial authentication
        if not args.quiet:
            print("This script will help you authenticate with Telegram")
            print("Make sure you have your phone nearby to receive SMS verification codes")
            print()
        
        if not args.yes and not args.quiet:
            response = input("Continue with authentication? (y/n): ")
            if response.lower() != 'y':
                print("Authentication cancelled")
                return 0
    
    # Perform authentication
    try:
        result = asyncio.run(authenticate_telegram(force_renewal=args.renew))
        
        if result:
            if not args.quiet:
                print()
                if args.renew:
                    print("🎉 Session renewal completed successfully!")
                    print("✅ Your scraper can now continue with a fresh session")
                else:
                    print("🎉 Authentication completed successfully!")
                    print("✅ You can now run: ./scripts/quick_start.sh")
            return 0
        else:
            if not args.quiet:
                print()
                print("💥 Authentication failed. Please check your configuration and try again.")
            return 1
            
    except KeyboardInterrupt:
        if not args.quiet:
            print("\n\n⏹️  Authentication cancelled by user")
        return 1
    except Exception as e:
        if not args.quiet:
            print(f"\n❌ Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())