import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

import requests                  # To work on API Requests
from src.core import log_handling as lh         # My custom class for log handling


from msal import ConfidentialClientApplication

import string                    # Used in getTableRangeFromListOfDict 

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "sharepoint.log")
LOG_TZ = "Asia/Manila"
LOGGER = lh.LogHandling(LOG_FILE, LOG_TZ)


class SharepointProcessor:
   token = ""
   siteID = ""
   fileID = ""
   sessionID = ""
   
   def __init__(self, clientID, clientSecret, tenantID, spSite, siteName, filePath):
      self._error_count = 0
      
      self.token = self.getAccessToken(clientID, clientSecret, tenantID)
      #print(f"token = {self.token}")
      self.siteID, self.fileID = self.getFileAndSiteIDs(spSite, siteName, filePath)
      #print(f"siteID = {self.siteID}, fileID = {self.fileID}")
      if self.token != "" and self.siteID != "" and self.fileID != "":
         self.sessionID = self.createExcelSession()
         #print(f"sessionID = {self.sessionID}")
      
      if self.sessionID == "":
         LOGGER.writeLog(f"Failed SharepointProcessor initialization")
         
         # Send critical exception to admin for initialization failure
         try:
            from .teams_utils import send_critical_exception
            send_critical_exception(
               "SharePointInitializationError",
               "Failed to initialize SharePoint processor",
               "SharepointProcessor.__init__",
               additional_context={
                  "site_name": siteName if 'siteName' in locals() else None,
                  "file_path": filePath if 'filePath' in locals() else None,
                  "has_token": self.token != "",
                  "has_site_id": self.siteID != "",
                  "has_file_id": self.fileID != ""
               }
            )
         except Exception as admin_error:
            LOGGER.writeLog(f"Failed to send SharePoint initialization error to admin: {admin_error}")


   # Enhanced authenticate and get a Microsoft Graph API token with retry logic
   def getAccessToken(self, clientID, clientSecret, tenantID):
      max_attempts = 3
      for attempt in range(max_attempts):
         try:
            LOGGER.writeLog(f"Acquiring access token - attempt {attempt + 1}/{max_attempts}")
            
            authority = f"https://login.microsoftonline.com/{tenantID}"
            app = ConfidentialClientApplication(clientID, authority=authority, client_credential=clientSecret)
            
            # Add timeout for token acquisition
            token = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
            
            if "access_token" in token:
               LOGGER.writeLog(f"Access token acquired successfully on attempt {attempt + 1}")
               return token["access_token"]
            else:
               error_desc = token.get("error_description", "Unknown error")
               error_code = token.get("error", "unknown_error")
               LOGGER.writeLog(f"Authentication failed on attempt {attempt + 1}: {error_code} - {error_desc}")
               
               # Don't retry for certain error types
               if error_code in ["invalid_client", "invalid_client_secret", "unauthorized_client"]:
                  raise Exception(f"Authentication failed - {error_code}: {error_desc}")
               
               if attempt < max_attempts - 1:
                  import time
                  time.sleep(5)  # Wait 5 seconds before retry
                  continue
               else:
                  raise Exception(f"Authentication failed after {max_attempts} attempts - {error_code}: {error_desc}")
                  
         except Exception as e:
            LOGGER.writeLog(f"Token acquisition error on attempt {attempt + 1}: {e}")
            if attempt < max_attempts - 1:
               import time
               time.sleep(5)
               continue
            else:
               # Send critical exception to admin for token acquisition failure
               try:
                  from .teams_utils import send_critical_exception
                  send_critical_exception(
                     "SharePointAuthError",
                     str(e),
                     "SharepointProcessor.getAccessToken",
                     additional_context={
                        "client_id": clientID[:8] + "***" if clientID else None,
                        "tenant_id": tenantID[:8] + "***" if tenantID else None,
                        "attempts": max_attempts
                     }
                  )
               except Exception as admin_error:
                  LOGGER.writeLog(f"Failed to send SharePoint auth error to admin: {admin_error}")
               
               return ""
      
      return ""


   # Get file ID and site ID
   def getFileAndSiteIDs(self, spSite, siteName, filePath):
      try:
         headers = {"Authorization": f"Bearer {self.token}"}
         # Get site ID
         site_url = f"https://graph.microsoft.com/v1.0/sites/{spSite}:/sites/{siteName}"
         site_response = requests.get(site_url, headers=headers).json()
         if not site_response["id"] or site_response["id"] == "":
            raise Exception("The HTTP response did not return a Site ID")
         site_id = site_response["id"]

         # Get file ID
         file_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/root:{filePath}"
         file_response = requests.get(file_url, headers=headers).json()
         if not file_response["id"] or file_response["id"] == "":
            raise Exception("The HTTP response did not return a File ID")
         file_id = file_response["id"]

         return site_id, file_id
      except Exception as e:
         LOGGER.writeLog(f"Failed to retrieve either the Site ID or the File ID - {e}")
         return "", ""
      

   # Open a session to the Excel file with enhanced error handling
   def createExcelSession(self):
      try: 
         headers = {"Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
         }
         session_url = f"https://graph.microsoft.com/v1.0/sites/{self.siteID}/drive/items/{self.fileID}/workbook/createSession"
         
         # Add timeout and enhanced error handling
         response = requests.post(session_url, json={"persistChanges": True}, headers=headers, timeout=30)
         
         LOGGER.writeLog(f"Excel session creation response: status={response.status_code}")
         
         if response.status_code in [200, 201]:  # Accept both OK and Created status codes
            response_json = response.json()
            if "id" in response_json and response_json["id"]:
               LOGGER.writeLog(f"Excel session created successfully: {response_json['id'][:8]}...")
               return response_json["id"]
            else:
               raise Exception("Response missing session ID")
         elif response.status_code == 401:
            raise Exception("Authentication failed - token may be expired")
         elif response.status_code == 403:
            raise Exception("Access denied - insufficient permissions")
         elif response.status_code == 404:
            raise Exception("File not found - check file path and permissions")
         elif response.status_code == 429:
            raise Exception("Rate limit exceeded - too many requests")
         else:
            raise Exception(f"HTTP {response.status_code}: {response.text[:200]}")
            
      except requests.exceptions.Timeout:
         LOGGER.writeLog("Excel session creation timed out after 30 seconds")
         raise Exception("Session creation timeout")
      except requests.exceptions.ConnectionError:
         LOGGER.writeLog("Connection error during Excel session creation")
         raise Exception("Connection error")
      except Exception as e:
         LOGGER.writeLog(f"Failed to acquire a Session ID - {e}")
         raise Exception(f"Session creation failed: {e}")
         return ""


   # Enhanced method to check if you are properly connected to the Sharepoint File
   def isConnectedToSharepointFile(self):
      if (not self.token or not self.siteID or not self.fileID or not self.sessionID):
         return False
      return True
   
   # New method to validate session is still active
   def validateSession(self):
      """Test if the current session is still valid by making a lightweight API call"""
      try:
         if not self.isConnectedToSharepointFile():
            return False
            
         headers = {
            "Authorization": f"Bearer {self.token}",
            "workbook-session-id": self.sessionID,
            "Content-Type": "application/json"
         }
         
         # Try to get workbook info as a lightweight test
         url = f"https://graph.microsoft.com/v1.0/sites/{self.siteID}/drive/items/{self.fileID}/workbook"
         response = requests.get(url, headers=headers, timeout=15)
         
         if response.status_code == 200:
            LOGGER.writeLog("Session validation successful")
            return True
         elif response.status_code == 401:
            LOGGER.writeLog("Session validation failed - authentication error")
            return False
         else:
            LOGGER.writeLog(f"Session validation failed - HTTP {response.status_code}")
            return False
            
      except Exception as e:
         LOGGER.writeLog(f"Session validation error: {e}")
         return False


   # Delete only the contenst in the specified range, not the formatting
   def deleteRange(self, worksheet_name, range_address):
      try:
         headers = {
            "Authorization": f"Bearer {self.token}",
            "workbook-session-id": self.sessionID,
            "Content-Type": "application/json"
         }
         url = f"https://graph.microsoft.com/v1.0/sites/{self.siteID}/drive/items/{self.fileID}/workbook/worksheets/{worksheet_name}/range(address='{range_address}')/delete"
         response = requests.post(url, json={"shift": "Up"}, headers=headers)
         #print(f"response in deleteRange {response}")
         return response.status_code == 204     # 200 Response means successfully deleted the contents
      except Exception as e:
         LOGGER.writeLog(f"Failed to delete the entries in range {range_address} of excel file {self.fileID} - {e}")
         return False


   # Delete content in the specified range, along with formatting
   def clearRange(self, worksheet_name, range_address):
      try:
         headers = {
            "Authorization": f"Bearer {self.token}",
            "workbook-session-id": self.sessionID,
            "Content-Type": "application/json"
         }
         url = f"https://graph.microsoft.com/v1.0/sites/{self.siteID}/drive/items/{self.fileID}/workbook/worksheets/{worksheet_name}/range(address='{range_address}')/clear"
         response = requests.post(url, json={"applyTo": "all"}, headers=headers)
         #print(f"response in clearRange {response}")
         return response.status_code == 204     # 204 Response means successfully cleared the contents
      except Exception as e:
         LOGGER.writeLog(f"Failed to clear entries in range {range_address} of excel file {self.fileID} - {e}")
         return False


   # Enhanced update content in the specified range with retry logic
   def updateRange(self, worksheet_name, range_address, values):
      max_attempts = 3
      for attempt in range(max_attempts):
         try:
            # Validate session before making the request
            if attempt > 0:  # Only validate on retry attempts
               if not self.validateSession():
                  LOGGER.writeLog(f"Session invalid on attempt {attempt + 1}, trying to recreate...")
                  self.sessionID = self.createExcelSession()
                  if not self.sessionID:
                     raise Exception("Failed to recreate session")
            
            headers = {
               "Authorization": f"Bearer {self.token}",
               "workbook-session-id": self.sessionID,
               "Content-Type": "application/json"
            }
            url = f"https://graph.microsoft.com/v1.0/sites/{self.siteID}/drive/items/{self.fileID}/workbook/worksheets/{worksheet_name}/range(address='{range_address}')"
            
            # Log the request details for debugging
            LOGGER.writeLog(f"SharePoint updateRange (attempt {attempt + 1}): worksheet={worksheet_name}, range={range_address}, values={len(values)} rows")
            LOGGER.writeLog(f"Request URL: {url}")
            LOGGER.writeLog(f"Values data: {values}")
            
            response = requests.patch(url, json={"values": values}, headers=headers, timeout=45)
            
            # Log response details
            LOGGER.writeLog(f"SharePoint response: status={response.status_code}")
            
            if response.status_code == 200:
               LOGGER.writeLog(f"SharePoint update successful on attempt {attempt + 1}")
               return True
            elif response.status_code == 401:
               LOGGER.writeLog(f"Authentication failed on attempt {attempt + 1}")
               if attempt < max_attempts - 1:
                  continue  # Retry with session validation
            elif response.status_code == 403:
               LOGGER.writeLog(f"Access denied - insufficient permissions")
               return False  # No point retrying permissions issue
            elif response.status_code == 404:
               LOGGER.writeLog(f"Worksheet or range not found: {worksheet_name}, {range_address}")
               return False  # No point retrying not found
            elif response.status_code == 429:
               LOGGER.writeLog(f"Rate limit exceeded on attempt {attempt + 1}")
               if attempt < max_attempts - 1:
                  import time
                  time.sleep(10)  # Wait 10 seconds for rate limit
                  continue
            else:
               LOGGER.writeLog(f"SharePoint error response: status={response.status_code}, body={response.text[:300]}")
               if attempt < max_attempts - 1:
                  continue  # Retry other errors
            
            return False
            
         except requests.exceptions.Timeout:
            LOGGER.writeLog(f"SharePoint request timeout on attempt {attempt + 1}")
            if attempt < max_attempts - 1:
               import time
               time.sleep(5)
               continue
         except requests.exceptions.ConnectionError:
            LOGGER.writeLog(f"SharePoint connection error on attempt {attempt + 1}")
            if attempt < max_attempts - 1:
               import time
               time.sleep(5)
               continue
         except Exception as e:
            LOGGER.writeLog(f"SharePoint update error on attempt {attempt + 1}: {e}")
            if attempt < max_attempts - 1:
               import time
               time.sleep(3)
               continue
      
      # All attempts failed
      self._error_count += 1
      LOGGER.writeLog(f"Failed to update SharePoint range after {max_attempts} attempts")
      
      # Send critical exception to admin for data update failures (data loss concern)
      if self._error_count % 3 == 0:  # Every 3rd error to avoid spam (reduced from 5)
         try:
            from .teams_utils import send_critical_exception
            send_critical_exception(
               "SharePointUpdateError",
               f"Failed to update range after {max_attempts} attempts",
               "SharepointProcessor.updateRange",
               additional_context={
                  "worksheet": worksheet_name,
                  "range": range_address,
                  "data_rows": len(values) if values else 0,
                  "total_errors": self._error_count,
                  "attempts": max_attempts
               }
            )
         except Exception as admin_error:
            LOGGER.writeLog(f"Failed to send SharePoint update error to admin: {admin_error}")
      
      return False


   # Close the session
   def closeExcelSession(self):
      try:
         headers = {"Authorization": f"Bearer {self.token}",
            "workbook-session-id": self.sessionID,
            "Content-Type": "application/json"
         }
         url = f"https://graph.microsoft.com/v1.0/sites/{self.siteID}/drive/items/{self.fileID}/workbook/closeSession"
         requests.post(url, headers=headers)
      except Exception as e:
         LOGGER.writeLog(f"Failed to close workbook session - {e}")


   # Additional method to determine the table range based on the return value of convertDictToSPFormat that is compatible with 'updateRange' function
   def getTableRangeFrom2DArray(self, start_cell, data):
      if not data or not data[0]:
         raise ValueError("The data must be a non-empty 2D array.")

      # Determine the starting column and row from the start_cell
      start_column = ''.join(filter(str.isalpha, start_cell)).upper()
      start_row = int(''.join(filter(str.isdigit, start_cell)))

      # Calculate the number of rows and columns in the array
      num_rows = len(data)
      num_columns = len(data[0])

      # Get the starting column index
      start_col_index = string.ascii_uppercase.index(start_column) + 1

      # Determine the ending column letter
      end_col_index = start_col_index + num_columns - 1
      end_column = ""
      while end_col_index > 0:
         end_col_index, remainder = divmod(end_col_index - 1, 26)
         end_column = chr(65 + remainder) + end_column

      # Calculate the ending row
      end_row = start_row + num_rows - 1

      # Construct the range address
      range_address = f"{start_column}{start_row}:{end_column}{end_row}"
      return range_address


   # Additional method to convert a list of dictionaries into a 2D array suitable for the 'updateRange' function
   # Added the capability to select particular fields/keys only to be stored in the new 2D array
   def convertDictToSPFormat(self, data, selected_fields):
      if not data or selected_fields == []:
         return []

      # Extract headers from keys of the first dictionary
      #headers = list(data[0].keys())
      headers = selected_fields.copy()
      #print(f"headers = {headers}")
      
      # Extract data rows
      #rows = [list(item.values()) for item in data]
      # This also sets the value into empty string ('') if in case there is no data for the said column 
      rows = []
      for item in data:
         row = []
         for field in selected_fields:
            if field in item:
               row.append(item[field])
            else:
               row.append('')
         rows.append(row)
      #print(f"rows = {rows}")
      
      # Combine headers and rows
      result = [headers] + rows
      return result