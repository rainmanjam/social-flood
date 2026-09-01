"""
Social Flood API - Main Application Entry Point

This module initializes the FastAPI application with all necessary middleware,
exception handlers, and API routers. It serves as the main entry point for the
Social Flood API service.
"""
import logging
import time
import nltk
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any, Optional

from fastapi import FastAPI, Depends, Request, Response, APIRouter, Security
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
from starlette.exceptions import HTTPException
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

# Import application modules
from app.core.config import get_settings, Settings
from app.core.exceptions import (
    SocialFloodException, 
    configure_exception_handlers,
    RateLimitExceededError
)
from app.core.middleware import setup_middleware
from app.core.health_checks import check_health
from app.core.auth import get_api_key
from app.core.http_client import shutdown_http_client_manager
from app.core.rate_limiter import (
    start_cleanup_task as start_rate_limit_cleanup_task,
    stop_cleanup_task as stop_rate_limit_cleanup_task,
)

# Import API routers
from app.api.google_news.google_news_api import gnews_router, setup_nltk
from app.api.google_autocomplete.google_autocomplete_api import router as google_autocomplete_router
from app.api.google_trends.google_trends_api import google_trends_router
from app.api.youtube_transcripts.youtube_transcripts_api import youtube_transcripts_router
from app.api.google_maps.google_maps_api import google_maps_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Get application settings
settings = get_settings()

# Try to import slowapi for rate limiting
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    
    # Create rate limiter
    limiter = Limiter(key_func=get_remote_address)
    RATE_LIMITING_AVAILABLE = True
except ImportError:
    logger.warning("slowapi not installed. Rate limiting will be disabled.")
    limiter = None
    RATE_LIMITING_AVAILABLE = False

# Try to import prometheus client for metrics
try:
    from prometheus_client import Counter, Histogram
    from prometheus_fastapi_instrumentator import Instrumentator
    
    # Create metrics
    REQUESTS_TOTAL = Counter(
        "http_requests_total",
        "Total number of HTTP requests",
        ["method", "endpoint", "status"]
    )
    
    REQUEST_DURATION = Histogram(
        "http_request_duration_seconds",
        "HTTP request duration in seconds",
        ["method", "endpoint"]
    )
    
    METRICS_AVAILABLE = True
except ImportError:
    logger.warning("prometheus-client not installed. Metrics will be disabled.")
    METRICS_AVAILABLE = False

#: Header scheme used only to *declare* the API key in the OpenAPI schema for
#: the operational endpoints below. ``auto_error=False`` so that the
#: ENABLE_API_KEY_AUTH switch is honoured by require_api_key rather than being
#: short-circuited by the security scheme itself.
_operational_api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(
    api_key: Optional[str] = Security(_operational_api_key_scheme),
) -> None:
    """
    Gate for endpoints that disclose host or configuration detail.

    Delegates the actual validation to app.core.auth.get_api_key (unchanged),
    but reads settings per-request so the documented ENABLE_API_KEY_AUTH
    switch actually applies.

    Raises:
        HTTPException: 401 if authentication is enabled and the key is
            missing or invalid.
    """
    if not get_settings().ENABLE_API_KEY_AUTH:
        return
    await get_api_key(api_key)


