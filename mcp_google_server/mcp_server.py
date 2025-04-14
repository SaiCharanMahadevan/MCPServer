import datetime
import base64
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import re
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from mcp.server.fastmcp import FastMCP

# Import the authentication helper
from auth_helper import get_credentials

# Initialize FastMCP server
mcp = FastMCP("google_services")

# --- Gmail Tools --- #

@mcp.tool()
def list_emails(max_results: int = 10) -> str:
    """Lists the subjects of the most recent emails.

    Args:
        max_results: The maximum number of emails to retrieve (default: 10).
    """
    creds = get_credentials()
    if not creds:
        return "Error: Failed to obtain Google credentials."

    try:
        service = build('gmail', 'v1', credentials=creds)

        # Call the Gmail API
        results = service.users().messages().list(userId='me', maxResults=max_results, labelIds=['INBOX']).execute()
        messages = results.get('messages', [])

        if not messages:
            return "No recent messages found."

        email_subjects = []
        for message_info in messages:
            msg = service.users().messages().get(userId='me', id=message_info['id'], format='metadata', metadataHeaders=['subject']).execute()
            headers = msg.get('payload', {}).get('headers', [])
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
            email_subjects.append(f"- {subject}")

        return f"Recent email subjects:\n" + "\n".join(email_subjects)

    except HttpError as error:
        print(f'An API error occurred: {error}')
        return f"Gmail API error: {error}"
    except Exception as e:
        print(f'An unexpected error occurred: {e}')
        return f"An unexpected error occurred: {e}"

@mcp.tool()
def send_email(to: str, subject: str, body: str) -> str:
    """Sends an email from the authenticated user's account.

    Args:
        to: The recipient's email address.
        subject: The subject line of the email.
        body: The plain text body content of the email.
    """
    creds = get_credentials()
    if not creds:
        return "Error: Failed to obtain Google credentials."

    try:
        service = build('gmail', 'v1', credentials=creds)

        message = EmailMessage()
        message.set_content(body)
        message['To'] = to
        message['Subject'] = subject
        # Note: 'From' is automatically set to the authenticated user

        # Encode the message in base64url format
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {'raw': encoded_message}

        # Send the email
        send_message = service.users().messages().send(userId="me", body=create_message).execute()
        return f"Email sent successfully. Message ID: {send_message['id']}"

    except HttpError as error:
        print(f'An API error occurred: {error}')
        return f"Gmail API error: {error}"
    except Exception as e:
        print(f'An unexpected error occurred: {e}')
        return f"An unexpected error occurred: {e}"

@mcp.tool()
def read_email_body(message_id: str) -> str:
    """Reads the body content of a specific email using its unique message ID.

    Prioritizes plain text, falls back to stripping HTML (removing style/script first) if necessary.

    Args:
        message_id: The unique ID of the email message to read (obtainable from 'search_emails').
    """
    creds = get_credentials()
    if not creds:
        return "Error: Failed to obtain Google credentials."

    try:
        service = build('gmail', 'v1', credentials=creds)
        msg = service.users().messages().get(userId='me', id=message_id, format='full').execute()
        payload = msg.get('payload', {})
        subject = next((h['value'] for h in payload.get('headers', []) if h['name'].lower() == 'subject'), 'No Subject')

        plain_text_body = None
        html_body = None

        def find_text_parts(parts_list):
            nonlocal plain_text_body, html_body
            for part in parts_list:
                mime_type = part.get('mimeType')
                body_data = part.get('body', {}).get('data')
                if not body_data:
                    if part.get('parts'):
                        find_text_parts(part['parts'])
                    continue
                if mime_type == 'text/plain' and not plain_text_body:
                    plain_text_body = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='replace')
                elif mime_type == 'text/html' and not html_body:
                    html_body = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='replace')
                if plain_text_body:
                    return

        if payload.get('parts'):
            find_text_parts(payload['parts'])
        else:
            mime_type = payload.get('mimeType')
            body_data = payload.get('body', {}).get('data')
            if body_data:
                if mime_type == 'text/plain':
                    plain_text_body = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='replace')
                elif mime_type == 'text/html':
                    html_body = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='replace')

        body_content = ""
        result_type = ""
        if plain_text_body:
            body_content = plain_text_body
            result_type = "(Plain Text)"
        elif html_body:
            # Step 1: Remove style and script blocks
            clean_html = re.sub(r'<style.*?</style>', '', html_body, flags=re.DOTALL | re.IGNORECASE)
            clean_html = re.sub(r'<script.*?</script>', '', clean_html, flags=re.DOTALL | re.IGNORECASE)

            # Step 2: Convert block tags and line breaks to newlines
            clean_html = re.sub(r'</(p|div|tr|li|h[1-6])>', '\n', clean_html, flags=re.IGNORECASE) # Add newline after block tags
            clean_html = re.sub(r'<br\s*/?>', '\n', clean_html, flags=re.IGNORECASE)

            # Step 3: Remove remaining HTML tags
            clean_text = re.sub(r'<[^>]+>', '', clean_html)

            # Step 4: Decode common HTML entities
            clean_text = re.sub('&nbsp;', ' ', clean_text)
            clean_text = re.sub('&amp;', '&', clean_text)
            clean_text = re.sub('&lt;', '<', clean_text)
            clean_text = re.sub('&gt;', '>', clean_text)
            clean_text = re.sub('&quot;', '"', clean_text)
            clean_text = re.sub('&#39;', "'", clean_text)

            # Step 5: Clean up whitespace
            clean_text = re.sub(r'[ \t]+', ' ', clean_text) # Collapse spaces/tabs
            clean_text = re.sub(r'\n\s*\n', '\n\n', clean_text) # Collapse multiple blank lines
            body_content = clean_text.strip()
            result_type = "(HTML content processed)"
        else:
            body_content = "Could not find any readable text body parts (plain or HTML)."
            result_type = "(Error)"

        # Increase truncation limit significantly for potentially long booking confirmations
        return f"Subject: {subject}\n\nBody {result_type}:\n{body_content[:4000]}..."

    except HttpError as error:
        print(f'An API error occurred: {error}')
        return f"Gmail API error: {error}. Check if Message ID '{message_id}' is valid."
    except Exception as e:
        print(f'An unexpected error occurred: {e}')
        return f"An unexpected error occurred: {e}"

