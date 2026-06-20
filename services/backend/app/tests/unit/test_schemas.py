"""Unit tests for Pydantic schemas."""

from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from schemas.base import to_camel, CamelCaseModel
from schemas.health import HealthResponse, ReadinessResponse
from schemas.users import UserResponse, UserCreateRequest, UserUpdateRequest
from schemas.common import ErrorResponse, SuccessResponse


class TestUtilityFunctions:
    """Test utility functions."""

    def test_to_camel_basic(self):
        """Test basic snake_case to camelCase conversion."""
        assert to_camel("snake_case") == "snakeCase"
        assert to_camel("user_id") == "userId"
        assert to_camel("created_at") == "createdAt"

    def test_to_camel_edge_cases(self):
        """Test edge cases for camelCase conversion."""
        assert to_camel("") == ""
        assert to_camel("single") == "single"
        # pyhumps keeps all caps unchanged
        assert to_camel("UPPERCASE") == "UPPERCASE"
        assert to_camel("already_has_CAPS") == "alreadyHasCAPS"


class TestCamelCaseModel:
    """Test CamelCase base model."""

    def test_camel_case_serialization(self):
        """Test that fields are serialized to camelCase."""

        class TestModel(CamelCaseModel):
            user_id: str
            created_at: datetime
            is_active: bool

        model = TestModel(user_id="123", created_at=datetime.now(), is_active=True)

        data = model.model_dump(by_alias=True)
        assert "userId" in data
        assert "createdAt" in data
        assert "isActive" in data
        assert "user_id" not in data

    def test_camel_case_deserialization(self):
        """Test that camelCase input is accepted."""

        class TestModel(CamelCaseModel):
            user_id: str
            is_active: bool

        # Should accept both formats
        model1 = TestModel(user_id="123", is_active=True)
        assert model1.user_id == "123"

        model2 = TestModel(**{"userId": "456", "isActive": False})
        assert model2.user_id == "456"


class TestHealthSchemas:
    """Test health check schemas."""

    def test_health_response(self):
        """Test HealthResponse schema."""
        response = HealthResponse(status="healthy")
        assert response.status == "healthy"
        assert response.service == "backend"  # default value

    def test_readiness_response(self):
        """Test ReadinessResponse schema."""
        response = ReadinessResponse(status="ready", database="connected")
        assert response.status == "ready"
        assert response.database == "connected"
        assert response.error is None

    def test_readiness_with_error(self):
        """Test ReadinessResponse with error."""
        response = ReadinessResponse(
            status="not ready", database="disconnected", error="Connection timeout"
        )
        assert response.status == "not ready"
        assert response.error == "Connection timeout"


class TestUserSchemas:
    """Test user-related schemas."""

    def test_user_response(self):
        """Test UserResponse schema."""
        now = datetime.now()
        response = UserResponse(
            id=uuid4(),
            clerk_user_id="user_123",
            preferred_name="John Doe",
            initials="JD",
            role="user",
            created_at=now,
            updated_at=now,
        )
        assert response.clerk_user_id == "user_123"
        assert response.role == "user"

    def test_user_response_from_orm(self):
        """Test UserResponse.from_orm method."""

        # Mock ORM object
        class MockUser:
            id = uuid4()
            clerk_user_id = "user_456"
            preferred_name = "Jane Doe"
            initials = "JD"
            role = "admin"
            created_at = datetime.now()
            updated_at = datetime.now()

        response = UserResponse.from_orm(MockUser())
        assert response.clerk_user_id == "user_456"
        assert response.role == "admin"

    def test_user_create_request(self):
        """Test UserCreateRequest validation."""
        # Valid request
        request = UserCreateRequest(
            clerk_user_id="user_789", preferred_name="Test User", initials="TU"
        )
        assert request.clerk_user_id == "user_789"
        assert request.role == "user"  # default

        # Empty clerk_user_id should fail
        with pytest.raises(ValidationError):
            UserCreateRequest(clerk_user_id="")

    def test_user_update_request_initials_validation(self):
        """Test that initials are uppercased."""
        # Validator uppercases but Pydantic max_length prevents >2 chars
        request = UserUpdateRequest(initials="ab")
        assert request.initials == "AB"  # Uppercased

        request2 = UserUpdateRequest(initials="x")
        assert request2.initials == "X"

        # Test that >2 chars raises validation error
        with pytest.raises(ValidationError):
            UserUpdateRequest(initials="abcd")


class TestCommonSchemas:
    """Test common response schemas."""

    def test_error_response(self):
        """Test ErrorResponse schema."""
        response = ErrorResponse(
            error="Something went wrong", detail={"field": "value"}, status_code=400
        )
        assert response.success is False
        assert response.error == "Something went wrong"
        assert response.status_code == 400

    def test_success_response(self):
        """Test SuccessResponse schema."""
        response = SuccessResponse(data={"result": "ok"})
        assert response.success is True
        assert response.data == {"result": "ok"}
