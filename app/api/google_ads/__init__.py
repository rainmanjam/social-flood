"""
Google Ads API package for the Social Flood API.

This package provides access to Google Ads API data, including keyword research,
search volume, competition analysis, and bid estimates. It also includes an endpoint
that combines Google Autocomplete with Google Ads data for comprehensive SEO analysis.
"""
import logging
from fastapi import APIRouter, HTTPException
from app.core.config import get_settings
from app.api.google_ads.google_ads_api import router as google_ads_router

# Configure logging
logger = logging.getLogger(__name__)

# Get application settings
settings = get_settings()

# Check if Google Ads API credentials are configured
google_ads_enabled = all([
    settings.GOOGLE_ADS_DEVELOPER_TOKEN,
    settings.GOOGLE_ADS_CLIENT_ID,
    settings.GOOGLE_ADS_CLIENT_SECRET,
    settings.GOOGLE_ADS_REFRESH_TOKEN
])

if google_ads_enabled:
    # Call the router() method to get the actual APIRouter instance
    # This is necessary because BaseRouter.__call__() returns the underlying APIRouter
    router = google_ads_router()
    logger.info("Google Ads API enabled")
else:
    # Create a placeholder router that returns a 503 Service Unavailable response
    logger.warning("Google Ads API disabled: credentials not fully configured")
    
    # Create a placeholder router
    router = APIRouter(prefix="/api/v1/google-ads", tags=["Google Ads API"])
    
    @router.get("/", summary="Google Ads API Status")
    @router.get("/{path:path}", summary="Google Ads API Status")
    async def google_ads_disabled():
        """Google Ads API is disabled due to missing credentials."""
        raise HTTPException(
            status_code=503,
            detail="Google Ads API is disabled: credentials not fully configured"
        )

__all__ = ["router"]
