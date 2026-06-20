"""Job model for worker queue tracking."""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.db.base import BaseModel

if TYPE_CHECKING:
    from packages.db.models.user import User


class Job(BaseModel):
    """Model for tracking background jobs processed by workers.

    Stores job metadata, status, and results for async task processing.
    Used by the worker service to track and manage background tasks.
    """

    __tablename__ = "jobs"

    # Job type/name for routing to appropriate handler
    job_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Job type identifier (e.g., 'process_file', 'send_email')",
    )

    # Job status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
        comment="Job status: pending, running, completed, failed, cancelled",
    )

    # Priority for queue ordering (lower = higher priority)
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,
        server_default="100",
        index=True,
        comment="Job priority (lower = higher priority)",
    )

    # Job payload/arguments
    payload: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Job input data/arguments as JSON",
    )

    # Job result/output
    result: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Job result data as JSON",
    )

    # Error information if failed
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if job failed",
    )

    # Retry tracking
    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Number of execution attempts",
    )

    max_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        server_default="3",
        comment="Maximum retry attempts",
    )

    # Optional user association
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User who triggered this job (if applicable)",
    )

    # Relationships
    user: Mapped["User | None"] = relationship("User")

    def __repr__(self) -> str:
        """String representation."""
        return f"<Job(id={self.id}, type={self.job_type}, status={self.status})>"
