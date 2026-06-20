"""Unit tests for UserService with mocked dependencies."""

from datetime import datetime, UTC
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from services.user_service import UserService, get_user_service


class TestUserServiceCreateOrGet:
    """Test create_or_get_user functionality."""

    @pytest.mark.asyncio
    async def test_returns_existing_user(self, mocker):
        """Test that existing user is returned without creating new."""
        service = UserService()
        mock_db = mocker.AsyncMock()

        # Mock existing user
        mock_user = mocker.Mock()
        mock_user.id = uuid4()
        mock_user.clerk_user_id = "user_123"

        mocker.patch.object(
            service, "_get_user_by_clerk_id_query", return_value=mock_user
        )
        result = await service.create_or_get_user("user_123", mock_db)

        assert result == mock_user
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_new_user(self, mocker):
        """Test new user creation when none exists."""
        service = UserService()
        mock_db = mocker.Mock()
        mock_db.add = mocker.Mock()
        mock_db.commit = mocker.AsyncMock()
        mock_db.refresh = mocker.AsyncMock()

        mocker.patch.object(service, "_get_user_by_clerk_id_query", return_value=None)
        await service.create_or_get_user("user_new", mock_db)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_race_condition(self, mocker):
        """Test graceful handling of concurrent user creation."""
        service = UserService()
        mock_db = mocker.Mock()
        mock_db.add = mocker.Mock()
        mock_db.commit = mocker.AsyncMock()
        mock_db.rollback = mocker.AsyncMock()
        mock_db.refresh = mocker.AsyncMock()

        mock_user = mocker.Mock()
        mock_user.id = uuid4()
        mock_user.clerk_user_id = "user_race"

        # First call returns None, commit raises IntegrityError, retry returns user
        mocker.patch.object(
            service, "_get_user_by_clerk_id_query", side_effect=[None, mock_user]
        )
        mock_db.commit.side_effect = IntegrityError("", "", "")

        result = await service.create_or_get_user("user_race", mock_db)

        assert result == mock_user
        mock_db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_validates_empty_id(self, mocker):
        """Test that empty clerk_user_id raises ValueError."""
        service = UserService()
        mock_db = mocker.AsyncMock()

        with pytest.raises(ValueError, match="clerk_user_id cannot be empty"):
            await service.create_or_get_user("", mock_db)

        with pytest.raises(ValueError, match="clerk_user_id cannot be empty"):
            await service.create_or_get_user("  ", mock_db)


class TestUserServiceGetters:
    """Test user retrieval methods."""

    @pytest.mark.asyncio
    async def test_get_user_by_clerk_id(self, mocker):
        """Test successful user retrieval by Clerk ID."""
        service = UserService()
        mock_db = mocker.AsyncMock()

        mock_user = mocker.Mock()
        mock_user.clerk_user_id = "user_get"

        mocker.patch.object(
            service, "_get_user_by_clerk_id_query", return_value=mock_user
        )
        result = await service.get_user_by_clerk_id("user_get", mock_db)
        assert result == mock_user

    @pytest.mark.asyncio
    async def test_get_user_by_clerk_id_empty(self, mocker):
        """Test get_user_by_clerk_id with empty/None ID."""
        service = UserService()
        mock_db = mocker.AsyncMock()

        assert await service.get_user_by_clerk_id("", mock_db) is None
        assert await service.get_user_by_clerk_id(None, mock_db) is None

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, mocker):
        """Test user retrieval by internal UUID."""
        service = UserService()
        mock_db = mocker.AsyncMock()
        user_id = uuid4()

        mock_user = mocker.Mock()
        mock_user.id = user_id

        mock_result = mocker.Mock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        result = await service.get_user_by_id(user_id, mock_db)
        assert result == mock_user


class TestUserServiceDelete:
    """Test user deletion functionality."""

    @pytest.mark.asyncio
    async def test_soft_delete_existing_user(self, mocker):
        """Test successful soft deletion."""
        service = UserService()
        mock_db = mocker.AsyncMock()

        mock_user = mocker.Mock()
        mock_user.clerk_user_id = "user_delete"
        mock_user.deleted_at = None

        mock_result = mocker.Mock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        result = await service.delete_user("user_delete", mock_db)

        assert result is True
        assert mock_user.is_deleted is True
        assert mock_user.deleted_at is not None
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_user(self, mocker):
        """Test deletion returns False for missing user."""
        service = UserService()
        mock_db = mocker.AsyncMock()

        mock_result = mocker.Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await service.delete_user("user_not_found", mock_db)

        assert result is False
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_already_deleted_user(self, mocker):
        """Test deletion of already deleted user returns True."""
        service = UserService()
        mock_db = mocker.AsyncMock()

        mock_user = mocker.Mock()
        mock_user.clerk_user_id = "user_already_deleted"
        mock_user.deleted_at = datetime.now(UTC)

        mock_result = mocker.Mock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        result = await service.delete_user("user_already_deleted", mock_db)

        assert result is True
        mock_db.commit.assert_not_called()


class TestUserServiceDependencyInjection:
    """Test dependency injection pattern implementation."""

    def test_returns_new_instance(self):
        """Verify get_user_service returns new instances (DI pattern)."""
        service1 = get_user_service()
        service2 = get_user_service()

        # With DI pattern, each call creates a new instance
        # FastAPI will cache per request, but in tests they're different
        assert service1 is not service2
        assert isinstance(service1, UserService)
        assert isinstance(service2, UserService)
