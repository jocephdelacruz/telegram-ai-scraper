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
      self.token = self.getAccessToken(clientID, clientSecret, tenantID)
      #print(f"token = {self.token}")
      self.siteID, self.fileID = self.getFileAndSiteIDs(spSite, siteName, filePath)
      #print(f"siteID = {self.siteID}, fileID = {self.fileID}")
      if self.token != "" and self.siteID != "" and self.fileID != "":
         self.sessionID = self.createExcelSession()
         #print(f"sessionID = {self.sessionID}")
      
      if self.sessionID == "":
         LOGGER.writeLog(f"Failed SharepointProcessor initialization")


   # Authenticate and get a Microsoft Graph API token
   def getAccessToken(self, clientID, clientSecret, tenantID):
      try:
         authority = f"https://login.microsoftonline.com/{tenantID}"
         app = ConfidentialClientApplication(clientID, authority=authority, client_credential=clientSecret)
         token = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
         if "access_token" in token:
            return token["access_token"]
         else:
            raise Exception("Authentication failed:", token.get("error_description"))
      except Exception as e:
         LOGGER.writeLog(f"Failed to acquire access token - {e}")
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
      

   # Open a session to the Excel file
   def createExcelSession(self):
      try: 
         headers = {"Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
         }
         session_url = f"https://graph.microsoft.com/v1.0/sites/{self.siteID}/drive/items/{self.fileID}/workbook/createSession"
         response = requests.post(session_url, json={"persistChanges": True}, headers=headers)
         #print(f"response in createExcelSession {response}")
         if response.json()["id"] and response.json()["id"] != "":
            return response.json()["id"]
         else:
            raise Exception("The HTTP response did not return a Session ID")
      except Exception as e:
         LOGGER.writeLog(f"Failed to acquire a Session ID - {e}")
         return ""


   # A way to check if you are properly connected to the Sharepoint File
   def isConnectedToSharepointFile(self):
      if token == "" or siteID == "" or fileID == "" or sessionID == "":
         return False
      return True


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


   # Update content in the specified range
   def updateRange(self, worksheet_name, range_address, values):
      try:
         headers = {
            "Authorization": f"Bearer {self.token}",
            "workbook-session-id": self.sessionID,
            "Content-Type": "application/json"
         }
         url = f"https://graph.microsoft.com/v1.0/sites/{self.siteID}/drive/items/{self.fileID}/workbook/worksheets/{worksheet_name}/range(address='{range_address}')"
         response = requests.patch(url, json={"values": values}, headers=headers)
         #print(f"response in updateRange {response}")
         return response.status_code == 200
      except Exception as e:
         LOGGER.writeLog(f"Failed to add values in {range_address} of excel file {self.fileID} - {e}")
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