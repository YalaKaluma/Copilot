# Backend Code Patterns Guide

This guide documents the coding patterns and conventions used in this FastAPI backend for AI code generators (Claude, Cursor, etc).

## Testing Patterns

### Test Framework
- **Use pytest** - The test framework
- **Use pytest-mock** - For all mocking (provides `mocker` fixture)
- **Use pytest-asyncio** - For async test support

### Test Structure
```python
import pytest
from uuid import uuid4

class TestServiceName:
    """Test [ServiceName] functionality."""

    @pytest.mark.asyncio
    async def test_method_name(self, mocker):
        """Test that [specific behavior]."""
        service = ServiceName()

        # Create mocks using mocker fixture
        mock_db = mocker.AsyncMock()
        mock_user = mocker.Mock()
        mock_user.id = uuid4()

        # Patch with mocker - automatic cleanup
        mocker.patch.object(service, '_internal_method', return_value=mock_user)

        # Act
        result = await service.public_method(param, mock_db)

        # Assert
        assert result == expected_value
        mock_db.commit.assert_called_once()
```

### Fixture Patterns
```python
@pytest.fixture
def mock_storage_service(mocker):
    """Create a mock storage service."""
    mock = mocker.Mock(spec=BaseStorageService)
    mock.upload_file = mocker.AsyncMock(return_value="https://storage.example.com/file.pdf")
    return mock

@pytest.fixture
def mock_external_api(mocker):
    """Mock external API calls."""
    # Always patch at the import location, not definition
    mock_get = mocker.patch('routers.endpoint.requests.get')
    mock_get.return_value.json.return_value = {"status": "success"}
    return mock_get

@pytest_asyncio.fixture
async def authenticated_client(client: TestClient, test_db: AsyncSession, mocker):
    """Create a test client with mock authentication."""
    mock_verify = mocker.patch('core.dependencies.verify_clerk_token')
    mock_verify.return_value = {"user_id": "test_123", "user": test_user}
    return client
```

## Service Patterns

### Dependency Injection Pattern
All services use dependency injection, NOT singletons:

```python
from fastapi import Depends
from core.config import Settings, get_settings

class ServiceName:
    """Service for [domain] operations."""

    def __init__(self):
        """Initialize service."""
        self._client = None
        self._initialized = False

    def _get_client(self):
        """Lazy load expensive resources."""
        if not self._initialized:
            settings = get_settings()
            self._client = ExpensiveClient(settings.api_key)
            self._initialized = True
        return self._client

def get_service_name(settings: Settings = Depends(get_settings)) -> ServiceName:
    """Create service instance with dependency injection.

    FastAPI will cache this per request.
    """
    return ServiceName()
```

### Service with Expensive Initialization
Use @lru_cache for services with expensive initialization:

```python
from functools import lru_cache

@lru_cache()
def get_storage_service(settings: Settings = Depends(get_settings)) -> BaseStorageService:
    """Get storage service with caching for expensive GCS client."""
    provider = settings.storage_provider or StorageProvider.DEFAULT
    return create_storage_service(provider)
```

### Type Aliases for Dependencies
Define in `core/dependencies.py`:

```python
from typing import Annotated
from fastapi import Depends

ServiceNameDep = Annotated[ServiceName, Depends(get_service_name)]
DatabaseDep = Annotated[AsyncSession, Depends(get_db)]
AuthTokenDep = Annotated[dict, Depends(verify_clerk_token)]
```

## Router Patterns

### Endpoint Structure
```python
from fastapi import APIRouter, HTTPException, status
from core.dependencies import AuthTokenDep, DatabaseDep, ServiceNameDep
from core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["tag-name"])

@router.post("/resource", response_model=ResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_resource(
    request: RequestSchema,
    token: AuthTokenDep,  # Named parameter, not _
    db: DatabaseDep,
    service: ServiceNameDep
) -> ResponseSchema:
    """Create a new resource.

    Detailed description for OpenAPI docs.
    """
    try:
        # Business logic
        result = await service.create_resource(request.data, db)
        return ResponseSchema.from_model(result)

    except ValueError as e:
        # Domain errors -> 400
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        # Re-raise FastAPI exceptions
        raise
    except Exception as e:
        # Unexpected errors -> 500
        logger.error(f"Error creating resource: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create resource"
        )
```

## Error Handling Patterns

### Centralized Exception Handling
The application uses centralized exception handlers registered in `main.py`. Custom exceptions are defined in `core/exceptions.py` and automatically converted to appropriate HTTP responses.

### Custom Exceptions
Import from `core.exceptions` or `core`:

```python
from core.exceptions import NotFoundError, ValidationError, ConflictError, ForbiddenError
# or
from core import NotFoundError, ValidationError
```

| Exception | Status Code | When to Use |
|-----------|-------------|-------------|
| `NotFoundError` | 404 | Resource doesn't exist |
| `ValidationError` | 400 | Domain validation failed |
| `ConflictError` | 409 | Duplicate or conflict |
| `ForbiddenError` | 403 | User lacks permission |
| `UnauthorizedError` | 401 | Auth required/failed |
| `ServiceError` | 500 | Internal operation failed |
| `ServiceUnavailableError` | 503 | Service not configured |
| `ExternalAPIError` | 502 | External API failed |
| `RateLimitError` | 429 | Rate limit exceeded |

### Service Layer
Services raise custom exceptions - no try/except needed in routers:

