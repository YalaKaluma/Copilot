"""Template service for managing instruction templates."""

from datetime import datetime, UTC
from typing import cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import NotFoundError
from core.logging import get_logger
from packages.db.models.template import Template

logger = get_logger(__name__)
_UNSET = object()


class TemplateService:
    """Service for managing reusable instruction templates."""

    async def list_templates(self, user_id: UUID, db: AsyncSession) -> list[Template]:
        """List all templates for a user."""
        stmt = (
            select(Template)
            .where(
                Template.user_id == user_id,
                Template.is_deleted.is_(False),
            )
            .order_by(Template.updated_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_template(
        self, template_id: UUID, user_id: UUID, db: AsyncSession
    ) -> Template:
        """Get a template by ID."""
        stmt = select(Template).where(
            Template.id == template_id,
            Template.user_id == user_id,
            Template.is_deleted.is_(False),
        )
        result = await db.execute(stmt)
        template = result.scalar_one_or_none()
        if not template:
            raise NotFoundError("Template", template_id)
        return template

    async def create_template(
        self,
        user_id: UUID,
        name: str,
        content: str,
        db: AsyncSession,
        description: str | None = None,
        is_default: bool = False,
    ) -> Template:
        """Create a new template."""
        if is_default:
            await self._clear_defaults(user_id, db)

        template = Template(
            user_id=user_id,
            name=name,
            description=description,
            content=content,
            is_default=is_default,
        )
        db.add(template)
        await db.commit()
        await db.refresh(template)
        return template

    async def update_template(
        self,
        template_id: UUID,
        user_id: UUID,
        db: AsyncSession,
        name: str | object = _UNSET,
        description: str | None | object = _UNSET,
        content: str | object = _UNSET,
        is_default: bool | object = _UNSET,
    ) -> Template:
        """Update an existing template."""
        template = await self.get_template(template_id, user_id, db)

        if is_default is True:
            await self._clear_defaults(user_id, db)

        if name is not _UNSET:
            template.name = cast(str, name)
        if description is not _UNSET:
            template.description = cast(str | None, description)
        if content is not _UNSET:
            template.content = cast(str, content)
        if is_default is not _UNSET:
            template.is_default = cast(bool, is_default)

        await db.commit()
        await db.refresh(template)
        return template

    async def delete_template(
        self, template_id: UUID, user_id: UUID, db: AsyncSession
    ) -> bool:
        """Soft delete a template."""
        template = await self.get_template(template_id, user_id, db)
        template.is_deleted = True
        template.deleted_at = datetime.now(UTC)
        await db.commit()
        return True

    async def _clear_defaults(self, user_id: UUID, db: AsyncSession) -> None:
        """Clear the default flag on all user templates."""
        stmt = (
            update(Template)
            .where(
                Template.user_id == user_id,
                Template.is_default.is_(True),
                Template.is_deleted.is_(False),
            )
            .values(is_default=False)
        )
        await db.execute(stmt)


def get_template_service() -> TemplateService:
    """Create template service instance."""
    return TemplateService()
