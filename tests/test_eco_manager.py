import pytest
import os
import sys
from pathlib import Path
import datetime
import time
from unittest.mock import patch

# Ensure we can import the module from the parent directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from eco_manager import ECO

@pytest.fixture
def eco_system(tmp_path):
    # Create valid paths for DB and attachments within the temp directory
    db_path = tmp_path / "test_eco.db"
    attachments_dir = tmp_path / "test_attachments"
    return ECO(db_path=str(db_path), attachments_dir=str(attachments_dir))

def test_create_user(eco_system):
    user_id = eco_system.get_or_create_user("testuser")
    assert user_id is not None
    # Verify same user gets same ID
    user_id_2 = eco_system.get_or_create_user("testuser")
    assert user_id == user_id_2

def test_create_eco(eco_system):
    eco_id = eco_system.create_eco("My Title", "My Desc", "author")
    assert eco_id is not None
    
    details = eco_system.get_eco_details(eco_id)
    assert details['title'] == "My Title"
    assert details['description'] == "My Desc"
    assert details['created_by'] == "author"
    assert details['status'] == "DRAFT"

def test_eco_lifecycle(eco_system):
    eco_id = eco_system.create_eco("Lifecycle Test", "Desc", "user1")
    
    # Submit
    assert eco_system.submit_eco(eco_id, "user1", "Ready for review") is True
    details = eco_system.get_eco_details(eco_id)
    assert details['status'] == "SUBMITTED"
    
    # Verify history
    history = details['history']
    assert len(history) == 2 # CREATED, SUBMITTED
    assert history[1]['action'] == 'SUBMITTED'
    
    # Approve
    assert eco_system.approve_eco(eco_id, "approver", "Looks good") is True
    details = eco_system.get_eco_details(eco_id)
    assert details['status'] == "APPROVED"
    
    last_event = details['history'][-1]
    assert last_event['action'] == 'APPROVED'

def test_reject_flow(eco_system):
    eco_id = eco_system.create_eco("Reject Test", "Desc", "user1")
    eco_system.submit_eco(eco_id, "user1")
    
    assert eco_system.reject_eco(eco_id, "reviewer", "Bad design") is True
    details = eco_system.get_eco_details(eco_id)
    assert details['status'] == "REJECTED"

def test_invalid_transitions(eco_system):
    eco_id = eco_system.create_eco("Invalid Trans", "Desc", "user1")
    
    # Cannot approve/reject if not SUBMITTED (it is DRAFT)
    assert eco_system.approve_eco(eco_id, "admin") is False
    assert eco_system.reject_eco(eco_id, "admin", "No") is False

def test_attachments(eco_system, tmp_path):
    eco_id = eco_system.create_eco("Attach Test", "Desc", "user1")
    
    # Create a dummy file to upload
    source_file = tmp_path / "source.txt"
    source_file.write_text("dummy content")
    
    # The second arg 'filename' in add_attachment is actually not used to rename the file in the implementation
    # defined in eco_manager.py line 148: safe_filename = src_path.name
    # Wait, line 139: def add_attachment(self, eco_id: int, filename: str, file_path: str, username: str)
    # The 'filename' argument provided is ignored in favor of src_path.name inside the method logic (lines 148-149).
    # This might be a bug or intended, but I will test based on current implementation behavior.
    
    assert eco_system.add_attachment(eco_id, "ignored_name.txt", str(source_file), "user1") is True
    
    details = eco_system.get_eco_details(eco_id)
    attachments = details['attachments']
    assert len(attachments) == 1
    # It uses the source filename
    assert attachments[0]['filename'] == "source.txt" 
    
    # Check if file was copied to attachments dir
    stored_path = attachments[0]['file_path']
    assert os.path.exists(stored_path)
    assert Path(stored_path).read_text() == "dummy content"

def test_get_nonexistent_eco(eco_system):
    assert eco_system.get_eco_details(999) is None

def test_list_ecos(eco_system):
    eco_system.create_eco("A", "D", "u")
    time.sleep(0.01) # ensure distinct timestamps if OS clock resolution is low
    eco_system.create_eco("B", "D", "u")
    
    ecos = eco_system.list_ecos()
    assert len(ecos) == 2
    # Verify order is DESC (newest first)
    assert ecos[0][1] == "B"
    assert ecos[1][1] == "A"

def test_submit_invalid_eco(eco_system):
    # Test submitting a non-existent ECO ID
    assert eco_system.submit_eco(999, "user1") is False

def test_add_attachment_invalid_path(eco_system):
    eco_id = eco_system.create_eco("Attach Test", "Desc", "user1")
    # File does not exist
    assert eco_system.add_attachment(eco_id, "foo.txt", "/path/to/nowhere/foo.txt", "user1") is False

def test_add_attachment_exception(eco_system, tmp_path):
    eco_id = eco_system.create_eco("Attach Test", "Desc", "user1")
    source_file = tmp_path / "valid.txt"
    source_file.write_text("content")
    
    # Mock shutil.copy2 to raise an exception
    with patch('shutil.copy2', side_effect=OSError("Disk full")):
        assert eco_system.add_attachment(eco_id, "valid.txt", str(source_file), "user1") is False
