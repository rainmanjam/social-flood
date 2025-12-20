"""
Google Maps API Module.

Provides endpoints using DataForSEO API for:
- Place search (SERP API)
- Place details (My Business Info API)
- Reviews extraction (Reviews API - async task workflow)
"""

from app.api.google_maps.google_maps_api import google_maps_router

__all__ = ["google_maps_router"]
