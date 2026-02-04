# ECOmanager

An Engineering Change Order (ECO) management system built with Python, FastAPI, and SQLite. Features a modern dark-mode web UI, token-based authentication, full audit history, and file attachments.

## Features

- **ECO Lifecycle** -- Create, Submit, Approve, and Reject engineering change orders
- **Audit History** -- Every action is recorded with user, timestamp, and optional comment
- **File Attachments** -- Upload and download files per ECO with MIME type detection
- **Report Generation** -- Export ECO details to Markdown reports
- **Role-Based Access** -- Admin and User roles; first registered user becomes admin
- **REST API** -- FastAPI with interactive docs at `/docs`
- **Search & Filter** -- Search ECOs by title or description, filter by status
- **Pagination** -- Configurable 10, 50, or 100 items per page with Previous/Next navigation
- **Admin Actions** -- Admins can edit and delete ECOs
- **Web Interface** -- Glassmorphism dark-mode UI with status badges and built-in help guide
- **Configurable** -- Database path, CORS origins, upload limits, and more via environment variables

## Prerequisites

- Python 3.8+

## Quick Start

```bash
git clone https://github.com/sbj-ee/ECOmanager.git
cd ECOmanager
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn api:app --reload
```

Open **http://127.0.0.1:8000** and register your first account (automatically gets admin privileges).

### Production

```bash
gunicorn api:app -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8000
```

### Docker

```bash
docker build -t ecomanager .
docker run -p 8000:8000 -v eco_data:/app/attachments ecomanager
```

## Configuration

All settings are optional environment variables with sensible defaults:

| Variable | Default | Description |
| --- | --- | --- |
| `DATABASE_PATH` | `eco_system.db` | Path to the SQLite database file |
| `ATTACHMENTS_DIR` | `attachments` | Directory for uploaded files |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins (restrict in production) |
| `MAX_UPLOAD_SIZE` | `10485760` (10 MB) | Maximum file upload size in bytes |

## Web Interface

From the dashboard you can:

- Create new ECOs
- View ECO details, history, and attachments
- Submit, Approve, or Reject ECOs
- Edit or Delete ECOs (admin only)
- Search by title/description and filter by status
- Paginate results (10, 50, or 100 per page)
- Upload and view file attachments
- Download Markdown reports
- Access the built-in Help guide
- Manage users via the Admin Panel (admins only)

## Administration

The system has two roles: **User** and **Admin**.

- The **first user** registered is automatically assigned admin privileges
- Admins can view all users and delete non-admin users
- Admins cannot delete themselves or the last remaining admin

To promote an existing user to admin:

```bash
python3 make_admin.py <username>
```

## API

Interactive documentation is available at `http://127.0.0.1:8000/docs` when the server is running.

### Authentication

The API uses token-based authentication via the `X-API-Token` header.

```bash
# Register
curl -X POST http://127.0.0.1:8000/register \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "secretpassword"}'

# Get token
curl -X POST http://127.0.0.1:8000/token \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "secretpassword"}'
# Returns: {"token": "your_generated_token", "is_admin": true}

# Use token
curl http://127.0.0.1:8000/ecos \
  -H "X-API-Token: your_generated_token"
```

### Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Health check (no auth required) |
| `POST` | `/register` | Register a new user |
| `POST` | `/token` | Generate an API token |
| `POST` | `/logout` | Revoke current API token |
| `GET` | `/ecos` | List ECOs (`?limit=`, `?offset=`, `?search=`, `?status=`) |
| `POST` | `/ecos` | Create a new ECO |
| `PUT` | `/ecos/{id}` | Edit an ECO (admin only) |
| `DELETE` | `/ecos/{id}` | Delete an ECO (admin only) |
| `GET` | `/ecos/{id}` | Get ECO details, history, and attachments |
| `POST` | `/ecos/{id}/submit` | Submit ECO for review |
| `POST` | `/ecos/{id}/approve` | Approve a submitted ECO |
| `POST` | `/ecos/{id}/reject` | Reject a submitted ECO (comment required) |
| `POST` | `/ecos/{id}/attachments` | Upload a file attachment |
| `GET` | `/ecos/{id}/attachments/{filename}` | Download an attachment |
| `GET` | `/ecos/{id}/report` | Download a Markdown report |
| `GET` | `/admin/users` | List all users (admin only) |
| `DELETE` | `/admin/users/{id}` | Delete a user (admin only) |

## Python Library Usage

The core logic in `eco_manager.py` can be used independently:

```python
from eco_manager import ECO

eco = ECO(db_path="my_eco.db")

eco_id = eco.create_eco("New Project", "Description...", "alice")
eco.submit_eco(eco_id, "alice", "Ready for review")
eco.add_attachment(eco_id, "spec.pdf", "/path/to/spec.pdf", "alice")
eco.approve_eco(eco_id, "bob", "Approved!")
eco.generate_report(eco_id, "eco_report.md")
```

## Testing

```bash
pytest                  # run all tests
pytest -v               # verbose output
pytest --cov            # with coverage report
```

## License

MIT