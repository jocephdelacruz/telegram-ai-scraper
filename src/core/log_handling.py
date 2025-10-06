from datetime import datetime     # For adding timestamp in logs
import os, time                   # For setting up timezone


class LogHandling:
  log_file = ""
  log_tz = ""

  def __init__(self, fname = "_script.log", tz = ""):
    self.log_file = fname
    self.log_tz = tz


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