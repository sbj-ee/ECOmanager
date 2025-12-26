# ECOmanager

A simple Engineering Change Order (ECO) management system built with Python and SQLite.

## Features

- **User Management**: Simple user creation.
- **ECO Lifecycle**: Create, Submit, Approve, and Reject ECOs.
- **History Tracking**: full audit history of actions performed on an ECO.
- **Attachments**: Support for file attachments to ECOs.

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

4.  Install dependencies (currently only for testing):

    ```bash
    pip install pytest
    ```

## Usage

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