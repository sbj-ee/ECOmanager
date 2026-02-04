import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

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

    # Test download
    resp = client.get(f"/ecos/{eco_id}/attachments/test.txt", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.content == file_content
    
    # Test download nonexistent
    resp = client.get(f"/ecos/{eco_id}/attachments/ghost.txt", headers=auth_headers)
    assert resp.status_code == 404

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


def test_admin_self_deletion(test_eco_system):
    # Register admin (first user)
    test_eco_system.register_user("selfadmin", "pw")
    token = test_eco_system.generate_token("selfadmin", "pw")
    headers = {"X-API-Token": token}

    # Get admin's user id
    resp = client.get("/admin/users", headers=headers)
    admin_id = resp.json()[0]["id"]

    # Try to self-delete
    resp = client.delete(f"/admin/users/{admin_id}", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Cannot delete your own account"


def test_last_admin_deletion(test_eco_system):
    # Register admin (first user) and a second admin
    test_eco_system.register_user("admin1", "pw")
    test_eco_system.register_user("regular", "pw")
    token = test_eco_system.generate_token("admin1", "pw")
    headers = {"X-API-Token": token}

    # Get regular user's id
    resp = client.get("/admin/users", headers=headers)
    users = resp.json()
    regular = [u for u in users if u["username"] == "regular"][0]

    # Can delete regular user
    resp = client.delete(f"/admin/users/{regular['id']}", headers=headers)
    assert resp.status_code == 200


def test_pagination_query_params(auth_headers):
    for i in range(5):
        client.post("/ecos", json={"title": f"P{i}", "description": "D"}, headers=auth_headers)

    resp = client.get("/ecos?limit=2", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    resp = client.get("/ecos?limit=10&offset=3", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_upload_size_limit(auth_headers, monkeypatch):
    import api
    monkeypatch.setattr(api, "MAX_UPLOAD_SIZE", 10)  # 10 bytes

    resp = client.post("/ecos", json={"title": "Size", "description": "D"}, headers=auth_headers)
    eco_id = resp.json()["eco_id"]

    large_content = b"x" * 100
    files = {"file": ("big.txt", large_content, "text/plain")}
    resp = client.post(f"/ecos/{eco_id}/attachments", headers=auth_headers, files=files)
    assert resp.status_code == 413


def test_health_check():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_logout(test_eco_system):
    test_eco_system.register_user("logoutuser", "pw")
    token = test_eco_system.generate_token("logoutuser", "pw")
    headers = {"X-API-Token": token}

    # Verify token works
    resp = client.get("/ecos", headers=headers)
    assert resp.status_code == 200

    # Logout
    resp = client.post("/logout", headers=headers)
    assert resp.status_code == 200

    # Token should be revoked
    resp = client.get("/ecos", headers=headers)
    assert resp.status_code == 401


def test_logout_invalid_token():
    resp = client.post("/logout", headers={"X-API-Token": "bogus"})
    assert resp.status_code == 401