@mcp.tool()
def search_emails(query: str, max_results: int = 5) -> str:
    """Searches for emails matching a specific query string using standard Gmail search operators.

    Returns a list of matching emails including their Subject, Sender, and unique Message ID.
    The Message ID can be used with other tools like 'read_email_body' or 'forward_email_with_attachments'.

    Args:
        query: The search query string (e.g., 'from:user@example.com', 'subject:Meeting', 'scoot booking').
        max_results: Maximum number of results to return (default: 5).
    """
    creds = get_credentials()
    if not creds:
        return "Error: Failed to obtain Google credentials."

    try:
        service = build('gmail', 'v1', credentials=creds)

        results = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
        messages = results.get('messages', [])

        if not messages:
            return f"No messages found matching query: '{query}'"

        email_summaries = ["Found emails:"]
        for message_info in messages:
            msg = service.users().messages().get(userId='me', id=message_info['id'], format='metadata', metadataHeaders=['subject', 'from']).execute()
            headers = msg.get('payload', {}).get('headers', [])
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown Sender')
            email_summaries.append(f"- ID: {message_info['id']}, From: {sender}, Subject: {subject}")

        return "\n".join(email_summaries)

    except HttpError as error:
        print(f'An API error occurred: {error}')
        return f"Gmail API error: {error}"
    except Exception as e:
        print(f'An unexpected error occurred: {e}')
        return f"An unexpected error occurred: {e}"