def _docs_enabled() -> bool:
    """
    Decide whether the interactive docs and OpenAPI schema are served.

    /docs, /redoc and /openapi.json publish the complete API surface -- every
    path, parameter, enum and response model -- to anyone who can reach the
    service. They require no API key by design (the schema has to be readable
    before you can authenticate against it), so in production they hand an
    unauthenticated attacker a free map of the attack surface.

    They stay on outside production, where they are the main reason the
    service is pleasant to develop against. In production they are not
    registered at all, so they 404 rather than 401 -- a 401 would confirm the
    routes exist. Publish the schema to consumers from CI instead of from the
    live service.
    """
    return getattr(settings, "ENVIRONMENT", "development") != "production"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Manage application startup and shutdown.

    Replaces the deprecated @app.on_event hooks, which were removed in newer
    Starlette releases.
    """
    # --- startup ---
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} in {settings.ENVIRONMENT} mode")

    # Initialize NLTK
    await setup_nltk()

    # Start the rate limiter's cleanup task. Without this the in-memory
    # rate-limit store grows without bound for the life of the process.
    start_rate_limit_cleanup_task()

    if _docs_enabled():
        logger.info("API documentation available at /api/docs and /api/redoc")
    else:
        logger.info("API documentation disabled in production")
    logger.info("Health check available at /health")

    # Log rate limiting status
    if RATE_LIMITING_AVAILABLE and settings.RATE_LIMIT_ENABLED:
        logger.info(f"Rate limiting enabled: {settings.RATE_LIMIT_REQUESTS} requests per {settings.RATE_LIMIT_TIMEFRAME} seconds")
    else:
        logger.info("Rate limiting disabled")

    # Log metrics status
    if METRICS_AVAILABLE:
        logger.info("Metrics enabled at /metrics")
    else:
        logger.info("Metrics disabled")

    try:
        yield
    finally:
        # --- shutdown ---
        logger.info(f"Shutting down {settings.PROJECT_NAME}")
        stop_rate_limit_cleanup_task()
        await shutdown_http_client_manager()


# Create the FastAPI application
def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        FastAPI: The configured FastAPI application
    """
    docs_enabled = _docs_enabled()

    # Create FastAPI app with settings from environment
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.DESCRIPTION,
        version=settings.VERSION,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    # Setup middleware
    setup_middleware(app, settings)
    
    # Configure exception handlers
    configure_exception_handlers(app)
    
    # Setup rate limiting if available
    if RATE_LIMITING_AVAILABLE and settings.RATE_LIMIT_ENABLED:
        app.state.limiter = limiter
        
        @app.exception_handler(RateLimitExceeded)
        async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
            """Handle rate limit exceeded errors."""
            error = RateLimitExceededError(
                detail=f"Rate limit exceeded: {exc.detail}",
                headers={"Retry-After": str(exc.retry_after)}
            )
            return JSONResponse(
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                content=error.to_dict(),
                headers=error.headers
            )
    
    # Setup metrics if available
    if METRICS_AVAILABLE:
        instrumentator = Instrumentator()
        instrumentator.instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
    
    # Add custom OpenAPI documentation endpoints (non-production only, see
    # _docs_enabled: they enumerate the entire authenticated API surface).
    if docs_enabled:
        @app.get("/api/docs", include_in_schema=False)
        async def custom_swagger_ui_html():
            """Serve custom Swagger UI."""
            return get_swagger_ui_html(
                openapi_url=app.openapi_url,
                title=f"{settings.PROJECT_NAME} - API Documentation",
                swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
                swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
            )

        @app.get("/api/redoc", include_in_schema=False)
        async def custom_redoc_html():
            """Serve custom ReDoc."""
            return get_redoc_html(
                openapi_url=app.openapi_url,
                title=f"{settings.PROJECT_NAME} - API Documentation",
                redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
            )

    # Add health check endpoints
    @app.get("/health", tags=["Health"], summary="Basic health check")
    async def health_check():
        """
        Liveness probe.

        Intentionally returns nothing beyond liveness. Version and environment
        were removed: this endpoint is unauthenticated, and advertising the
        running version tells an unauthenticated caller exactly which CVEs to
        try. Use the authenticated /status endpoint for build details.
        """
        return {"status": "healthy"}

    @app.get(
        "/health/detailed",
        tags=["Health"],
        summary="Detailed health check",
        dependencies=[Depends(require_api_key)],
    )
    async def detailed_health_check():
        """Detailed health check endpoint (requires an API key)."""
        return await check_health(include_details=True, settings=settings)

    @app.get("/ping", tags=["Health"], summary="Simple ping endpoint")
    async def ping():
        """Simple ping endpoint for load balancers."""
        return {"ping": "pong"}

    @app.get(
        "/status",
        tags=["Health"],
        summary="Application status",
        dependencies=[Depends(require_api_key)],
    )
    async def status():
        """Application status endpoint (requires an API key)."""
        return {
            "status": "online",
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "timestamp": time.time(),
            "uptime": time.time() - app.state.start_time if hasattr(app.state, "start_time") else 0
        }

    # Add API configuration endpoints
    @app.get(
        "/api-config",
        tags=["Configuration"],
        summary="API configuration",
        dependencies=[Depends(require_api_key)],
    )
    async def api_config():
        """API configuration endpoint."""
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "rate_limiting": {
                "enabled": settings.RATE_LIMIT_ENABLED and RATE_LIMITING_AVAILABLE,
                "requests": settings.RATE_LIMIT_REQUESTS,
                "timeframe": settings.RATE_LIMIT_TIMEFRAME
            },
            "caching": {
                "enabled": settings.ENABLE_CACHE,
                "ttl": settings.CACHE_TTL
            },
            "cors": {
                "origins": settings.CORS_ORIGINS,
                "methods": settings.CORS_METHODS,
                "headers": settings.CORS_HEADERS
            }
        }
    
    @app.get(
        "/config-sources",
        tags=["Configuration"],
        summary="Configuration sources",
        dependencies=[Depends(require_api_key)],
    )
    async def config_sources():
        """Configuration sources endpoint."""
        return {
            "environment_variables": True,
            "env_file": ".env" in settings.model_config.get("env_file", []),
            "defaults": True
        }
    
    # Create v1 router
    v1_router = APIRouter(prefix="/api/v1")
    
    # Include API routers in v1 router
    v1_router.include_router(
        gnews_router,
        prefix="/google-news",
        tags=["Google News API"],
        dependencies=[Depends(get_api_key)]
    )
    
    v1_router.include_router(
        google_trends_router,
        prefix="/google-trends",
        tags=["Google Trends API"],
        dependencies=[Depends(get_api_key)]
    )
    
    v1_router.include_router(
        google_autocomplete_router,
        prefix="/google-autocomplete", 
        tags=["Google Autocomplete API"],
        dependencies=[Depends(get_api_key)]
    )
    
    v1_router.include_router(
        youtube_transcripts_router,
        prefix="/youtube-transcripts",
        tags=["YouTube Transcripts API"],
        dependencies=[Depends(get_api_key)]
    )

    v1_router.include_router(
        google_maps_router,
        prefix="/google-maps",
        tags=["Google Maps API"],
        dependencies=[Depends(get_api_key)]
    )

    # Include v1 router in app
    app.include_router(v1_router)
    
    # Store start time for uptime calculation
    app.state.start_time = time.time()
    
    return app

# Create the application instance
app = create_application()

# Run the application if executed directly
if __name__ == "__main__":
    import uvicorn
    
    # Get host and port from settings if available
    host = getattr(settings, "HOST", "0.0.0.0")
    port = getattr(settings, "PORT", 8000)
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=settings.DEBUG,
        log_level="info"
    )
