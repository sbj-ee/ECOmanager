# ECOmanager

A simple Engineering Change Order (ECO) management system built with Python, SQLite, and FastAPI, featuring a modern Web UI.

## Features

- **User Management**: Simple user creation.
- **ECO Lifecycle**: Create, Submit, Approve, and Reject ECOs.
- **History Tracking**: full audit history of actions performed on an ECO.
- **Attachments**: Support for file attachments to ECOs.
- **Report Generation**: Export ECO details to Markdown reports.
- **REST API**: Full-featured API built with FastAPI.
- **Web Interface**: Modern UI for managing ECOs.

## Prerequisites

- Python 3.8+
- SQLite3

## Setup

1.  Clone the repository.
2.  Create a virtual environment:

    ```bash
    python3 -m venv .venv
    ```

3.  Activate the virtual environment:

    - On macOS/Linux: `source .venv/bin/activate`
    - On Windows: `.venv\Scripts\activate`

4.  Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

## Web Interface
The project includes a modern, dark-mode web interface for managing ECOs.

1.  Start the API server: `uvicorn api:app --reload`
2.  Open **http://127.0.0.1:8000** in your web browser.
3.  **Register** a new account (or login if you already have one).
4.  From the dashboard, you can:
    -   Create new ECOs.
    -   View ECO details and history.
    -   Upload and view attachments.
    -   Submit, Approve, or Reject ECOs.
    -   Download PDF-ready Markdown reports.
    -   (Admins) Manage users via the Admin Panel.

## Administration

The system supports two user roles: **User** and **Admin**.
-   **Admins** can manage users (view list, delete users).
-   The **first user** registered in the system is automatically assigned Admin privileges.

### Promoting Users
To promote an existing user to Admin, use the provided helper script:

```bash
python3 make_admin.py <username>
```

## Python Library Usage

The core logic is in `eco_manager.py`. You can import the `ECO` class in your own scripts or application.

```python
from eco_manager import ECO

# Initialize
eco = ECO(db_path="my_eco.db")

# Create a new ECO
eco_id = eco.create_eco("New Project", "Description...", "alice")

# Submit for approval
eco.submit_eco(eco_id, "alice", "Ready for review")

# Add an attachment
eco.add_attachment(eco_id, "spec.pdf", "/path/to/local/spec.pdf", "alice")

# Approve
eco.approve_eco(eco_id, "bob", "Approved!")

# Generate a Report
eco.generate_report(eco_id, "eco_report.md")
```

## API

The project includes a REST API built with FastAPI.

To run the API server:

```bash
uvicorn api:app --reload
```

The API will be available at `http://127.0.0.1:8000`. 
Interactive documentation is available at `http://127.0.0.1:8000/docs`.

### Authentication

The API uses token-based authentication. Users must first register to set a password.

1.  **Register a User**:

    ```bash
    curl -X POST http://127.0.0.1:8000/register \
      -H "Content-Type: application/json" \
      -d '{"username": "alice", "password": "secretpassword"}'
    ```

2.  **Generate a Token**:

    ```bash
    curl -X POST http://127.0.0.1:8000/token \
      -H "Content-Type: application/json" \
      -d '{"username": "alice", "password": "secretpassword"}'
    ```

    Response:
    ```json
    {"token": "your_generated_token"}
    ```

3.  **Use the Token**: Include the token in the `X-API-Token` header for all requests.

    ```bash
    curl -X GET http://127.0.0.1:8000/ecos \
      -H "X-API-Token: your_generated_token"
    ```

## Testing

This project includes a test suite using `pytest`.

To run the tests:

```bash
# If using the virtual environment directly:
.venv/bin/pytest

# Or if activated:
pytest
```