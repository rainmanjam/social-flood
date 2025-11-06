"""
Request ID Middleware for tracking requests across the system.

This middleware adds a unique request ID to each request, which can be used
for logging, tracing, and debugging purposes.
"""
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, Response
from typing import Callable


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds a unique request ID to each request.

    The request ID can be provided by the client via the X-Request-ID header,
    or will be automatically generated if not provided.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request and add a unique request ID.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler

        Returns:
            Response: The HTTP response with X-Request-ID header
        """
        # Get existing request ID from header or generate a new one
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Store request ID in request state for access in route handlers
        request.state.request_id = request_id

        # Process the request
        response = await call_next(request)

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response
