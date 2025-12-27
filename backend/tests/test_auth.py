def test_register_success(client):
    response = client.post(
        "/auth/register",
        json={"email": "pytest@example.com", "password": "strongpassword123"}
    )
    assert response.status_code == 200
    data = response.json()
    # Should either return token or verification instructions
    assert "access_token" in data or "message" in data

def test_register_duplicate_email(client, db):
    # 1. Register
    client.post(
        "/auth/register",
        json={"email": "duplicate@example.com", "password": "params"}
    )
    # 2. Register again
    response = client.post(
        "/auth/register",
        json={"email": "duplicate@example.com", "password": "params"}
    )
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]

def test_login_success(client, db):
    # Create user manually to skip verification logic if needed
    from app.models import User
    from app.auth import get_password_hash
    user = User(
        email="login@example.com", 
        hashed_password=get_password_hash("password123"),
        is_verified=True
    )
    db.add(user)
    db.commit()

    response = client.post(
        "/auth/login",
        data={"username": "login@example.com", "password": "password123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_protected_route(client, mock_user_token):
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {mock_user_token}"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"
