import os.path
import pickle  # Consider using json for better readability if preferred

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Define the scopes needed by the tools
# If modifying these scopes, delete the file token.json.
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',        # Read emails
    'https://www.googleapis.com/auth/gmail.send',            # Send emails (add if needed later)
    # Add more specific Gmail scopes if needed (e.g., modify, labels)
    'https://www.googleapis.com/auth/calendar.events',       # Read/write calendar events
    'https://www.googleapis.com/auth/calendar.readonly',     # Read-only calendar access
]

TOKEN_FILE = 'token.json'
CREDENTIALS_FILE = 'credentials.json'

def get_credentials():
    """Gets valid user credentials from storage or initiates OAuth flow."""
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    if os.path.exists(TOKEN_FILE):
        # Using pickle here, matching some Google examples. JSON is also common.
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token) # Or json.load(token) if using JSON

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing token: {e}")
                # Force re-authentication if refresh fails
                creds = None
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"ERROR: Credentials file '{CREDENTIALS_FILE}' not found.")
                print("Please download it from Google Cloud Console and place it in the project directory.")
                return None
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    CREDENTIALS_FILE, SCOPES)
                # Run local server flow - this opens the browser for authorization
                creds = flow.run_local_server(port=0)
            except Exception as e:
                print(f"Error during authentication flow: {e}")
                return None

        # Save the credentials for the next run
        if creds:
            with open(TOKEN_FILE, 'wb') as token:
                 # Use pickle.dump or json.dump
                pickle.dump(creds, token)

    if not creds:
        print("Failed to obtain credentials.")
        return None

    return creds

if __name__ == '__main__':
    # Simple test to run the auth flow if executed directly
    print("Attempting to get credentials...")
    credentials = get_credentials()
    if credentials:
        print("Successfully obtained credentials.")
        # You could optionally print token expiry or other info here for testing
        # print(f"Token expires at: {credentials.expiry}")
    else:
        print("Failed to get credentials.")
