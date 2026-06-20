"""User service for managing user operations."""

from datetime import datetime, UTC
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from packages.db.models import User

logger = get_logger(__name__)


class UserService:
    """Service for user-related database operations."""

    async def create_or_get_user(self, clerk_user_id: str, db: AsyncSession) -> User:
        """Create a new user or get existing user by Clerk user ID.

        This is the primary method for handling user authentication.
        Called when a user first hits our API with a valid Clerk token.

        Args:
            clerk_user_id: Unique identifier from Clerk authentication system
            db: Database session to use for the operation

        Returns:
            User model instance (either newly created or existing)

        Raises:
            ValueError: If clerk_user_id is empty or invalid
        """
        if not clerk_user_id or not clerk_user_id.strip():
            raise ValueError("clerk_user_id cannot be empty")

        clerk_user_id = clerk_user_id.strip()

        try:
            # First, try to get existing user
            existing_user = await self._get_user_by_clerk_id_query(clerk_user_id, db)
            if existing_user:
                logger.debug(f"Found existing user for Clerk ID: {clerk_user_id}")
                return existing_user

            # Create new user if doesn't exist
            new_user = User(clerk_user_id=clerk_user_id)
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)

            logger.info(
                f"Created new user for Clerk ID: {clerk_user_id}, DB ID: {new_user.id}"
            )
            return new_user

        except IntegrityError:
            # Handle race condition - another request created the user
            await db.rollback()
            logger.debug(
                f"Race condition creating user for Clerk ID: {clerk_user_id}, retrying..."
            )

            # Try to get the user that was created by the other request
            existing_user = await self._get_user_by_clerk_id_query(clerk_user_id, db)
            if existing_user:
                return existing_user

            # If still not found, something went wrong
            logger.error(
                f"Failed to create or retrieve user for Clerk ID: {clerk_user_id}"
            )
            raise ValueError(f"Failed to create user for Clerk ID: {clerk_user_id}")

    async def get_user_by_clerk_id(
        self, clerk_user_id: str, db: AsyncSession
    ) -> User | None:
        """Get user by Clerk user ID.

        Args:
            clerk_user_id: Unique identifier from Clerk authentication system
            db: Database session to use for the operation

        Returns:
            User model instance or None if not found
        """
        if not clerk_user_id or not clerk_user_id.strip():
            return None

        return await self._get_user_by_clerk_id_query(clerk_user_id.strip(), db)

    async def _get_user_by_clerk_id_query(
        self, clerk_user_id: str, db: AsyncSession
    ) -> User | None:
        """Internal method to execute the query."""
        try:
            stmt = select(User).where(
                User.clerk_user_id == clerk_user_id,
                User.is_deleted == False,  # noqa: E712
            )
            result = await db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error querying user by Clerk ID {clerk_user_id}: {e}")
            return None

    async def get_user_by_id(self, user_id: UUID, db: AsyncSession) -> User | None:
        """Get user by internal database ID.

        Args:
            user_id: Internal database UUID for the user
            db: Database session to use for the operation

        Returns:
            User model instance or None if not found
        """
        try:
            stmt = select(User).where(
                User.id == user_id,
                User.is_deleted == False,  # noqa: E712
            )
            result = await db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error querying user by ID {user_id}: {e}")
            return None

    async def delete_user(self, clerk_user_id: str, db: AsyncSession) -> bool:
        """Soft delete user by Clerk user ID.

        This method is called via Clerk webhooks when a user
        is deleted from Clerk's system. Performs soft delete for audit purposes.

        Args:
            clerk_user_id: Unique identifier from Clerk authentication system
            db: Database session to use for the operation

        Returns:
            True if user was deleted, False if user didn't exist
        """
        try:
            # Query without the deleted_at filter to find the user
            stmt = select(User).where(User.clerk_user_id == clerk_user_id)
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                logger.debug(f"User not found for deletion: {clerk_user_id}")
                return False

            if user.deleted_at is not None:
                logger.debug(f"User already soft deleted: {clerk_user_id}")
                return True

            # Soft delete by setting deleted_at timestamp
            user.is_deleted = True
            user.deleted_at = datetime.now(UTC)
            await db.commit()

            logger.info(f"Soft deleted user for Clerk ID: {clerk_user_id}")
            return True

        except Exception as e:
            await db.rollback()
            logger.error(f"Error deleting user {clerk_user_id}: {e}")
            raise ValueError(f"Failed to delete user: {str(e)}")


def get_user_service() -> UserService:
    """Create user service instance with dependency injection.

    FastAPI will cache this per request, so we don't create multiple instances
    within the same request context.

    Returns:
        UserService instance
    """
    return UserService()
