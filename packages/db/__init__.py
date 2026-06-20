"""Shared database package for backend and worker services."""

from packages.db.base import Base, BaseModel, metadata
from packages.db.connection import (
    DatabaseManager,
    db_manager,
    init_database,
    close_database,
    get_db,
    fix_database_url_for_asyncpg,
)
from packages.db.models import (
    User,
    File,
    Bucket,
    Job,
    SkaiCredential,
    Conversation,
    ConversationMessage,
    Project,
    Template,
    CopilotFeedback,
)

__all__ = [
    # Base classes
    "Base",
    "BaseModel",
    "metadata",
    # Connection management
    "DatabaseManager",
    "db_manager",
    "init_database",
    "close_database",
    "get_db",
    "fix_database_url_for_asyncpg",
    # Models
    "User",
    "File",
    "Bucket",
    "Job",
    "SkaiCredential",
    "Conversation",
    "ConversationMessage",
    "Project",
    "Template",
    "CopilotFeedback",
]
