"""
Rate limiting implementation for the Social Flood application.

This module provides rate limiting functionality to protect the API
from abuse and ensure fair usage.

Storage Backends:
-----------------
1. Redis (Recommended for production): When REDIS_URL is configured, rate limits
   are stored in Redis, enabling accurate rate limiting across multiple instances.

2. In-Memory (Fallback): When Redis is unavailable, falls back to thread-safe
   in-memory storage. Note: In-memory storage is NOT shared across instances.

For production multi-instance deployments:
- Set REDIS_URL environment variable (e.g., redis://localhost:6379/0)
- Rate limits will automatically use Redis for shared state

See also: app/core/cache_manager.py for Redis configuration details.
"""
from fastapi import Request, Response, Depends
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import time
import asyncio
from typing import Dict, Tuple, Optional, Callable, Any, Union
import logging
from datetime import datetime

from app.core.config import get_settings, Settings
from app.core.exceptions import RateLimitExceededError
from app.core.auth import get_current_api_key

# Configure logger
logger = logging.getLogger(__name__)

# Thread-safe in-memory storage for rate limiting (fallback when Redis unavailable)
# Format: {key: (requests_count, window_start_timestamp)}
_rate_limit_store: Dict[str, Tuple[int, float]] = {}

# Lock for thread-safe access to in-memory store
_rate_limit_lock: asyncio.Lock = asyncio.Lock()

# Global cleanup task reference to prevent garbage collection
_cleanup_task: Optional[asyncio.Task] = None

# Redis client instance (initialized lazily)
_redis_client: Optional[Any] = None
_redis_initialized: bool = False


def _get_redis_client():
    """
    Get or initialize the Redis client for rate limiting.

    Returns:
        Optional[redis.Redis]: Redis client or None if unavailable
    """
    global _redis_client, _redis_initialized

    if _redis_initialized:
        return _redis_client

    _redis_initialized = True
    settings = get_settings()
    redis_url = getattr(settings, 'REDIS_URL', None)

    if not redis_url:
        logger.debug("Redis URL not configured, using in-memory rate limiting")
        return None

    try:
        import redis
        _redis_client = redis.from_url(str(redis_url))
        # Test connection
        _redis_client.ping()
        logger.info("Redis rate limiter initialized successfully")
        return _redis_client
    except ImportError:
        logger.warning("Redis package not installed. Using in-memory rate limiting.")
        return None
    except Exception as e:
        logger.warning(f"Failed to connect to Redis for rate limiting: {e}. Using in-memory fallback.")
        return None


