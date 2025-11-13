from fastapi import APIRouter, HTTPException, Query, Depends, Request
from fastapi.responses import JSONResponse
from GoogleNews import GoogleNews
from typing import List, Optional
import logging
import json
import asyncio
from urllib.parse import quote, urlparse
import httpx
from selectolax.parser import HTMLParser
import os
import nltk
from pydantic import BaseModel, validator, ValidationError
import re
from app.core.proxy import get_proxy
import datetime
from app.core.rate_limiter import rate_limit
from app.core.cache_manager import cache_manager
from app.core.config import get_settings

# Note: newspaper library removed due to Python 3.11+ dependency conflicts (sgmllib3k)
# Article details extraction endpoint has been removed

# Initialize NLTK asynchronously at module level
async def setup_nltk():
    """Setup NLTK resources once at startup."""
    try:
        # Set NLTK data path to a writable directory
        nltk_data_dir = os.path.join(os.getcwd(), "nltk_data")
        os.makedirs(nltk_data_dir, exist_ok=True)
        nltk.data.path.insert(0, nltk_data_dir)

        # Check if 'punkt_tab' is already downloaded
        try:
            nltk.data.find('tokenizers/punkt_tab')
            logger.info("NLTK 'punkt_tab' resource already available.")
        except LookupError:
            # 'punkt_tab' not found, so download it
            logger.info("NLTK 'punkt_tab' resource not found. Downloading...")
            nltk.download('punkt_tab', nltk_data_dir, quiet=True)
            logger.info("NLTK 'punkt_tab' resource downloaded successfully.")

        # Also download 'punkt' as fallback
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            logger.info("Downloading fallback 'punkt' resource...")
            nltk.download('punkt', nltk_data_dir, quiet=True)

    except Exception as e:
        # Handle any other exceptions during NLTK setup
        logger.error(f"An error occurred during NLTK setup: {e}")

# Run NLTK setup at import time (this will be awaited in the lifespan event)
_nltk_setup_task = None

async def ensure_nltk_setup():
    """Ensure NLTK is set up, running setup only once."""
    global _nltk_setup_task
    if _nltk_setup_task is None:
        _nltk_setup_task = asyncio.create_task(setup_nltk())
    await _nltk_setup_task

# Initialize Google News API Router
gnews_router = APIRouter()
logger = logging.getLogger(__name__)

# Pydantic Model for Input Validation
class SourceQuery(BaseModel):
    source: str

    @validator('source')
    def validate_source(cls, v):
        # Optimized regex to validate domain names or full URLs
        pattern = r'^(https?://)?(www\.)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$'
        if not re.fullmatch(pattern, v):
            raise ValueError('Invalid source URL or domain.')
        return v

AVAILABLE_TOPICS = [
    "WORLD", "NATION", "BUSINESS", "TECHNOLOGY", "ENTERTAINMENT", "SPORTS", "SCIENCE", "HEALTH"
]

AVAILABLE_LANGUAGES = {
    'english': 'en',
    'spanish': 'es',
    'french': 'fr',
    'german': 'de',
    'italian': 'it',
    'dutch': 'nl',
    'portuguese': 'pt',
    'russian': 'ru',
    'chinese': 'zh',
    'japanese': 'ja',
    'korean': 'ko',
    'arabic': 'ar',
    'hindi': 'hi'
}

AVAILABLE_COUNTRIES = {
    'United States': 'US',
    'United Kingdom': 'GB',
    'Canada': 'CA',
    'Australia': 'AU',
    'India': 'IN',
    'Germany': 'DE',
    'France': 'FR',
    'Spain': 'ES',
    'Italy': 'IT',
    'Japan': 'JP',
    'China': 'CN',
    'Brazil': 'BR',
    'Mexico': 'MX',
    'Russia': 'RU'
}

# Global cache manager instance
settings = get_settings()

# -----------------------------------------------------------------------------
# Cache key generation functions
# -----------------------------------------------------------------------------
def generate_cache_key(endpoint: str, **params) -> str:
    """
    Generate a cache key for Google News API calls.

    Args:
        endpoint: The API endpoint name
        **params: Query parameters

    Returns:
        str: Cache key
    """
    # Sort parameters for consistent key generation
    sorted_params = sorted(params.items())
    param_str = "_".join(f"{k}:{v}" for k, v in sorted_params if v is not None)
    return f"gnews:{endpoint}:{param_str}"

async def get_cached_or_fetch(key: str, fetch_func, ttl: int = None):
    """
    Get data from cache or fetch and cache it.

    Args:
        key: Cache key
        fetch_func: Async function to fetch data if not cached
        ttl: Time to live in seconds

    Returns:
        The fetched or cached data
    """
    if not settings.ENABLE_CACHE:
        return await fetch_func()

    # Try to get from cache
    cached_data = await cache_manager.get(key, namespace="gnews")
    if cached_data is not None:
        logger.debug(f"Cache hit for key: {key}")
        return cached_data

    # Fetch data
    data = await fetch_func()

    # Cache the result
    if data:
        ttl = ttl or settings.CACHE_TTL
        await cache_manager.set(key, data, ttl=ttl, namespace="gnews")
        logger.debug(f"Cached data for key: {key}, TTL: {ttl}s")

    return data

