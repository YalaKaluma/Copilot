"""Unit tests for projects router."""

from datetime import datetime, UTC
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from main import app
from core.dependencies import verify_clerk_token, get_project_service
from packages.db import get_db
from packages.db.models import User


@pytest.fixture
def mock_user():
    """Mock user for auth."""
    user_id = uuid4()
    user = User(
        id=user_id,
        clerk_user_id="test_clerk_123",
        preferred_name="Test User",
        initials="TU",
        role="user",
    )
    return user


@pytest.fixture
def mock_project(mock_user):
    """Mock project returned by service."""
    project_id = uuid4()
    return type(
        "Project",
        (),
        {
            "id": project_id,
            "user_id": mock_user.id,
            "name": "Test Project",
            "description": "A test project",
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        },
    )()


@pytest.fixture
def client_with_mock_project_service(mock_user, mock_project):
    """Test client with mocked auth and project service."""

    async def mock_verify_token(credentials=None, db=None):
        return {
            "type": "clerk",
            "user_id": mock_user.clerk_user_id,
            "email": "test@example.com",
            "user": mock_user,
            "jwt_payload": {"sub": mock_user.clerk_user_id},
        }

    class MockProjectService:
        async def list_for_user(self, user_id, db):
            return [mock_project]

        async def create(self, user_id, name, description, db):
            return mock_project

        async def get(self, project_id, user_id, db):
            return mock_project

        async def update(self, project_id, user_id, db, name=None, description=None):
            return mock_project

        async def delete(self, project_id, user_id, db):
            return True

    async def override_get_db():
        yield None  # Mock session; service ignores it

    app.dependency_overrides[verify_clerk_token] = mock_verify_token
    app.dependency_overrides[get_project_service] = lambda: MockProjectService()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        c.headers["Authorization"] = "Bearer test_token"
        yield c

    app.dependency_overrides.clear()


class TestListProjects:
    """Test GET /api/projects."""

    def test_list_returns_200_and_list(self, client_with_mock_project_service):
        """List returns 200 and array of project items."""
        response = client_with_mock_project_service.get("/api/projects")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        item = data[0]
        assert "id" in item
        assert item.get("name") == "Test Project"
        assert item.get("description") == "A test project"
        assert "createdAt" in item
        assert "updatedAt" in item


class TestCreateProject:
    """Test POST /api/projects."""

    def test_create_returns_200_and_project(self, client_with_mock_project_service):
        """Create returns 200 and project response."""
        response = client_with_mock_project_service.post(
            "/api/projects",
            json={"name": "New Project", "description": "New desc"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("name") == "Test Project"
        assert "id" in data
        assert "createdAt" in data
        assert "updatedAt" in data


class TestGetProject:
    """Test GET /api/projects/{project_id}."""

    def test_get_returns_200_and_project(
        self, client_with_mock_project_service, mock_project
    ):
        """Get returns 200 and project response."""
        response = client_with_mock_project_service.get(
            f"/api/projects/{mock_project.id}"
        )
        assert response.status_code == 200
        data = response.json()
        assert str(data.get("id")) == str(mock_project.id)
        assert data.get("name") == "Test Project"


class TestUpdateProject:
    """Test PATCH /api/projects/{project_id}."""

    def test_update_returns_200_and_project(
        self, client_with_mock_project_service, mock_project
    ):
        """Update returns 200 and project response."""
        response = client_with_mock_project_service.patch(
            f"/api/projects/{mock_project.id}",
            json={"name": "Updated Name", "description": "Updated desc"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data.get("name") == "Test Project"


class TestDeleteProject:
    """Test DELETE /api/projects/{project_id}."""

    def test_delete_returns_200_and_success(
        self, client_with_mock_project_service, mock_project
    ):
        """Delete returns 200 and success body."""
        response = client_with_mock_project_service.delete(
            f"/api/projects/{mock_project.id}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
