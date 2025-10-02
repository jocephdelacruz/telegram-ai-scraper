from datetime import datetime     # For adding timestamp in logs
import os, time                   # For setting up timezone
import file_handling as fh        # My custom class for file handling


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
    
    file = fh.FileHandling(self.log_file)
    return file.write(self.addLogPrefix() + text)


  def addLogPrefix(self):
    now = datetime.now()
    return now.strftime("[%Y%m%d_%H:%M:%S]: ")


  def clearLog(self):
    file = fh.FileHandling(log_file)
    return file.write("", True)    