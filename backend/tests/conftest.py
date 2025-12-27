import pytest
from sqlalchemy import create_engine
from sqlalchemy.in_executor import transaction
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.database import Base, get_db
from app.models import User

# SQLite In-Memory for Tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session")
def db_engine():
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    # Mock External Services
    
    # Mock MinIO
    from app.storage import minio_client
    minio_client.minio_client = MagicMock()
    minio_client.bucket_name = "test-bucket"
    
    # Mock Celery
    from app.routes import files
    files.process_file = MagicMock()
    files.process_file.delay = MagicMock()

    with TestClient(app) as c:
        yield c
        
    app.dependency_overrides.clear()

@pytest.fixture
def mock_user_token(client, db):
    # Create user
    from app.auth import get_password_hash
    user = User(
        email="test@example.com", 
        hashed_password=get_password_hash("password123"),
        is_verified=True
    )
    db.add(user)
    db.commit()
    
    # Login to get token
    response = client.post("/auth/login", data={"username": "test@example.com", "password": "password123"})
    return response.json()["access_token"]
