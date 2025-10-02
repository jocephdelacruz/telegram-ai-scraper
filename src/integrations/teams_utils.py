import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

import requests
import json
from datetime import datetime
from src.core import log_handling as lh

LOG_FILE = "../../logs/teams.log"
LOG_TZ = "Asia/Manila"
LOGGER = lh.LogHandling(LOG_FILE, LOG_TZ)


class TeamsNotifier:
    def __init__(self, webhook_url, channel_name="Telegram Alerts"):
        """
        Initialize Teams notifier
        
        Args:
            webhook_url: Microsoft Teams webhook URL
            channel_name: Name of the channel for display purposes
        """
        try:
            self.webhook_url = webhook_url
            self.channel_name = channel_name
            LOGGER.writeLog("TeamsNotifier initialized successfully")
        except Exception as e:
            LOGGER.writeLog(f"TeamsNotifier initialization failed: {e}")
            raise

    def send_message(self, title, message, color="good", facts=None):
        """
        Send a basic message to Teams
        
        Args:
            title: Message title
            message: Message content
            color: Message color theme (good, warning, attention)
            facts: List of key-value pairs for additional information
            
        Returns:
            Boolean indicating success
        """
        try:
            payload = {
                "@type": "MessageCard",
                "@context": "http://schema.org/extensions",
                "themeColor": self._get_color_code(color),
                "summary": title,
                "sections": [{
                    "activityTitle": title,
                    "activitySubtitle": f"Channel: {self.channel_name}",
                    "text": message,
                    "facts": facts or []
                }]
            }

            response = requests.post(
                self.webhook_url,
                headers={'Content-Type': 'application/json'},
                data=json.dumps(payload),
                timeout=30
            )

            if response.status_code == 200:
                LOGGER.writeLog(f"Successfully sent message to Teams: {title}")
                return True
            else:
                LOGGER.writeLog(f"Failed to send message to Teams. Status: {response.status_code}, Response: {response.text}")
                return False

        except Exception as e:
            LOGGER.writeLog(f"Error sending message to Teams: {e}")
            return False

    def send_telegram_alert(self, message_data, ai_category="Significant", keywords_matched=None):
        """
        Send a formatted Telegram message alert to Teams
        
        Args:
            message_data: Dictionary containing message information
            ai_category: AI classification result
            keywords_matched: List of matched keywords
            
        Returns:
            Boolean indicating success
        """
        try:
            # Prepare the title
            title = f"🚨 Significant Telegram Message Alert"
            
            # Prepare message content
            message_text = message_data.get('Message_Text', 'No text content')
            if len(message_text) > 500:
                message_text = message_text[:500] + "..."

            # Prepare facts for structured information
            facts = [
                {"name": "Channel", "value": message_data.get('Channel', 'Unknown')},
                {"name": "Date & Time", "value": f"{message_data.get('Date', '')} {message_data.get('Time', '')}"},
                {"name": "Author", "value": message_data.get('Author', 'Unknown')},
                {"name": "AI Classification", "value": ai_category},
                {"name": "Message Type", "value": message_data.get('Message_Type', 'text')},
            ]

            # Add forward information if available
            if message_data.get('Forward_From'):
                facts.append({"name": "Forwarded From", "value": message_data.get('Forward_From')})

            # Add media type if available
            if message_data.get('Media_Type'):
                facts.append({"name": "Media Type", "value": message_data.get('Media_Type')})

            # Add matched keywords if available
            if keywords_matched:
                facts.append({"name": "Keywords Matched", "value": ", ".join(keywords_matched)})

            # Determine color based on significance
            color = "attention" if ai_category == "Significant" else "good"

            # Create the message
            full_message = f"**Message Content:**\n\n{message_text}"
            
            # Add message ID for reference
            if message_data.get('Message_ID'):
                full_message += f"\n\n*Message ID: {message_data.get('Message_ID')}*"

            return self.send_message(title, full_message, color, facts)

        except Exception as e:
            LOGGER.writeLog(f"Error sending Telegram alert to Teams: {e}")
            return False

    def send_system_alert(self, alert_type, message, details=None):
        """
        Send a system alert to Teams (e.g., errors, status updates)
        
        Args:
            alert_type: Type of alert ("ERROR", "WARNING", "INFO")
            message: Alert message
            details: Additional details dictionary
            
        Returns:
            Boolean indicating success
        """
        try:
            # Prepare title with emoji
            emoji_map = {
                "ERROR": "❌",
                "WARNING": "⚠️",
                "INFO": "ℹ️",
                "SUCCESS": "✅"
            }
            
            emoji = emoji_map.get(alert_type.upper(), "🔔")
            title = f"{emoji} Telegram Scraper {alert_type.title()}"

            # Prepare facts
            facts = [
                {"name": "Timestamp", "value": datetime.now().strftime('%Y-%m-%d %H:%M:%S')},
                {"name": "System", "value": "Telegram AI Scraper"}
            ]

            if details:
                for key, value in details.items():
                    facts.append({"name": key, "value": str(value)})

            # Determine color
            color_map = {
                "ERROR": "attention",
                "WARNING": "warning",
                "INFO": "good",
                "SUCCESS": "good"
            }
            color = color_map.get(alert_type.upper(), "good")

            return self.send_message(title, message, color, facts)

        except Exception as e:
            LOGGER.writeLog(f"Error sending system alert to Teams: {e}")
            return False

    def send_daily_summary(self, summary_data):
        """
        Send a daily summary of Telegram scraping activity
        
        Args:
            summary_data: Dictionary containing summary information
            
        Returns:
            Boolean indicating success
        """
        try:
            title = "📊 Daily Telegram Scraper Summary"
            
            # Extract summary information
            total_messages = summary_data.get('total_messages', 0)
            significant_messages = summary_data.get('significant_messages', 0)
            channels_monitored = summary_data.get('channels_monitored', 0)
            errors_encountered = summary_data.get('errors_encountered', 0)

            # Create message content
            message = f"Daily scraping activity completed for {datetime.now().strftime('%Y-%m-%d')}"

            # Prepare facts
            facts = [
                {"name": "Total Messages Processed", "value": str(total_messages)},
                {"name": "Significant Messages", "value": str(significant_messages)},
                {"name": "Channels Monitored", "value": str(channels_monitored)},
                {"name": "Errors Encountered", "value": str(errors_encountered)},
                {"name": "Success Rate", "value": f"{((total_messages - errors_encountered) / max(total_messages, 1) * 100):.1f}%"}
            ]

            # Add top keywords if available
            if 'top_keywords' in summary_data:
                facts.append({"name": "Top Keywords", "value": ", ".join(summary_data['top_keywords'])})

            return self.send_message(title, message, "good", facts)

        except Exception as e:
            LOGGER.writeLog(f"Error sending daily summary to Teams: {e}")
            return False

    def _get_color_code(self, color_name):
        """
        Convert color name to hex code for Teams
        
        Args:
            color_name: Color name (good, warning, attention)
            
        Returns:
            Hex color code
        """
        color_map = {
            "good": "28a745",      # Green
            "warning": "ffc107",   # Yellow
            "attention": "dc3545", # Red
            "info": "17a2b8"       # Blue
        }
        return color_map.get(color_name.lower(), "17a2b8")

    def test_connection(self):
        """
        Test the Teams webhook connection
        
        Returns:
            Boolean indicating success
        """
        try:
            test_message = {
                "@type": "MessageCard",
                "@context": "http://schema.org/extensions",
                "summary": "Connection Test",
                "text": "This is a test message from the Telegram AI Scraper system."
            }

            response = requests.post(
                self.webhook_url,
                headers={'Content-Type': 'application/json'},
                data=json.dumps(test_message),
                timeout=10
            )

            if response.status_code == 200:
                LOGGER.writeLog("Teams webhook connection test successful")
                return True
            else:
                LOGGER.writeLog(f"Teams webhook connection test failed. Status: {response.status_code}")
                return False

        except Exception as e:
            LOGGER.writeLog(f"Teams webhook connection test error: {e}")
            return False