"""User management endpoints."""

from fastapi import APIRouter, HTTPException, status

from core.dependencies import AuthTokenDep, DatabaseDep, UserServiceDep
from core.logging import get_logger
from schemas.users import UserResponse
from schemas.common import ErrorResponse

logger = get_logger(__name__)
router = APIRouter(tags=["Users"])


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Retrieve the profile of the currently authenticated user",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Not authenticated or invalid token",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Internal server error",
        },
    },
)
async def get_current_user(
    token: AuthTokenDep, db: DatabaseDep, user_service: UserServiceDep
) -> UserResponse:
    """Get current authenticated user profile.

    Retrieves or creates the user profile based on the Clerk authentication token.
    On first access, automatically creates a user record in the database.

    Args:
        token: Authenticated user token from Clerk
        db: Database session
        user_service: User service for database operations

    Returns:
        UserResponse: Current user's profile information

    Raises:
        HTTPException: If authentication fails or user cannot be retrieved
    """
    try:
        # Accept all authentication types (clerk, testing, dev)
        clerk_user_id = token["user_id"]

        # Get or create user in database
        user = await user_service.create_or_get_user(clerk_user_id, db)

        return UserResponse.from_orm(user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user information",
        )
