import pytest
from fastapi.testclient import TestClient
import os
import sys
from unittest.mock import patch, MagicMock

# Ensure importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api import app
from eco_manager import ECO

client = TestClient(app)

@pytest.fixture(autouse=True)
def test_eco_system(tmp_path):
    # Setup
    db_path = tmp_path / "api_test.db"
    new_eco = ECO(db_path=str(db_path), attachments_dir=str(tmp_path))
    
    # Swap the global instance in api module
    import api
    original_eco = api.eco_system
    api.eco_system = new_eco
    
    yield new_eco
    
    # Teardown
    api.eco_system = original_eco

@pytest.fixture
def auth_headers(test_eco_system):
    # Must register to get token now
    test_eco_system.register_user("api_user", "password")
    token = test_eco_system.generate_token("api_user", "password")
    return {"X-API-Token": token}

def test_auth_failure():
    response = client.get("/ecos")
    assert response.status_code == 422 # Missing header
    
    response = client.get("/ecos", headers={"X-API-Token": "invalid"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API Token"

def test_register_and_token():
    # Register
    resp = client.post("/register", json={"username": "newuser", "password": "pw"})
    assert resp.status_code == 201
    
    # Register duplicate
    resp = client.post("/register", json={"username": "newuser", "password": "pw"})
    assert resp.status_code == 400
    
    # Get token invalid pw
    resp = client.post("/token", json={"username": "newuser", "password": "wrong"})
    assert resp.status_code == 401
    
    # Get token
    resp = client.post("/token", json={"username": "newuser", "password": "pw"})
    assert resp.status_code == 200
    assert "token" in resp.json()

def test_create_eco(auth_headers):
    response = client.post("/ecos", json={"title": "API Test", "description": "API Desc"}, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert "eco_id" in data
    assert data["message"] == "ECO created successfully"

def test_list_ecos(auth_headers):
    client.post("/ecos", json={"title": "ECO 1", "description": "D"}, headers=auth_headers)
    client.post("/ecos", json={"title": "ECO 2", "description": "D"}, headers=auth_headers)
    
    response = client.get("/ecos", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

def test_get_eco_details(auth_headers):
    resp = client.post("/ecos", json={"title": "Details", "description": "D"}, headers=auth_headers)
    eco_id = resp.json()["eco_id"]
    
    response = client.get(f"/ecos/{eco_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Details"

def test_get_nonexistent_eco(auth_headers):
    response = client.get("/ecos/999", headers=auth_headers)
    assert response.status_code == 404

def test_lifecycle_via_api(auth_headers):
    # Create
    resp = client.post("/ecos", json={"title": "Cycle", "description": "D"}, headers=auth_headers)
    eco_id = resp.json()["eco_id"]
    
    # Submit
    resp = client.post(f"/ecos/{eco_id}/submit", json={"comment": "Go"}, headers=auth_headers)
    assert resp.status_code == 200
    
    # Approve
    resp = client.post(f"/ecos/{eco_id}/approve", json={"comment": "OK"}, headers=auth_headers)
    assert resp.status_code == 200
    
    # Verify
    resp = client.get(f"/ecos/{eco_id}", headers=auth_headers)
    assert resp.json()["status"] == "APPROVED"

def test_lifecycle_failures(auth_headers):
    # Try to submit nonexistent ECO
    resp = client.post("/ecos/999/submit", json={"comment": "Go"}, headers=auth_headers)
    assert resp.status_code == 400
    
    # Try to approve nonexistent (or draft) ECO
    # Create one but don't submit
    resp = client.post("/ecos", json={"title": "Draft", "description": "D"}, headers=auth_headers)
    eco_id = resp.json()["eco_id"]
    
    resp = client.post(f"/ecos/{eco_id}/approve", json={"comment": "OK"}, headers=auth_headers)
    assert resp.status_code == 400

def test_reject_via_api(auth_headers):
    resp = client.post("/ecos", json={"title": "Reject", "description": "D"}, headers=auth_headers)
    eco_id = resp.json()["eco_id"]
    client.post(f"/ecos/{eco_id}/submit", json={"comment": "Submit"}, headers=auth_headers)
    
    # Reject without comment (should fail validation logic)
    resp = client.post(f"/ecos/{eco_id}/reject", json={}, headers=auth_headers)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Comment required for rejection"
    
    # Reject failure (e.g. invalid cycle or ID)
    # Mocking reject_eco to return False to ensure we hit the 400 error path
    with patch("api.eco_system.reject_eco", return_value=False):
         resp = client.post(f"/ecos/{eco_id}/reject", json={"comment": "No"}, headers=auth_headers)
         assert resp.status_code == 400
         assert resp.json()["detail"] == "Operation failed. Check ECO status."

    # Success
    resp = client.post(f"/ecos/{eco_id}/reject", json={"comment": "No"}, headers=auth_headers)
    assert resp.status_code == 200

def test_attachment_upload(auth_headers, tmp_path):
    resp = client.post("/ecos", json={"title": "Attach", "description": "D"}, headers=auth_headers)
    eco_id = resp.json()["eco_id"]
    
    file_content = b"test content"
    files = {"file": ("test.txt", file_content, "text/plain")}
    
    resp = client.post(f"/ecos/{eco_id}/attachments", headers=auth_headers, files=files)
    assert resp.status_code == 200
    
    details = client.get(f"/ecos/{eco_id}", headers=auth_headers).json()
    assert len(details["attachments"]) == 1
    assert details["attachments"][0]["filename"] == "test.txt"

def test_attachment_failure(auth_headers):
    file_content = b"test content"
    files = {"file": ("test.txt", file_content, "text/plain")}
    
    # Mock eco_system.add_attachment to return False
    with patch("api.eco_system.add_attachment", return_value=False):
        resp = client.post("/ecos/1/attachments", headers=auth_headers, files=files)
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Failed to add attachment"

def test_download_report(auth_headers):
    resp = client.post("/ecos", json={"title": "Report", "description": "D"}, headers=auth_headers)
    eco_id = resp.json()["eco_id"]
    
    resp = client.get(f"/ecos/{eco_id}/report", headers=auth_headers)
    assert resp.status_code == 200
    assert "ECO Report: Report" in resp.text

def test_download_report_failures(auth_headers):
    # Non-existent ID
    resp = client.get("/ecos/999/report", headers=auth_headers)
    assert resp.status_code == 404
    
    # Generation failure mock
    # Create valid ECO
    resp = client.post("/ecos", json={"title": "Fail Report", "description": "D"}, headers=auth_headers)
    eco_id = resp.json()["eco_id"]
    
    with patch('eco_manager.ECO.generate_report', return_value=False):
        resp = client.get(f"/ecos/{eco_id}/report", headers=auth_headers)
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Failed to generate report"
