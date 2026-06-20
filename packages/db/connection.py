"""Database connection and session management."""

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)


def fix_database_url_for_asyncpg(database_url: str) -> str:
    """
    Fix database URL for asyncpg compatibility.

    Handles:
    1. Escaped slashes from Terraform/Cloud Run (\\/ becomes /)
    2. Neon's 'sslmode=require' -> asyncpg's 'ssl=require'

    Args:
        database_url: PostgreSQL connection string

    Returns:
        Fixed connection string compatible with asyncpg
    """
    if not database_url:
        return database_url

    # Fix escaped slashes that come from Terraform environment variables
    # Cloud Run seems to escape the slashes when passing env vars
    if "\\/" in database_url or "%2F" in database_url:
        logger.debug(f"Fixing escaped DATABASE_URL: {database_url[:50]}...")
        # Replace escaped slashes
        database_url = database_url.replace("\\/", "/")
        # Also handle URL encoding if present
        database_url = database_url.replace("%2F", "/")
        logger.debug(f"Fixed DATABASE_URL: {database_url[:50]}...")

    if "sslmode=require" in database_url:
        logger.debug(
            "Converting sslmode=require to ssl=require for asyncpg compatibility"
        )
        database_url = database_url.replace("sslmode=require", "ssl=require")

    return database_url


class DatabaseManager:
    """Manages database connections and sessions."""

    def __init__(self):
        self.engine = None
        self.session_factory = None

    async def init(
        self,
        database_url: str,
        echo: bool = False,
        pool_size: int = 5,
        max_overflow: int = 10,
    ):
        """Initialize database connection."""
        if not database_url:
            raise ValueError("DATABASE_URL not configured")

        # Fix database URL for asyncpg compatibility
        database_url = fix_database_url_for_asyncpg(database_url)

        self.engine = create_async_engine(
            database_url,
            echo=echo,
            pool_pre_ping=True,
            pool_size=pool_size,
            max_overflow=max_overflow,
        )

        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        logger.info("Database connection initialized")

    async def close(self):
        """Close database connection."""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connection closed")

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a database session."""
        if not self.session_factory:
            raise RuntimeError("Database not initialized")

        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()


# Global database manager instance
db_manager = DatabaseManager()


# Convenience functions for backwards compatibility
async def init_database(
    database_url: str,
    echo: bool = False,
    pool_size: int = 5,
    max_overflow: int = 10,
):
    """Initialize database connection."""
    await db_manager.init(database_url, echo, pool_size, max_overflow)


async def close_database():
    """Close database connection."""
    await db_manager.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async for session in db_manager.get_session():
        yield session
