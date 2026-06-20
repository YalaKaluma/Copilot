"""Projects API router for user-scoped projects."""

from uuid import UUID

from fastapi import APIRouter

from core.dependencies import AuthTokenDep, DatabaseDep, ProjectServiceDep
from core.logging import get_logger
from schemas.project import (
    ProjectCreateRequest,
    ProjectListItem,
    ProjectResponse,
    ProjectUpdateRequest,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectListItem])
async def list_projects(
    auth: AuthTokenDep,
    project_service: ProjectServiceDep,
    db: DatabaseDep,
):
    """List all projects for the authenticated user."""
    user = auth["user"]
    projects = await project_service.list_for_user(user.id, db)
    return [
        ProjectListItem(
            id=p.id,
            name=p.name,
            description=p.description,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in projects
    ]


@router.post("", response_model=ProjectResponse)
async def create_project(
    body: ProjectCreateRequest,
    auth: AuthTokenDep,
    project_service: ProjectServiceDep,
    db: DatabaseDep,
):
    """Create a project for the authenticated user."""
    user = auth["user"]
    project = await project_service.create(
        user_id=user.id,
        name=body.name,
        description=body.description,
        db=db,
    )
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    auth: AuthTokenDep,
    project_service: ProjectServiceDep,
    db: DatabaseDep,
):
    """Get a project by id (must belong to the current user)."""
    user = auth["user"]
    project = await project_service.get(project_id, user.id, db)
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    body: ProjectUpdateRequest,
    auth: AuthTokenDep,
    project_service: ProjectServiceDep,
    db: DatabaseDep,
):
    """Update a project (must belong to the current user)."""
    user = auth["user"]
    project = await project_service.update(
        project_id,
        user.id,
        db,
        name=body.name,
        description=body.description,
    )
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.delete("/{project_id}")
async def delete_project(
    project_id: UUID,
    auth: AuthTokenDep,
    project_service: ProjectServiceDep,
    db: DatabaseDep,
):
    """Soft-delete a project (must belong to the current user)."""
    user = auth["user"]
    await project_service.delete(project_id, user.id, db)
    return {"success": True}
