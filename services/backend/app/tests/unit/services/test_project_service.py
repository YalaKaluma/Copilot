"""Unit tests for ProjectService."""

from datetime import datetime, UTC
from uuid import uuid4

import pytest

from core.exceptions import NotFoundError
from services.project_service import ProjectService, get_project_service


class TestProjectServiceCreate:
    """Test create behaviour."""

    @pytest.mark.asyncio
    async def test_create_adds_and_commits_project(self, mocker):
        """Create adds project, commits and refreshes, returns project."""
        service = ProjectService()
        mock_db = mocker.AsyncMock()
        user_id = uuid4()
        name = "My Project"
        description = "A test project."

        result = await service.create(
            user_id=user_id,
            name=name,
            description=description,
            db=mock_db,
        )

        mock_db.add.assert_called_once()
        (added,) = mock_db.add.call_args[0]
        assert added.user_id == user_id
        assert added.name == name
        assert added.description == description
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(added)
        assert result is added


class TestProjectServiceGet:
    """Test get by id (user-scoped)."""

    @pytest.mark.asyncio
    async def test_get_returns_project_when_found_and_owned(self, mocker):
        """Get returns project when id and user_id match."""
        service = ProjectService()
        mock_db = mocker.AsyncMock()
        project_id = uuid4()
        user_id = uuid4()
        mock_project = mocker.Mock()
        mock_project.id = project_id
        mock_project.user_id = user_id

        mock_result = mocker.Mock()
        mock_result.scalar_one_or_none.return_value = mock_project
        mock_db.execute.return_value = mock_result

        result = await service.get(project_id, user_id, mock_db)

        assert result is mock_project
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_raises_not_found_when_missing(self, mocker):
        """Get raises NotFoundError when no project matches."""
        service = ProjectService()
        mock_db = mocker.AsyncMock()
        project_id = uuid4()
        user_id = uuid4()

        mock_result = mocker.Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(NotFoundError) as exc_info:
            await service.get(project_id, user_id, mock_db)

        assert "Project" in str(exc_info.value)
        assert str(project_id) in str(exc_info.value)


class TestProjectServiceListForUser:
    """Test list_for_user."""

    @pytest.mark.asyncio
    async def test_list_returns_ordered_non_deleted_for_user(self, mocker):
        """List returns only non-deleted projects for user, ordered by updated_at desc."""
        service = ProjectService()
        mock_db = mocker.AsyncMock()
        user_id = uuid4()
        p1 = mocker.Mock(id=uuid4(), updated_at=datetime(2025, 1, 2, tzinfo=UTC))
        p2 = mocker.Mock(id=uuid4(), updated_at=datetime(2025, 1, 3, tzinfo=UTC))

        mock_result = mocker.Mock()
        mock_result.scalars.return_value.all.return_value = [p2, p1]
        mock_db.execute.return_value = mock_result

        result = await service.list_for_user(user_id, mock_db)

        assert result == [p2, p1]
        mock_db.execute.assert_called_once()


class TestProjectServiceUpdate:
    """Test update (partial fields)."""

    @pytest.mark.asyncio
    async def test_update_only_updates_provided_fields(self, mocker):
        """Update changes only name/description when provided."""
        service = ProjectService()
        mock_db = mocker.AsyncMock()
        project_id = uuid4()
        user_id = uuid4()
        mock_project = mocker.Mock()
        mock_project.id = project_id
        mock_project.user_id = user_id
        mock_project.name = "Old"
        mock_project.description = "Old desc"

        mocker.patch.object(
            service, "get", new=mocker.AsyncMock(return_value=mock_project)
        )

        result = await service.update(
            project_id,
            user_id,
            mock_db,
            name="New Name",
        )

        assert result is mock_project
        assert mock_project.name == "New Name"
        assert mock_project.description == "Old desc"
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(mock_project)

    @pytest.mark.asyncio
    async def test_update_raises_not_found_when_project_missing(self, mocker):
        """Update raises NotFoundError when get raises."""
        service = ProjectService()
        mock_db = mocker.AsyncMock()
        project_id = uuid4()
        user_id = uuid4()

        mocker.patch.object(
            service,
            "get",
            new=mocker.AsyncMock(side_effect=NotFoundError("Project", project_id)),
        )

        with pytest.raises(NotFoundError):
            await service.update(
                project_id,
                user_id,
                mock_db,
                name="New",
            )


class TestProjectServiceDelete:
    """Test soft delete."""

    @pytest.mark.asyncio
    async def test_delete_sets_soft_delete_and_commits(self, mocker):
        """Delete sets is_deleted and deleted_at, commits, returns True."""
        service = ProjectService()
        mock_db = mocker.AsyncMock()
        project_id = uuid4()
        user_id = uuid4()
        mock_project = mocker.Mock()
        mock_project.id = project_id
        mock_project.user_id = user_id
        mock_project.is_deleted = False
        mock_project.deleted_at = None

        mocker.patch.object(
            service, "get", new=mocker.AsyncMock(return_value=mock_project)
        )

        result = await service.delete(project_id, user_id, mock_db)

        assert result is True
        assert mock_project.is_deleted is True
        assert mock_project.deleted_at is not None
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_raises_not_found_when_project_missing(self, mocker):
        """Delete raises NotFoundError when get raises."""
        service = ProjectService()
        mock_db = mocker.AsyncMock()
        project_id = uuid4()
        user_id = uuid4()

        mocker.patch.object(
            service,
            "get",
            new=mocker.AsyncMock(side_effect=NotFoundError("Project", project_id)),
        )

        with pytest.raises(NotFoundError):
            await service.delete(project_id, user_id, mock_db)


class TestProjectServiceDependencyInjection:
    """Test get_project_service."""

    def test_returns_new_instance(self):
        """get_project_service returns a new ProjectService each time."""
        s1 = get_project_service()
        s2 = get_project_service()
        assert s1 is not s2
        assert isinstance(s1, ProjectService)
        assert isinstance(s2, ProjectService)
