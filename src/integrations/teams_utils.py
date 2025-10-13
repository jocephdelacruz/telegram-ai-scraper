import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

import requests
import json
from datetime import datetime
from src.core import log_handling as lh

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "teams.log")
LOG_TZ = "Asia/Manila"
LOGGER = lh.LogHandling(LOG_FILE, LOG_TZ)


class TeamsNotifier:
    def __init__(self, webhook_url, channel_name="Telegram Alerts", system_name="Aldebaran Scraper"):
        """
        Initialize Teams notifier
        
        Args:
            webhook_url: Microsoft Teams webhook URL
            channel_name: Name of the channel for display purposes
            system_name: Name of the system sending alerts (replaces "Unknown user")
        """
        try:
            self.webhook_url = webhook_url
            self.channel_name = channel_name
            self.system_name = system_name
            LOGGER.writeLog(f"TeamsNotifier initialized successfully as '{system_name}'")
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
                "originator": self.system_name,
                "sections": [{
                    "activityTitle": title,
                    "activitySubtitle": f"Source: {self.system_name} | Channel: {self.channel_name}",
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

    def _load_excluded_teams_fields(self):
        """
        Load excluded teams fields from config.json
        
        Returns:
            List of field names to exclude from Teams notifications
        """
        try:
            import os
            import json
            
            # Get project root directory
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            config_path = os.path.join(project_root, "config", "config.json")
            
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                return config.get('EXCLUDED_TEAMS_FIELDS', [])
            else:
                LOGGER.writeLog(f"Config file not found: {config_path}")
                return []
                
        except Exception as e:
            LOGGER.writeLog(f"Error loading excluded teams fields from config: {e}")
            return []

    def send_message_alert(self, message_data):
        """
        Send a formatted Telegram message alert to Teams with country support
        
        Args:
            message_data: Dictionary containing message information
            
        Returns:
            Boolean indicating success
        """
        try:
            # Extract data
            country_name = message_data.get('country_name', message_data.get('Country', 'Unknown'))
            ai_category = message_data.get('AI_Category', 'Significant')
            ai_reasoning = message_data.get('AI_Reasoning', 'No reasoning provided')
            
            # Prepare the title with country flag
            country_flag = self._get_country_flag(country_name)
            title = f"{country_flag} 🚨 Significant Telegram Message - {country_name}"
            
            # Prepare message content
            message_text = message_data.get('Message_Text', message_data.get('text', 'No text content'))
            if len(message_text) > 500:
                message_text = message_text[:500] + "..."

            # Load excluded fields from config
            excluded_fields = self._load_excluded_teams_fields()
            
            # Prepare facts for structured information (excluding fields specified in config)
            facts = []
            
            # Always include basic message information
            if 'Channel' not in excluded_fields:
                facts.append({"name": "Channel", "value": message_data.get('Channel', message_data.get('channel', 'Unknown'))})
            
            facts.append({"name": "Date & Time", "value": f"{message_data.get('Date', '')} {message_data.get('Time', '')}"})
            
            if 'Author' not in excluded_fields:
                facts.append({"name": "Author", "value": message_data.get('Author', 'Unknown')})
            
            facts.append({"name": "AI Reasoning", "value": ai_reasoning[:200] + "..." if len(ai_reasoning) > 200 else ai_reasoning})

            # Add matched keywords if available
            keywords = message_data.get('Keywords_Matched', '')
            if keywords:
                facts.append({"name": "Keywords Matched", "value": keywords})

            # Add Country information if not excluded (processing preserved)
            if 'Country' not in excluded_fields and message_data.get('Country'):
                facts.append({"name": "Country", "value": message_data.get('Country')})

            # Add AI Category information if not excluded (processing preserved)
            if 'AI_Category' not in excluded_fields and message_data.get('AI_Category'):
                facts.append({"name": "AI Category", "value": message_data.get('AI_Category')})

            # Add Message Type information if not excluded (processing preserved)
            if 'Message_Type' not in excluded_fields and message_data.get('Message_Type'):
                facts.append({"name": "Message Type", "value": message_data.get('Message_Type')})

            # Add Forward From information if not excluded (processing preserved)
            if 'Forward_From' not in excluded_fields and message_data.get('Forward_From'):
                facts.append({"name": "Forwarded From", "value": message_data.get('Forward_From')})

            # Add Media Type information if not excluded (processing preserved)
            if 'Media_Type' not in excluded_fields and message_data.get('Media_Type'):
                facts.append({"name": "Media Type", "value": message_data.get('Media_Type')})

            # Add translation information if available (processing preserved)
            if message_data.get('Was_Translated'):
                original_language = message_data.get('Original_Language', 'Unknown')
                facts.append({"name": "Original Language", "value": original_language})
                
                if 'Was_Translated' not in excluded_fields:
                    facts.append({"name": "Translation", "value": "✅ Translated to English"})

            # Add Processed Date information if not excluded (processing preserved)
            if 'Processed_Date' not in excluded_fields and message_data.get('Processed_Date'):
                facts.append({"name": "Processed Date", "value": message_data.get('Processed_Date')})

            # Create the message
            message_content_header = "**Message Content (English):**" if message_data.get('Was_Translated') else "**Message Content:**"
            full_message = f"{message_content_header}\n\n{message_text}"
            
            # If translated, also show original text (truncated)
            if message_data.get('Was_Translated') and message_data.get('Original_Text'):
                original_text = message_data.get('Original_Text', '')
                if len(original_text) > 300:
                    original_text = original_text[:300] + "..."
                full_message += f"\n\n**Original Text ({message_data.get('Original_Language', 'Unknown')}):**\n{original_text}"
            
            # Add message ID for reference
            message_id = message_data.get('Message_ID', message_data.get('id', ''))
            if message_id:
                full_message += f"\n\n*Message ID: {message_id}*"

            return self.send_message(title, full_message, "attention", facts)

        except Exception as e:
            LOGGER.writeLog(f"Error sending Telegram alert to Teams: {e}")
            return False

    def send_telegram_alert(self, message_data, ai_category="Significant", keywords_matched=None):
        """
        Legacy method - redirects to send_message_alert for backward compatibility
        """
        return self.send_message_alert(message_data)

    def _get_country_flag(self, country_name):
        """Get emoji flag for country"""
        flag_map = {
            "Philippines": "🇵🇭",
            "Singapore": "🇸🇬", 
            "Malaysia": "🇲🇾",
            "Thailand": "🇹🇭",
            "Indonesia": "🇮🇩",
            "Vietnam": "🇻🇳",
            "Unknown": "🌏",
            "unknown": "🌏"
        }
        return flag_map.get(country_name, "🌏")

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
            title = f"{emoji} {self.system_name} {alert_type.title()}"

            # Prepare facts
            facts = [
                {"name": "Timestamp", "value": datetime.now().strftime('%Y-%m-%d %H:%M:%S')},
                {"name": "System", "value": self.system_name}
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
                "summary": f"{self.system_name} - Connection Test",
                "originator": self.system_name,
                "text": f"This is a test message from {self.system_name}."
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


class AdminTeamsNotifier:
    """
    Specialized Teams notifier for admin alerts and critical system notifications.
    This class handles all critical exceptions, system failures, and administrative alerts.
    """
    
    def __init__(self, webhook_url, channel_name="Admin Alerts", system_name="Aldebaran Scraper"):
        """
        Initialize Admin Teams notifier for critical system alerts
        
        Args:
            webhook_url: Microsoft Teams webhook URL for admin channel
            channel_name: Name of the admin channel for display purposes
            system_name: Name of the system sending alerts
        """
        try:
            self.webhook_url = webhook_url
            self.channel_name = channel_name
            self.system_name = system_name
            LOGGER.writeLog(f"AdminTeamsNotifier initialized successfully for '{channel_name}'")
        except Exception as e:
            LOGGER.writeLog(f"AdminTeamsNotifier initialization failed: {e}")
            raise

    def send_critical_exception(self, exception_type, exception_message, module_name, stack_trace=None, additional_context=None):
        """
        Send critical exception notification to admin channel
        
        Args:
            exception_type: Type of exception (e.g., "ConnectionError", "DatabaseError")
            exception_message: Exception message
            module_name: Name of the module where exception occurred
            stack_trace: Full stack trace (optional)
            additional_context: Additional context dictionary (optional)
            
        Returns:
            Boolean indicating success
        """
        try:
            title = f"🚨 CRITICAL EXCEPTION - {exception_type}"
            
            # Prepare the main message
            message = f"**Module:** {module_name}\n\n**Exception:** {exception_message}"
            
            # Add stack trace if provided (truncated for readability)
            if stack_trace:
                truncated_trace = stack_trace[:1000] + "..." if len(stack_trace) > 1000 else stack_trace
                message += f"\n\n**Stack Trace:**\n```\n{truncated_trace}\n```"

            # Prepare facts for structured information
            facts = [
                {"name": "Timestamp", "value": datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')},
                {"name": "System", "value": self.system_name},
                {"name": "Module", "value": module_name},
                {"name": "Exception Type", "value": exception_type},
                {"name": "Severity", "value": "CRITICAL"}
            ]

            # Add additional context if provided
            if additional_context:
                for key, value in additional_context.items():
                    facts.append({"name": key, "value": str(value)})

            return self._send_admin_message(title, message, "attention", facts)

        except Exception as e:
            LOGGER.writeLog(f"Error sending critical exception to admin Teams: {e}")
            return False

    def send_service_failure(self, service_name, failure_reason, impact_level="HIGH", recovery_action=None):
        """
        Send service failure notification to admin channel
        
        Args:
            service_name: Name of the failed service
            failure_reason: Reason for the failure
            impact_level: Impact level (LOW, MEDIUM, HIGH, CRITICAL)
            recovery_action: Suggested recovery action (optional)
            
        Returns:
            Boolean indicating success
        """
        try:
            impact_emoji = {
                "LOW": "🟡",
                "MEDIUM": "🟠", 
                "HIGH": "🔴",
                "CRITICAL": "🚨"
            }
            
            emoji = impact_emoji.get(impact_level, "🔴")
            title = f"{emoji} SERVICE FAILURE - {service_name}"
            
            message = f"**Service:** {service_name}\n\n**Failure Reason:** {failure_reason}"
            
            if recovery_action:
                message += f"\n\n**Suggested Recovery:** {recovery_action}"

            facts = [
                {"name": "Timestamp", "value": datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')},
                {"name": "System", "value": self.system_name},
                {"name": "Service", "value": service_name},
                {"name": "Impact Level", "value": impact_level},
                {"name": "Status", "value": "FAILED"}
            ]

            color = "attention" if impact_level in ["HIGH", "CRITICAL"] else "warning"
            return self._send_admin_message(title, message, color, facts)

        except Exception as e:
            LOGGER.writeLog(f"Error sending service failure to admin Teams: {e}")
            return False

    def send_celery_failure(self, task_name, task_id, failure_reason, retry_count=0, max_retries=3):
        """
        Send Celery task failure notification to admin channel
        
        Args:
            task_name: Name of the failed Celery task
            task_id: Celery task ID
            failure_reason: Reason for the failure
            retry_count: Current retry count
            max_retries: Maximum retry attempts
            
        Returns:
            Boolean indicating success
        """
        try:
            if retry_count >= max_retries:
                title = "🚨 CELERY TASK PERMANENTLY FAILED"
                color = "attention"
            else:
                title = "⚠️ CELERY TASK FAILED (Retrying)"
                color = "warning"
            
            message = f"**Task:** {task_name}\n\n**Failure Reason:** {failure_reason}"
            
            facts = [
                {"name": "Timestamp", "value": datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')},
                {"name": "System", "value": self.system_name},
                {"name": "Task Name", "value": task_name},
                {"name": "Task ID", "value": task_id},
                {"name": "Retry Count", "value": f"{retry_count}/{max_retries}"},
                {"name": "Status", "value": "FAILED" if retry_count >= max_retries else "RETRYING"}
            ]

            return self._send_admin_message(title, message, color, facts)

        except Exception as e:
            LOGGER.writeLog(f"Error sending Celery failure to admin Teams: {e}")
            return False

    def send_system_startup(self, components_started, startup_time=None):
        """
        Send system startup notification to admin channel
        
        Args:
            components_started: List of components that started successfully
            startup_time: Time taken for startup (optional)
            
        Returns:
            Boolean indicating success
        """
        try:
            title = "✅ SYSTEM STARTUP COMPLETE"
            
            components_list = "\n".join([f"• {component}" for component in components_started])
            message = f"**System Components Started:**\n{components_list}"
            
            if startup_time:
                message += f"\n\n**Startup Time:** {startup_time} seconds"

            facts = [
                {"name": "Timestamp", "value": datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')},
                {"name": "System", "value": self.system_name},
                {"name": "Components Count", "value": str(len(components_started))},
                {"name": "Status", "value": "OPERATIONAL"}
            ]

            if startup_time:
                facts.append({"name": "Startup Time", "value": f"{startup_time}s"})

            return self._send_admin_message(title, message, "good", facts)

        except Exception as e:
            LOGGER.writeLog(f"Error sending system startup to admin Teams: {e}")
            return False

    def send_system_shutdown(self, reason="Manual shutdown", cleanup_performed=True):
        """
        Send system shutdown notification to admin channel
        
        Args:
            reason: Reason for shutdown
            cleanup_performed: Whether cleanup was performed
            
        Returns:
            Boolean indicating success
        """
        try:
            title = "🔄 SYSTEM SHUTDOWN"
            
            message = f"**Shutdown Reason:** {reason}\n\n**Cleanup Status:** {'✅ Completed' if cleanup_performed else '❌ Not performed'}"

            facts = [
                {"name": "Timestamp", "value": datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')},
                {"name": "System", "value": self.system_name},
                {"name": "Reason", "value": reason},
                {"name": "Cleanup", "value": "Completed" if cleanup_performed else "Failed"},
                {"name": "Status", "value": "SHUTDOWN"}
            ]

            return self._send_admin_message(title, message, "warning", facts)

        except Exception as e:
            LOGGER.writeLog(f"Error sending system shutdown to admin Teams: {e}")
            return False

    def send_configuration_error(self, config_file, error_details, suggested_fix=None):
        """
        Send configuration error notification to admin channel
        
        Args:
            config_file: Name of the configuration file with error
            error_details: Details of the configuration error
            suggested_fix: Suggested fix for the error (optional)
            
        Returns:
            Boolean indicating success
        """
        try:
            title = "⚙️ CONFIGURATION ERROR"
            
            message = f"**Configuration File:** {config_file}\n\n**Error Details:** {error_details}"
            
            if suggested_fix:
                message += f"\n\n**Suggested Fix:** {suggested_fix}"

            facts = [
                {"name": "Timestamp", "value": datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')},
                {"name": "System", "value": self.system_name},
                {"name": "Config File", "value": config_file},
                {"name": "Error Type", "value": "CONFIGURATION"},
                {"name": "Status", "value": "NEEDS ATTENTION"}
            ]

            return self._send_admin_message(title, message, "attention", facts)

        except Exception as e:
            LOGGER.writeLog(f"Error sending configuration error to admin Teams: {e}")
            return False

    def send_resource_alert(self, resource_type, current_value, threshold, unit=""):
        """
        Send resource usage alert to admin channel
        
        Args:
            resource_type: Type of resource (CPU, Memory, Disk, etc.)
            current_value: Current resource usage value
            threshold: Threshold value that was exceeded
            unit: Unit of measurement (%, GB, etc.)
            
        Returns:
            Boolean indicating success
        """
        try:
            title = f"📊 RESOURCE ALERT - {resource_type.upper()}"
            
            percentage_over = ((current_value - threshold) / threshold * 100) if threshold > 0 else 0
            message = f"**Resource Type:** {resource_type}\n\n**Current Usage:** {current_value}{unit}\n**Threshold:** {threshold}{unit}\n**Exceeded by:** {percentage_over:.1f}%"

            facts = [
                {"name": "Timestamp", "value": datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')},
                {"name": "System", "value": self.system_name},
                {"name": "Resource", "value": resource_type},
                {"name": "Current Value", "value": f"{current_value}{unit}"},
                {"name": "Threshold", "value": f"{threshold}{unit}"},
                {"name": "Status", "value": "THRESHOLD EXCEEDED"}
            ]

            return self._send_admin_message(title, message, "warning", facts)

        except Exception as e:
            LOGGER.writeLog(f"Error sending resource alert to admin Teams: {e}")
            return False

    def _send_admin_message(self, title, message, color="good", facts=None):
        """
        Internal method to send formatted message to admin Teams channel
        
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
                "originator": self.system_name,
                "sections": [{
                    "activityTitle": title,
                    "activitySubtitle": f"Admin Alert | {self.channel_name}",
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
                LOGGER.writeLog(f"Successfully sent admin message to Teams: {title}")
                return True
            else:
                LOGGER.writeLog(f"Failed to send admin message to Teams. Status: {response.status_code}, Response: {response.text}")
                return False

        except Exception as e:
            LOGGER.writeLog(f"Error sending admin message to Teams: {e}")
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

    def test_admin_connection(self):
        """
        Test the admin Teams webhook connection
        
        Returns:
            Boolean indicating success
        """
        try:
            test_message = {
                "@type": "MessageCard",
                "@context": "http://schema.org/extensions",
                "themeColor": "17a2b8",
                "summary": f"{self.system_name} - Admin Connection Test",
                "originator": self.system_name,
                "sections": [{
                    "activityTitle": "🔧 Admin Connection Test",
                    "activitySubtitle": f"Admin Alert | {self.channel_name}",
                    "text": f"This is a test message from {self.system_name} admin notifier.",
                    "facts": [
                        {"name": "Test Type", "value": "Admin Connection"},
                        {"name": "Timestamp", "value": datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')},
                        {"name": "Status", "value": "SUCCESS"}
                    ]
                }]
            }

            response = requests.post(
                self.webhook_url,
                headers={'Content-Type': 'application/json'},
                data=json.dumps(test_message),
                timeout=10
            )

            if response.status_code == 200:
                LOGGER.writeLog("Admin Teams webhook connection test successful")
                return True
            else:
                LOGGER.writeLog(f"Admin Teams webhook connection test failed. Status: {response.status_code}")
                return False

        except Exception as e:
            LOGGER.writeLog(f"Admin Teams webhook connection test error: {e}")
            return False


# Global admin notifier instance (lazy-loaded)
_admin_notifier = None
_admin_notifier_initialized = False

def get_admin_notifier():
    """
    Get or create the global admin notifier instance.
    Loads config automatically and caches the result.
    
    Returns:
        AdminTeamsNotifier instance or None if configuration is missing/invalid
    """
    global _admin_notifier, _admin_notifier_initialized
    
    if not _admin_notifier_initialized:
        try:
            # Load config automatically - avoid circular import
            import os
            import json
            
            # Get project root directory
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            config_path = os.path.join(project_root, "config", "config.json")
            
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                _admin_notifier = create_admin_notifier_from_config(config)
                if _admin_notifier:
                    LOGGER.writeLog("Global admin notifier initialized successfully")
                else:
                    LOGGER.writeLog("Admin notifier not configured (TEAMS_ADMIN_WEBHOOK missing)")
            else:
                LOGGER.writeLog(f"Config file not found: {config_path}")
                
        except Exception as e:
            LOGGER.writeLog(f"Failed to initialize global admin notifier: {e}")
        
        _admin_notifier_initialized = True
    
    return _admin_notifier

# Convenience functions for sending admin notifications from anywhere
def send_critical_exception(exception_type, exception_message, module_name, stack_trace=None, additional_context=None):
    """
    Send critical exception to admin channel (if configured).
    Can be called from anywhere without passing config.
    
    Args:
        exception_type: Type of exception (e.g., "ConnectionError", "DatabaseError")
        exception_message: Exception message
        module_name: Name of the module where exception occurred
        stack_trace: Full stack trace (optional)
        additional_context: Additional context dictionary (optional)
        
    Returns:
        Boolean indicating success (False if admin notifier not configured)
    """
    try:
        admin_notifier = get_admin_notifier()
        if admin_notifier:
            return admin_notifier.send_critical_exception(
                exception_type, exception_message, module_name, stack_trace, additional_context
            )
    except Exception as e:
        LOGGER.writeLog(f"Failed to send critical exception notification: {e}")
    return False

def send_service_failure(service_name, failure_reason, impact_level="HIGH", recovery_action=None):
    """
    Send service failure notification to admin channel (if configured).
    
    Args:
        service_name: Name of the failed service
        failure_reason: Reason for the failure
        impact_level: Impact level (LOW, MEDIUM, HIGH, CRITICAL)
        recovery_action: Suggested recovery action (optional)
        
    Returns:
        Boolean indicating success (False if admin notifier not configured)
    """
    try:
        admin_notifier = get_admin_notifier()
        if admin_notifier:
            return admin_notifier.send_service_failure(service_name, failure_reason, impact_level, recovery_action)
    except Exception as e:
        LOGGER.writeLog(f"Failed to send service failure notification: {e}")
    return False

def send_celery_failure(task_name, task_id, failure_reason, retry_count=0, max_retries=3):
    """
    Send Celery task failure notification to admin channel (if configured).
    
    Args:
        task_name: Name of the failed Celery task
        task_id: Celery task ID
        failure_reason: Reason for the failure
        retry_count: Current retry count
        max_retries: Maximum retry attempts
        
    Returns:
        Boolean indicating success (False if admin notifier not configured)
    """
    try:
        admin_notifier = get_admin_notifier()
        if admin_notifier:
            return admin_notifier.send_celery_failure(task_name, task_id, failure_reason, retry_count, max_retries)
    except Exception as e:
        LOGGER.writeLog(f"Failed to send Celery failure notification: {e}")
    return False

def send_system_startup(components_started, startup_time=None):
    """
    Send system startup notification to admin channel (if configured).
    
    Args:
        components_started: List of components that started successfully
        startup_time: Time taken for startup (optional)
        
    Returns:
        Boolean indicating success (False if admin notifier not configured)
    """
    try:
        admin_notifier = get_admin_notifier()
        if admin_notifier:
            return admin_notifier.send_system_startup(components_started, startup_time)
    except Exception as e:
        LOGGER.writeLog(f"Failed to send system startup notification: {e}")
    return False

def send_system_shutdown(reason="Manual shutdown", cleanup_performed=True):
    """
    Send system shutdown notification to admin channel (if configured).
    
    Args:
        reason: Reason for shutdown
        cleanup_performed: Whether cleanup was performed
        
    Returns:
        Boolean indicating success (False if admin notifier not configured)
    """
    try:
        admin_notifier = get_admin_notifier()
        if admin_notifier:
            return admin_notifier.send_system_shutdown(reason, cleanup_performed)
    except Exception as e:
        LOGGER.writeLog(f"Failed to send system shutdown notification: {e}")
    return False

def send_configuration_error(config_file, error_details, suggested_fix=None):
    """
    Send configuration error notification to admin channel (if configured).
    
    Args:
        config_file: Name of the configuration file with error
        error_details: Details of the configuration error
        suggested_fix: Suggested fix for the error (optional)
        
    Returns:
        Boolean indicating success (False if admin notifier not configured)
    """
    try:
        admin_notifier = get_admin_notifier()
        if admin_notifier:
            return admin_notifier.send_configuration_error(config_file, error_details, suggested_fix)
    except Exception as e:
        LOGGER.writeLog(f"Failed to send configuration error notification: {e}")
    return False

def send_resource_alert(resource_type, current_value, threshold, unit=""):
    """
    Send resource usage alert to admin channel (if configured).
    
    Args:
        resource_type: Type of resource (CPU, Memory, Disk, etc.)
        current_value: Current resource usage value
        threshold: Threshold value that was exceeded
        unit: Unit of measurement (%, GB, etc.)
        
    Returns:
        Boolean indicating success (False if admin notifier not configured)
    """
    try:
        admin_notifier = get_admin_notifier()
        if admin_notifier:
            return admin_notifier.send_resource_alert(resource_type, current_value, threshold, unit)
    except Exception as e:
        LOGGER.writeLog(f"Failed to send resource alert notification: {e}")
    return False

# Helper function to create admin notifier from config (kept for backward compatibility)
def create_admin_notifier_from_config(config_dict):
    """
    Create AdminTeamsNotifier instance from configuration dictionary
    
    Args:
        config_dict: Configuration dictionary containing TEAMS_ADMIN_WEBHOOK and TEAMS_ADMIN_CHANNEL
        
    Returns:
        AdminTeamsNotifier instance or None if configuration is missing
    """
    try:
        webhook_url = config_dict.get('TEAMS_ADMIN_WEBHOOK')
        channel_name = config_dict.get('TEAMS_ADMIN_CHANNEL', 'Admin Alerts')
        sender_name = config_dict.get('TEAMS_SENDER_NAME', 'Aldebaran Scraper')
        
        if not webhook_url:
            LOGGER.writeLog("TEAMS_ADMIN_WEBHOOK not found in configuration")
            return None
            
        return AdminTeamsNotifier(webhook_url, channel_name, sender_name)
        
    except Exception as e:
        LOGGER.writeLog(f"Error creating admin notifier from config: {e}")
        return None