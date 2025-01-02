# app/core/auth.py
from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
import os

# Create API Key header schema
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

# Get API key from environment variable
API_KEY = os.getenv("API_KEY")

async def get_api_key(api_key_header: str = Security(api_key_header)):
    """
    Validate API key from request header
    """
    if not API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key not configured. Please set the API_KEY environment variable."
        )
    
    if api_key_header != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key provided."
        )
    
    return api_key_header