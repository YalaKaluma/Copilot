"""Templates API router for instruction templates."""

from uuid import UUID

from fastapi import APIRouter

from core.dependencies import AuthTokenDep, DatabaseDep, TemplateServiceDep
from core.logging import get_logger
from schemas.template import (
    CreateTemplateRequest,
    TemplateDetail,
    TemplateListItem,
    UpdateTemplateRequest,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=list[TemplateListItem])
async def list_templates(
    auth: AuthTokenDep,
    template_service: TemplateServiceDep,
    db: DatabaseDep,
):
    """List all templates for the authenticated user."""
    user = auth["user"]
    templates = await template_service.list_templates(user.id, db)
    return [
        TemplateListItem(
            id=t.id,
            name=t.name,
            description=t.description,
            is_default=t.is_default,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in templates
    ]


@router.get("/{template_id}", response_model=TemplateDetail)
async def get_template(
    template_id: UUID,
    auth: AuthTokenDep,
    template_service: TemplateServiceDep,
    db: DatabaseDep,
):
    """Get a template with full content."""
    user = auth["user"]
    template = await template_service.get_template(template_id, user.id, db)
    return TemplateDetail(
        id=template.id,
        name=template.name,
        description=template.description,
        content=template.content,
        is_default=template.is_default,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


@router.post("", response_model=TemplateDetail)
async def create_template(
    request: CreateTemplateRequest,
    auth: AuthTokenDep,
    template_service: TemplateServiceDep,
    db: DatabaseDep,
):
    """Create a new template."""
    user = auth["user"]
    template = await template_service.create_template(
        user_id=user.id,
        name=request.name,
        content=request.content,
        db=db,
        description=request.description,
        is_default=request.is_default,
    )
    return TemplateDetail(
        id=template.id,
        name=template.name,
        description=template.description,
        content=template.content,
        is_default=template.is_default,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


@router.patch("/{template_id}", response_model=TemplateDetail)
async def update_template(
    template_id: UUID,
    request: UpdateTemplateRequest,
    auth: AuthTokenDep,
    template_service: TemplateServiceDep,
    db: DatabaseDep,
):
    """Update an existing template."""
    user = auth["user"]
    update_data = request.model_dump(exclude_unset=True)
    template = await template_service.update_template(
        template_id=template_id,
        user_id=user.id,
        db=db,
        **update_data,
    )
    return TemplateDetail(
        id=template.id,
        name=template.name,
        description=template.description,
        content=template.content,
        is_default=template.is_default,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


@router.delete("/{template_id}")
async def delete_template(
    template_id: UUID,
    auth: AuthTokenDep,
    template_service: TemplateServiceDep,
    db: DatabaseDep,
):
    """Soft delete a template."""
    user = auth["user"]
    await template_service.delete_template(template_id, user.id, db)
    return {"success": True}
