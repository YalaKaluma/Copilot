"""Project service for user-scoped project CRUD."""

from datetime import datetime, UTC
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import NotFoundError
from core.logging import get_logger
from packages.db.models.project import Project

logger = get_logger(__name__)


class ProjectService:
    """Service for managing user-scoped projects."""

    async def create(
        self,
        user_id: UUID,
        name: str,
        description: str | None,
        db: AsyncSession,
    ) -> Project:
        """Create a project for the user."""
        project = Project(
            user_id=user_id,
            name=name,
            description=description,
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)
        return project

    async def get(
        self,
        project_id: UUID,
        user_id: UUID,
        db: AsyncSession,
    ) -> Project:
        """Get a project by id; must belong to the user."""
        stmt = select(Project).where(
            Project.id == project_id,
            Project.user_id == user_id,
            Project.is_deleted.is_(False),
        )
        result = await db.execute(stmt)
        project = result.scalar_one_or_none()
        if not project:
            raise NotFoundError("Project", project_id)
        return project

    async def list_for_user(self, user_id: UUID, db: AsyncSession) -> list[Project]:
        """List all non-deleted projects for the user, ordered by updated_at desc."""
        stmt = (
            select(Project)
            .where(
                Project.user_id == user_id,
                Project.is_deleted.is_(False),
            )
            .order_by(Project.updated_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def update(
        self,
        project_id: UUID,
        user_id: UUID,
        db: AsyncSession,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Project:
        """Update a project; only provided fields are updated."""
        project = await self.get(project_id, user_id, db)
        if name is not None:
            project.name = name
        if description is not None:
            project.description = description
        await db.commit()
        await db.refresh(project)
        return project

    async def delete(
        self,
        project_id: UUID,
        user_id: UUID,
        db: AsyncSession,
    ) -> bool:
        """Soft-delete a project."""
        project = await self.get(project_id, user_id, db)
        project.is_deleted = True
        project.deleted_at = datetime.now(UTC)
        await db.commit()
        return True


def get_project_service() -> ProjectService:
    """Create project service instance."""
    return ProjectService()
