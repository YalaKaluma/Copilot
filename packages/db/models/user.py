"""User model for Clerk authentication integration."""

from datetime import datetime, UTC
from uuid import uuid4

from sqlalchemy import Column, DateTime, String, Boolean
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import relationship

from packages.db.base import Base


class User(Base):
    """User model linked to Clerk authentication.

    Stores minimal user data locally - most user info comes from Clerk API.
    This table primarily serves as a foreign key reference for other entities.
    No PII is stored - all personal information remains in Clerk.
    """

    __tablename__ = "users"

    # Primary key
    id = Column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Clerk user ID - our primary reference to Clerk's user system
    clerk_user_id = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique identifier from Clerk authentication system",
    )

    # Optional display name (not real name)
    preferred_name = Column(
        String(255), nullable=True, comment="User's preferred display name for UI"
    )

    # User initials for display in UI (max 2 characters)
    initials = Column(
        String(2),
        nullable=True,
        comment="User initials for UI display (max 2 characters)",
    )

    # User role for role-based access control
    role = Column(
        String(50),
        nullable=True,
        default="user",
        comment="User role for access control (e.g., user, admin)",
    )

    # Soft delete
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships for storage features
    created_files = relationship(
        "File", foreign_keys="File.created_by_id", back_populates="created_by"
    )
    updated_files = relationship(
        "File", foreign_keys="File.updated_by_id", back_populates="updated_by"
    )
    created_buckets = relationship(
        "Bucket", foreign_keys="Bucket.created_by_id", back_populates="created_by"
    )
    updated_buckets = relationship(
        "Bucket", foreign_keys="Bucket.updated_by_id", back_populates="updated_by"
    )

    # Optional SKAI credentials (stored separately to avoid mixing concerns)
    skai_credentials = relationship(
        "SkaiCredential",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # Chat history
    conversations = relationship(
        "Conversation",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # Projects (user-scoped)
    projects = relationship(
        "Project",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # Instruction templates
    templates = relationship(
        "Template",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # Copilot feedback (on conversation messages)
    copilot_feedback = relationship(
        "CopilotFeedback",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<User {self.clerk_user_id}>"
