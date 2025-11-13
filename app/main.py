import os
import nltk
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

# Import version from version file
try:
    from app.__version__ import __version__ as app_version
except ImportError:
    app_version = "1.0.0"  # Fallback version

# Import API routers
# from app.api.google_news.google_news_api import gnews_router  # Temporarily disabled - dependency issue
from app.api.google_trends.google_trends_api import google_trends_router
from app.api.google_autocomplete.google_autocomplete_api import router as google_autocomplete_router
from app.api.youtube_transcripts.youtube_transcripts_api import youtube_transcripts_router
from app.api.google_ads.google_ads_api import google_ads_router

# Configure logging
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Download required NLTK data on startup
    try:
        # Set NLTK data path to a writable directory
        nltk_data_dir = os.path.join(os.getcwd(), "nltk_data")
        os.makedirs(nltk_data_dir, exist_ok=True)
        nltk.data.path.insert(0, nltk_data_dir)

        # Download required NLTK resources
        nltk.download('punkt_tab', download_dir=nltk_data_dir, quiet=True)
        logger.info("NLTK resources downloaded successfully")
    except Exception as e:
        logger.warning(f"Failed to download NLTK resources: {e}")

    yield

# Update FastAPI app initialization
app = FastAPI(
    title="Social Flood API",
    description="API for social media monitoring, content analysis, and keyword research",
    version=app_version,  # Use dynamic version
    lifespan=lifespan
)

# Add middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include API routers
# app.include_router(gnews_router, prefix="/api/v1/google-news", tags=["Google News"])  # Temporarily disabled
app.include_router(google_trends_router, prefix="/api/v1/google-trends", tags=["Google Trends"])
app.include_router(google_autocomplete_router, prefix="/api/v1/google-autocomplete", tags=["Google Autocomplete"])
app.include_router(youtube_transcripts_router, prefix="/api/v1/youtube-transcripts", tags=["YouTube Transcripts"])
app.include_router(google_ads_router, prefix="/api/v1/google-ads", tags=["Google Ads"])

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Social Flood API",
        "version": app_version,
        "docs": "/docs",
        "redoc": "/redoc",
        "apis": {
            # "google_news": "/api/v1/google-news",  # Temporarily disabled
            "google_trends": "/api/v1/google-trends",
            "google_autocomplete": "/api/v1/google-autocomplete",
            "youtube_transcripts": "/api/v1/youtube-transcripts",
            "google_ads": "/api/v1/google-ads"
        }
    }

@app.get("/health", tags=["Health"])
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "version": app_version}