class RateLimiter:
    """
    Rate limiter for API requests.

    This class provides rate limiting functionality based on API keys
    or IP addresses. Uses Redis when available for multi-instance support,
    falls back to thread-safe in-memory storage.
    """

    def __init__(
        self,
        requests: int = 100,
        timeframe: int = 3600,  # seconds
        settings: Optional[Settings] = None
    ):
        """
        Initialize the rate limiter.

        Args:
            requests: Maximum number of requests allowed in the timeframe
            timeframe: Timeframe in seconds
            settings: Optional settings instance
        """
        self.settings = settings or get_settings()

        # Use provided values, or fall back to settings, or use defaults
        if requests != 100:
            self.requests = requests
        elif hasattr(self.settings, "RATE_LIMIT_REQUESTS"):
            self.requests = self.settings.RATE_LIMIT_REQUESTS
        else:
            self.requests = 100

        if timeframe != 3600:
            self.timeframe = timeframe
        elif hasattr(self.settings, "RATE_LIMIT_TIMEFRAME"):
            self.timeframe = self.settings.RATE_LIMIT_TIMEFRAME
        else:
            self.timeframe = 3600
        self.enabled = (
            self.settings.RATE_LIMIT_ENABLED
            if hasattr(self.settings, "RATE_LIMIT_ENABLED")
            else True
        )
    
    async def _get_rate_limit_key(self, request: Request) -> str:
        """
        Get the key to use for rate limiting.
        
        This method tries to use the API key if available, otherwise
        falls back to the client IP address.
        
        Args:
            request: The request object
            
        Returns:
            str: The rate limit key
        """
        # Try to get the API key from the request
        try:
            api_key = await get_current_api_key(request)
            return f"rate_limit:api_key:{api_key}"
        except Exception:
            # Fall back to IP address
            client_host = request.client.host if request.client else "unknown"
            return f"rate_limit:ip:{client_host}"
    
    async def is_rate_limited(self, request: Request) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if a request is rate limited.

        Args:
            request: The request object

        Returns:
            Tuple[bool, Dict[str, Any]]: (is_limited, rate_limit_info)
        """
        if not self.enabled:
            return False, {}

        # Get the rate limit key
        key = await self._get_rate_limit_key(request)

        # Try Redis first if available
        redis_client = _get_redis_client()
        if redis_client:
            return await self._check_rate_limit_redis(key, redis_client)

        # Fall back to thread-safe in-memory storage
        return await self._check_rate_limit_memory(key)

    async def _check_rate_limit_redis(
        self,
        key: str,
        redis_client: Any
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check rate limit using Redis storage.

        Uses Redis INCR with EXPIRE for atomic rate limiting.

        Args:
            key: The rate limit key
            redis_client: Redis client instance

        Returns:
            Tuple[bool, Dict[str, Any]]: (is_limited, rate_limit_info)
        """
        try:
            # Use Redis pipeline for atomic operations
            pipe = redis_client.pipeline()

            # Get current count and TTL
            pipe.incr(key)
            pipe.ttl(key)
            results = pipe.execute()

            current_count = results[0]
            ttl = results[1]

            # If this is the first request (TTL is -1), set expiration
            if ttl == -1:
                redis_client.expire(key, self.timeframe)
                ttl = self.timeframe

            # Calculate reset time
            reset = max(0, ttl)

            # Check if rate limited
            is_limited = current_count > self.requests

            return is_limited, self._get_rate_limit_headers(
                current_count, self.requests, self.timeframe, time.time() - (self.timeframe - reset)
            )
        except Exception as e:
            logger.error(f"Redis rate limit error: {e}. Falling back to in-memory.")
            # Fall back to in-memory on Redis error
            return await self._check_rate_limit_memory(key)

    async def _check_rate_limit_memory(self, key: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Check rate limit using thread-safe in-memory storage.

        Args:
            key: The rate limit key

        Returns:
            Tuple[bool, Dict[str, Any]]: (is_limited, rate_limit_info)
        """
        now = time.time()

        async with _rate_limit_lock:
            # Check if the key exists in the store
            if key in _rate_limit_store:
                requests_count, window_start = _rate_limit_store[key]

                # Check if the window has expired
                if now - window_start > self.timeframe:
                    # Reset the window
                    _rate_limit_store[key] = (1, now)
                    return False, self._get_rate_limit_headers(1, self.requests, self.timeframe)

                # Increment the request count
                new_count = requests_count + 1
                _rate_limit_store[key] = (new_count, window_start)

                # Check if the request count exceeds the limit
                if new_count > self.requests:
                    # Rate limited
                    return True, self._get_rate_limit_headers(
                        new_count, self.requests, self.timeframe, window_start
                    )

                return False, self._get_rate_limit_headers(
                    new_count, self.requests, self.timeframe, window_start
                )

            # First request for this key
            _rate_limit_store[key] = (1, now)
            return False, self._get_rate_limit_headers(1, self.requests, self.timeframe)
    
    def _get_rate_limit_headers(
        self,
        current: int,
        limit: int,
        timeframe: int,
        window_start: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Get rate limit headers for the response.
        
        Args:
            current: Current request count
            limit: Maximum request count
            timeframe: Timeframe in seconds
            window_start: Window start timestamp
            
        Returns:
            Dict[str, Any]: Rate limit headers and info
        """
        now = time.time()
        window_start = window_start or now
        reset = int(window_start + timeframe - now)
        
        return {
            "headers": {
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": str(max(0, limit - current)),
                "X-RateLimit-Reset": str(reset)
            },
            "current": current,
            "limit": limit,
            "reset": reset
        }
    
    async def limit(
        self,
        request: Request,
        call_next: Optional[Callable] = None
    ) -> Union[Response, Any]:
        """
        Apply rate limiting to a request.
        
        This method can be used as a middleware or a dependency.
        
        Args:
            request: The request object
            call_next: Optional next middleware or route handler
            
        Returns:
            Union[Response, Any]: Response or next middleware result
            
        Raises:
            RateLimitExceededError: If the request is rate limited
        """
        # Check if rate limiting is enabled
        if not self.enabled:
            if call_next:
                return await call_next(request)
            return None
        
        # Check if the request is rate limited
        is_limited, rate_limit_info = await self.is_rate_limited(request)
        
        if is_limited:
            # Log the rate limit
            logger.warning(
                "Rate limit exceeded",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "client_host": request.client.host if request.client else "unknown",
                    "rate_limit_info": rate_limit_info
                }
            )
            
            # If used as a middleware, return a response
            if call_next:
                return JSONResponse(
                    status_code=429,
                    content={
                        "type": "https://socialflood.com/problems/rate_limit_exceeded",
                        "title": "Too Many Requests",
                        "status": 429,
                        "detail": f"Rate limit exceeded. Try again in {rate_limit_info['reset']} seconds.",
                        "limit": rate_limit_info["limit"],
                        "reset": rate_limit_info["reset"]
                    },
                    headers=rate_limit_info["headers"]
                )
            
            # If used as a dependency, raise an exception
            raise RateLimitExceededError(
                detail=f"Rate limit exceeded. Try again in {rate_limit_info['reset']} seconds.",
                reset=rate_limit_info["reset"],
                limit=rate_limit_info["limit"]
            )
        
        # Add rate limit headers to the response
        if call_next:
            response = await call_next(request)
            
            # Add rate limit headers
            for header, value in rate_limit_info["headers"].items():
                response.headers[header] = value
            
            return response
        
        # If used as a dependency, return None
        return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware for rate limiting requests.
    
    This middleware applies rate limiting to all requests based on
    API key or IP address.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        requests: int = 100,
        timeframe: int = 3600,  # seconds
        settings: Optional[Settings] = None
    ):
        """
        Initialize the middleware.
        
        Args:
            app: The ASGI application
            requests: Maximum number of requests allowed in the timeframe
            timeframe: Timeframe in seconds
            settings: Optional settings instance
        """
        super().__init__(app)
        self.limiter = RateLimiter(requests, timeframe, settings)
    
    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """
        Apply rate limiting to the request.
        
        Args:
            request: The request object
            call_next: The next middleware or route handler
            
        Returns:
            Response: The response
        """
        return await self.limiter.limit(request, call_next)


