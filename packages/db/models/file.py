"""File model for tracking uploaded files in buckets."""

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.db.base import BaseModel

if TYPE_CHECKING:
    from packages.db.models.bucket import Bucket
    from packages.db.models.user import User


class File(BaseModel):
    """Model for tracking file metadata in cloud storage buckets.

    Stores metadata about files uploaded to buckets, including original
    filenames, processed names, storage paths, and user ownership.
    """

    __tablename__ = "upd_files"

    # Bucket relationship
    bucket_id: Mapped[UUID] = mapped_column(
        ForeignKey("upd_bucket.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the bucket containing this file",
    )

    # File identification and metadata
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Display name for the file (can be renamed)",
    )

    original_filename: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Original filename when uploaded"
    )

    extension: Mapped[str] = mapped_column(
        String(10), nullable=True, comment="File extension (e.g., '.pdf', '.xlsx')"
    )

    file_size: Mapped[int] = mapped_column(
        BigInteger, nullable=True, comment="File size in bytes"
    )

    content_type: Mapped[str] = mapped_column(
        String(100), nullable=True, comment="MIME type (e.g., 'application/pdf')"
    )

    # Storage path
    storage_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Full path within the bucket (e.g., 'reports/2024/Q1/report.pdf')",
    )

    # File status for upload tracking
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
        comment="Upload status: pending, uploading, available, deleted",
    )

    # Additional metadata (optional)
    file_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional file metadata (e.g., dimensions for images, duration for videos)",
    )

    # User relationships
    created_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        comment="User who uploaded this file",
    )

    updated_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who last updated this file metadata",
    )

    # Relationships
    bucket: Mapped["Bucket"] = relationship("Bucket", back_populates="files")

    created_by: Mapped["User"] = relationship(
        "User", foreign_keys=[created_by_id], back_populates="created_files"
    )

    updated_by: Mapped["User"] = relationship(
        "User", foreign_keys=[updated_by_id], back_populates="updated_files"
    )

    # Table constraints
    __table_args__ = (
        UniqueConstraint("bucket_id", "storage_path", name="uq_bucket_storage_path"),
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<File(id={self.id}, filename={self.filename}, storage_path={self.storage_path})>"
