import os
import json
import csv
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "file_handling.log")
LOG_TZ = "Asia/Manila"

# Initialize logger with lazy loading to avoid circular imports
LOGGER = None

def get_logger():
    global LOGGER
    if LOGGER is None:
        from src.core.log_handling import LogHandling
        LOGGER = LogHandling(LOG_FILE, LOG_TZ)
    return LOGGER


class FileHandling:
    def __init__(self, filename):
        """
        Initialize file handling
        
        Args:
            filename: Path to the file
        """
        self.filename = filename
        self._error_count = 0
        
        self.ensure_directory_exists()


    def ensure_directory_exists(self):
        """Ensure the directory for the file exists"""
        try:
            directory = os.path.dirname(self.filename)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)
                get_logger().writeLog(f"Created directory: {directory}")
        except Exception as e:
            get_logger().writeLog(f"Error creating directory for {self.filename}: {e}")
            
            # Send critical exception to admin for directory creation failures
            try:
                from src.integrations.teams_utils import send_critical_exception
                send_critical_exception(
                    "DirectoryCreationError",
                    str(e),
                    "FileHandling.ensure_directory_exists",
                    additional_context={
                        "filename": self.filename,
                        "directory": directory if 'directory' in locals() else None
                    }
                )
            except Exception as admin_error:
                get_logger().writeLog(f"Failed to send directory creation error to admin: {admin_error}")


    def write(self, content, overwrite=False):
        """
        Write content to file
        
        Args:
            content: Content to write
            overwrite: If True, overwrite file; if False, append
            
        Returns:
            Boolean indicating success
        """
        try:
            mode = 'w' if overwrite else 'a'
            with open(self.filename, mode, encoding='utf-8') as file:
                file.write(content + '\n')
            return True
        except Exception as e:
            get_logger().writeLog(f"Error writing to file {self.filename}: {e}")
            return False


    def read(self):
        """
        Read content from file
        
        Returns:
            File content as string or None if error
        """
        try:
            if not os.path.exists(self.filename):
                return ""
            
            with open(self.filename, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            get_logger().writeLog(f"Error reading file {self.filename}: {e}")
            return None


    def read_json(self):
        """
        Read JSON content from file
        
        Returns:
            Parsed JSON data or None if error
        """
        try:
            if not os.path.exists(self.filename):
                return None
                
            with open(self.filename, 'r', encoding='utf-8') as file:
                return json.load(file)
        except Exception as e:
            get_logger().writeLog(f"Error reading JSON from {self.filename}: {e}")
            
            # Send critical exception to admin for JSON reading failures (config files are critical)
            try:
                from src.integrations.teams_utils import send_critical_exception
                send_critical_exception(
                    "JSONReadError",
                    str(e),
                    "FileHandling.read_json",
                    additional_context={
                        "filename": self.filename,
                        "file_exists": os.path.exists(self.filename)
                    }
                )
            except Exception as admin_error:
                get_logger().writeLog(f"Failed to send JSON read error to admin: {admin_error}")
            
            return None


    def write_json(self, data, indent=2):
        """
        Write JSON data to file
        
        Args:
            data: Data to write as JSON
            indent: JSON indentation
            
        Returns:
            Boolean indicating success
        """
        try:
            with open(self.filename, 'w', encoding='utf-8') as file:
                json.dump(data, file, indent=indent, ensure_ascii=False)
            return True
        except Exception as e:
            get_logger().writeLog(f"Error writing JSON to {self.filename}: {e}")
            return False


    def append_to_csv(self, data, fieldnames=None):
        """
        Append data to CSV file
        
        Args:
            data: Dictionary or list of dictionaries to append
            fieldnames: List of field names for CSV header
            
        Returns:
            Boolean indicating success
        """
        try:
            # Ensure data is a list
            if isinstance(data, dict):
                data = [data]

            # Check if file exists to determine if we need headers
            file_exists = os.path.exists(self.filename)
            
            with open(self.filename, 'a', newline='', encoding='utf-8') as file:
                if data and fieldnames:
                    writer = csv.DictWriter(file, fieldnames=fieldnames)
                    
                    # Write header if file is new
                    if not file_exists:
                        writer.writeheader()
                    
                    # Write data
                    for row in data:
                        writer.writerow(row)
                        
            return True
        except Exception as e:
            get_logger().writeLog(f"Error appending to CSV {self.filename}: {e}")
            self._error_count += 1
            
            # Send critical exception to admin for CSV write failures (data loss concern)
            if self._error_count % 5 == 0:  # Every 5th error to avoid spam
                try:
                    from src.integrations.teams_utils import send_critical_exception
                    send_critical_exception(
                        "CSVWriteError",
                        str(e),
                        "FileHandling.append_to_csv",
                        additional_context={
                            "filename": self.filename,
                            "data_count": len(data) if isinstance(data, list) else 1,
                            "total_errors": self._error_count
                        }
                    )
                except Exception as admin_error:
                    get_logger().writeLog(f"Failed to send CSV write error to admin: {admin_error}")
            
            return False


    def read_csv(self):
        """
        Read CSV file content
        
        Returns:
            List of dictionaries or None if error
        """
        try:
            if not os.path.exists(self.filename):
                return []
                
            data = []
            with open(self.filename, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    data.append(row)
            return data
        except Exception as e:
            get_logger().writeLog(f"Error reading CSV {self.filename}: {e}")
            return None


    def exists(self):
        """Check if file exists"""
        return os.path.exists(self.filename)


    def delete(self):
        """
        Delete the file
        
        Returns:
            Boolean indicating success
        """
        try:
            if os.path.exists(self.filename):
                os.remove(self.filename)
                get_logger().writeLog(f"Deleted file: {self.filename}")
            return True
        except Exception as e:
            get_logger().writeLog(f"Error deleting file {self.filename}: {e}")
            return False


    def get_size(self):
        """
        Get file size in bytes
        
        Returns:
            File size or 0 if error
        """
        try:
            if os.path.exists(self.filename):
                return os.path.getsize(self.filename)
            return 0
        except Exception as e:
            get_logger().writeLog(f"Error getting size of {self.filename}: {e}")
            return 0


    def get_modification_time(self):
        """
        Get file modification time
        
        Returns:
            Datetime object or None if error
        """
        try:
            if os.path.exists(self.filename):
                timestamp = os.path.getmtime(self.filename)
                return datetime.fromtimestamp(timestamp)
            return None
        except Exception as e:
            get_logger().writeLog(f"Error getting modification time of {self.filename}: {e}")
            return None