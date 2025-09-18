"""
Centralized dependency injection functions.

This module provides reusable dependencies that can be used across
the application for common functionality like authentication,
database access, and more.
"""

from typing import Any, Dict, List, Optional

from fastapi import Depends, Header, Request

from app.core.auth import authenticate_api_key, get_current_api_key
from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError, PermissionDeniedError


# Settings dependency
def get_app_settings() -> Settings:
    """
    Get application settings.

    Returns:
        Settings: Application settings
    """
    return get_settings()


# Authentication dependencies
async def get_api_key_dependency(api_key: str = Depends(authenticate_api_key)) -> str:
    """
    Get the current API key.

    This is an alias for authenticate_api_key for backward compatibility.

    Args:
        api_key: The API key from authenticate_api_key

    Returns:
        str: The current API key
    """
    return api_key


async def get_optional_api_key(
    request: Request, x_api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> Optional[str]:
    """
    Get the API key if provided, but don't require it.

    Args:
        request: The request object
        x_api_key: The API key from the header

    Returns:
        Optional[str]: The API key if provided and valid, None otherwise
    """
    if not x_api_key:
        return None

    try:
        return await authenticate_api_key(x_api_key, request)
    except:
        return None


async def get_current_user(request: Request, authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """
    Get the current user from the Authorization header.

    This is a placeholder for future user authentication.
    Currently, it just returns a dummy user.

    Args:
        request: The request object
        authorization: The Authorization header

    Returns:
        Dict[str, Any]: The current user

    Raises:
        AuthenticationError: If authentication fails
    """
    settings = get_settings()

    # This is a placeholder for future user authentication
    # In a real application, you would validate the token and get the user
    if not authorization:
        raise AuthenticationError("Authorization header is required")

    if not authorization.startswith("Bearer "):
        raise AuthenticationError("Invalid authorization scheme")

    token = authorization.replace("Bearer ", "")

    # Placeholder: validate token and get user
    # For now, just check if it matches the configured bearer token
    if settings.X_BEARER_TOKEN and token == settings.X_BEARER_TOKEN:
        return {"id": "user-1", "username": "admin", "roles": ["admin"]}

    raise AuthenticationError("Invalid token")


async def get_optional_user(request: Request, authorization: Optional[str] = Header(None)) -> Optional[Dict[str, Any]]:
    """
    Get the current user if authenticated, but don't require it.

    Args:
        request: The request object
        authorization: The Authorization header

    Returns:
        Optional[Dict[str, Any]]: The current user if authenticated, None otherwise
    """
    if not authorization:
        return None

    try:
        return await get_current_user(request, authorization)
    except:
        return None


# Role-based access control
async def require_role(role: str, user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Require that the current user has a specific role.

    Args:
        role: The required role
        user: The current user

    Returns:
        Dict[str, Any]: The current user

    Raises:
        PermissionDeniedError: If the user doesn't have the required role
    """
    if "roles" not in user or role not in user["roles"]:
        raise PermissionDeniedError(f"Role '{role}' is required")

    return user


async def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Require that the current user has the admin role.

    Args:
        user: The current user

    Returns:
        Dict[str, Any]: The current user

    Raises:
        PermissionDeniedError: If the user doesn't have the admin role
    """
    return await require_role("admin", user)


# Request context
async def get_request_id(request: Request, x_request_id: Optional[str] = Header(None, alias="X-Request-ID")) -> str:
    """
    Get the request ID from the X-Request-ID header or generate a new one.

    Args:
        request: The request object
        x_request_id: The X-Request-ID header

    Returns:
        str: The request ID
    """
    if x_request_id:
        return x_request_id

    # If no request ID is provided, use the one from the request state
    # or generate a new one
    if not hasattr(request.state, "request_id"):
        import uuid

        request.state.request_id = str(uuid.uuid4())

    return request.state.request_id


# Feature flags
async def feature_enabled(feature_name: str, settings: Settings = Depends(get_app_settings)) -> bool:
    """
    Check if a feature is enabled.

    Args:
        feature_name: The name of the feature
        settings: Application settings

    Returns:
        bool: True if the feature is enabled, False otherwise
    """
    # This is a simple implementation that checks environment variables
    # In a real application, you might use a feature flag service

    # Convert feature_name to uppercase and check if it exists in settings
    feature_flag = f"ENABLE_{feature_name.upper()}"
    return getattr(settings, feature_flag, False)


async def require_feature(feature_name: str, enabled: bool = Depends(feature_enabled)) -> None:
    """
    Require that a feature is enabled.

    Args:
        feature_name: The name of the feature
        enabled: Whether the feature is enabled

    Raises:
        PermissionDeniedError: If the feature is not enabled
    """
    if not enabled:
        raise PermissionDeniedError(f"Feature '{feature_name}' is not enabled")