# Create a global rate limiter instance
limiter = RateLimiter()


# Dependency for rate limiting
async def rate_limit(request: Request):
    """
    Dependency for rate limiting.
    
    This dependency can be used in FastAPI routes to apply rate limiting.
    
    Args:
        request: The request object
        
    Raises:
        RateLimitExceededError: If the request is rate limited
    """
    await limiter.limit(request)


# Cleanup task for the in-memory store
async def cleanup_rate_limit_store():
    """
    Periodically clean up expired rate limit entries.

    This task runs in the background to remove expired entries from
    the in-memory rate limit store using thread-safe access.
    """
    while True:
        try:
            now = time.time()
            settings = get_settings()
            timeframe = settings.RATE_LIMIT_TIMEFRAME if hasattr(settings, "RATE_LIMIT_TIMEFRAME") else 3600

            # Thread-safe cleanup
            async with _rate_limit_lock:
                # Find expired keys
                expired_keys = [
                    key for key, (_, window_start) in _rate_limit_store.items()
                    if now - window_start > timeframe
                ]

                # Remove expired keys
                for key in expired_keys:
                    del _rate_limit_store[key]

            # Log cleanup (outside lock)
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired rate limit entries")
        except Exception as e:
            logger.error(f"Error in rate limit store cleanup: {str(e)}")

        # Sleep for a while
        await asyncio.sleep(60)  # Clean up every minute


def start_cleanup_task():
    """
    Start the rate limit store cleanup task.

    The task reference is stored globally to prevent garbage collection.
    """
    global _cleanup_task
    if _cleanup_task is None or _cleanup_task.done():
        _cleanup_task = asyncio.create_task(cleanup_rate_limit_store())
        logger.debug("Rate limit cleanup task started")


def stop_cleanup_task():
    """Stop the rate limit store cleanup task."""
    global _cleanup_task
    if _cleanup_task and not _cleanup_task.done():
        _cleanup_task.cancel()
        logger.debug("Rate limit cleanup task stopped")
