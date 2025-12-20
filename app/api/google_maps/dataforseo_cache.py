"""
Redis-based caching layer for DataForSEO API.

Provides:
- Response caching with configurable TTL
- Cache key generation
- Cache statistics
- Automatic cache invalidation
"""

import json
import hashlib
import logging
from typing import Optional, Dict, Any, Callable, TypeVar
from functools import wraps

from app.core.cache_manager import cache_manager, generate_cache_key

logger = logging.getLogger("uvicorn")

# Cache TTL constants (in seconds)
CACHE_TTL_SEARCH = 3600        # 1 hour for search results
CACHE_TTL_DETAILS = 3600       # 1 hour for business details
CACHE_TTL_REVIEWS = 3600       # 1 hour for reviews
CACHE_TTL_REVIEWS_TASK = 86400 # 24 hours for completed review tasks

# Cache namespace
CACHE_NAMESPACE = "dataforseo"

T = TypeVar('T')


def _generate_cache_key(prefix: str, **kwargs) -> str:
    """
    Generate a consistent cache key for DataForSEO requests.

    Args:
        prefix: Key prefix (e.g., "search", "details", "reviews")
        **kwargs: Request parameters

    Returns:
        Cache key string
    """
    # Filter out None values and sort for consistency
    filtered = {k: v for k, v in sorted(kwargs.items()) if v is not None}

    # Create a deterministic string representation
    key_parts = [prefix]
    for k, v in filtered.items():
        if isinstance(v, (list, dict)):
            v = json.dumps(v, sort_keys=True)
        key_parts.append(f"{k}={v}")

    key_str = ":".join(key_parts)

    # Hash if too long
    if len(key_str) > 200:
        key_hash = hashlib.md5(key_str.encode()).hexdigest()
        return f"{prefix}:{key_hash}"

    return key_str