# Global HTTP client pool for GNews operations
_gnews_http_client: Optional[httpx.AsyncClient] = None

async def get_gnews_http_client(proxy_url: Optional[str] = None) -> httpx.AsyncClient:
    """Get or create a shared HTTP client for GNews operations with connection pooling."""
    global _gnews_http_client

    if _gnews_http_client is None:
        limits = httpx.Limits(
            max_keepalive_connections=settings.HTTP_MAX_KEEPALIVE_CONNECTIONS,
            max_connections=settings.HTTP_MAX_CONNECTIONS_PER_HOST,
            keepalive_expiry=30.0
        )

        timeout = httpx.Timeout(
            connect=settings.HTTP_CONNECTION_TIMEOUT,
            read=settings.HTTP_READ_TIMEOUT,
            write=10.0,
            pool=5.0
        )

        mounts = None
        if proxy_url:
            mounts = {
                "http://": httpx.AsyncHTTPTransport(proxy=proxy_url),
                "https://": httpx.AsyncHTTPTransport(proxy=proxy_url),
            }

        _gnews_http_client = httpx.AsyncClient(
            limits=limits,
            timeout=timeout,
            mounts=mounts,
            follow_redirects=True
        )
        logger.debug("Created shared HTTP client for GNews operations")

    return _gnews_http_client

# -----------------------------------------------------------------------------
# Helper function to create a new GoogleNews instance per request
# -----------------------------------------------------------------------------
async def get_googlenews_instance(
    language: str = "en",
    country: str = "US",
    max_results: int = 10,
    period: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> GoogleNews:
    """
    Create a GoogleNews instance with specified parameters.

    Note: GoogleNews package has different API than gnews, so this is adapted.
    """
    # Map language codes if needed
    lang = language if len(language) == 2 else 'en'

    # Create instance
    googlenews = GoogleNews(lang=lang)

    # Set period if specified (format: '7d', '1m', etc.)
    if period:
        googlenews.set_period(period)
    elif start_date and end_date:
        # GoogleNews expects MM/DD/YYYY format
        googlenews.set_time_range(start_date, end_date)

    # Set encode to 'utf-8' for proper character handling
    googlenews.set_encode('utf-8')

    return googlenews

# -----------------------------------------------------------------------------
# Helper: Transform Article Data from GoogleNews format
# -----------------------------------------------------------------------------
def transform_googlenews_article(article: dict) -> dict:
    """Transform GoogleNews article format to our standard format."""
    return {
        "title": article.get("title", ""),
        "description": article.get("desc", ""),
        "published_date": article.get("date", ""),
        "url": article.get("link", ""),
        "publisher": article.get("site", article.get("media", ""))
    }

# -----------------------------------------------------------------------------
# Pydantic Models for Responses
# -----------------------------------------------------------------------------
class NewsArticle(BaseModel):
    title: str
    published_date: str
    description: Optional[str]
    url: str
    publisher: Optional[str]

class NewsResponse(BaseModel):
    articles: List[NewsArticle]

class ErrorResponse(BaseModel):
    detail: str

# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@gnews_router.get(
    "/available-languages/",
    summary="Get Available Languages",
    response_description="List of available languages for Google News.",
    response_model=dict
)
async def get_languages():
    """Get a list of available languages for Google News."""
    return {"available_languages": AVAILABLE_LANGUAGES}

@gnews_router.get(
    "/available-countries/",
    summary="Get Available Countries",
    response_description="List of available countries for Google News.",
    response_model=dict
)
async def get_available_countries():
    """Get a list of available countries for Google News."""
    return {"available_countries": AVAILABLE_COUNTRIES}

