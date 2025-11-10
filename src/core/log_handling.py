from datetime import datetime     # For adding timestamp in logs
import os, time                   # For setting up timezone
import json                       # For reading config file


class LogHandling:
  log_file = ""
  log_tz = ""

  def __init__(self, fname = "_script.log", tz = ""):
    self.log_file = fname
    self.log_tz = tz
    self._log_error_count = 0
    self._debug_mode = None  # Cache for DEBUG_MODE config
    self._config_checked = False  # Flag to avoid repeated config reads


  def _load_debug_mode(self):
    """Load DEBUG_MODE from config.json, cache the result to avoid repeated file reads"""
    if self._config_checked:
      return self._debug_mode
    
    self._config_checked = True
    try:
      # Get project root and config path
      current_dir = os.path.dirname(os.path.abspath(__file__))
      project_root = os.path.dirname(os.path.dirname(current_dir))
      config_path = os.path.join(project_root, "config", "config.json")
      
      if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as file:
          config = json.load(file)
          self._debug_mode = config.get('DEBUG_MODE', False)  # Default to False to minimize logs
      else:
        self._debug_mode = False  # Default to False if config doesn't exist
        
    except Exception as e:
      print(f"Warning: Could not load DEBUG_MODE from config, defaulting to False: {e}")
      self._debug_mode = False  # Default to False on error to minimize logs
    
    return self._debug_mode


  def _processLog(self, text):
    """Internal method to process and write log entries"""
    #Set timezone to be used (particularly in log prefix)
    if self.log_tz != "":
      os.environ['TZ'] = self.log_tz
      time.tzset()
    
    # Direct file writing to avoid circular imports
    log_content = self.addLogPrefix() + text
    try:
      # Ensure directory exists
      directory = os.path.dirname(self.log_file)
      if directory and not os.path.exists(directory):
        os.makedirs(directory)
        
      # Append to log file
      with open(self.log_file, 'a', encoding='utf-8') as file:
        file.write(log_content + '\n')
      return True
    except Exception as e:
      print(f"Error writing to log file {self.log_file}: {e}")
      self._log_error_count += 1
      
      # Send critical exception to admin for logging failures (system monitoring concern)
      if self._log_error_count % 10 == 0:  # Every 10th error to avoid infinite loops
        try:
          from src.integrations.teams_utils import send_critical_exception
          send_critical_exception(
            "LogWriteError",
            str(e),
            "LogHandling._processLog",
            additional_context={
              "log_file": self.log_file,
              "total_log_errors": self._log_error_count,
              "log_timezone": self.log_tz
            }
          )
        except Exception as admin_error:
          print(f"Failed to send log write error to admin: {admin_error}")
      
      return False


  def writeLog(self, text):
    """Write log entry - always writes (for critical logs, errors, initialization)"""
    return self._processLog(text)


  def writeDebugLog(self, text):
    """Write debug log entry - only writes if DEBUG_MODE is True"""
    if self._load_debug_mode():
      return self._processLog(text)
    return True  # Return True to indicate "success" even when not writing


  def addLogPrefix(self):
    now = datetime.now()
    return now.strftime("[%Y%m%d_%H:%M:%S]: ")


  def clearLog(self):
    try:
      with open(self.log_file, 'w', encoding='utf-8') as file:
        file.write("")  # Clear the file
      return True
    except Exception as e:
      print(f"Error clearing log file {self.log_file}: {e}")
      return False    