"""
Google Maps API module.

Provides FastAPI endpoints for Google Maps data extraction via gosom scraper.
"""
from app.api.google_maps.google_maps_api import google_maps_router

__all__ = ["google_maps_router"]