@mcp.tool()
def forward_email_with_attachments(original_message_id: str, to: str, forward_body: str | None = None) -> str:
    """Uses the provided message ID to find an original email and forwards it, including attachments and original format (if available), to a new recipient.

    Prepends 'Fwd:' to the subject and adds original sender/date info to the plain text part.

    Args:
        original_message_id: The unique ID of the email to find and forward (obtainable from 'search_emails').
        to: The email address of the recipient to forward to.
        forward_body: Optional additional text to add at the beginning of the forwarded message (plain text part).
    """
    creds = get_credentials()
    if not creds:
        return "Error: Failed to obtain Google credentials."

    try:
        service = build('gmail', 'v1', credentials=creds)

        # 1. Get the original message
        original_msg = service.users().messages().get(userId='me', id=original_message_id, format='full').execute()
        original_payload = original_msg.get('payload', {})
        original_headers = original_payload.get('headers', [])
        original_subject = next((h['value'] for h in original_headers if h['name'].lower() == 'subject'), 'No Subject')
        original_from = next((h['value'] for h in original_headers if h['name'].lower() == 'from'), 'Unknown Sender')
        original_date = next((h['value'] for h in original_headers if h['name'].lower() == 'date'), 'Unknown Date')

        # 2. Construct the new message (now explicitly multipart/mixed)
        new_message = MIMEMultipart('mixed') # Main container: mixed for body + attachments
        new_message['To'] = to
        new_message['Subject'] = f"Fwd: {original_subject}"

        # 3. Extract original body parts (plain and HTML)
        original_plain_text = None
        original_html_text = None # Renamed variable for clarity
        def find_original_body(parts_list):
            nonlocal original_plain_text, original_html_text
            for part in parts_list:
                mime_type = part.get('mimeType')
                body_data = part.get('body', {}).get('data')
                if not body_data:
                    if part.get('parts'): find_original_body(part['parts'])
                    continue
                # Prioritize finding both, don't stop early if only one is found initially
                if mime_type == 'text/plain' and not original_plain_text:
                    original_plain_text = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='replace')
                elif mime_type == 'text/html' and not original_html_text:
                    original_html_text = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='replace')

        if original_payload.get('parts'): find_original_body(original_payload['parts'])
        else: # Handle simple, non-multipart original email
            mime_type = original_payload.get('mimeType')
            body_data = original_payload.get('body', {}).get('data')
            if body_data:
                if mime_type == 'text/plain': original_plain_text = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='replace')
                elif mime_type == 'text/html': original_html_text = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='replace')

        # 4. Prepare the body part (multipart/alternative)
        body_part = MIMEMultipart('alternative')

        # --- Create Plain Text Part ---
        forward_header = f"---------- Forwarded message ----------\nFrom: {original_from}\nDate: {original_date}\nSubject: {original_subject}\n\n"
        plain_text_content = ""
        if forward_body:
            plain_text_content += f"{forward_body}\n\n{forward_header}"
        else:
            plain_text_content += forward_header

        if original_plain_text:
            plain_text_content += original_plain_text
        elif original_html_text: # Generate basic plain text from HTML if no original plain text exists
            clean_html = re.sub(r'<style.*?</style>', '', original_html_text, flags=re.DOTALL | re.IGNORECASE)
            clean_html = re.sub(r'<script.*?</script>', '', clean_html, flags=re.DOTALL | re.IGNORECASE)
            clean_text = re.sub(r'<[^>]+>', '', clean_html)
            clean_text = re.sub('&nbsp;', ' ', clean_text)
            clean_text = clean_text.strip()
            plain_text_content += clean_text
        else:
            plain_text_content += "[Original email body could not be read]"

        body_part.attach(MIMEText(plain_text_content, 'plain', _charset='utf-8'))

        # --- Create HTML Part (if original HTML exists) ---
        if original_html_text:
            # Generally, do NOT inject the forward header into the HTML body
            # Just attach the original HTML content
            body_part.attach(MIMEText(original_html_text, 'html', _charset='utf-8'))

        # 5. Attach the body_part (alternative) to the main message (mixed)
        new_message.attach(body_part)

        # 6. Find, fetch, and attach attachments (attaches to main 'mixed' message)
        attachments_to_add = []
        def find_attachments_to_add(parts_list):
            for part in parts_list:
                filename = part.get('filename')
                attachment_id = part.get('body', {}).get('attachmentId')
                mime_type = part.get('mimeType')
                # Ensure it's actually an attachment part, not inline image/text part with filename
                content_disposition = part.get('headers', [{}])[0].get('value', '')
                if filename and attachment_id and ('attachment' in content_disposition.lower() or not mime_type.startswith('text/')):
                    attachments_to_add.append({
                        'filename': filename,
                        'id': attachment_id,
                        'mimeType': mime_type or 'application/octet-stream'
                    })
                if part.get('parts'): find_attachments_to_add(part['parts'])

        if original_payload.get('parts'): find_attachments_to_add(original_payload['parts'])
        # Also check if the top-level payload itself is an attachment
        elif original_payload.get('filename') and original_payload.get('body', {}).get('attachmentId'):
             attachments_to_add.append({
                'filename': original_payload.get('filename'),
                'id': original_payload.get('body', {}).get('attachmentId'),
                'mimeType': original_payload.get('mimeType', 'application/octet-stream')
            })


        for att_info in attachments_to_add:
            try:
                attachment_data = service.users().messages().attachments().get(userId='me', messageId=original_message_id, id=att_info['id']).execute()
                file_data = base64.urlsafe_b64decode(attachment_data['data'].encode('UTF-8'))

                main_type, sub_type = att_info['mimeType'].split('/', 1)
                mime_part = MIMEBase(main_type, sub_type)
                mime_part.set_payload(file_data)
                encoders.encode_base64(mime_part)
                mime_part.add_header('Content-Disposition', 'attachment', filename=att_info['filename'])
                new_message.attach(mime_part) # Attach to the main 'mixed' message
            except HttpError as attach_error:
                 print(f"Error fetching attachment {att_info['filename']} (ID: {att_info['id']}): {attach_error}")
                 error_part = MIMEText(f"[Could not forward attachment: {att_info['filename']} - Error: {attach_error}]", 'plain')
                 new_message.attach(error_part)
            except Exception as general_attach_error:
                 print(f"Unexpected error with attachment {att_info['filename']}: {general_attach_error}")
                 error_part = MIMEText(f"[Could not forward attachment: {att_info['filename']} - Unexpected Error]", 'plain')
                 new_message.attach(error_part)

        # 7. Encode and send the new message
        encoded_new_message = base64.urlsafe_b64encode(new_message.as_bytes()).decode()
        create_forwarded_message = {'raw': encoded_new_message}

        sent_message = service.users().messages().send(userId="me", body=create_forwarded_message).execute()
        return f"Email forwarded successfully to {to}. New Message ID: {sent_message['id']}"

    except HttpError as error:
        print(f'An API error occurred: {error}')
        return f"Gmail API error forwarding message {original_message_id}: {error}"
    except Exception as e:
        print(f'An unexpected error occurred: {e}')
        return f"An unexpected error occurred while forwarding: {e}"

