"""Health check endpoints for Kubernetes/monitoring patterns.

Implements standard K8s health check patterns:
- Liveness: Is the service alive and responding?
- Readiness: Is the service ready to handle traffic?
"""

import os
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from core.logging import get_logger
from packages.db import get_db
from schemas.health import HealthResponse, ReadinessResponse
from packages.langfuse import is_langfuse_enabled as langfuse_enabled

logger = get_logger(__name__)
router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe",
    description="Kubernetes liveness probe - checks if the service is alive. Does NOT check dependencies.",
    tags=["Health"],
)
async def health_check() -> HealthResponse:
    """Liveness probe endpoint (Kubernetes pattern).

    Used by Kubernetes/Cloud Run to determine if the container should be restarted.
    Intentionally does not check database or external dependencies.

    Returns:
        HealthResponse: Basic service health status
    """
    return HealthResponse(status="healthy", service="backend")


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe",
    description="Kubernetes readiness probe - checks if the service is ready to handle traffic, including all dependencies.",
    tags=["Health"],
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ReadinessResponse,
            "description": "Service not ready to handle requests",
        }
    },
)
async def readiness_check(db: AsyncSession = Depends(get_db)) -> ReadinessResponse:
    """Readiness probe endpoint (Kubernetes pattern).

    Used by Kubernetes/Cloud Run to determine if traffic should be routed to this instance.
    Checks all critical dependencies (database, external services, etc.).

    Args:
        db: Database session

    Returns:
        ReadinessResponse: Service readiness with component status
    """
    db_status = "disconnected"
    redis_status = "not configured"
    langfuse_status = "enabled" if langfuse_enabled() else "not configured"
    errors = []

    # Check database connection
    try:
        result = await db.execute(text("SELECT 1"))
        result.scalar()
        db_status = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        errors.append(f"database: {e}")

    # Determine overall status (database is critical, redis is optional)
    is_ready = db_status == "connected"

    return ReadinessResponse(
        status="ready" if is_ready else "not ready",
        database=db_status,
        redis=redis_status,
        langfuse=langfuse_status,
        error="; ".join(errors) if errors else None,
    )


@router.get(
    "/health/storage",
    summary="Storage configuration status",
    description="Check if real Google Cloud Storage is configured",
    tags=["Health"],
)
async def storage_status():
    """Check storage configuration status.

    Returns:
        dict: Storage configuration details
    """
    has_explicit_credentials = bool(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"))
    gcs_bucket = os.getenv("GCS_BUCKET_NAME", "")
    emulator_host = os.getenv("STORAGE_EMULATOR_HOST")
    is_cloud_run = bool(os.getenv("K_SERVICE"))  # Cloud Run sets this

    # Using real GCS if:
    # 1. We have explicit credentials, OR
    # 2. We're on Cloud Run (uses Application Default Credentials)
    is_real_gcs = (has_explicit_credentials or is_cloud_run) and gcs_bucket

    return {
        "configured": gcs_bucket if is_real_gcs else False,
        "mode": "real" if is_real_gcs else "fake",
        "bucket_name": gcs_bucket if is_real_gcs else None,
        "details": {
            "storage_mode": "real" if is_real_gcs else "fake",
            "has_credentials": has_explicit_credentials,
            "is_cloud_run": is_cloud_run,
            "has_bucket_name": bool(gcs_bucket),
            "emulator_host": emulator_host,
        },
    }
