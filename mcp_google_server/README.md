# MCP Google Services Server

This project implements a Model Context Protocol (MCP) server that provides tools for interacting with Google Gmail and Google Calendar APIs. It allows MCP clients (like Claude Desktop or custom clients) to perform actions on your behalf, such as reading emails, sending emails, listing events, and creating events.

## Features (MCP Tools Provided)

The server currently exposes the following tools:

**Gmail:**
*   `list_emails`: Lists subjects of recent emails.
*   `send_email`: Sends an email from your account.
*   `read_email_body`: Reads the plain text or processed HTML content of a specific email using its Message ID.
*   `search_emails`: Searches emails using Gmail query syntax and returns summaries including Message IDs.
*   `get_email_attachments_info`: Lists attachments for a specific email using its Message ID.
*   `forward_email_with_attachments`: Forwards a specific email (including attachments and original format) using its Message ID.

**Calendar:**
*   `list_upcoming_events`: Lists upcoming events from the primary calendar.
*   `create_event`: Creates a new event on the primary calendar.
*   `modify_event`: Modifies an existing event using its Event ID.
*   `delete_event`: Deletes an event using its Event ID.

## Prerequisites

*   Python 3.10 or higher
*   [uv](https://github.com/astral-sh/uv) (Python package installer and virtual environment manager) installed.
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```
    *(Restart your terminal after installation)*

## Setup Instructions

1.  **Clone/Download:** Get the project files into a local directory (e.g., `mcp_google_server`).
2.  **Google Cloud Project & Credentials:**
    *   Go to the [Google Cloud Console](https://console.cloud.google.com/).
    *   Create a new project or select an existing one.
    *   Enable the **Gmail API** and **Google Calendar API** for your project.
    *   Go to "Credentials" -> "Create Credentials" -> "OAuth client ID".
    *   Select "Desktop app" as the Application type.
    *   Give it a name (e.g., "MCP Google Server Client").
    *   Download the JSON credentials file.
    *   **IMPORTANT:** Rename the downloaded file to `credentials.json` and place it inside the `mcp_google_server` directory. **Do not commit `credentials.json` to version control.**
3.  **Create Python Environment & Install Dependencies:**
    *   Navigate to the `mcp_google_server` directory in your terminal.
    *   Initialize the project if `pyproject.toml` doesn't exist:
        ```bash
        uv init
        ```
    *   Create and activate a virtual environment (using Python 3.10+):
        ```bash
        # Ensure pyenv is set to 3.10+ locally or use --python flag
        # pyenv local 3.10.14 
        uv venv 
        source .venv/bin/activate 
        # On Windows: .venv\Scripts\activate
        ```
    *   Install dependencies from `pyproject.toml`:
        ```bash
        uv sync 
        # Or if you need to add them first:
        # uv add "mcp[cli]" httpx google-api-python-client google-auth-httplib2 google-auth-oauthlib
        ```
4.  **Initial Authentication:**
    *   Run the authentication helper script. This will open a browser window asking you to log in to your Google Account and grant permissions (defined by `SCOPES` in `auth_helper.py`).
        ```bash
        python auth_helper.py
        ```
    *   After successful authorization, a `token.json` file will be created in the directory. This stores your access token. **Do not commit `token.json` to version control.**

## Running the Server

Ensure your virtual environment is active (`source .venv/bin/activate`). Then, run the server script:

```bash
uv run mcp_server.py
```

The server will start and wait for an MCP client to connect via standard input/output (stdio).

## Connecting a Client

You need an MCP client application to interact with this server.

*   **Claude Desktop:** Configure it by editing `claude_desktop_config.json` (see path in MCP docs) and adding an entry like:
    ```json
    {
        "mcpServers": {
            "google_services": {
                "command": "/path/to/your/uv", // Use absolute path to uv executable
                "args": [
                    "--directory",
                    "/absolute/path/to/mcp_google_server", // Adjust path
                    "run",
                    "mcp_server.py"
                ]
            }
        }
    }
    ```
    *(Restart Claude Desktop after editing)*
*   **Custom Client:** You can use the `mcp_client` project in this workspace or build your own client using MCP SDKs. The client needs to launch the server process (e.g., using the `uv run ...` command) and communicate via stdio.

## Important Files

*   `mcp_server.py`: Main server logic, defines the MCP tools.
*   `auth_helper.py`: Handles Google OAuth 2.0 authentication flow.
*   `credentials.json`: (You provide this) Your downloaded Google Cloud OAuth credentials. **SECRET.**
*   `token.json`: (Generated on first auth) Stores your access/refresh tokens. **SECRET.**
*   `pyproject.toml`: Project metadata and dependencies for `uv`.

## API Scopes Used

This server requests the following Google API scopes during authentication (defined in `auth_helper.py`):

*   `https://www.googleapis.com/auth/gmail.readonly`
*   `https://www.googleapis.com/auth/gmail.send`
*   `https://www.googleapis.com/auth/calendar.events`
*   `https://www.googleapis.com/auth/calendar.readonly`

If you modify scopes, you must delete `token.json` to re-authorize.

## Troubleshooting

*   **`uv` or `python` command not found:** Ensure `uv` is installed correctly and its bin directory is in your system PATH, or use absolute paths. Make sure the correct Python version (3.10+) is active in the environment.
*   **Authentication Errors:** Double-check that `credentials.json` is present and correct. Ensure you granted the necessary permissions during the browser flow. Delete `token.json` to force re-authentication if scopes changed or the token seems invalid.
*   **API Errors:** Check the specific error message returned by the tool. Ensure the necessary APIs (Gmail, Calendar) are enabled in your Google Cloud Project.
*   **Client Connection Issues (e.g., Claude Desktop):** Verify the absolute path to `uv` and the server directory in the client configuration. Check client logs for connection errors (`spawn ... ENOENT`, etc.).