@mcp.tool()
def get_email_attachments_info(message_id: str) -> str:
    """Uses the provided message ID to find an email and list information about its attachments (filename, type, size).

    Args:
        message_id: The unique ID of the email message to check for attachments (obtainable from 'search_emails').
    """
    creds = get_credentials()
    if not creds:
        return "Error: Failed to obtain Google credentials."

    try:
        service = build('gmail', 'v1', credentials=creds)
        msg = service.users().messages().get(userId='me', id=message_id, format='full').execute()
        payload = msg.get('payload', {})

        attachments_info = []

        def find_attachments(parts_list):
            for part in parts_list:
                filename = part.get('filename')
                attachment_id = part.get('body', {}).get('attachmentId')
                size = part.get('body', {}).get('size')
                mime_type = part.get('mimeType')

                if filename and attachment_id:
                    attachments_info.append({
                        'filename': filename,
                        'mime_type': mime_type,
                        'size': size,
                        'attachment_id': attachment_id # Keep ID for potential future fetching
                    })

                # Recursively check nested parts
                if part.get('parts'):
                    find_attachments(part['parts'])

        # Start searching for attachments
        if payload.get('parts'):
            find_attachments(payload['parts'])
        # Check if the main payload itself is an attachment (less common)
        elif payload.get('filename') and payload.get('body', {}).get('attachmentId'):
             attachments_info.append({
                'filename': payload.get('filename'),
                'mime_type': payload.get('mimeType'),
                'size': payload.get('body', {}).get('size'),
                'attachment_id': payload.get('body', {}).get('attachmentId')
            })


        if not attachments_info:
            return f"No attachments found in email ID: {message_id}"

        output_lines = [f"Attachments for email ID: {message_id}"]
        for info in attachments_info:
            output_lines.append(f"- Filename: {info['filename']}, Type: {info['mime_type']}, Size: {info['size']} bytes") # Attachment ID kept internally

        return "\n".join(output_lines)

    except HttpError as error:
        print(f'An API error occurred: {error}')
        return f"Gmail API error: {error}. Check if Message ID '{message_id}' is valid."
    except Exception as e:
        print(f'An unexpected error occurred: {e}')
        return f"An unexpected error occurred: {e}"

# --- Calendar Tools --- #

@mcp.tool()
def list_upcoming_events(max_results: int = 10) -> str:
    """Lists the next upcoming events from the primary calendar.

    Args:
        max_results: The maximum number of events to retrieve (default: 10).
    """
    creds = get_credentials()
    if not creds:
        return "Error: Failed to obtain Google credentials."

    try:
        service = build('calendar', 'v3', credentials=creds)

        # Call the Calendar API
        now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        events_result = service.events().list(
            calendarId='primary', timeMin=now,
            maxResults=max_results, singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])

        if not events:
            return "No upcoming events found."

        event_summaries = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date')) # Handles all-day events
            event_summaries.append(f"- {start}: {event['summary']}")

        return f"Upcoming events:\n" + "\n".join(event_summaries)

    except HttpError as error:
        print(f'An API error occurred: {error}')
        return f"Calendar API error: {error}"
    except Exception as e:
        print(f'An unexpected error occurred: {e}')
        return f"An unexpected error occurred: {e}"

