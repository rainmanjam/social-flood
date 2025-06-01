"""
Minimal test script for the BaseRouter class.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Any, Callable, Dict, List, Optional, Type, Union
import re

class BaseRouter:
    """
    Base router class that provides common functionality for all API routers.
    
    Features:
    - Auto-derives service_name from prefix if not provided
    - Supports OpenAPI responses documentation
    - Provides RFC7807 compliant error responses
    """
    
    def __init__(
        self,
        prefix: str,
        service_name: Optional[str] = None,
        responses: Optional[Dict[int, dict]] = None,
        **kwargs
    ):
        """
        Initialize a new BaseRouter.
        
        Args:
            prefix: URL prefix for all routes (e.g., "/google-ads")
            service_name: Optional name for the service. If not provided, derived from prefix.
            responses: Optional dict of status codes to response models for OpenAPI docs.
            **kwargs: Additional arguments to pass to the underlying APIRouter.
        """
        # Validate and normalize prefix
        if not prefix.startswith("/"):
            prefix = f"/{prefix}"
            
        # Extract service name from prefix
        extracted_service_name = self._extract_service_name(prefix)
        
        # Use provided service_name or extracted one
        self.service_name = service_name or extracted_service_name
        
        # Validate consistency between extracted and provided service_name
        if service_name and service_name != extracted_service_name:
            print(
                f"WARNING: Provided service_name '{service_name}' differs from extracted "
                f"service_name '{extracted_service_name}' from prefix '{prefix}'"
            )
        
        # Create the underlying FastAPI router
        self.router = APIRouter(
            prefix=prefix,
            tags=[self.service_name],
            responses=responses or self._default_responses(),
            **kwargs
        )
    
    def _extract_service_name(self, prefix: str) -> str:
        """
        Extract service name from the URL prefix.
        
        Example:
            "/google-ads" -> "google-ads"
            "/youtube-transcripts" -> "youtube-transcripts"
            "/api/v1/google-ads" -> "google-ads"
        
        Args:
            prefix: URL prefix string
            
        Returns:
            Extracted service name
        """
        # Remove leading slash if present
        if prefix.startswith("/"):
            prefix = prefix[1:]
            
        # Split on slashes
        parts = prefix.split("/")
        if not parts:
            raise ValueError(f"Cannot extract service name from prefix: {prefix}")
        
        # If the prefix is like "/api/v1/google-ads", take the last segment
        if len(parts) > 1 and parts[0] == "api" and parts[1].startswith("v"):
            return parts[2] if len(parts) > 2 else parts[0]
        
        # Otherwise take the first segment
        if not parts[0]:
            raise ValueError(f"Cannot extract service name from prefix: {prefix}")
            
        return parts[0]
    
    def _default_responses(self) -> Dict[int, dict]:
        """
        Provide default response schemas for common HTTP status codes.
        
        Returns:
            Dictionary of status codes to response schemas
        """
        return {
            400: {"description": "Bad Request"},
            401: {"description": "Unauthorized"},
            403: {"description": "Forbidden"},
            404: {"description": "Not Found"},
            500: {"description": "Internal Server Error"}
        }
    
    def __call__(self):
        """Return the underlying router instance."""
        return self.router


# Create a FastAPI app
from fastapi import FastAPI
app = FastAPI()

print("Starting test...")

# Test 1: Create a router with auto-derived service_name
print("\nTest 1: Create a router with auto-derived service_name")
router1 = BaseRouter(prefix="/google-ads")
print(f"Router 1 service_name: {router1.service_name}")
assert router1.service_name == "google-ads", f"Expected 'google-ads', got '{router1.service_name}'"
print("Test 1 passed!")

# Test 2: Create a router with explicit service_name
print("\nTest 2: Create a router with explicit service_name")
router2 = BaseRouter(prefix="/google-ads", service_name="google-ads-service")
print(f"Router 2 service_name: {router2.service_name}")
assert router2.service_name == "google-ads-service", f"Expected 'google-ads-service', got '{router2.service_name}'"
print("Test 2 passed!")

# Test 3: Create a router with API versioned prefix
print("\nTest 3: Create a router with API versioned prefix")
router3 = BaseRouter(prefix="/api/v1/google-ads")
print(f"Router 3 service_name: {router3.service_name}")
assert router3.service_name == "google-ads", f"Expected 'google-ads', got '{router3.service_name}'"
print("Test 3 passed!")

# Test 4: Create a router with custom responses
print("\nTest 4: Create a router with custom responses")
custom_responses = {
    200: {"description": "Success"},
    400: {"description": "Bad Request"}
}
router4 = BaseRouter(prefix="/google-ads", responses=custom_responses)
print(f"Router 4 responses keys: {router4.router.responses.keys()}")
assert 200 in router4.router.responses, "Expected 200 in responses"
assert 400 in router4.router.responses, "Expected 400 in responses"
assert router4.router.responses[200] == {"description": "Success"}, f"Expected {{'description': 'Success'}}, got {router4.router.responses[200]}"
print("Test 4 passed!")

# Test 5: Include the routers in the app
print("\nTest 5: Include the routers in the app")
app.include_router(router1())
app.include_router(router2())
app.include_router(router3())
app.include_router(router4())
print("All routers included successfully!")
print("Test 5 passed!")

print("\nAll tests passed!")