@gnews_router.get(
    "/search/",
    summary="Search Google News",
    response_description="List of news articles based on the search query.",
    response_model=NewsResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid query parameters."},
        404: {"model": ErrorResponse, "description": "No news found for the given query."},
        500: {"model": ErrorResponse, "description": "Internal Server Error."},
    }
)
async def search_google_news(
    request: Request,
    query: str = Query(..., description="The search query string."),
    language: str = Query("en", description="Language for the news results."),
    max_results: int = Query(10, ge=1, le=100, description="Maximum number of news results (1-100)."),
    period: Optional[str] = Query("7d", description="Time period (e.g., '7d', '1m')"),
    rate_limit_check: None = Depends(rate_limit),
):
    """
    Search Google News articles based on a query string.

    ### Parameters:
    - **query**: The search query string.
    - **language**: Language for the news results (default: 'en').
    - **max_results**: Maximum number of news results (1-100).
    - **period**: Time period for results (default: '7d').

    ### Responses:
    - **200 OK**: Returns a list of news articles based on the search query.
    - **400 Bad Request**: Invalid query parameters.
    - **404 Not Found**: No news found for the given query.
    - **500 Internal Server Error**: Unexpected server error.
    """
    try:
        # Generate cache key
        cache_key = generate_cache_key(
            "search",
            query=query,
            language=language,
            max_results=max_results,
            period=period
        )

        async def fetch_search_results():
            # Create GoogleNews instance
            googlenews = await get_googlenews_instance(
                language=language,
                max_results=max_results,
                period=period
            )

            # Run search in executor (GoogleNews is synchronous)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, googlenews.search, query)
            results = await loop.run_in_executor(None, googlenews.results)

            if not results:
                raise HTTPException(status_code=404, detail="No news found for the given query.")

            # Transform articles
            articles = [transform_googlenews_article(article) for article in results[:max_results]]

            # Clear results for next search
            await loop.run_in_executor(None, googlenews.clear)

            return {"articles": articles}

        # Get cached result or fetch and cache
        return await get_cached_or_fetch(cache_key, fetch_search_results)

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error fetching Google News for query '{query}': {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@gnews_router.get(
    "/top/",
    summary="Get Top Google News",
    response_description="List of top news articles.",
    response_model=NewsResponse,
    responses={
        404: {"model": ErrorResponse, "description": "No top news found."},
        500: {"model": ErrorResponse, "description": "Internal Server Error."},
    }
)
async def get_top_google_news(
    language: str = Query("en", description="Language for the news results."),
    max_results: int = Query(10, ge=1, le=100, description="Maximum number of news results (1-100)."),
):
    """
    Get the top Google News articles.

    ### Parameters:
    - **language**: Language for the news results (default: 'en').
    - **max_results**: Maximum number of news results (1-100).

    ### Responses:
    - **200 OK**: Returns a list of top news articles.
    - **404 Not Found**: No top news found.
    - **500 Internal Server Error**: Unexpected server error.
    """
    try:
        # Create GoogleNews instance
        googlenews = await get_googlenews_instance(
            language=language,
            max_results=max_results,
        )

        loop = asyncio.get_event_loop()
        # Search for "top stories" or general news
        await loop.run_in_executor(None, googlenews.search, "top stories")
        results = await loop.run_in_executor(None, googlenews.results)

        if not results:
            raise HTTPException(status_code=404, detail="No top news found.")

        # Transform articles
        articles = [transform_googlenews_article(article) for article in results[:max_results]]

        # Clear results
        await loop.run_in_executor(None, googlenews.clear)

        return {"articles": articles}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error fetching top Google News: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@gnews_router.get(
    "/topic/",
    summary="Get Google News by Topic",
    response_description="List of news articles based on the specified topic.",
    response_model=NewsResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid topic provided."},
        404: {"model": ErrorResponse, "description": "No news found for the given topic."},
        500: {"model": ErrorResponse, "description": "Internal Server Error."},
    }
)
async def get_news_by_topic(
    topic: str = Query(..., description="The topic to filter news articles."),
    language: str = Query("en", description="Language for the news results."),
    max_results: int = Query(10, ge=1, le=100, description="Maximum number of news results (1-100)."),
):
    """
    Get Google News articles based on a specific topic.

    ### Parameters:
    - **topic**: The topic to filter news articles.
    - **language**: Language for the news results (default: 'en').
    - **max_results**: Maximum number of news results (1-100).

    ### Responses:
    - **200 OK**: Returns a list of news articles based on the specified topic.
    - **400 Bad Request**: Invalid topic provided.
    - **404 Not Found**: No news found for the given topic.
    - **500 Internal Server Error**: Unexpected server error.
    """
    if topic.upper() not in AVAILABLE_TOPICS:
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid topic provided.", "available_topics": AVAILABLE_TOPICS}
        )
    try:
        # Create GoogleNews instance
        googlenews = await get_googlenews_instance(
            language=language,
            max_results=max_results,
        )

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, googlenews.search, topic)
        results = await loop.run_in_executor(None, googlenews.results)

        if not results:
            raise HTTPException(status_code=404, detail="No news found for the given topic.")

        # Transform articles
        articles = [transform_googlenews_article(article) for article in results[:max_results]]

        # Clear results
        await loop.run_in_executor(None, googlenews.clear)

        return {"articles": articles}
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error fetching Google News for topic '{topic}': {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

# Note: /article-details endpoint removed due to newspaper library dependency conflicts
# The newspaper3k and newspaper4k libraries have unmaintained dependencies (sgmllib3k)
# that are incompatible with Python 3.11+
# Users can extract article content directly from the URLs returned by other endpoints
