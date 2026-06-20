"""Database initialization wrapper using app settings.

The actual database logic lives in packages.db.
This module provides a thin wrapper that reads from app config.
"""

from packages.db import (
    init_database as _init_database,
    close_database,
)
from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)


async def init_database():
    """Initialize database connection using app settings."""
    settings = get_settings()
    if not settings.database_url:
        raise ValueError("DATABASE_URL not configured")

    await _init_database(
        database_url=settings.database_url,
        echo=settings.debug,
        pool_size=5,
        max_overflow=10,
    )

    logger.info("Database connection initialized")


__all__ = ["init_database", "close_database"]
