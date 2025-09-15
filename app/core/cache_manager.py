"""
Caching utilities for the Social Flood application.

This module provides caching functionality to improve performance
by storing frequently accessed data in memory or Redis.
"""
from typing import Any, Dict, Optional, Union, Callable, TypeVar, Generic, List, Tuple
import time
import json
import asyncio
import logging
import functools
import hashlib
from datetime import datetime, timedelta

from app.core.config import get_settings, Settings

# Configure logger
logger = logging.getLogger(__name__)

# Type variable for generic cache
T = TypeVar('T')

# In-memory cache storage
# Format: {key: (value, expiry_timestamp)}
_cache_store: Dict[str, Tuple[Any, float]] = {}


class CacheManager:
    """
    Cache manager for storing and retrieving data.
    
    This class provides a simple interface for caching data in memory
    or Redis, with automatic expiration.
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize the cache manager.
        
        Args:
            settings: Optional settings instance
        """
        self.settings = settings or get_settings()
        self.enabled = self.settings.ENABLE_CACHE if hasattr(self.settings, "ENABLE_CACHE") else True
        self.ttl = self.settings.CACHE_TTL if hasattr(self.settings, "CACHE_TTL") else 3600  # seconds
        self.redis_url = self.settings.REDIS_URL if hasattr(self.settings, "REDIS_URL") else None
        self.redis_client = None
        
        # Initialize Redis client if URL is provided
        if self.redis_url and self.enabled:
            self._init_redis()
    
    def _init_redis(self):
        """Initialize the Redis client."""
        try:
            import redis
            self.redis_client = redis.from_url(str(self.redis_url))
            logger.info("Redis cache initialized")
        except ImportError:
            logger.warning("Redis package not installed. Falling back to in-memory cache.")
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {str(e)}")
    
    def _get_redis_client(self):
        """
        Get the Redis client, initializing it if necessary.
        
        Returns:
            Optional[redis.Redis]: Redis client or None
        """
        if not self.redis_client and self.redis_url and self.enabled:
            self._init_redis()
        return self.redis_client
    
    def _serialize(self, value: Any) -> str:
        """
        Serialize a value to a string.
        
        Args:
            value: The value to serialize
            
        Returns:
            str: Serialized value
        """
        try:
            return json.dumps(value)
        except (TypeError, ValueError):
            # If the value can't be JSON serialized, use string representation
            return str(value)
    
    def _deserialize(self, value: str) -> Any:
        """
        Deserialize a string to a value.
        
        Args:
            value: The string to deserialize
            
        Returns:
            Any: Deserialized value
        """
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            # If the value can't be JSON deserialized, return as is
            return value
    
    def _generate_key(self, key: str, namespace: Optional[str] = None) -> str:
        """
        Generate a cache key with optional namespace.
        
        Args:
            key: The base key
            namespace: Optional namespace
            
        Returns:
            str: The full cache key
        """
        if namespace:
            return f"cache:{namespace}:{key}"
        return f"cache:{key}"
    
    async def get(
        self,
        key: str,
        namespace: Optional[str] = None,
        default: Any = None
    ) -> Any:
        """
        Get a value from the cache.
        
        Args:
            key: The cache key
            namespace: Optional namespace
            default: Default value if key not found
            
        Returns:
            Any: The cached value or default
        """
        if not self.enabled:
            return default
        
        full_key = self._generate_key(key, namespace)
        
        # Try Redis first if available
        redis_client = self._get_redis_client()
        if redis_client:
            try:
                value = redis_client.get(full_key)
                if value is not None:
                    logger.debug(f"Cache hit (Redis): {full_key}")
                    return self._deserialize(value.decode('utf-8'))
            except Exception as e:
                logger.error(f"Redis error in get: {str(e)}")
        
        # Fall back to in-memory cache
        if full_key in _cache_store:
            value, expiry = _cache_store[full_key]
            
            # Check if expired
            if expiry > time.time():
                logger.debug(f"Cache hit (memory): {full_key}")
                return value
            
            # Remove expired entry
            del _cache_store[full_key]
        
        logger.debug(f"Cache miss: {full_key}")
        return default
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        namespace: Optional[str] = None
    ) -> bool:
        """
        Set a value in the cache.
        
        Args:
            key: The cache key
            value: The value to cache
            ttl: Time to live in seconds (None for default)
            namespace: Optional namespace
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        ttl = ttl if ttl is not None else self.ttl
        full_key = self._generate_key(key, namespace)
        
        # Try Redis first if available
        redis_client = self._get_redis_client()
        if redis_client:
            try:
                serialized = self._serialize(value)
                redis_client.setex(full_key, ttl, serialized)
                logger.debug(f"Cache set (Redis): {full_key}, TTL: {ttl}s")
                return True
            except Exception as e:
                logger.error(f"Redis error in set: {str(e)}")
        
        # Fall back to in-memory cache
        expiry = time.time() + ttl
        _cache_store[full_key] = (value, expiry)
        logger.debug(f"Cache set (memory): {full_key}, TTL: {ttl}s")
        return True
    
    async def delete(
        self,
        key: str,
        namespace: Optional[str] = None
    ) -> bool:
        """
        Delete a value from the cache.
        
        Args:
            key: The cache key
            namespace: Optional namespace
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        full_key = self._generate_key(key, namespace)
        
        # Try Redis first if available
        redis_client = self._get_redis_client()
        if redis_client:
            try:
                redis_client.delete(full_key)
                logger.debug(f"Cache delete (Redis): {full_key}")
            except Exception as e:
                logger.error(f"Redis error in delete: {str(e)}")
        
        # Also delete from in-memory cache
        if full_key in _cache_store:
            del _cache_store[full_key]
            logger.debug(f"Cache delete (memory): {full_key}")
            return True
        
        return False
    
    async def clear(self, namespace: Optional[str] = None) -> bool:
        """
        Clear all values from the cache or a specific namespace.
        
        Args:
            namespace: Optional namespace to clear
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        # Clear Redis cache if available
        redis_client = self._get_redis_client()
        if redis_client:
            try:
                if namespace:
                    pattern = f"cache:{namespace}:*"
                    keys = redis_client.keys(pattern)
                    if keys:
                        redis_client.delete(*keys)
                        logger.debug(f"Cache clear (Redis) for namespace: {namespace}, {len(keys)} keys")
                else:
                    pattern = "cache:*"
                    keys = redis_client.keys(pattern)
                    if keys:
                        redis_client.delete(*keys)
                        logger.debug(f"Cache clear (Redis): {len(keys)} keys")
            except Exception as e:
                logger.error(f"Redis error in clear: {str(e)}")
        
        # Clear in-memory cache
        if namespace:
            prefix = f"cache:{namespace}:"
            keys_to_delete = [k for k in _cache_store.keys() if k.startswith(prefix)]
            for k in keys_to_delete:
                del _cache_store[k]
            logger.debug(f"Cache clear (memory) for namespace: {namespace}, {len(keys_to_delete)} keys")
        else:
            count = len(_cache_store)
            _cache_store.clear()
            logger.debug(f"Cache clear (memory): {count} keys")
        
        return True
    
    def cached(
        self,
        ttl: Optional[int] = None,
        namespace: Optional[str] = None,
        key_builder: Optional[Callable[..., str]] = None
    ):
        """
        Decorator for caching function results.
        
        Args:
            ttl: Time to live in seconds (None for default)
            namespace: Optional namespace
            key_builder: Optional function to build the cache key
            
        Returns:
            Callable: Decorated function
        """
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                if not self.enabled:
                    return await func(*args, **kwargs)
                
                # Build cache key
                if key_builder:
                    key = key_builder(*args, **kwargs)
                else:
                    # Default key builder: function name + args + kwargs
                    key_parts = [func.__name__]
                    
                    # Add args to key
                    for arg in args:
                        key_parts.append(str(arg))
                    
                    # Add kwargs to key (sorted for consistency)
                    for k, v in sorted(kwargs.items()):
                        key_parts.append(f"{k}={v}")
                    
                    # Join and hash if too long
                    key_str = ":".join(key_parts)
                    if len(key_str) > 250:  # Redis keys are limited to 512 bytes
                        key = hashlib.md5(key_str.encode()).hexdigest()
                    else:
                        key = key_str
                
                # Try to get from cache
                cached_value = await self.get(key, namespace)
                if cached_value is not None:
                    return cached_value
                
                # Call the function
                result = await func(*args, **kwargs)
                
                # Cache the result
                await self.set(key, result, ttl, namespace)
                
                return result
            
            return wrapper
        
        return decorator


# Cleanup task for the in-memory cache
async def cleanup_cache_store():
    """
    Periodically clean up expired cache entries.
    
    This task runs in the background to remove expired entries from
    the in-memory cache store.
    """
    while True:
        try:
            now = time.time()
            
            # Find expired keys
            expired_keys = []
            for key, (_, expiry) in _cache_store.items():
                if expiry <= now:
                    expired_keys.append(key)
            
            # Remove expired keys
            for key in expired_keys:
                del _cache_store[key]
            
            # Log cleanup
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
        except Exception as e:
            logger.error(f"Error in cache store cleanup: {str(e)}")
        
        # Sleep for a while
        await asyncio.sleep(60)  # Clean up every minute


# Start the cleanup task
def start_cleanup_task():
    """Start the cache store cleanup task."""
    asyncio.create_task(cleanup_cache_store())


# Create a global cache manager instance
cache_manager = CacheManager()


# Convenience functions
async def get_from_cache(
    key: str,
    namespace: Optional[str] = None,
    default: Any = None
) -> Any:
    """
    Get a value from the cache.
    
    Args:
        key: The cache key
        namespace: Optional namespace
        default: Default value if key not found
        
    Returns:
        Any: The cached value or default
    """
    return await cache_manager.get(key, namespace, default)


async def set_in_cache(
    key: str,
    value: Any,
    ttl: Optional[int] = None,
    namespace: Optional[str] = None
) -> bool:
    """
    Set a value in the cache.
    
    Args:
        key: The cache key
        value: The value to cache
        ttl: Time to live in seconds (None for default)
        namespace: Optional namespace
        
    Returns:
        bool: True if successful, False otherwise
    """
    return await cache_manager.set(key, value, ttl, namespace)


async def delete_from_cache(
    key: str,
    namespace: Optional[str] = None
) -> bool:
    """
    Delete a value from the cache.
    
    Args:
        key: The cache key
        namespace: Optional namespace
        
    Returns:
        bool: True if successful, False otherwise
    """
    return await cache_manager.delete(key, namespace)


async def clear_cache(namespace: Optional[str] = None) -> bool:
    """
    Clear all values from the cache or a specific namespace.
    
    Args:
        namespace: Optional namespace to clear
        
    Returns:
        bool: True if successful, False otherwise
    """
    return await cache_manager.clear(namespace)


def cached(
    ttl: Optional[int] = None,
    namespace: Optional[str] = None,
    key_builder: Optional[Callable[..., str]] = None
):
    """
    Decorator for caching function results.
    
    Args:
        ttl: Time to live in seconds (None for default)
        namespace: Optional namespace
        key_builder: Optional function to build the cache key
        
    Returns:
        Callable: Decorated function
    """
    return cache_manager.cached(ttl, namespace, key_builder)


def generate_cache_key(base_key: str, **kwargs) -> str:
    """
    Generate a consistent cache key from a base key and parameters.
    
    Args:
        base_key: The base cache key (e.g., "trends_interest_over_time")
        **kwargs: Additional parameters to include in the key
        
    Returns:
        str: A consistent cache key
    """
    # Sort kwargs for consistent key generation
    sorted_kwargs = sorted(kwargs.items())
    
    # Build key components
    key_parts = [base_key]
    
    for key, value in sorted_kwargs:
        if value is not None:
            # Convert value to string and handle special cases
            if isinstance(value, list):
                value_str = ",".join(str(v) for v in value)
            else:
                value_str = str(value)
            key_parts.append(f"{key}={value_str}")
    
    # Join parts with colons
    full_key = ":".join(key_parts)
    
    # If key is too long, hash it
    if len(full_key) > 250:  # Redis key limit is 512 bytes, be conservative
        full_key = hashlib.md5(full_key.encode()).hexdigest()
    
    return full_key


async def get_cached_or_fetch(cache_key: str, fetch_func: Callable[[], Any], ttl: Optional[int] = None) -> Any:
    """
    Get data from cache or fetch and cache it if not found.
    
    Args:
        cache_key: The cache key to use
        fetch_func: Async function to call if data not in cache
        ttl: Optional TTL override
        
    Returns:
        Any: The cached or freshly fetched data
    """
    # Try to get from cache first
    cached_data = await cache_manager.get(cache_key)
    if cached_data is not None:
        logger.debug(f"Cache hit for key: {cache_key}")
        return cached_data
    
    # Cache miss - fetch the data
    logger.debug(f"Cache miss for key: {cache_key}, fetching data")
    try:
        data = await fetch_func()
        
        # Cache the result
        await cache_manager.set(cache_key, data, ttl)
        logger.debug(f"Cached data for key: {cache_key}")
        
        return data
    except Exception as e:
        logger.error(f"Error fetching data for cache key {cache_key}: {e}")
        raise
