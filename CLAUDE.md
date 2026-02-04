# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

ECOmanager is an Engineering Change Order management system with a FastAPI backend, SQLite database, and vanilla JS frontend.

## Architecture

- `api.py` -- FastAPI REST API (routes, auth dependencies, file upload handling)
- `eco_manager.py` -- Core business logic (`ECO` class with all DB operations)
- `static/` -- Frontend (vanilla JS, CSS, HTML)
- `tests/` -- pytest test suite

The `ECO` class owns all database access. The API layer is thin -- it validates input via Pydantic models, resolves the current user from the `X-API-Token` header, and delegates to `ECO` methods.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api:app --reload
```

## Testing

```bash
pytest tests/ -v
```

All tests use temporary databases via `tmp_path` fixtures. The API tests swap `api.eco_system` with a fresh instance per test.

## Configuration

Settings are read from environment variables in `api.py`:

- `DATABASE_PATH` (default: `eco_system.db`)
- `ATTACHMENTS_DIR` (default: `attachments`)
- `CORS_ORIGINS` (default: `*`, comma-separated)
- `MAX_UPLOAD_SIZE` (default: 10MB)

## Key Patterns

- Authentication: token-based via `X-API-Token` header, resolved by `get_current_user` dependency
- Admin checks: `get_current_admin` dependency wraps `get_current_user`
- Database: raw `sqlite3` with parameterized queries; each method opens its own connection
- Passwords: hashed with `bcrypt`
- ECO state machine: DRAFT -> SUBMITTED -> APPROVED/REJECTED (enforced in `eco_manager.py`)
- First registered user is auto-promoted to admin

## Conventions

- Keep the API layer thin; business logic belongs in `eco_manager.py`
- Use parameterized SQL queries -- never interpolate user input into SQL
- Frontend uses safe DOM construction (`textContent`, `createElement`) -- avoid `innerHTML` with user data
- Catch specific exceptions (`OSError`, `sqlite3.Error`), not bare `except`
- Log security-relevant events (failed logins, deletions) via the `logging` module
