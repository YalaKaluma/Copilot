"""Repository for File model database operations.

Pure database CRUD operations with no business logic.
All methods are static and take a session as parameter.
"""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from packages.db.models import File

logger = logging.getLogger(__name__)


class FileRepository:
    """Repository for File database operations."""

    @staticmethod
    async def create(
        db: AsyncSession,
        bucket_id: UUID,
        filename: str,
        original_filename: str,
        storage_path: str,
        content_type: str,
        file_size: int,
        created_by_id: UUID,
        status: str = "pending",
        extension: str | None = None,
        file_metadata: dict[str, Any] | None = None,
    ) -> File:
        """Create a new file record.

        Args:
            db: Database session
            bucket_id: Bucket UUID
            filename: Sanitized filename
            original_filename: Original uploaded filename
            storage_path: Path in cloud storage
            content_type: MIME type
            file_size: Size in bytes
            created_by_id: User UUID who created the file
            status: Initial status (default: pending)
            extension: File extension
            file_metadata: Optional metadata dict

        Returns:
            Created File instance
        """
        file = File(
            bucket_id=bucket_id,
            filename=filename,
            original_filename=original_filename,
            storage_path=storage_path,
            content_type=content_type,
            file_size=file_size,
            created_by_id=created_by_id,
            status=status,
            extension=extension,
            file_metadata=file_metadata,
        )
        db.add(file)
        await db.commit()
        await db.refresh(file)

        logger.info(f"Created file {file.id}: {original_filename}")
        return file

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        file_id: UUID,
        include_bucket: bool = False,
    ) -> File | None:
        """Get a file by ID.

        Args:
            db: Database session
            file_id: File UUID
            include_bucket: Whether to eager load bucket relationship

        Returns:
            File instance or None
        """
        stmt = select(File).where(File.id == file_id)
        if include_bucket:
            stmt = stmt.options(selectinload(File.bucket))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_bucket(
        db: AsyncSession,
        bucket_id: UUID,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> list[File]:
        """Get files for a bucket.

        Args:
            db: Database session
            bucket_id: Bucket UUID
            limit: Maximum number of files to return
            offset: Number of files to skip
            status: Optional status filter

        Returns:
            List of File instances
        """
        stmt = (
            select(File)
            .where(File.bucket_id == bucket_id)
            .order_by(File.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if status:
            stmt = stmt.where(File.status == status)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_user(
        db: AsyncSession,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[File]:
        """Get files created by a user.

        Args:
            db: Database session
            user_id: User UUID
            limit: Maximum number of files to return
            offset: Number of files to skip

        Returns:
            List of File instances
        """
        stmt = (
            select(File)
            .where(File.created_by_id == user_id)
            .order_by(File.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update_status(
        db: AsyncSession,
        file_id: UUID,
        status: str,
    ) -> File | None:
        """Update file status.

        Args:
            db: Database session
            file_id: File UUID
            status: New status

        Returns:
            Updated File instance or None
        """
        stmt = (
            update(File)
            .where(File.id == file_id)
            .values(status=status, updated_at=datetime.now(timezone.utc))
        )
        await db.execute(stmt)
        await db.commit()

        logger.info(f"Updated file {file_id} status to {status}")
        return await FileRepository.get_by_id(db, file_id)

    @staticmethod
    async def update_metadata(
        db: AsyncSession,
        file_id: UUID,
        metadata: dict[str, Any],
        merge: bool = True,
    ) -> File | None:
        """Update file metadata.

        Args:
            db: Database session
            file_id: File UUID
            metadata: Metadata to set/merge
            merge: If True, merge with existing; if False, replace

        Returns:
            Updated File instance or None
        """
        file = await FileRepository.get_by_id(db, file_id)
        if not file:
            return None

        if merge and file.file_metadata:
            file.file_metadata = {**file.file_metadata, **metadata}
        else:
            file.file_metadata = metadata

        file.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(file)

        logger.info(f"Updated file {file_id} metadata")
        return file

    @staticmethod
    async def search(
        db: AsyncSession,
        query: str,
        bucket_id: UUID | None = None,
        limit: int = 20,
    ) -> list[File]:
        """Search files by filename.

        Args:
            db: Database session
            query: Search query
            bucket_id: Optional bucket filter
            limit: Maximum results

        Returns:
            List of matching File instances
        """
        search_pattern = f"%{query}%"
        stmt = (
            select(File)
            .where(
                (File.filename.ilike(search_pattern))
                | (File.original_filename.ilike(search_pattern))
            )
            .order_by(File.created_at.desc())
            .limit(limit)
        )
        if bucket_id:
            stmt = stmt.where(File.bucket_id == bucket_id)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_stats(
        db: AsyncSession,
        bucket_id: UUID | None = None,
        user_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Get file statistics.

        Args:
            db: Database session
            bucket_id: Optional bucket filter
            user_id: Optional user filter

        Returns:
            Dict with total_files, total_size_bytes, average_size_bytes
        """
        stmt = select(
            func.count(File.id).label("total_files"),
            func.coalesce(func.sum(File.file_size), 0).label("total_size"),
            func.coalesce(func.avg(File.file_size), 0).label("avg_size"),
        ).where(File.status == "available")

        if bucket_id:
            stmt = stmt.where(File.bucket_id == bucket_id)
        if user_id:
            stmt = stmt.where(File.created_by_id == user_id)

        result = await db.execute(stmt)
        row = result.one()

        return {
            "total_files": row.total_files,
            "total_size_bytes": int(row.total_size),
            "average_size_bytes": int(row.avg_size),
        }

    @staticmethod
    async def soft_delete(
        db: AsyncSession,
        file_id: UUID,
    ) -> File | None:
        """Soft delete a file by setting status to deleted.

        Args:
            db: Database session
            file_id: File UUID

        Returns:
            Updated File instance or None
        """
        return await FileRepository.update_status(db, file_id, "deleted")
