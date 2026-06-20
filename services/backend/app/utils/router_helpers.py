"""Helper functions for API routers."""

from fastapi import HTTPException, status

from core.logging import get_logger

logger = get_logger(__name__)


def check_service_configured(service_name: str, is_configured: bool) -> None:
    """
    Check if a service is configured.

    Args:
        service_name: Name of the service
        is_configured: Service configuration status

    Raises:
        HTTPException: If service is not configured
    """
    if not is_configured:
        logger.warning(f"{service_name} service accessed but not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{service_name} service not configured.",
        )
