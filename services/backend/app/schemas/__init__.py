"""API schemas for request/response models."""

from .base import CamelCaseModel, BaseResponse, TimestampedResponse
from .common import ErrorResponse, SuccessResponse, PaginatedResponse
from .health import HealthResponse, ReadinessResponse
from .users import UserResponse, UserCreateRequest, UserUpdateRequest

__all__ = [
    # Base
    "CamelCaseModel",
    "BaseResponse",
    "TimestampedResponse",
    # Common
    "ErrorResponse",
    "SuccessResponse",
    "PaginatedResponse",
    # Health
    "HealthResponse",
    "ReadinessResponse",
    # Users
    "UserResponse",
    "UserCreateRequest",
    "UserUpdateRequest",
]
