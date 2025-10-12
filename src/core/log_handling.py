from datetime import datetime     # For adding timestamp in logs
import os, time                   # For setting up timezone


class LogHandling:
  log_file = ""
  log_tz = ""

  def __init__(self, fname = "_script.log", tz = ""):
    self.log_file = fname
    self.log_tz = tz
    self._log_error_count = 0


  def writeLog(self, text):
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
            "LogHandling.writeLog",
            additional_context={
              "log_file": self.log_file,
              "total_log_errors": self._log_error_count,
              "log_timezone": self.log_tz
            }
          )
        except Exception as admin_error:
          print(f"Failed to send log write error to admin: {admin_error}")
      
      return False


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