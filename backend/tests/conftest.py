import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base, get_db
from app.models.user import User, UserRole
from app.core.auth.security import get_password_hash

# 1. Setup In-Memory SQLite Database
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 2. Dependency Override
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# 3. Fixtures
@pytest.fixture(scope="module")
def client():
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Pre-seed Data
    db = TestingSessionLocal()
    
    # Super Admin
    if not db.query(User).filter(User.email == "admin@example.com").first():
        admin = User(
            email="admin@example.com",
            hashed_password=get_password_hash("admin123"),
            username="admin",
            full_name="Super Admin",
            role=UserRole.SUPER_ADMIN,
            is_active=True,
            user_id="ADMIN001",
            mobile="0000000000"
        )
        db.add(admin)
    
    # Normal User
    if not db.query(User).filter(User.email == "user@example.com").first():
        user = User(
            email="user@example.com",
            hashed_password=get_password_hash("user123"),
            username="user",
            full_name="Normal User",
            role=UserRole.USER,
            is_active=True,
            user_id="USER001",
            mobile="1111111111"
        )
        db.add(user)
    
    db.commit()
    db.close()
    
    with TestClient(app) as c:
        yield c
        
    # Drop tables (cleanup)
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="module")
def admin_token(client):
    response = client.post("/api/v1/auth/login", json={"identifier": "admin@example.com", "password": "admin123"})
    return response.json()["access_token"]

@pytest.fixture(scope="module")
def user_token(client):
    response = client.post("/api/v1/auth/login", json={"identifier": "user@example.com", "password": "user123"})
    return response.json()["access_token"]
