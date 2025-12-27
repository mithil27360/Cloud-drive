from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_read_root():
    """Test the root endpoint returns welcome message."""
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()
    assert response.json()["message"] == "Welcome to AI Cloud Drive API"

def test_health_check():
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_docs_endpoint():
    """Test that swagger docs are accessible."""
    response = client.get("/docs")
    assert response.status_code == 200

def test_404_not_found():
    """Test a non-existent route returns 404."""
    response = client.get("/non-existent-route")
    assert response.status_code == 404
