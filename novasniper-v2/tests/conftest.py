"""
NovaSniper v2.0 Test Configuration
Pytest fixtures and test utilities
"""
import asyncio
import pytest
from typing import Generator, AsyncGenerator
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_db, Base
from app.models import User, TrackedProduct, Platform, AlertStatus
from app.utils.auth import get_password_hash, generate_api_key


# Test database
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """Create a fresh database for each test"""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db: Session) -> Generator[TestClient, None, None]:
    """Create test client with database override"""
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db: Session) -> User:
    """Create a test user"""
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=get_password_hash("testpassword123"),
        api_key=generate_api_key(),
        is_active=True,
        is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_user(db: Session) -> User:
    """Create an admin test user"""
    user = User(
        email="admin@example.com",
        username="admin",
        hashed_password=get_password_hash("adminpassword123"),
        api_key=generate_api_key(),
        is_active=True,
        is_admin=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    """Get authentication headers for test user"""
    return {"X-API-Key": test_user.api_key}


@pytest.fixture
def admin_headers(admin_user: User) -> dict:
    """Get authentication headers for admin user"""
    return {"X-API-Key": admin_user.api_key}


@pytest.fixture
def sample_product(db: Session, test_user: User) -> TrackedProduct:
    """Create a sample tracked product"""
    product = TrackedProduct(
        user_id=test_user.id,
        platform=Platform.AMAZON,
        product_id="B08N5WRWNW",
        asin="B08N5WRWNW",
        title="Test Product",
        current_price=99.99,
        target_price=79.99,
        currency="USD",
        alert_status=AlertStatus.PENDING,
        is_active=True,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@pytest.fixture
def sample_products(db: Session, test_user: User) -> list[TrackedProduct]:
    """Create multiple sample products"""
    products = []
    
    for i, platform in enumerate([Platform.AMAZON, Platform.EBAY, Platform.WALMART]):
        product = TrackedProduct(
            user_id=test_user.id,
            platform=platform,
            product_id=f"PROD{i+1}",
            title=f"Test Product {i+1}",
            current_price=50.0 + (i * 25),
            target_price=40.0 + (i * 20),
            currency="USD",
            alert_status=AlertStatus.PENDING,
            is_active=True,
        )
        db.add(product)
        products.append(product)
    
    db.commit()
    for p in products:
        db.refresh(p)
    
    return products


# Mock price fetcher for testing
class MockPriceResult:
    def __init__(self, price: float = 99.99, success: bool = True):
        self.success = success
        self.price = price
        self.currency = "USD"
        self.title = "Mock Product"
        self.image_url = "https://example.com/image.jpg"
        self.product_url = "https://example.com/product"
        self.availability = "in_stock"
        self.error = None if success else "Mock error"


@pytest.fixture
def mock_price_fetcher(monkeypatch):
    """Mock the price fetcher service"""
    async def mock_fetch(*args, **kwargs):
        return MockPriceResult()
    
    from app.services import price_fetcher
    monkeypatch.setattr(price_fetcher.price_fetcher_service, "fetch_price", mock_fetch)
