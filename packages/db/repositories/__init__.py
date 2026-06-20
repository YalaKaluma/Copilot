"""Repository pattern for database access.

Provides a clean separation between data access and business logic.
All repositories use async SQLAlchemy 2.0 patterns.

Usage:
    from packages.db.repositories import JobRepository, FileRepository

    # Create a job
    job = await JobRepository.create(db, "process_file", {"file_id": "..."})

    # Get by ID
    job = await JobRepository.get_by_id(db, job_id)
"""

from .job_repository import JobRepository
from .file_repository import FileRepository

__all__ = [
    "JobRepository",
    "FileRepository",
]
