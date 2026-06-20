"""Repository for Job model database operations.

Pure database CRUD operations with no business logic.
All methods are static and take a session as parameter.
"""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import Job

logger = logging.getLogger(__name__)


class JobRepository:
    """Repository for Job database operations."""

    @staticmethod
    async def create(
        db: AsyncSession,
        job_type: str,
        payload: dict[str, Any],
        user_id: UUID | None = None,
        priority: int = 100,
        max_attempts: int = 3,
    ) -> Job:
        """Create a new job.

        Args:
            db: Database session
            job_type: Type of job (e.g., "process_file")
            payload: Job payload data
            user_id: Optional user who created the job
            priority: Job priority (lower = higher priority)
            max_attempts: Maximum retry attempts

        Returns:
            Created Job instance
        """
        job = Job(
            job_type=job_type,
            payload=payload,
            created_by_id=user_id,
            priority=priority,
            max_attempts=max_attempts,
            status="pending",
            attempt_count=0,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        logger.info(f"Created job {job.id}: {job_type}")
        return job

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        job_id: UUID,
    ) -> Job | None:
        """Get a job by ID.

        Args:
            db: Database session
            job_id: Job UUID

        Returns:
            Job instance or None
        """
        stmt = select(Job).where(Job.id == job_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_user(
        db: AsyncSession,
        user_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Job]:
        """Get jobs for a user.

        Args:
            db: Database session
            user_id: User UUID
            limit: Maximum number of jobs to return
            offset: Number of jobs to skip

        Returns:
            List of Job instances
        """
        stmt = (
            select(Job)
            .where(Job.created_by_id == user_id)
            .order_by(Job.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_pending(
        db: AsyncSession,
        limit: int = 10,
    ) -> list[Job]:
        """Get pending jobs ordered by priority.

        Args:
            db: Database session
            limit: Maximum number of jobs to return

        Returns:
            List of pending Job instances
        """
        stmt = (
            select(Job)
            .where(Job.status == "pending")
            .order_by(Job.priority.asc(), Job.created_at.asc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update_status(
        db: AsyncSession,
        job_id: UUID,
        status: str,
        result: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> Job | None:
        """Update job status.

        Args:
            db: Database session
            job_id: Job UUID
            status: New status
            result: Optional result data (for completed jobs)
            error_message: Optional error message (for failed jobs)

        Returns:
            Updated Job instance or None
        """
        update_data: dict[str, Any] = {
            "status": status,
            "updated_at": datetime.now(timezone.utc),
        }

        if status == "running":
            update_data["started_at"] = datetime.now(timezone.utc)
        elif status in ("completed", "failed"):
            update_data["completed_at"] = datetime.now(timezone.utc)

        if result is not None:
            update_data["result"] = result
        if error_message is not None:
            update_data["error_message"] = error_message

        stmt = update(Job).where(Job.id == job_id).values(**update_data)
        await db.execute(stmt)
        await db.commit()

        logger.info(f"Updated job {job_id} status to {status}")
        return await JobRepository.get_by_id(db, job_id)

    @staticmethod
    async def mark_running(
        db: AsyncSession,
        job_id: UUID,
    ) -> Job | None:
        """Mark a job as running.

        Args:
            db: Database session
            job_id: Job UUID

        Returns:
            Updated Job instance or None
        """
        job = await JobRepository.get_by_id(db, job_id)
        if job:
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            job.attempt_count = (job.attempt_count or 0) + 1
            await db.commit()
            await db.refresh(job)
            logger.info(f"Job {job_id} marked as running (attempt {job.attempt_count})")
        return job

    @staticmethod
    async def mark_completed(
        db: AsyncSession,
        job_id: UUID,
        result: dict[str, Any] | None = None,
    ) -> Job | None:
        """Mark a job as completed.

        Args:
            db: Database session
            job_id: Job UUID
            result: Optional result data

        Returns:
            Updated Job instance or None
        """
        return await JobRepository.update_status(db, job_id, "completed", result=result)

    @staticmethod
    async def mark_failed(
        db: AsyncSession,
        job_id: UUID,
        error_message: str,
    ) -> Job | None:
        """Mark a job as failed.

        If max attempts not reached, marks as pending for retry.

        Args:
            db: Database session
            job_id: Job UUID
            error_message: Error message

        Returns:
            Updated Job instance or None
        """
        job = await JobRepository.get_by_id(db, job_id)
        if not job:
            return None

        if job.attempt_count < job.max_attempts:
            # Retry - set back to pending
            job.status = "pending"
            job.error_message = error_message
            logger.info(
                f"Job {job_id} failed, will retry "
                f"({job.attempt_count}/{job.max_attempts})"
            )
        else:
            # Max attempts reached - mark as failed
            job.status = "failed"
            job.error_message = error_message
            job.completed_at = datetime.now(timezone.utc)
            logger.info(
                f"Job {job_id} failed permanently "
                f"({job.attempt_count}/{job.max_attempts})"
            )

        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def update_progress(
        db: AsyncSession,
        job_id: UUID,
        progress: int,
        progress_message: str | None = None,
    ) -> Job | None:
        """Update job progress.

        Args:
            db: Database session
            job_id: Job UUID
            progress: Progress percentage (0-100)
            progress_message: Optional progress message

        Returns:
            Updated Job instance or None
        """
        update_data: dict[str, Any] = {
            "progress": progress,
            "updated_at": datetime.now(timezone.utc),
        }
        if progress_message:
            update_data["progress_message"] = progress_message

        stmt = update(Job).where(Job.id == job_id).values(**update_data)
        await db.execute(stmt)
        await db.commit()

        return await JobRepository.get_by_id(db, job_id)
