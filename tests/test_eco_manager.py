import os
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

from eco_manager import ECO

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


def test_cannot_submit_twice(eco_system):
    eco_id = eco_system.create_eco("Double Submit", "Desc", "user1")
    assert eco_system.submit_eco(eco_id, "user1") is True
    # Second submission should fail
    assert eco_system.submit_eco(eco_id, "user1") is False


def test_cannot_resubmit_rejected(eco_system):
    eco_id = eco_system.create_eco("Reject Resubmit", "Desc", "user1")
    eco_system.submit_eco(eco_id, "user1")
    eco_system.reject_eco(eco_id, "reviewer", "Bad")
    # Cannot go from REJECTED back to SUBMITTED
    assert eco_system.submit_eco(eco_id, "user1") is False


def test_cannot_submit_approved(eco_system):
    eco_id = eco_system.create_eco("Approved Submit", "Desc", "user1")
    eco_system.submit_eco(eco_id, "user1")
    eco_system.approve_eco(eco_id, "reviewer", "Good")
    # Cannot go from APPROVED back to SUBMITTED
    assert eco_system.submit_eco(eco_id, "user1") is False

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
    # It uses the provided filename now
    assert attachments[0]['filename'] == "ignored_name.txt" 
    
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

def test_generate_report(eco_system, tmp_path):
    eco_id = eco_system.create_eco("Report Test", "Some Description", "userR")
    eco_system.submit_eco(eco_id, "userR", "Submit Comment")
    
    # Add dummy attachment
    att_source = tmp_path / "dummy.txt"
    att_source.write_text("content")
    eco_system.add_attachment(eco_id, "dummy.txt", str(att_source), "userR")
    
    report_file = tmp_path / "report.md"
    assert eco_system.generate_report(eco_id, str(report_file)) is True
    
    content = report_file.read_text(encoding='utf-8')
    assert "# ECO Report: Report Test" in content
    assert "**Status:** SUBMITTED" in content
    assert "Some Description" in content
    assert "dummy.txt" in content
    assert "Submit Comment" in content

def test_generate_report_invalid_id(eco_system, tmp_path):
    report_file = tmp_path / "fail.md"
    assert eco_system.generate_report(999, str(report_file)) is False

def test_generate_report_io_error(eco_system, tmp_path):
    eco_id = eco_system.create_eco("IO Test", "Desc", "user1")
    # Tries to write to a directory path instead of a file
    assert eco_system.generate_report(eco_id, str(tmp_path)) is False

def test_generate_report_no_data(eco_system, tmp_path):
    eco_id = eco_system.create_eco("Empty Test", "Desc", "user1")
    
    # Manually clear history to test the "No history" branch
    with sqlite3.connect(eco_system.db_path) as conn:
        conn.execute("DELETE FROM eco_history WHERE eco_id = ?", (eco_id,))
        conn.commit()
        
    report_file = tmp_path / "empty_report.md"
    assert eco_system.generate_report(eco_id, str(report_file)) is True
    

def test_verify_password_edge_cases(eco_system):
    # Non-existent user
    assert eco_system.verify_password("ghost", "pass") is False

    # User without password (simulated legacy user)
    eco_system.get_or_create_user("legacy") # Creates user with NULL password
    assert eco_system.verify_password("legacy", "pass") is False


def test_delete_last_admin(eco_system):
    eco_system.register_user("admin1", "pw")  # First user is auto-admin
    # Verify the user is admin
    users = eco_system.get_all_users()
    admin = [u for u in users if u['is_admin']][0]
    # Cannot delete last admin
    assert eco_system.delete_user(admin['id']) is False


def test_delete_non_admin_user(eco_system):
    eco_system.register_user("admin1", "pw")  # auto-admin
    eco_system.register_user("regular", "pw")
    users = eco_system.get_all_users()
    regular = [u for u in users if not u['is_admin']][0]
    assert eco_system.delete_user(regular['id']) is True


def test_token_cleanup_on_user_delete(eco_system):
    eco_system.register_user("admin1", "pw")  # auto-admin
    eco_system.register_user("doomed", "pw")
    token = eco_system.generate_token("doomed", "pw")
    assert eco_system.get_user_from_token(token) is not None
    users = eco_system.get_all_users()
    doomed = [u for u in users if u['username'] == 'doomed'][0]
    eco_system.delete_user(doomed['id'])
    # Token should be invalidated
    assert eco_system.get_user_from_token(token) is None


def test_list_ecos_pagination(eco_system):
    for i in range(5):
        eco_system.create_eco(f"ECO {i}", "D", "user")

    # Default gets all (limit 50 > 5)
    assert len(eco_system.list_ecos()) == 5

    # Limit
    assert len(eco_system.list_ecos(limit=2)) == 2

    # Offset
    assert len(eco_system.list_ecos(limit=10, offset=3)) == 2


def test_delete_nonexistent_user(eco_system):
    assert eco_system.delete_user(999) is False


def test_mime_type_detection(eco_system, tmp_path):
    eco_id = eco_system.create_eco("MIME Test", "Desc", "user1")
    source_file = tmp_path / "test.pdf"
    source_file.write_bytes(b"%PDF-1.4 dummy")
    eco_system.add_attachment(eco_id, "test.pdf", str(source_file), "user1")
    details = eco_system.get_eco_details(eco_id)
    assert details['attachments'][0]['mime_type'] == 'application/pdf'
