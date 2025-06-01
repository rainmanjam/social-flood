"""
Authentication utilities for API key validation.

This module provides functions and dependencies for validating API keys
in incoming requests.
"""
from fastapi import Security, HTTPException, status, Depends, Request
from fastapi.security.api_key import APIKeyHeader
from typing import List, Optional, Dict, Set
import os
from pydantic_settings import BaseSettings

# Create API Key header schema
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

class AuthSettings(BaseSettings):
    """Settings for authentication."""
    API_KEYS: List[str] = []
    ENABLE_API_KEY_AUTH: bool = True
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": False
    }

# Global settings instance
auth_settings = AuthSettings()

# Convert API_KEYS list to a set for faster lookups
_api_keys_set: Set[str] = set()

# API key to metadata mapping (for future use)
_api_key_metadata: Dict[str, Dict] = {}

def initialize_api_keys():
    """
    Initialize the API keys from environment variables.
    
    This function reads API keys from:
    1. The API_KEYS environment variable (comma-separated list)
    2. The API_KEY environment variable (single key, for backward compatibility)
    
    It populates the _api_keys_set for fast validation.
    """
    global _api_keys_set, _api_key_metadata
    
    # Clear existing keys
    _api_keys_set = set()
    _api_key_metadata = {}
    
    # Get API keys from environment
    api_keys = auth_settings.API_KEYS
    
    # For backward compatibility, also check for API_KEY
    single_api_key = os.getenv("API_KEY")
    if single_api_key and single_api_key not in api_keys:
        api_keys.append(single_api_key)
    
    # Add keys to the set
    for key in api_keys:
        if key and key.strip():
            _api_keys_set.add(key.strip())
            _api_key_metadata[key.strip()] = {"source": "environment"}
    
    # If no keys are configured, add a warning
    if not _api_keys_set and auth_settings.ENABLE_API_KEY_AUTH:
        print("WARNING: No API keys configured. API key authentication is enabled but will reject all requests.")

# Initialize API keys on module import
initialize_api_keys()

def validate_api_key(api_key: str) -> bool:
    """
    Validate if the provided API key is valid.
    
    Args:
        api_key: The API key to validate
        
    Returns:
        bool: True if the API key is valid, False otherwise
    """
    return api_key in _api_keys_set

def get_api_key_metadata(api_key: str) -> Optional[Dict]:
    """
    Get metadata for an API key.
    
    Args:
        api_key: The API key to get metadata for
        
    Returns:
        Optional[Dict]: Metadata for the API key, or None if the key is invalid
    """
    return _api_key_metadata.get(api_key)

async def get_api_key(api_key_header: str = Security(api_key_header)) -> str:
    """
    Validate API key from request header.
    
    This function is kept for backward compatibility.
    
    Args:
        api_key_header: The API key from the request header
        
    Returns:
        str: The validated API key
        
    Raises:
        HTTPException: If the API key is invalid or authentication is not configured
    """
    return await authenticate_api_key(api_key_header)

async def authenticate_api_key(
    api_key_header: str = Security(api_key_header),
    request: Optional[Request] = None
) -> str:
    """
    Validate API key from request header.
    
    This function can be used as a dependency in FastAPI routes.
    
    Args:
        api_key_header: The API key from the request header
        request: Optional request object for future use (e.g., rate limiting)
        
    Returns:
        str: The validated API key
        
    Raises:
        HTTPException: If the API key is invalid or authentication is not configured
    """
    # Skip validation if API key authentication is disabled
    if not auth_settings.ENABLE_API_KEY_AUTH:
        return "authentication-disabled"
    
    # Check if any API keys are configured
    if not _api_keys_set:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key authentication is enabled but no API keys are configured."
        )
    
    # Validate the API key
    if not validate_api_key(api_key_header):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key provided.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    return api_key_header

def get_current_api_key(
    api_key: str = Depends(authenticate_api_key)
) -> str:
    """
    Get the current API key.
    
    This is a convenience dependency that can be used in routes
    that need access to the current API key.
    
    Args:
        api_key: The API key from authenticate_api_key
        
    Returns:
        str: The current API key
    """
    return api_key
