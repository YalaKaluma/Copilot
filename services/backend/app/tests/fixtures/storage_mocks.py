"""Mock fixtures for Google Cloud Storage testing.

This module provides reusable mock fixtures for testing GCS-dependent code.
Following best practices from the Python community for mocking GCS SDK.
"""

from unittest.mock import AsyncMock, Mock, PropertyMock, patch

import pytest


@pytest.fixture
def mock_gcs_client():
    """Mock Google Cloud Storage client for unit testing.

    Returns a mock client with commonly used methods pre-configured.
    Tests can further customize the mock as needed.
    """
    with patch("services.storage.gcp_storage.storage.Client") as mock_client_class:
        # Create mock instances
        mock_client = Mock()
        mock_bucket = Mock()
        mock_blob = Mock()

        # Configure the client
        mock_client_class.return_value = mock_client
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        # Configure blob methods with sensible defaults
        mock_blob.exists.return_value = False
        mock_blob.upload_from_string.return_value = None
        mock_blob.upload_from_file.return_value = None
        mock_blob.download_as_bytes.return_value = b"test content"
        mock_blob.download_as_text.return_value = "test content"
        mock_blob.delete.return_value = None

        # Configure blob properties
        type(mock_blob).size = PropertyMock(return_value=1024)
        type(mock_blob).content_type = PropertyMock(
            return_value="application/octet-stream"
        )
        type(mock_blob).metadata = PropertyMock(return_value={})
        type(mock_blob).public_url = PropertyMock(
            return_value="https://storage.googleapis.com/test-bucket/test-file"
        )

        # Configure generate_signed_url
        mock_blob.generate_signed_url.return_value = (
            "https://storage.googleapis.com/signed-url"
        )

        # List blobs returns empty by default
        mock_bucket.list_blobs.return_value = []

        yield {
            "client_class": mock_client_class,
            "client": mock_client,
            "bucket": mock_bucket,
            "blob": mock_blob,
        }


@pytest.fixture
def mock_gcs_with_files():
    """Mock GCS client with pre-existing files for testing.

    Sets up a mock GCS environment with some test files already present.
    """
    with patch("services.storage.gcp_storage.storage.Client") as mock_client_class:
        mock_client = Mock()
        mock_bucket = Mock()

        # Create multiple mock blobs
        mock_blobs = []
        for i in range(3):
            blob = Mock()
            blob.name = f"test-file-{i}.txt"
            type(blob).size = PropertyMock(return_value=1024 * (i + 1))
            type(blob).content_type = PropertyMock(return_value="text/plain")
            blob.exists.return_value = True
            blob.download_as_text.return_value = f"Content of file {i}"
            mock_blobs.append(blob)

        # Configure client and bucket
        mock_client_class.return_value = mock_client
        mock_client.bucket.return_value = mock_bucket

        # Configure list_blobs to return our mock blobs
        mock_bucket.list_blobs.return_value = mock_blobs

        # Configure blob() to return appropriate blob based on name
        def get_blob(name):
            for blob in mock_blobs:
                if blob.name == name:
                    return blob
            # Return a new mock for non-existing files
            new_blob = Mock()
            new_blob.name = name
            new_blob.exists.return_value = False
            return new_blob

        mock_bucket.blob.side_effect = get_blob

        yield {
            "client_class": mock_client_class,
            "client": mock_client,
            "bucket": mock_bucket,
            "blobs": mock_blobs,
        }


@pytest.fixture
def mock_gcs_with_errors():
    """Mock GCS client that simulates various error conditions.

    Useful for testing error handling in storage operations.
    """
    with patch("services.storage.gcp_storage.storage.Client") as mock_client_class:
        from google.cloud import exceptions

        mock_client = Mock()
        mock_bucket = Mock()
        mock_blob = Mock()

        mock_client_class.return_value = mock_client
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        # Configure methods to raise exceptions
        mock_blob.upload_from_string.side_effect = exceptions.GoogleCloudError(
            "Upload failed"
        )
        mock_blob.download_as_bytes.side_effect = exceptions.NotFound("Blob not found")
        mock_blob.delete.side_effect = exceptions.Forbidden("Permission denied")
        mock_blob.exists.return_value = False

        # List blobs raises an error
        mock_bucket.list_blobs.side_effect = exceptions.GoogleCloudError("List failed")

        yield {
            "client_class": mock_client_class,
            "client": mock_client,
            "bucket": mock_bucket,
            "blob": mock_blob,
            "exceptions": exceptions,
        }


@pytest.fixture
def mock_storage_service():
    """Mock the entire storage service for higher-level testing.

    This mocks at the service level rather than the GCS SDK level.
    Useful when you want to test business logic without GCS details.
    """
    mock_service = Mock()

    # Configure async methods with AsyncMock
    mock_service.upload_file = AsyncMock(
        return_value={
            "file_path": "test/path/file.txt",
            "public_url": "https://storage.googleapis.com/bucket/file.txt",
            "size": 1024,
        }
    )

    mock_service.generate_signed_url = AsyncMock(
        return_value="https://storage.googleapis.com/signed-url"
    )

    mock_service.download_file = AsyncMock(return_value=b"test content")

    mock_service.delete_file = AsyncMock(return_value=True)

    mock_service.list_files = AsyncMock(
        return_value=[
            {"name": "file1.txt", "size": 1024},
            {"name": "file2.txt", "size": 2048},
        ]
    )

    mock_service.file_exists = AsyncMock(return_value=True)

    mock_service.get_file_metadata = AsyncMock(
        return_value={
            "size": 1024,
            "content_type": "text/plain",
            "created": "2024-01-01T00:00:00Z",
        }
    )

    # Add provider attribute
    mock_service.provider = "mock"

    yield mock_service


@pytest.fixture
def mock_storage_service_factory():
    """Factory fixture for creating custom mock storage services.

    Returns a function that creates configured mock storage services.
    """

    def create_mock_service(**kwargs):
        """Create a mock storage service with custom configuration.

        Args:
            **kwargs: Custom return values for service methods
        """
        mock_service = AsyncMock()

        # Set default values
        defaults = {
            "upload_file": {"file_path": "test/file.txt", "size": 1024},
            "get_presigned_upload_url": {"upload_url": "https://signed.url"},
            "get_presigned_download_url": "https://download.url",
            "download_file": b"content",
            "delete_file": True,
            "list_files": [],
            "file_exists": False,
        }

        # Override with custom values
        defaults.update(kwargs)

        # Configure mock methods
        for method, return_value in defaults.items():
            if hasattr(mock_service, method):
                getattr(mock_service, method).return_value = return_value

        return mock_service

    return create_mock_service
