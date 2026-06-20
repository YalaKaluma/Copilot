"""Health check schemas."""

from pydantic import Field

from .base import CamelCaseModel


class HealthResponse(CamelCaseModel):
    """Health check response."""

    status: str = Field(
        ..., description="Health status", examples=["healthy", "degraded", "unhealthy"]
    )
    service: str = Field(default="backend", description="Service name")


class ReadinessResponse(CamelCaseModel):
    """Readiness check response with component status."""

    status: str = Field(
        ..., description="Overall readiness status", examples=["ready", "not ready"]
    )
    database: str = Field(
        ...,
        description="Database connection status",
        examples=["connected", "disconnected"],
    )
    redis: str = Field(
        default="not configured",
        description="Redis connection status",
        examples=["connected", "disconnected", "not configured"],
    )
    langfuse: str = Field(
        default="not configured",
        description="Langfuse observability status",
        examples=["enabled", "not configured"],
    )
    error: str | None = Field(default=None, description="Error message if not ready")