@mcp.tool()
def create_event(summary: str, start_time: str, end_time: str, description: str | None = None, location: str | None = None) -> str:
    """Creates a new event on the primary calendar.

    Args:
        summary: The title/summary of the event.
        start_time: The start date/time in RFC3339 format (e.g., '2024-12-31T15:00:00-08:00' or '2024-12-31' for all-day).
        end_time: The end date/time in RFC3339 format (e.g., '2024-12-31T16:00:00-08:00' or '2025-01-01' for all-day).
        description: Optional description for the event.
        location: Optional location for the event.
    """
    creds = get_credentials()
    if not creds:
        return "Error: Failed to obtain Google credentials."

    try:
        service = build('calendar', 'v3', credentials=creds)

        event = {
            'summary': summary,
            'location': location,
            'description': description,
            'start': {
                # Check if it's a date or datetime based on format
                'dateTime' if 'T' in start_time else 'date': start_time,
            },
            'end': {
                'dateTime' if 'T' in end_time else 'date': end_time,
            },
        }

        created_event = service.events().insert(calendarId='primary', body=event).execute()
        return f"Event created successfully. Event ID: {created_event.get('id')}"

    except HttpError as error:
        print(f'An API error occurred: {error}')
        return f"Calendar API error: {error}. Check time formats (RFC3339 required)."
    except Exception as e:
        print(f'An unexpected error occurred: {e}')
        return f"An unexpected error occurred: {e}"

@mcp.tool()
def modify_event(event_id: str, summary: str | None = None, start_time: str | None = None, end_time: str | None = None, description: str | None = None, location: str | None = None) -> str:
    """Modifies an existing event on the primary calendar.

    Provide only the fields you want to change. Requires the Event ID.

    Args:
        event_id: The unique ID of the event to modify.
        summary: The new title/summary (if changing).
        start_time: The new start date/time in RFC3339 format (if changing).
        end_time: The new end date/time in RFC3339 format (if changing).
        description: The new description (if changing).
        location: The new location (if changing).
    """
    creds = get_credentials()
    if not creds:
        return "Error: Failed to obtain Google credentials."

    try:
        service = build('calendar', 'v3', credentials=creds)

        # First, get the existing event to update only specified fields
        event = service.events().get(calendarId='primary', eventId=event_id).execute()

        # Update fields if new values are provided
        if summary is not None:
            event['summary'] = summary
        if location is not None:
            event['location'] = location
        if description is not None:
            event['description'] = description
        if start_time is not None:
            event['start'] = {'dateTime' if 'T' in start_time else 'date': start_time}
        if end_time is not None:
            event['end'] = {'dateTime' if 'T' in end_time else 'date': end_time}

        updated_event = service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
        return f"Event '{event_id}' updated successfully. Updated summary: {updated_event.get('summary')}"

    except HttpError as error:
        print(f'An API error occurred: {error}')
        return f"Calendar API error: {error}. Check Event ID and time formats."
    except Exception as e:
        print(f'An unexpected error occurred: {e}')
        return f"An unexpected error occurred: {e}"

@mcp.tool()
def delete_event(event_id: str) -> str:
    """Deletes an event from the primary calendar.

    Args:
        event_id: The unique ID of the event to delete.
    """
    creds = get_credentials()
    if not creds:
        return "Error: Failed to obtain Google credentials."

    try:
        service = build('calendar', 'v3', credentials=creds)

        service.events().delete(calendarId='primary', eventId=event_id).execute()
        return f"Event with ID '{event_id}' deleted successfully."

    except HttpError as error:
        print(f'An API error occurred: {error}')
        return f"Calendar API error: {error}. Check if Event ID '{event_id}' is valid."
    except Exception as e:
        print(f'An unexpected error occurred: {e}')
        return f"An unexpected error occurred: {e}"

# --- Server Runner --- #

if __name__ == "__main__":
    print("Starting Google Services MCP Server...")
    print("Attempting initial credential load/check...")
    initial_creds = get_credentials() # Run once at start to potentially trigger auth flow
    if initial_creds:
        print("Credentials loaded successfully.")
        mcp.run(transport='stdio')
    else:
        print("Failed to load initial credentials. Server cannot start.") 