"""
Social Flood API - Main Application Entry Point

This module initializes the FastAPI application with all necessary middleware,
exception handlers, and API routers. It serves as the main entry point for the
Social Flood API service.
"""
import logging
import time
import nltk
from typing import Dict, Any, Optional

from fastapi import FastAPI, Depends, Request, Response, APIRouter
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

# Import API routers
from app.api.google_news.google_news_api import gnews_router, setup_nltk
from app.api.google_autocomplete.google_autocomplete_api import router as google_autocomplete_router
from app.api.google_trends.google_trends_api import google_trends_router
from app.api.youtube_transcripts.youtube_transcripts_api import youtube_transcripts_router
from app.api.google_ads import router as google_ads_router

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

# Create the FastAPI application
def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        FastAPI: The configured FastAPI application
    """
    # Create FastAPI app with settings from environment
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.DESCRIPTION,
        version=settings.VERSION,
        docs_url="/docs",  # Standard docs endpoint
        redoc_url="/redoc",  # Standard redoc endpoint
        openapi_url="/openapi.json",
        debug=settings.DEBUG
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
    
    # Add startup event
    @app.on_event("startup")
    async def startup_event():
        """Initialize resources on startup."""
        logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} in {settings.ENVIRONMENT} mode")
        
        # Initialize NLTK
        await setup_nltk()
        
        # Log application settings
        logger.info(f"API documentation available at /api/docs and /api/redoc")
        logger.info(f"Health check available at /health")
        
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
    
    # Add shutdown event
    @app.on_event("shutdown")
    async def shutdown_event():
        """Clean up resources on shutdown."""
        logger.info(f"Shutting down {settings.PROJECT_NAME}")
    
    # Add custom OpenAPI documentation endpoints
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
        """Basic health check endpoint."""
        return {
            "status": "healthy",
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "timestamp": time.time()
        }
    
    @app.get("/health/detailed", tags=["Health"], summary="Detailed health check")
    async def detailed_health_check():
        """Detailed health check endpoint."""
        return await check_health(include_details=True, settings=settings)
    
    @app.get("/ping", tags=["Health"], summary="Simple ping endpoint")
    async def ping():
        """Simple ping endpoint for load balancers."""
        return {"ping": "pong"}
    
    @app.get("/status", tags=["Health"], summary="Application status")
    async def status():
        """Application status endpoint."""
        return {
            "status": "online",
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "timestamp": time.time(),
            "uptime": time.time() - app.state.start_time if hasattr(app.state, "start_time") else 0
        }
    
    # Add API configuration endpoints
    @app.get("/api-config", tags=["Configuration"], summary="API configuration")
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
    
    @app.get("/config-sources", tags=["Configuration"], summary="Configuration sources")
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
    
    # The google_ads_router is already an APIRouter instance (from BaseRouter.__call__())
    # and already has prefix, tags, and dependencies set
    v1_router.include_router(google_ads_router)
    
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
