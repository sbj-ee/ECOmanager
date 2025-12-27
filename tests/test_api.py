import pytest
from fastapi.testclient import TestClient
import os
import sys

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
    token = test_eco_system.generate_token("api_user")
    return {"X-API-Token": token}

def test_auth_failure():
    response = client.get("/ecos")
    assert response.status_code == 422 # Missing header
    
    response = client.get("/ecos", headers={"X-API-Token": "invalid"})
    assert response.status_code == 401

def test_generate_token():
    resp = client.post("/token", json={"username": "newuser"})
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

def test_lifecycle_via_api(auth_headers):
    # Create
    resp = client.post("/ecos", json={"title": "Cycle", "description": "D"}, headers=auth_headers)
    eco_id = resp.json()["eco_id"]
    
    # Submit
    resp = client.post(f"/ecos/{eco_id}/submit", json={"comment": "Go"}, headers=auth_headers)
    assert resp.status_code == 200
    
    # Verify
    resp = client.get(f"/ecos/{eco_id}", headers=auth_headers)
    assert resp.json()["status"] == "SUBMITTED"

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
