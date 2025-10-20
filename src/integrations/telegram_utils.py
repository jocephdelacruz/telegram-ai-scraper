import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from telethon import TelegramClient, events
from telethon.tl.types import PeerChannel, MessageMediaPhoto, MessageMediaDocument, MessageMediaWebPage
import json
import csv
import redis
from datetime import datetime, timedelta, timezone
import asyncio
from src.core import log_handling as lh
from .telegram_session_manager import TelegramSessionManager, TelegramRateLimitError, TelegramSessionError, TelegramAuthError


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "telegram.log")
LOG_TZ = "Asia/Manila"
LOGGER = lh.LogHandling(LOG_FILE, LOG_TZ)

# Maximum age for messages to be processed (4 hours in seconds)
MAX_MESSAGE_AGE_HOURS = 4
MAX_MESSAGE_AGE_SECONDS = MAX_MESSAGE_AGE_HOURS * 3600


class TelegramScraper:
    def __init__(self, api_id, api_hash, phone_number, session_file="telegram_session"):
        """
        Initialize Telegram scraper with advanced session management
        
        Args:
            api_id: Telegram API ID
            api_hash: Telegram API Hash
            phone_number: Phone number for authentication
            session_file: Session file name for persistent login
        """
        try:
            self.api_id = api_id
            self.api_hash = api_hash
            self.phone_number = phone_number
            self.session_file = session_file
            self._error_count = 0
            
            # Use advanced session manager instead of direct client management
            self.session_manager = TelegramSessionManager(api_id, api_hash, phone_number, session_file)
            self.client = None
            self.monitored_channels = []
            self.message_handler = None
            LOGGER.writeLog("TelegramScraper initialized successfully with advanced session management")
        except Exception as e:
            LOGGER.writeLog(f"TelegramScraper initialization failed: {e}")
            
            # Send critical exception to admin
            try:
                from .teams_utils import send_critical_exception
                send_critical_exception(
                    "TelegramInitializationError",
                    str(e),
                    "TelegramScraper.__init__",
                    additional_context={
                        "api_id": api_id,
                        "phone_number": phone_number[:3] + "***" if phone_number else None
                    }
                )
            except Exception as admin_error:
                LOGGER.writeLog(f"Failed to send Telegram initialization error to admin: {admin_error}")
            
            raise


    async def _ensure_client(self):
        """Ensure we have a working client connection with improved error handling"""
        try:
            self.client = await self.session_manager.get_client()
            return self.client
        except Exception as e:
            error_msg = str(e)
            LOGGER.writeLog(f"Failed to ensure Telegram client: {error_msg}")
            
            # The session manager already provides detailed error classification
            # Just re-raise the specific exception types
            raise


    async def start_client(self):
        """Start the Telegram client using the advanced session manager"""
        try:
            self.client = await self.session_manager.get_client()
            LOGGER.writeLog("Telegram client started successfully via session manager")
            return True
        except TelegramRateLimitError as e:
            LOGGER.writeLog(f"🚫 TELEGRAM RATE LIMITED: {e}")
            LOGGER.writeLog("⚠️  System will pause until rate limit expires. Use 'python3 tests/check_telegram_status.py' to monitor.")
            
            # Send rate limit alert to admin
            try:
                from .teams_utils import send_service_failure
                send_service_failure(
                    "Telegram API",
                    f"Rate limited: {str(e)}",
                    impact_level="HIGH",
                    recovery_action="Wait for rate limit to expire, then retry"
                )
            except Exception as admin_error:
                LOGGER.writeLog(f"Failed to send rate limit error to admin: {admin_error}")
            
            raise
        except TelegramSessionError as e:
            LOGGER.writeLog(f"🔐 SESSION ISSUE: {e}")
            LOGGER.writeLog("💡 Run 'python3 scripts/telegram_auth.py' to re-authenticate")
            
            # Send session error alert to admin
            try:
                from .teams_utils import send_service_failure
                send_service_failure(
                    "Telegram Session",
                    f"Session authentication failed: {str(e)}",
                    impact_level="HIGH",
                    recovery_action="Run 'python3 scripts/telegram_auth.py' to re-authenticate"
                )
            except Exception as admin_error:
                LOGGER.writeLog(f"Failed to send session error to admin: {admin_error}")
            
            raise
        except TelegramAuthError as e:
            LOGGER.writeLog(f"🚨 AUTH ERROR: {e}")
            LOGGER.writeLog("💡 Check your API credentials in config.json")
            
            # Send auth error alert to admin
            try:
                from .teams_utils import send_service_failure
                send_service_failure(
                    "Telegram Authentication",
                    f"Auth error: {str(e)}",
                    impact_level="CRITICAL",
                    recovery_action="Check API credentials in config.json"
                )
            except Exception as admin_error:
                LOGGER.writeLog(f"Failed to send auth error to admin: {admin_error}")
            
            raise
        except Exception as e:
            LOGGER.writeLog(f"❌ Unexpected error starting client: {e}")
            
            # Send critical exception to admin
            try:
                from .teams_utils import send_critical_exception
                send_critical_exception(
                    "TelegramClientStartError",
                    str(e),
                    "TelegramScraper.start_client"
                )
            except Exception as admin_error:
                LOGGER.writeLog(f"Failed to send client start error to admin: {admin_error}")
            
            raise


    async def stop_client(self):
        """Stop the Telegram client using the session manager"""
        try:
            await self.session_manager.close()
            self.client = None
            LOGGER.writeLog("Telegram client stopped successfully via session manager")
        except Exception as e:
            LOGGER.writeLog(f"Error stopping Telegram client: {e}")


    def get_session_status(self):
        """Get current session status information"""
        return self.session_manager.get_connection_status()


    def is_rate_limited(self):
        """Check if currently rate limited"""
        return self.session_manager.is_rate_limited()


    def get_rate_limit_info(self):
        """Get rate limit information"""
        return self.session_manager.get_rate_limit_info()


    async def health_check(self):
        """Perform a comprehensive health check"""
        return await self.session_manager.health_check()


    async def get_channel_entity(self, channel_username):
        """Get channel entity by username"""
        try:
            client = await self._ensure_client()
            entity = await client.get_entity(channel_username)
            LOGGER.writeLog(f"Successfully retrieved entity for channel: {channel_username}")
            return entity
        except Exception as e:
            LOGGER.writeLog(f"Failed to get entity for channel {channel_username}: {e}")
            return None


    async def get_channel_messages(self, channel_username, limit=10, cutoff_time=None, redis_client=None, log_found_messages=True):
        """
        Get recent messages from a channel with optional filtering
        
        Args:
            channel_username: Channel username (e.g., @channelname)
            limit: Number of messages to retrieve
            cutoff_time: Only return messages newer than this datetime (optional)
            redis_client: Redis client for duplicate detection (optional)
            log_found_messages: Whether to log found messages (default True for backward compatibility)
            
        Returns:
            List of message dictionaries (only new/valid messages if filters applied)
        """
        try:
            entity = await self.get_channel_entity(channel_username)
            if not entity:
                return []

            client = await self._ensure_client()
            messages = []
            message_count = 0
            new_messages = 0
            duplicate_count = 0
            old_messages = 0
            
            async for message in client.iter_messages(entity, limit=limit):
                message_data = await self.parse_message(message, channel_username)
                if message_data:
                    message_count += 1
                    message_id = message_data.get('Message_ID', '')
                    
                    # Apply duplicate detection if Redis client provided
                    if redis_client and message_id:
                        try:
                            duplicate_key = f"processed_msg:{channel_username}:{message_id}"
                            if redis_client.exists(duplicate_key):
                                duplicate_count += 1
                                continue  # Skip duplicates, don't log or add to results
                        except Exception as redis_error:
                            LOGGER.writeLog(f"Redis duplicate check failed for {channel_username}: {redis_error}")
                    
                    # Apply age filtering if cutoff_time provided
                    if cutoff_time:
                        # Use the stored UTC datetime for accurate comparison
                        message_datetime_utc = message_data.get('Datetime_UTC')
                        
                        if message_datetime_utc:
                            try:
                                # Both cutoff_time and message_datetime_utc should now be in UTC
                                # Ensure both have timezone info for proper comparison
                                from datetime import timezone
                                
                                # Ensure message datetime has timezone info
                                if message_datetime_utc.tzinfo is None:
                                    message_datetime_utc = message_datetime_utc.replace(tzinfo=timezone.utc)
                                
                                # Ensure cutoff time has timezone info  
                                if cutoff_time.tzinfo is None:
                                    cutoff_time = cutoff_time.replace(tzinfo=timezone.utc)
                                
                                if message_datetime_utc < cutoff_time:
                                    old_messages += 1
                                    continue  # Skip old messages, don't log or add to results
                            except Exception as e:
                                LOGGER.writeLog(f"Could not process message datetime from {channel_username}: {e}")
                                # If we can't process the datetime, include the message to be safe
                    
                    # Message passed all filters - add to results
                    messages.append(message_data)
                    new_messages += 1
                    
                    # Log message preview only if requested and message is new
                    if log_found_messages:
                        message_preview = (message_data.get('Message_Text', '') or '')[:20].replace('\n', ' ').strip()
                        if message_preview:
                            LOGGER.writeLog(f"Found NEW message from {channel_username}: '{message_preview}...' (ID: {message_data.get('Message_ID', 'N/A')})")

            # Provide summary based on filtering applied
            if cutoff_time or redis_client:
                # Detailed logging when filtering is applied
                if new_messages > 0:
                    LOGGER.writeLog(f"Retrieved {new_messages} NEW messages from {channel_username} (checked {message_count} total, skipped {duplicate_count} duplicates, {old_messages} too old)")
                else:
                    skip_reasons = []
                    if duplicate_count > 0:
                        skip_reasons.append(f"{duplicate_count} duplicates")
                    if old_messages > 0:
                        skip_reasons.append(f"{old_messages} too old")
                    if message_count == 0:
                        LOGGER.writeLog(f"No messages found in {channel_username}")
                    else:
                        reason_text = ", ".join(skip_reasons) if skip_reasons else "unknown reasons"
                        LOGGER.writeLog(f"No new messages from {channel_username} (checked {message_count} total, skipped: {reason_text})")
            else:
                # Simple logging for backward compatibility
                LOGGER.writeLog(f"Retrieved {len(messages)} valid messages from {channel_username} (checked {message_count} total)")
            
            return messages
        except Exception as e:
            LOGGER.writeLog(f"Failed to get messages from {channel_username}: {e}")
            self._error_count += 1
            
            # Send critical exception to admin for message retrieval failures
            if self._error_count % 10 == 0:  # Every 10th error
                try:
                    from .teams_utils import send_critical_exception
                    send_critical_exception(
                        "TelegramMessageRetrievalError",
                        str(e),
                        "TelegramScraper.get_channel_messages",
                        additional_context={
                            "channel": channel_username,
                            "limit": limit,
                            "total_errors": self._error_count
                        }
                    )
                except Exception as admin_error:
                    LOGGER.writeLog(f"Failed to send message retrieval error to admin: {admin_error}")
            
            return []


    async def parse_message(self, message, channel_username):
        """
        Parse a Telegram message into a structured format
        
        Args:
            message: Telegram message object
            channel_username: Channel username
            
        Returns:
            Dictionary with message data
        """
        try:
            # Skip empty messages
            if not message.text and not message.media:
                return None

            # Generate Telegram message URL
            # Format: https://t.me/channel_name/message_id (remove @ from channel)
            clean_channel = channel_username.lstrip('@')
            message_url = f"https://t.me/{clean_channel}/{message.id}"

            message_data = {
                'Message_ID': message.id,
                'Channel': channel_username,
                'Message_URL': message_url,
                'Date': message.date.strftime('%Y-%m-%d'),
                'Time': message.date.strftime('%H:%M:%S'),
                'Datetime_UTC': message.date,  # Store the original UTC datetime for accurate comparison
                'Author': '',
                'Message_Text': message.text or '',
                'Attached_Links': '',  # Will be populated below
                'AI_Category': '',
                'Keywords_Matched': '',
                'Message_Type': 'text',
                'Forward_From': '',
                'Media_Type': '',
                'Processed_Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            # Get author information
            if message.sender:
                if hasattr(message.sender, 'username') and message.sender.username:
                    message_data['Author'] = f"@{message.sender.username}"
                elif hasattr(message.sender, 'first_name'):
                    name = message.sender.first_name
                    if hasattr(message.sender, 'last_name') and message.sender.last_name:
                        name += f" {message.sender.last_name}"
                    message_data['Author'] = name
                elif hasattr(message.sender, 'title'):
                    message_data['Author'] = message.sender.title

            # Check if message is forwarded
            if message.forward:
                if message.forward.from_name:
                    message_data['Forward_From'] = message.forward.from_name
                elif message.forward.chat:
                    message_data['Forward_From'] = message.forward.chat.title or str(message.forward.chat.id)

            # Determine message type and media
            if message.media:
                if isinstance(message.media, MessageMediaPhoto):
                    message_data['Message_Type'] = 'photo'
                    message_data['Media_Type'] = 'photo'
                elif isinstance(message.media, MessageMediaDocument):
                    message_data['Message_Type'] = 'document'
                    message_data['Media_Type'] = 'document'
                    if message.media.document.mime_type:
                        if 'video' in message.media.document.mime_type:
                            message_data['Media_Type'] = 'video'
                        elif 'audio' in message.media.document.mime_type:
                            message_data['Media_Type'] = 'audio'
                elif isinstance(message.media, MessageMediaWebPage):
                    message_data['Message_Type'] = 'webpage'
                    message_data['Media_Type'] = 'webpage'
                    # Add webpage URL to message text if available
                    if message.media.webpage.url:
                        message_data['Message_Text'] += f"\n\nURL: {message.media.webpage.url}"

            # Extract attached links using dedicated function with comprehensive duplicate prevention
            message_data['Attached_Links'] = self._extract_attached_links(message)

            return message_data
        except Exception as e:
            LOGGER.writeLog(f"Error parsing message {message.id}: {e}")
            return None


    def _extract_attached_links(self, message):
        """
        Extract all attached links from a Telegram message using multiple methods
        with comprehensive duplicate prevention
        
        Args:
            message: Telegram message object
            
        Returns:
            str: Comma-separated string of unique URLs, or empty string if none found
        """
        try:
            # Use a set to automatically prevent duplicates during collection
            links_set = set()
            
            # 1. Enhanced extraction from message entities (URLs, text links)
            if hasattr(message, 'entities') and message.entities:
                for entity in message.entities:
                    try:
                        # URL entities (plain text URLs) - extract from message text using offset/length
                        if entity.__class__.__name__ == 'MessageEntityUrl':
                            if message.text and hasattr(entity, 'offset') and hasattr(entity, 'length'):
                                url_text = message.text[entity.offset:entity.offset + entity.length]
                                if url_text and len(url_text) > 4:
                                    links_set.add(url_text.strip())
                        # Text link entities (hyperlinked text) - get URL from entity
                        elif entity.__class__.__name__ == 'MessageEntityTextUrl':
                            if hasattr(entity, 'url') and entity.url:
                                links_set.add(entity.url.strip())
                        # Fallback for entities with direct URL attribute
                        elif hasattr(entity, 'url') and entity.url:
                            links_set.add(entity.url.strip())
                    except Exception as entity_error:
                        LOGGER.writeLog(f"Error processing entity in message {message.id}: {entity_error}")
                        continue
            
            # 2. Extract URLs from webpage media
            if message.media and isinstance(message.media, MessageMediaWebPage):
                if hasattr(message.media.webpage, 'url') and message.media.webpage.url:
                    links_set.add(message.media.webpage.url.strip())
                
                # Also check for embedded URLs in webpage content
                if hasattr(message.media.webpage, 'description') and message.media.webpage.description:
                    import re
                    # Extract URLs from webpage description
                    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
                    description_urls = re.findall(url_pattern, message.media.webpage.description)
                    for url in description_urls:
                        if len(url) > 4:
                            links_set.add(url.strip())
            
            # 3. Extract URLs from document attributes (avoid file download URLs)
            if message.media and isinstance(message.media, MessageMediaDocument):
                document = message.media.document
                
                # Check document attributes for public URLs (not download URLs)
                if hasattr(document, 'attributes') and document.attributes:
                    for attr in document.attributes:
                        try:
                            # Look for URL attributes that don't require authentication
                            if hasattr(attr, 'url') and attr.url:
                                # Skip if it looks like a file download URL that needs auth
                                if not any(skip_term in attr.url.lower() for skip_term in ['download', 'file_id', 'access_token']):
                                    links_set.add(attr.url.strip())
                        except Exception as attr_error:
                            continue
            
            # 4. Regex extraction for URLs missed by entities (backup method)
            if message.text:
                import re
                # Comprehensive URL regex pattern
                url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
                text_urls = re.findall(url_pattern, message.text)
                for url in text_urls:
                    if len(url) > 4:
                        links_set.add(url.strip())
                
                # Also look for common URL patterns without http/https
                domain_pattern = r'(?:www\.)?[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}'
                domain_matches = re.findall(domain_pattern, message.text)
                for domain in domain_matches:
                    # Add protocol if missing and it looks like a valid domain
                    if '.' in domain and len(domain) > 4:
                        full_url = f"https://{domain}"
                        # Only add if not already covered by a full URL
                        domain_already_covered = any(domain in existing_url for existing_url in links_set)
                        if not domain_already_covered:
                            links_set.add(full_url)
            
            # 5. Clean up URLs and apply final deduplication with normalization
            cleaned_links = []
            for link in links_set:
                if link and len(link) > 4:
                    # Remove trailing punctuation that might be captured
                    cleaned_link = link.rstrip('.,;!?)')
                    
                    # Normalize URLs for better duplicate detection
                    normalized = cleaned_link.lower()
                    
                    # Check if this normalized URL is already in our final list
                    already_exists = any(
                        existing.lower() == normalized or 
                        existing.lower().rstrip('/') == normalized.rstrip('/') or
                        normalized in existing.lower() or 
                        existing.lower() in normalized
                        for existing in cleaned_links
                    )
                    
                    if not already_exists:
                        cleaned_links.append(cleaned_link)
            
            # Sort links for consistent output
            cleaned_links.sort()
            
            # Return comma-separated string
            return ', '.join(cleaned_links) if cleaned_links else ''
            
        except Exception as e:
            LOGGER.writeLog(f"Error extracting links from message {getattr(message, 'id', 'unknown')}: {e}")
            return ''


    def set_message_handler(self, handler_function):
        """Set a custom message handler function"""
        self.message_handler = handler_function


    async def start_monitoring(self, channels):
        """
        Start monitoring specified channels for new messages
        
        Args:
            channels: List of channel usernames to monitor
        """
        try:
            self.monitored_channels = channels
            
            # Get channel entities
            channel_entities = []
            for channel in channels:
                entity = await self.get_channel_entity(channel)
                if entity:
                    channel_entities.append(entity)
                    LOGGER.writeLog(f"Added channel {channel} to monitoring list")

            if not channel_entities:
                LOGGER.writeLog("No valid channels found for monitoring")
                return

            # Set up event handler for new messages
            client = await self._ensure_client()
            @client.on(events.NewMessage(chats=channel_entities))
            async def handle_new_message(event):
                try:
                    channel_username = None
                    # Find which channel this message came from
                    for channel in channels:
                        try:
                            entity = await self.get_channel_entity(channel)
                            if entity and entity.id == event.chat_id:
                                channel_username = channel
                                break
                        except:
                            continue

                    if not channel_username:
                        channel_username = f"Channel_{event.chat_id}"

                    message_data = await self.parse_message(event.message, channel_username)
                    if message_data and self.message_handler:
                        await self.message_handler(message_data)
                        
                except Exception as e:
                    LOGGER.writeLog(f"Error handling new message: {e}")

            LOGGER.writeLog(f"Started monitoring {len(channel_entities)} channels")
            
            # Keep the client running
            await client.run_until_disconnected()
            
        except Exception as e:
            LOGGER.writeLog(f"Error starting channel monitoring: {e}")
            
            # Send critical exception to admin for monitoring failures
            try:
                from .teams_utils import send_critical_exception
                send_critical_exception(
                    "TelegramMonitoringError",
                    str(e),
                    "TelegramScraper.start_monitoring",
                    additional_context={
                        "channels": channels,
                        "monitored_channels_count": len(self.monitored_channels)
                    }
                )
            except Exception as admin_error:
                LOGGER.writeLog(f"Failed to send monitoring error to admin: {admin_error}")


    async def get_channel_info(self, channel_username):
        """Get information about a channel"""
        try:
            entity = await self.get_channel_entity(channel_username)
            if not entity:
                return None

            info = {
                'id': entity.id,
                'title': entity.title,
                'username': entity.username,
                'participants_count': getattr(entity, 'participants_count', 0),
                'description': getattr(entity, 'about', ''),
                'verified': getattr(entity, 'verified', False),
                'restricted': getattr(entity, 'restricted', False)
            }
            
            LOGGER.writeLog(f"Retrieved info for channel: {channel_username}")
            return info
        except Exception as e:
            LOGGER.writeLog(f"Failed to get info for channel {channel_username}: {e}")
            return None


    async def search_messages(self, channel_username, query, limit=50):
        """
        Search for messages containing specific text in a channel
        
        Args:
            channel_username: Channel username
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of matching messages
        """
        try:
            entity = await self.get_channel_entity(channel_username)
            if not entity:
                return []

            client = await self._ensure_client()
            messages = []
            async for message in client.iter_messages(entity, search=query, limit=limit):
                message_data = await self.parse_message(message, channel_username)
                if message_data:
                    messages.append(message_data)

            LOGGER.writeLog(f"Found {len(messages)} messages matching '{query}' in {channel_username}")
            return messages
        except Exception as e:
            LOGGER.writeLog(f"Failed to search messages in {channel_username}: {e}")
            return []


    async def get_channel_messages_with_tracking(self, channel_username, config=None, redis_client=None, log_found_messages=True):
        """
        I'M NO LONGER USING THIS METHOD SINCE IT CAUSES THE TELEGRAM SESSION TO EXPIRE, PARTICULARLY WHEN THE PROJECT WAS NOT RUN FOR A WHILE.
        
        Efficient message fetching with Redis tracking and CSV fallback
        
        This method implements optimized message fetching that:
        1. Uses Redis to track the last processed message ID per channel
        2. Falls back to CSV files to determine last processed ID when Redis is unavailable
        3. Only fetches messages newer than the last processed ID
        4. Respects the 4-hour maximum message age limit
        5. Minimizes Telegram API calls to avoid rate limiting
        
        Args:
            channel_username: Channel username (e.g., @channelname)
            config: Configuration dictionary containing country-specific settings
            redis_client: Redis client instance for tracking (optional)
            log_found_messages: Whether to log found messages (default True)
            
        Returns:
            List of new message dictionaries that need processing
        """
        try:
            # Initialize tracking variables
            new_messages = 0
            skipped_old = 0
            skipped_processed = 0
            total_checked = 0
            
            # Step 1: Determine the minimum message ID to fetch (last processed + 1)
            last_processed_id = await self._get_last_processed_message_id(
                channel_username, config, redis_client
            )
            
            if last_processed_id:
                LOGGER.writeLog(f"🔍 Last processed message ID for {channel_username}: {last_processed_id}")
                min_id = last_processed_id  # Fetch messages newer than this ID
            else:
                LOGGER.writeLog(f"🆕 No tracking data found for {channel_username}, using 4-hour age limit")
                min_id = None  # Will use age-based filtering only
            
            # Step 2: Calculate 4-hour age cutoff (absolute maximum)
            age_cutoff = datetime.now(timezone.utc) - timedelta(seconds=MAX_MESSAGE_AGE_SECONDS)
            LOGGER.writeLog(f"⏰ Age cutoff: {age_cutoff.strftime('%Y-%m-%d %H:%M:%S')} UTC (4 hours ago)")
            
            # Step 3: Get channel entity
            entity = await self.get_channel_entity(channel_username)
            if not entity:
                LOGGER.writeLog(f"❌ Cannot get entity for {channel_username}")
                return []
            
            client = await self._ensure_client()
            messages = []
            
            # Step 4: Fetch messages efficiently
            if min_id:
                # Efficient: Fetch only messages newer than last processed ID
                LOGGER.writeLog(f"📥 Fetching messages from {channel_username} newer than ID {min_id}")
                async for message in client.iter_messages(entity, min_id=min_id):
                    total_checked += 1
                    
                    # Skip if message is too old (4-hour absolute limit)
                    if message.date < age_cutoff:
                        skipped_old += 1
                        continue
                    
                    # Parse and add the message
                    message_data = await self.parse_message(message, channel_username)
                    if message_data:
                        # Check for duplicates using Redis if available
                        if redis_client:
                            message_id = message_data.get('Message_ID', '')
                            duplicate_key = f"processed_msg:{channel_username}:{message_id}"
                            try:
                                if redis_client.exists(duplicate_key):
                                    skipped_processed += 1
                                    continue
                            except Exception as redis_error:
                                LOGGER.writeLog(f"Redis duplicate check failed: {redis_error}")
                        
                        messages.append(message_data)
                        new_messages += 1
                        
                        if log_found_messages:
                            self._log_new_message(message_data, channel_username)
            else:
                # Final fallback: Use original fetch interval method when no tracking data available
                # This prevents massive duplication when both Redis and CSV are unavailable
                fetch_interval_seconds = 240  # Default fallback
                fetch_message_limit = 10      # Default fallback
                
                # Try to get config values if available
                if config:
                    telegram_config = config.get('TELEGRAM_CONFIG', {})
                    fetch_interval_seconds = telegram_config.get('FETCH_INTERVAL_SECONDS', 240) 
                    fetch_message_limit = telegram_config.get('FETCH_MESSAGE_LIMIT', 10)
                
                # Calculate conservative cutoff based on fetch interval
                conservative_cutoff = datetime.now(timezone.utc) - timedelta(seconds=fetch_interval_seconds + 30)
                
                LOGGER.writeLog(f"⚠️  No tracking data for {channel_username}, using conservative fetch (limit: {fetch_message_limit}, age: {fetch_interval_seconds}s)")
                LOGGER.writeLog(f"📅 Conservative cutoff: {conservative_cutoff.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                
                async for message in client.iter_messages(entity, limit=fetch_message_limit):
                    total_checked += 1
                    
                    # Skip if message is older than conservative cutoff (fetch interval based)
                    if message.date < conservative_cutoff:
                        skipped_old += 1
                        continue
                    
                    # Parse and add the message
                    message_data = await self.parse_message(message, channel_username)
                    if message_data:
                        # Check for duplicates using Redis if available
                        if redis_client:
                            message_id = message_data.get('Message_ID', '')
                            duplicate_key = f"processed_msg:{channel_username}:{message_id}"
                            try:
                                if redis_client.exists(duplicate_key):
                                    skipped_processed += 1
                                    continue
                            except Exception as redis_error:
                                LOGGER.writeLog(f"Redis duplicate check failed: {redis_error}")
                        
                        messages.append(message_data)
                        new_messages += 1
                        
                        if log_found_messages:
                            self._log_new_message(message_data, channel_username)
            
            # Step 5: Update Redis tracking with the newest message ID
            if messages and redis_client:
                await self._update_last_processed_id(
                    channel_username, messages, redis_client
                )
            
            # Step 6: Log summary
            if new_messages > 0:
                LOGGER.writeLog(
                    f"✅ Retrieved {new_messages} NEW messages from {channel_username} "
                    f"(checked {total_checked}, skipped {skipped_old} too old, {skipped_processed} already processed)"
                )
            else:
                skip_reasons = []
                if skipped_old > 0:
                    skip_reasons.append(f"{skipped_old} too old")
                if skipped_processed > 0:
                    skip_reasons.append(f"{skipped_processed} already processed")
                
                if total_checked == 0:
                    LOGGER.writeLog(f"📭 No messages found in {channel_username}")
                else:
                    reason_text = ", ".join(skip_reasons) if skip_reasons else "unknown reasons"
                    LOGGER.writeLog(
                        f"📭 No new messages from {channel_username} "
                        f"(checked {total_checked}, skipped: {reason_text})"
                    )
            
            return messages
            
        except Exception as e:
            LOGGER.writeLog(f"❌ Error in efficient message fetch from {channel_username}: {e}")
            self._error_count += 1
            
            # Send critical exception to admin for tracking failures
            if self._error_count % 10 == 0:
                try:
                    from .teams_utils import send_critical_exception
                    send_critical_exception(
                        "EfficientMessageFetchError",
                        str(e),
                        "TelegramScraper.get_channel_messages_with_tracking",
                        additional_context={
                            "channel": channel_username,
                            "total_errors": self._error_count,
                            "has_redis": redis_client is not None
                        }
                    )
                except Exception as admin_error:
                    LOGGER.writeLog(f"Failed to send tracking error to admin: {admin_error}")
            
            return []


    async def _get_last_processed_message_id(self, channel_username, config, redis_client):
        """
        Get the last processed message ID for a channel from Redis or CSV fallback
        
        Priority order:
        1. Redis tracking data
        2. Latest message ID from CSV files (significant + trivial)
        3. None (use age-based filtering only)
        
        Returns:
            int: Last processed message ID, or None if no tracking data
        """
        try:
            # Option 1: Try Redis first
            if redis_client:
                try:
                    redis_key = f"last_processed:{channel_username}"
                    last_id_bytes = redis_client.get(redis_key)
                    if last_id_bytes:
                        last_id = int(last_id_bytes.decode('utf-8'))
                        LOGGER.writeLog(f"🔍 Found Redis tracking for {channel_username}: {last_id}")
                        return last_id
                except Exception as redis_error:
                    LOGGER.writeLog(f"Redis lookup failed for {channel_username}: {redis_error}")
            
            # Option 2: CSV fallback - check both significant and trivial files
            if config:
                countries = config.get('COUNTRIES', {})
                for country_code, country_info in countries.items():
                    channels = country_info.get('channels', [])
                    if channel_username in channels:
                        LOGGER.writeLog(f"📁 Checking CSV fallback for {channel_username} ({country_code})")
                        
                        csv_last_id = await self._get_last_id_from_csv(channel_username, country_code)
                        if csv_last_id:
                            LOGGER.writeLog(f"📄 Found CSV tracking for {channel_username}: {csv_last_id}")
                            
                            # Update Redis with this ID for future use
                            if redis_client:
                                try:
                                    redis_key = f"last_processed:{channel_username}"
                                    redis_client.setex(redis_key, 86400, str(csv_last_id))  # 24 hours
                                    LOGGER.writeLog(f"💾 Updated Redis tracking for {channel_username}")
                                except Exception as redis_error:
                                    LOGGER.writeLog(f"Failed to update Redis tracking: {redis_error}")
                            
                            return csv_last_id
                        break
            
            # Option 3: No tracking data found
            LOGGER.writeLog(f"🔍 No tracking data found for {channel_username}")
            return None
            
        except Exception as e:
            LOGGER.writeLog(f"Error getting last processed ID for {channel_username}: {e}")
            return None


    async def _get_last_id_from_csv(self, channel_username, country_code):
        """
        Get the highest message ID for a channel from CSV files
        
        Checks both significant and trivial CSV files and returns the highest ID found
        
        Returns:
            int: Highest message ID found, or None if no data
        """
        try:
            data_dir = os.path.join(PROJECT_ROOT, "data")
            highest_id = None
            
            # Check both significant and trivial CSV files
            csv_files = [
                f"{country_code}_significant_messages.csv",
                f"{country_code}_trivial_messages.csv"
            ]
            
            for csv_file in csv_files:
                csv_path = os.path.join(data_dir, csv_file)
                
                if not os.path.exists(csv_path):
                    continue
                
                try:
                    with open(csv_path, 'r', encoding='utf-8') as file:
                        reader = csv.DictReader(file)
                        
                        for row in reader:
                            # Check if this row is from our channel
                            row_channel = row.get('Channel', '')
                            if row_channel == channel_username:
                                try:
                                    message_id = int(row.get('Message_ID', 0))
                                    if highest_id is None or message_id > highest_id:
                                        highest_id = message_id
                                except (ValueError, TypeError):
                                    continue
                
                except Exception as file_error:
                    LOGGER.writeLog(f"Error reading CSV file {csv_file}: {file_error}")
                    continue
            
            if highest_id:
                LOGGER.writeLog(f"📊 Highest message ID in CSV for {channel_username}: {highest_id}")
            
            return highest_id
            
        except Exception as e:
            LOGGER.writeLog(f"Error checking CSV files for {channel_username}: {e}")
            return None


    async def _update_last_processed_id(self, channel_username, messages, redis_client):
        """
        Update Redis with the highest message ID from the processed messages
        
        Args:
            channel_username: Channel username
            messages: List of processed messages
            redis_client: Redis client instance
        """
        try:
            if not messages or not redis_client:
                return
            
            # Find the highest message ID
            highest_id = 0
            for message in messages:
                message_id = message.get('Message_ID', 0)
                if isinstance(message_id, int) and message_id > highest_id:
                    highest_id = message_id
            
            if highest_id > 0:
                redis_key = f"last_processed:{channel_username}"
                redis_client.setex(redis_key, 86400, str(highest_id))  # 24 hours expiry
                LOGGER.writeLog(f"💾 Updated Redis tracking for {channel_username}: {highest_id}")
            
        except Exception as e:
            LOGGER.writeLog(f"Error updating Redis tracking for {channel_username}: {e}")


    def _log_new_message(self, message_data, channel_username):
        """Helper method to log new message details"""
        try:
            message_id = message_data.get('Message_ID', 'N/A')
            message_preview = (message_data.get('Message_Text', '') or '')[:30].replace('\n', ' ').strip()
            message_date = message_data.get('Date', '')
            message_time = message_data.get('Time', '')
            
            if message_preview:
                date_info = f"({message_date} {message_time})" if message_date and message_time else ""
                LOGGER.writeLog(
                    f"📨 NEW message {message_id} from {channel_username}: '{message_preview}...' {date_info}"
                )
            
        except Exception as e:
            LOGGER.writeLog(f"Error logging message details: {e}")
