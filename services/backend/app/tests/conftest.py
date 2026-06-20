"""Shared test fixtures and configuration.

Provides fixtures for:
- Test database setup/teardown
- Test client with/without authentication
- Mock services and data
"""

import asyncio
from typing import AsyncGenerator
from uuid import uuid4

# No environment variables needed - we'll mock everything properly

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from core.config import Settings, get_settings
from main import app
from packages.db import Base, get_db
from packages.db.models import User


@pytest.fixture(autouse=True)
def uncached_get_filter_options():
    """Replace get_filter_options with uncached version so alru_cache is not shared across event loops."""
    from unittest.mock import patch

    from services.skai_api import get_filter_options

    original = get_filter_options.__wrapped__

    async def _uncached(skai):
        return await original(skai)

    with (
        patch("copilot_agents.orchestrator.get_filter_options", _uncached),
        patch("tools.skai.tools.get_filter_options", _uncached),
        patch("routers.skai.get_filter_options", _uncached),
    ):
        yield


# Test database URL - using sqlite for tests with proper async setup
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Override settings for testing."""
    return Settings(
        database_url=TEST_DATABASE_URL,
        env="test",
        debug=True,
        clerk_secret_key="test_secret",
        clerk_webhook_secret="whsec_test",
        # Mock GCS settings to prevent real service initialization
        gcp_project_id="test-project",
        gcs_bucket_name="test-bucket",
        storage_env_prefix="test",
    )


@pytest_asyncio.fixture
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session.

    Creates a fresh database for each test and tears it down after.
    """
    # Create test engine with proper SQLite settings for async
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=StaticPool,  # Use StaticPool for in-memory SQLite
        connect_args={
            "check_same_thread": False,  # Required for SQLite
        },
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    TestSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with TestSessionLocal() as session:
        yield session
        # Don't rollback - let the test complete its transaction

    # Clean up
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def client(
    test_settings: Settings, test_db: AsyncSession, mock_storage_service
) -> AsyncGenerator[TestClient, None]:
    """Create a test client with overridden dependencies."""

    # Override settings
    app.dependency_overrides[get_settings] = lambda: test_settings

    # Override database with our test database
    async def override_get_db():
        try:
            yield test_db
        finally:
            pass  # Session cleanup is handled by the fixture

    app.dependency_overrides[get_db] = override_get_db

    # Override storage service dependency
    from services.storage_service import get_storage_service

    app.dependency_overrides[get_storage_service] = lambda: mock_storage_service

    with TestClient(app) as test_client:
        yield test_client

    # Clean up overrides
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def authenticated_client(client: TestClient, test_db: AsyncSession) -> TestClient:
    """Create a test client with mock authentication and ensure user exists in DB."""

    # Mock the verify_clerk_token dependency
    from core.dependencies import verify_clerk_token
    from sqlalchemy import select

    # Create a consistent test user ID
    test_user_id = uuid4()
    clerk_user_id = "test_user_123"

    # Check if user already exists
    stmt = select(User).where(User.clerk_user_id == clerk_user_id)
    result = await test_db.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        test_user = existing_user
    else:
        # Create new user
        test_user = User(
            id=test_user_id,
            clerk_user_id=clerk_user_id,
            preferred_name="Test User",
            initials="TU",
            role="user",
        )
        test_db.add(test_user)
        await test_db.commit()
        await test_db.refresh(test_user)

    async def mock_verify_token(credentials=None, db=None):
        # If we have a database session, ensure user exists
        if db:
            from sqlalchemy import select

            stmt = select(User).where(User.clerk_user_id == clerk_user_id)
            result = await db.execute(stmt)
            existing_user = result.scalar_one_or_none()

            if not existing_user:
                # Create user in database
                db_user = User(
                    id=test_user_id,
                    clerk_user_id=clerk_user_id,
                    preferred_name="Test User",
                    initials="TU",
                    role="user",
                )
                db.add(db_user)
                await db.commit()
                await db.refresh(db_user)
                return {
                    "type": "clerk",
                    "user_id": clerk_user_id,
                    "email": "test@example.com",
                    "user": db_user,
                    "jwt_payload": {"sub": clerk_user_id},
                }
            else:
                return {
                    "type": "clerk",
                    "user_id": clerk_user_id,
                    "email": "test@example.com",
                    "user": existing_user,
                    "jwt_payload": {"sub": clerk_user_id},
                }
        else:
            # No DB session, return mock user
            return {
                "type": "clerk",
                "user_id": clerk_user_id,
                "email": "test@example.com",
                "user": test_user,
                "jwt_payload": {"sub": clerk_user_id},
            }

    app.dependency_overrides[verify_clerk_token] = mock_verify_token

    # Set auth header
    client.headers["Authorization"] = "Bearer test_token"

    return client


@pytest.fixture
def mock_clerk_webhook_payload():
    """Create a mock Clerk webhook payload with unique ID."""
    # Generate unique ID for each test to avoid conflicts
    unique_id = str(uuid4()).replace("-", "")[:20]
    return {
        "type": "user.created",
        "data": {
            "id": f"user_{unique_id}",
            "email_addresses": [{"email_address": f"test_{unique_id}@example.com"}],
            "first_name": "Test",
            "last_name": "User",
        },
    }


@pytest.fixture
def mock_svix_headers():
    """Create mock Svix webhook headers."""
    return {
        "svix-id": "msg_test123",
        "svix-timestamp": "1234567890",
        "svix-signature": "v1,test_signature",
    }


@pytest.fixture
def sample_user_data():
    """Create sample user data for testing."""
    return {
        "id": uuid4(),
        "clerk_user_id": "user_test123",
        "preferred_name": "Test User",
        "initials": "TU",
        "role": "user",
    }


# # Async client fixture for async tests
# @pytest_asyncio.fixture
# async def async_client(test_settings: Settings, test_db: AsyncSession):
#     """Create an async test client."""
#     from httpx import AsyncClient

#     # Override settings
#     app.dependency_overrides[get_settings] = lambda: test_settings

#     # Override database
#     async def override_get_db():
#         yield test_db

#     app.dependency_overrides[get_db] = override_get_db

#     async with AsyncClient(app=app, base_url="http://test") as client:
#         yield client

#     # Clean up overrides
#     app.dependency_overrides.clear()