class DataForSEOCache:
    """
    Caching wrapper for DataForSEO API responses.

    Uses Redis (via cache_manager) for distributed caching with
    automatic fallback to in-memory cache.
    """

    def __init__(self):
        """Initialize the cache."""
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "errors": 0
        }

    async def get_cached_search(
        self,
        query: str,
        location: Optional[str] = None,
        location_code: Optional[int] = None,
        language_code: str = "en",
        depth: int = 20
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached search results.

        Args:
            query: Search query
            location: Location name
            location_code: Location code
            language_code: Language code
            depth: Result depth

        Returns:
            Cached result or None if not found
        """
        key = _generate_cache_key(
            "search",
            query=query.lower().strip(),
            location=location,
            location_code=location_code,
            language_code=language_code,
            depth=depth
        )
        return await self._get(key)

    async def set_cached_search(
        self,
        result: Dict[str, Any],
        query: str,
        location: Optional[str] = None,
        location_code: Optional[int] = None,
        language_code: str = "en",
        depth: int = 20
    ) -> bool:
        """Cache search results."""
        key = _generate_cache_key(
            "search",
            query=query.lower().strip(),
            location=location,
            location_code=location_code,
            language_code=language_code,
            depth=depth
        )
        return await self._set(key, result, CACHE_TTL_SEARCH)

    async def get_cached_details(
        self,
        keyword: Optional[str] = None,
        place_id: Optional[str] = None,
        cid: Optional[str] = None,
        location_code: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Get cached business details."""
        key = _generate_cache_key(
            "details",
            keyword=keyword.lower().strip() if keyword else None,
            place_id=place_id,
            cid=cid,
            location_code=location_code
        )
        return await self._get(key)

    async def set_cached_details(
        self,
        result: Dict[str, Any],
        keyword: Optional[str] = None,
        place_id: Optional[str] = None,
        cid: Optional[str] = None,
        location_code: Optional[int] = None
    ) -> bool:
        """Cache business details."""
        key = _generate_cache_key(
            "details",
            keyword=keyword.lower().strip() if keyword else None,
            place_id=place_id,
            cid=cid,
            location_code=location_code
        )
        return await self._set(key, result, CACHE_TTL_DETAILS)

    async def get_cached_reviews(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get cached reviews by task ID."""
        key = f"reviews:task:{task_id}"
        return await self._get(key)

    async def set_cached_reviews(
        self,
        task_id: str,
        result: Dict[str, Any]
    ) -> bool:
        """Cache completed reviews task results."""
        key = f"reviews:task:{task_id}"
        return await self._set(key, result, CACHE_TTL_REVIEWS_TASK)

    async def get_cached_reviews_by_place(
        self,
        place_id: Optional[str] = None,
        cid: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get cached reviews by place ID or CID."""
        if place_id:
            key = f"reviews:place:{place_id}"
        elif cid:
            key = f"reviews:cid:{cid}"
        else:
            return None
        return await self._get(key)

    async def set_cached_reviews_by_place(
        self,
        result: Dict[str, Any],
        place_id: Optional[str] = None,
        cid: Optional[str] = None
    ) -> bool:
        """Cache reviews by place ID or CID."""
        if place_id:
            key = f"reviews:place:{place_id}"
        elif cid:
            key = f"reviews:cid:{cid}"
        else:
            return False
        return await self._set(key, result, CACHE_TTL_REVIEWS)

    async def _get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get value from cache."""
        try:
            result = await cache_manager.get(key, namespace=CACHE_NAMESPACE)
            if result is not None:
                self._stats["hits"] += 1
                logger.debug(f"Cache hit: {key}")
                return result
            self._stats["misses"] += 1
            logger.debug(f"Cache miss: {key}")
            return None
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Cache get error: {e}")
            return None

    async def _set(self, key: str, value: Dict[str, Any], ttl: int) -> bool:
        """Set value in cache."""
        try:
            # Only cache successful responses
            if value.get("success", True):
                await cache_manager.set(key, value, ttl=ttl, namespace=CACHE_NAMESPACE)
                self._stats["sets"] += 1
                logger.debug(f"Cache set: {key}, TTL: {ttl}s")
                return True
            return False
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Cache set error: {e}")
            return False

    async def invalidate_place(self, place_id: str) -> bool:
        """Invalidate all cached data for a specific place."""
        try:
            await cache_manager.clear(namespace=f"{CACHE_NAMESPACE}:*{place_id}*")
            logger.info(f"Invalidated cache for place: {place_id}")
            return True
        except Exception as e:
            logger.error(f"Cache invalidation error: {e}")
            return False

    async def clear_all(self) -> bool:
        """Clear all DataForSEO cache entries."""
        try:
            await cache_manager.clear(namespace=CACHE_NAMESPACE)
            logger.info("Cleared all DataForSEO cache")
            return True
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0.0

        # Calculate estimated savings
        # Assuming ~$0.01 per API call
        estimated_savings = self._stats["hits"] * 0.01

        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "sets": self._stats["sets"],
            "errors": self._stats["errors"],
            "hit_rate": f"{hit_rate:.2f}%",
            "estimated_savings_usd": f"${estimated_savings:.2f}",
            "ttl_search_seconds": CACHE_TTL_SEARCH,
            "ttl_details_seconds": CACHE_TTL_DETAILS,
            "ttl_reviews_seconds": CACHE_TTL_REVIEWS
        }


# Global cache instance
dataforseo_cache = DataForSEOCache()


def cached_search(func: Callable) -> Callable:
    """Decorator to cache search results."""
    @wraps(func)
    async def wrapper(self, query: str, location: Optional[str] = None,
                     location_code: Optional[int] = None, language_code: str = "en",
                     depth: int = 20, skip_cache: bool = False):
        # Check cache first (unless skip_cache is True)
        if not skip_cache:
            cached = await dataforseo_cache.get_cached_search(
                query, location, location_code, language_code, depth
            )
            if cached is not None:
                cached["from_cache"] = True
                return cached

        # Call the actual method
        result = await func(self, query, location, location_code, language_code, depth)

        # Cache successful results
        if result.get("success"):
            result["from_cache"] = False
            await dataforseo_cache.set_cached_search(
                result, query, location, location_code, language_code, depth
            )

        return result

    return wrapper


def cached_details(func: Callable) -> Callable:
    """Decorator to cache business details."""
    @wraps(func)
    async def wrapper(self, keyword: Optional[str] = None, place_id: Optional[str] = None,
                     cid: Optional[str] = None, location: Optional[str] = None,
                     location_code: Optional[int] = None, language_code: str = "en",
                     skip_cache: bool = False):
        # Check cache first
        if not skip_cache:
            cached = await dataforseo_cache.get_cached_details(
                keyword, place_id, cid, location_code
            )
            if cached is not None:
                cached["from_cache"] = True
                return cached

        # Call the actual method
        result = await func(self, keyword, place_id, cid, location, location_code, language_code)

        # Cache successful results
        if result.get("success"):
            result["from_cache"] = False
            await dataforseo_cache.set_cached_details(
                result, keyword, place_id, cid, location_code
            )

        return result

    return wrapper
