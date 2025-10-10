import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from telethon import TelegramClient, events
from telethon.tl.types import PeerChannel, MessageMediaPhoto, MessageMediaDocument, MessageMediaWebPage
import json
from datetime import datetime
import asyncio
from src.core import log_handling as lh

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "telegram.log")
LOG_TZ = "Asia/Manila"
LOGGER = lh.LogHandling(LOG_FILE, LOG_TZ)


class TelegramScraper:
    def __init__(self, api_id, api_hash, phone_number, session_file="telegram_session"):
        """
        Initialize Telegram scraper
        
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
            # Don't create TelegramClient in __init__ to avoid event loop issues
            # Create it lazily when needed in async methods
            self.client = None
            self.monitored_channels = []
            self.message_handler = None
            LOGGER.writeLog("TelegramScraper initialized successfully")
        except Exception as e:
            LOGGER.writeLog(f"TelegramScraper initialization failed: {e}")
            raise

    def _ensure_client(self):
        """Ensure the Telegram client is created (lazy initialization)"""
        if self.client is None:
            try:
                self.client = TelegramClient(self.session_file, self.api_id, self.api_hash)
                LOGGER.writeLog("TelegramClient created successfully")
            except Exception as e:
                LOGGER.writeLog(f"Failed to create TelegramClient: {e}")
                raise
        return self.client

    async def start_client(self):
        """Start the Telegram client and authenticate if needed"""
        try:
            # Ensure client is created
            client = self._ensure_client()
            
            # More explicit authentication with better error handling
            await client.start(
                phone=lambda: self.phone_number,
                code_callback=self._code_callback,
                password=self._password_callback
            )
            LOGGER.writeLog("Telegram client started successfully")
            return True
        except Exception as e:
            LOGGER.writeLog(f"Failed to start Telegram client: {e}")
            # Re-raise the exception so the calling code can handle it with detailed messages
            raise e

    def _code_callback(self):
        """Callback for SMS verification code input"""
        try:
            code = input("Please enter the verification code sent to your phone: ")
            return code.strip()
        except KeyboardInterrupt:
            print("\n❌ Authentication cancelled by user")
            raise
        except Exception as e:
            print(f"❌ Error getting verification code: {e}")
            raise

    def _password_callback(self):
        """Callback for 2FA password input (if enabled)"""
        try:
            import getpass
            password = getpass.getpass("Please enter your 2FA password (if enabled): ")
            return password.strip()
        except KeyboardInterrupt:
            print("\n❌ Authentication cancelled by user")
            raise
        except Exception as e:
            print(f"❌ Error getting 2FA password: {e}")
            raise

    async def stop_client(self):
        """Stop the Telegram client"""
        try:
            if self.client:
                await self.client.disconnect()
                LOGGER.writeLog("Telegram client stopped successfully")
        except Exception as e:
            LOGGER.writeLog(f"Error stopping Telegram client: {e}")

    async def get_channel_entity(self, channel_username):
        """Get channel entity by username"""
        try:
            client = self._ensure_client()
            entity = await client.get_entity(channel_username)
            LOGGER.writeLog(f"Successfully retrieved entity for channel: {channel_username}")
            return entity
        except Exception as e:
            LOGGER.writeLog(f"Failed to get entity for channel {channel_username}: {e}")
            return None

    async def get_channel_messages(self, channel_username, limit=100):
        """
        Get recent messages from a channel
        
        Args:
            channel_username: Channel username (e.g., @channelname)
            limit: Number of messages to retrieve
            
        Returns:
            List of message dictionaries
        """
        try:
            entity = await self.get_channel_entity(channel_username)
            if not entity:
                return []

            client = self._ensure_client()
            messages = []
            message_count = 0
            async for message in client.iter_messages(entity, limit=limit):
                message_data = await self.parse_message(message, channel_username)
                if message_data:
                    messages.append(message_data)
                    # Log message preview for visibility
                    message_preview = (message_data.get('Message_Text', '') or '')[:20].replace('\n', ' ').strip()
                    if message_preview:
                        LOGGER.writeLog(f"Found message from {channel_username}: '{message_preview}...' (ID: {message_data.get('Message_ID', 'N/A')})")
                message_count += 1

            LOGGER.writeLog(f"Retrieved {len(messages)} valid messages from {channel_username} (checked {message_count} total)")
            return messages
        except Exception as e:
            LOGGER.writeLog(f"Failed to get messages from {channel_username}: {e}")
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

            message_data = {
                'Message_ID': message.id,
                'Channel': channel_username,
                'Date': message.date.strftime('%Y-%m-%d'),
                'Time': message.date.strftime('%H:%M:%S'),
                'Author': '',
                'Message_Text': message.text or '',
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

            return message_data
        except Exception as e:
            LOGGER.writeLog(f"Error parsing message {message.id}: {e}")
            return None

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
            client = self._ensure_client()
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

            client = self._ensure_client()
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