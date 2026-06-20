"""Bucket model for GCP storage management."""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.db.base import BaseModel

if TYPE_CHECKING:
    from packages.db.models.file import File
    from packages.db.models.user import User


class Bucket(BaseModel):
    """Model for managing cloud storage buckets (primarily GCP).

    Represents a storage bucket configuration with metadata about
    access permissions, provider details, and user ownership.
    """

    __tablename__ = "upd_bucket"

    # Bucket identification
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Actual bucket name (e.g., 'investment-reports-dev')",
    )

    slug: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Human-readable slug for URLs (e.g., 'investment-reports')",
    )

    # Provider and access configuration
    provider: Mapped[str] = mapped_column(
        String(50),
        default="gcp",
        nullable=False,
        comment="Cloud provider: 'gcp', 'aws', 'azure'",
    )

    is_public: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether bucket contents are publicly accessible",
    )

    # User relationships
    created_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        comment="User who created this bucket",
    )

    updated_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who last updated this bucket",
    )

    # Relationships
    created_by: Mapped["User"] = relationship(
        "User", foreign_keys=[created_by_id], back_populates="created_buckets"
    )

    updated_by: Mapped["User"] = relationship(
        "User", foreign_keys=[updated_by_id], back_populates="updated_buckets"
    )

    files: Mapped[list["File"]] = relationship(
        "File", back_populates="bucket", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<Bucket(id={self.id}, name={self.name}, slug={self.slug})>"