```python
from core.exceptions import NotFoundError, ValidationError, ConflictError

class ServiceName:
    async def get_resource(self, resource_id: UUID, db: AsyncSession) -> Resource:
        resource = await self._get_by_id(resource_id, db)
        if not resource:
            raise NotFoundError("Resource", resource_id)
        return resource

    async def create_resource(self, data: dict, db: AsyncSession) -> Resource:
        # Domain validation
        if not data.get("name"):
            raise ValidationError("Name is required")

        # Check for duplicates
        existing = await self._get_by_name(data["name"], db)
        if existing:
            raise ConflictError("Resource with this name already exists")

        return await self._create(data, db)

    async def delete_resource(self, resource_id: UUID, user_id: UUID, db: AsyncSession):
        resource = await self.get_resource(resource_id, db)  # Raises NotFoundError

        if resource.owner_id != user_id:
            raise ForbiddenError("Cannot delete another user's resource")

        await self._delete(resource, db)
```

### Router Layer
Routers are clean - just call services. Global handlers catch exceptions:

```python
from core.dependencies import AuthTokenDep, DatabaseDep, ServiceNameDep

@router.get("/resources/{resource_id}", response_model=ResourceResponse)
async def get_resource(
    resource_id: UUID,
    token: AuthTokenDep,
    db: DatabaseDep,
    service: ServiceNameDep,
) -> ResourceResponse:
    """Get resource by ID."""
    # No try/except needed - NotFoundError auto-converts to 404
    resource = await service.get_resource(resource_id, db)
    return ResourceResponse.from_model(resource)

@router.post("/resources", response_model=ResourceResponse, status_code=201)
async def create_resource(
    request: ResourceRequest,
    token: AuthTokenDep,
    db: DatabaseDep,
    service: ServiceNameDep,
) -> ResourceResponse:
    """Create resource."""
    # ValidationError -> 400, ConflictError -> 409 automatically
    resource = await service.create_resource(request.model_dump(), db)
    return ResourceResponse.from_model(resource)
```

### When to Use HTTPException
Still use `HTTPException` for router-specific HTTP logic:

```python
from fastapi import HTTPException, status

@router.post("/webhooks")
async def handle_webhook(request: Request):
    # Signature verification is HTTP-specific
    if not verify_signature(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature"
        )
```

### Migration from ValueError Pattern
Old pattern (still works but not recommended):
```python
# Service
if not valid:
    raise ValueError("Invalid input")

# Router
try:
    result = await service.do_something()
except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e))
```

New pattern (recommended):
```python
# Service
if not valid:
    raise ValidationError("Invalid input")

# Router - no try/except needed
result = await service.do_something()
```

## Schema Patterns

### Response Schema with Model Conversion
Use class methods for model-to-schema conversion:

```python
from pydantic import BaseModel
from typing import Any
from uuid import UUID

class ResourceResponse(BaseModel):
    """Resource response model."""
    id: UUID
    name: str
    created_at: str
    metadata: dict[str, Any] = {}

    @classmethod
    def from_model(cls, model) -> "ResourceResponse":
        """Convert database model to response schema."""
        return cls(
            id=model.id,
            name=model.name,
            created_at=model.created_at.isoformat(),
            metadata=model.metadata or {}
        )
```

Note: Use `from_model()` or specific names like `from_file_model()`, NOT deprecated `from_orm()`.

### Request Validation
```python
from pydantic import BaseModel, Field, field_validator

class ResourceRequest(BaseModel):
    """Resource creation request."""
    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., pattern="^[a-z0-9-]+$")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate name format."""
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()
```

## Database Patterns

### Async Session Usage
```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

async def get_resources(self, db: AsyncSession) -> list[Resource]:
    """Get all resources."""
    stmt = select(Resource).where(
        Resource.is_deleted == False
    ).order_by(Resource.created_at.desc())

    result = await db.execute(stmt)
    return result.scalars().all()
```

### Transaction Handling
```python
try:
    resource = Resource(name=name)
    db.add(resource)
    await db.commit()
    await db.refresh(resource)
    return resource

except IntegrityError:
    await db.rollback()
    # Handle unique constraint violation
    raise ValueError("Resource with this name already exists")
```

## Status Codes

### Common HTTP Status Codes
- **200** OK - Successful GET, PUT
- **201** Created - Successful POST creating new resource
- **204** No Content - Successful DELETE
- **400** Bad Request - Validation error, domain error (ValueError)
- **401** Unauthorized - No/invalid authentication token
- **403** Forbidden - Clerk returns 403 for invalid tokens (not 401)
- **404** Not Found - Resource doesn't exist
- **422** Unprocessable Entity - FastAPI validation error
- **500** Internal Server Error - Unexpected errors

## Configuration Patterns

### Settings with Pydantic
```python
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    """Application settings."""
    database_url: str
    clerk_secret_key: str | None = None

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
```

## Main Application Structure

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting application...")
    await init_database()

    # Services initialized via DI on first use
    logger.info("✅ Services configured for dependency injection")

    yield

    # Shutdown
    await close_database()

app = FastAPI(lifespan=lifespan)
```

## Testing with Dependency Overrides

```python
# In conftest.py
app.dependency_overrides[get_storage_service] = lambda: mock_storage_service
app.dependency_overrides[get_settings] = lambda: test_settings

# In tests
@pytest_asyncio.fixture
async def authenticated_client(client: TestClient, test_db: AsyncSession):
    """Override auth dependency."""
    app.dependency_overrides[verify_clerk_token] = mock_verify_token
    return client
```

## Key Principles

1. **No Singletons** - Use dependency injection for all services
2. **Lazy Loading** - Initialize expensive resources only when needed
3. **Per-Request Caching** - FastAPI caches dependencies per request
4. **Clear Error Handling** - Map exceptions consistently across layers
5. **Type Safety** - Use type hints and Pydantic models everywhere
6. **Async First** - Use async/await for all I/O operations
7. **Test Isolation** - Mock dependencies, don't modify app logic for tests
