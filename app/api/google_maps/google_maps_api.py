"""
Google Maps API endpoints.

This module provides FastAPI endpoints for Google Maps data extraction
using native Python with Playwright for browser automation.

Features:
- Places search with customizable parameters
- Comprehensive place details extraction
- Service options (dine-in, drive-through, delivery, etc.)
- Review topics and keywords with mention counts
- Popular times hourly data
- Review summary with star breakdown
- Related places ("People also search for")
- Operating hours with daily schedules
- Photos, menu links, and action buttons
- Async job management for large searches

Extended Features:
- Place Lookup: Direct place details by URL or Place ID
- Nearby Search: Coordinate-based radius search
- Reviews Endpoint: Paginated review fetching
- Photos Endpoint: High-resolution photo URLs
- Autocomplete: Place name suggestions
- Bulk Search: Multiple queries in one request
- Export Formats: CSV, Excel, JSON Lines
- Q&A Extraction: Questions and answers from listings
- Review Analytics: Sentiment analysis and trends
- Competitor Analysis: Compare nearby businesses
- Place Monitoring: Track changes over time
- Webhooks: Job completion notifications
- Directions: Route planning between locations
- Street View: Street-level imagery URLs
- Menu Extraction: Structured menu data
- Batch Geocoding: Address to coordinates
"""
import logging
import csv
import io
import json
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query, Path, BackgroundTasks, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, validator

from app.core.auth import get_api_key
from app.core.rate_limiter import rate_limit
from app.core.cache_manager import generate_cache_key, get_cached_or_fetch
from app.services.google_maps_service import google_maps_service

logger = logging.getLogger(__name__)

# Create router
google_maps_router = APIRouter(tags=["Google Maps API"])


# Pydantic models for request/response
class SearchRequest(BaseModel):
    """Request model for places search."""
    query: str = Field(
        ...,
        description="Search query (e.g., 'restaurants in New York', 'coffee shops near Times Square')",
        min_length=3,
        max_length=500,
        examples=["restaurants in New York", "coffee shops near Times Square"]
    )
    language: str = Field(
        "en",
        description="Language code for results (ISO 639-1)",
        examples=["en", "es", "fr", "de"]
    )
    max_results: int = Field(
        20,
        ge=1,
        le=100,
        description="Maximum number of results to return"
    )
    depth: int = Field(
        1,
        ge=1,
        le=3,
        description="Crawl depth for pagination (1=first page only, higher=more results)"
    )
    email_extraction: bool = Field(
        False,
        description="Extract emails from business websites (slower but provides contact info)"
    )
    zoom: int = Field(
        15,
        ge=1,
        le=21,
        description="Map zoom level (1=world, 21=building level)"
    )
    geo_coordinates: Optional[str] = Field(
        None,
        description="Search center coordinates (format: 'lat,lng')",
        examples=["40.7128,-74.0060"]
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "coffee shops in Manhattan",
                "language": "en",
                "max_results": 20,
                "depth": 1,
                "email_extraction": False,
                "zoom": 15
            }
        }


class JobResponse(BaseModel):
    """Response model for job creation."""
    success: bool
    job_id: Optional[str] = None
    status: str
    message: Optional[str] = None
    estimated_time: Optional[str] = None


class ReviewTopic(BaseModel):
    """Model for a review topic/keyword."""
    topic: str = Field(..., description="Topic or keyword mentioned in reviews", examples=["drive thru", "breakfast", "coffee"])
    count: int = Field(..., description="Number of reviews mentioning this topic", examples=[102, 45, 23])


class RelatedPlace(BaseModel):
    """Model for a related place from 'People also search for'."""
    name: str = Field(..., description="Name of the related business")
    rating: Optional[float] = Field(None, description="Star rating (1-5)")
    review_count: Optional[int] = Field(None, description="Number of reviews")
    category: Optional[str] = Field(None, description="Business category")


class PlaceResult(BaseModel):
    """
    Model for a single place result.

    Contains comprehensive business information extracted from Google Maps,
    including basic details, reviews, service options, and engagement data.
    """
    # Basic Information
    place_id: Optional[str] = Field(None, description="Unique Google Maps place identifier (CID)")
    name: Optional[str] = Field(None, description="Business name", examples=["Starbucks", "McDonald's"])
    address: Optional[str] = Field(None, description="Full street address")
    phone: Optional[str] = Field(None, description="Phone number with country code")
    website: Optional[str] = Field(None, description="Business website URL")

    # Location
    latitude: Optional[float] = Field(None, description="Geographic latitude coordinate", examples=[45.5231])
    longitude: Optional[float] = Field(None, description="Geographic longitude coordinate", examples=[-122.6765])
    plus_code: Optional[str] = Field(None, description="Google Plus Code for precise location", examples=["85HQ+XX Portland, Oregon"])
    google_maps_url: Optional[str] = Field(None, description="Direct link to Google Maps page")

    # Business Classification
    category: Optional[str] = Field(None, description="Primary business category", examples=["Coffee shop", "Restaurant", "Hotel"])
    description: Optional[str] = Field(None, description="Business description or 'About' text")

    # Ratings & Reviews
    rating: Optional[float] = Field(None, description="Average star rating (1.0-5.0)", ge=1.0, le=5.0, examples=[4.2])
    review_count: Optional[int] = Field(None, description="Total number of reviews", examples=[1523])
    review_summary: Optional[dict] = Field(
        None,
        description="Star breakdown showing count per rating level",
        examples=[{"5_star": 474, "4_star": 120, "3_star": 45, "2_star": 15, "1_star": 10}]
    )
    review_topics: Optional[List[dict]] = Field(
        None,
        description="Keywords frequently mentioned in reviews with counts",
        examples=[[{"topic": "drive thru", "count": 102}, {"topic": "breakfast", "count": 45}]]
    )
    sample_reviews: Optional[List[str]] = Field(None, description="Sample review quotes displayed prominently")
    reviews: Optional[List[dict]] = Field(None, description="Full review data (when available)")

    # Pricing
    price_level: Optional[str] = Field(None, description="Price indicator ($, $$, $$$, $$$$)")
    price_per_person: Optional[str] = Field(None, description="Estimated cost per person", examples=["$1–10", "$10–25"])

    # Hours & Availability
    hours: Optional[dict] = Field(
        None,
        description="Operating hours by day of week",
        examples=[{"Monday": ["6 AM–9 PM"], "Tuesday": ["6 AM–9 PM"]}]
    )
    is_open_now: Optional[bool] = Field(None, description="Whether currently open")
    popular_times: Optional[dict] = Field(
        None,
        description="Hourly busy percentages by day",
        examples=[{"Saturday": [{"hour": "10 AM", "busy_percent": 45}, {"hour": "12 PM", "busy_percent": 85}]}]
    )

    # Live Wait Time & Busyness
    wait_time_minutes: Optional[int] = Field(
        None,
        description="Current or typical wait time in minutes",
        examples=[15, 30, 45]
    )
    wait_time_raw: Optional[str] = Field(
        None,
        description="Raw wait time text from Google Maps",
        examples=["Usually 15 min wait", "Live: 20 min wait"]
    )
    live_busyness: Optional[str] = Field(
        None,
        description="Live busyness indicator from Google Maps",
        examples=["Live: Busier than usual", "Live: Not too busy", "Live: As busy as it gets"]
    )
    typical_busyness: Optional[str] = Field(
        None,
        description="Typical busyness level at current time",
        examples=["Usually not too busy", "Usually a little busy", "Usually not busy"]
    )

    # Service Options & Features
    service_options: Optional[List[str]] = Field(
        None,
        description="Available service types",
        examples=[["Dine-In", "Drive-Through", "Delivery", "Takeout", "Curbside Pickup"]]
    )
    accessibility: Optional[List[str]] = Field(None, description="Accessibility features available")
    amenities: Optional[List[str]] = Field(None, description="Available amenities and highlights")

    # Media & Links
    photos: Optional[List[str]] = Field(None, description="Photo URLs (high resolution)")
    menu_link: Optional[str] = Field(None, description="Link to menu page")
    order_link: Optional[str] = Field(None, description="Link to online ordering")
    reserve_link: Optional[str] = Field(None, description="Link to make reservations")

    # Related Content
    related_places: Optional[List[dict]] = Field(
        None,
        description="'People also search for' suggestions",
        examples=[[{"name": "Burger King", "rating": 3.3, "review_count": 1084, "category": "Restaurant"}]]
    )

    # Contact Information (from email extraction)
    emails: Optional[List[str]] = Field(None, description="Extracted email addresses (requires email_extraction=true)")
    social_media: Optional[dict] = Field(
        None,
        description="Social media profile links",
        examples=[{"facebook": "https://facebook.com/...", "instagram": "https://instagram.com/..."}]
    )

    class Config:
        json_schema_extra = {
            "example": {
                "place_id": "0x54950a0d7f8a85e5:0x1234567890abcdef",
                "name": "Starbucks",
                "address": "123 Main St, Portland, OR 97201",
                "phone": "+1 503-555-0100",
                "website": "https://www.starbucks.com",
                "latitude": 45.5231,
                "longitude": -122.6765,
                "category": "Coffee shop",
                "rating": 4.2,
                "review_count": 523,
                "price_level": "$$",
                "service_options": ["Dine-In", "Drive-Through", "Delivery"],
                "review_topics": [
                    {"topic": "coffee", "count": 89},
                    {"topic": "drive thru", "count": 45}
                ],
                "hours": {
                    "Monday": ["5:30 AM–8 PM"],
                    "Tuesday": ["5:30 AM–8 PM"]
                },
                "is_open_now": True,
                "menu_link": "https://www.starbucks.com/menu"
            }
        }


class SearchResponse(BaseModel):
    """Response model for search results."""
    success: bool
    query: str
    total_results: int
    places: List[dict]
    message: Optional[str] = None
    job_id: Optional[str] = None
    timestamp: str


# ============================================================================
# Extended Feature Models
# ============================================================================

class NearbySearchRequest(BaseModel):
    """Request model for nearby search."""
    latitude: float = Field(..., description="Center latitude", ge=-90, le=90, examples=[40.7128])
    longitude: float = Field(..., description="Center longitude", ge=-180, le=180, examples=[-74.0060])
    radius_meters: int = Field(1000, ge=100, le=50000, description="Search radius in meters")
    query: Optional[str] = Field(None, description="Optional filter query (e.g., 'restaurants')")
    language: str = Field("en", description="Language code")
    max_results: int = Field(20, ge=1, le=100, description="Maximum results")


class PlaceLookupRequest(BaseModel):
    """Request model for place lookup by URL or ID."""
    url: Optional[str] = Field(None, description="Google Maps URL", examples=["https://www.google.com/maps/place/..."])
    place_id: Optional[str] = Field(None, description="Google Place ID (CID)", examples=["0x89c259af18b60947:0x8c5e3c1d36e36e0a"])

    @validator('url', 'place_id')
    def at_least_one_required(cls, v, values):
        if not v and not values.get('url') and not values.get('place_id'):
            pass  # Validation will happen at endpoint level
        return v


class BulkSearchRequest(BaseModel):
    """Request model for bulk search operations."""
    queries: List[str] = Field(..., min_items=1, max_items=50, description="List of search queries")
    language: str = Field("en", description="Language code")
    max_results_per_query: int = Field(10, ge=1, le=50, description="Max results per query")


class ReviewsRequest(BaseModel):
    """Request model for reviews endpoint."""
    sort_by: str = Field("most_relevant", description="Sort order", examples=["most_relevant", "newest", "highest_rating", "lowest_rating"])
    limit: int = Field(50, ge=1, le=200, description="Number of reviews to fetch")
    offset: int = Field(0, ge=0, description="Pagination offset")
    min_rating: Optional[int] = Field(None, ge=1, le=5, description="Minimum star rating filter")
    include_owner_responses: bool = Field(True, description="Include business owner responses")


class PhotosRequest(BaseModel):
    """Request model for photos endpoint."""
    max_photos: int = Field(20, ge=1, le=100, description="Maximum photos to return")
    size: str = Field("large", description="Photo size", examples=["thumbnail", "medium", "large", "original"])
    category: Optional[str] = Field(None, description="Photo category filter", examples=["all", "food", "interior", "exterior", "menu"])


class QARequest(BaseModel):
    """Request model for Q&A endpoint."""
    limit: int = Field(20, ge=1, le=100, description="Maximum Q&A pairs to return")
    include_answers: bool = Field(True, description="Include answers for each question")


class ReviewAnalyticsRequest(BaseModel):
    """Request model for review analytics."""
    time_period: str = Field("all", description="Time period for analysis", examples=["week", "month", "quarter", "year", "all"])
    include_sentiment: bool = Field(True, description="Include sentiment analysis")
    include_trends: bool = Field(True, description="Include rating trends over time")
    include_keywords: bool = Field(True, description="Include keyword extraction")


class CompetitorRequest(BaseModel):
    """Request model for competitor analysis."""
    latitude: float = Field(..., ge=-90, le=90, description="Center latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Center longitude")
    category: str = Field(..., description="Business category", examples=["restaurants", "coffee shops", "hotels"])
    radius_meters: int = Field(2000, ge=500, le=20000, description="Search radius")
    max_competitors: int = Field(10, ge=1, le=30, description="Maximum competitors to analyze")


class MonitorRequest(BaseModel):
    """Request model for place monitoring."""
    place_id: Optional[str] = Field(None, description="Place ID to monitor")
    url: Optional[str] = Field(None, description="Google Maps URL to monitor")
    webhook_url: Optional[str] = Field(None, description="Webhook URL for change notifications")
    check_interval_hours: int = Field(24, ge=1, le=168, description="Check interval in hours")
    track_fields: List[str] = Field(
        ["rating", "review_count", "hours"],
        description="Fields to track for changes"
    )


class WebhookRequest(BaseModel):
    """Request model for webhook registration."""
    url: str = Field(..., description="Webhook URL to receive notifications")
    events: List[str] = Field(
        ["job.completed", "job.failed"],
        description="Events to subscribe to",
        examples=[["job.completed", "job.failed", "monitor.changed"]]
    )
    secret: Optional[str] = Field(None, description="Secret for signing webhook payloads")


class DirectionsRequest(BaseModel):
    """Request model for directions."""
    origin_lat: float = Field(..., ge=-90, le=90, description="Origin latitude")
    origin_lng: float = Field(..., ge=-180, le=180, description="Origin longitude")
    destination_lat: float = Field(..., ge=-90, le=90, description="Destination latitude")
    destination_lng: float = Field(..., ge=-180, le=180, description="Destination longitude")
    mode: str = Field("driving", description="Travel mode", examples=["driving", "walking", "transit", "bicycling"])
    alternatives: bool = Field(False, description="Return alternative routes")
    avoid: Optional[List[str]] = Field(None, description="Features to avoid", examples=[["tolls", "highways", "ferries"]])


class GeocodeRequest(BaseModel):
    """Request model for batch geocoding."""
    addresses: List[str] = Field(..., min_items=1, max_items=100, description="List of addresses to geocode")


class MenuExtractionRequest(BaseModel):
    """Request model for menu extraction."""
    include_prices: bool = Field(True, description="Include prices in extraction")
    include_descriptions: bool = Field(True, description="Include item descriptions")
    categorize: bool = Field(True, description="Categorize menu items")


class AutocompleteRequest(BaseModel):
    """Request model for autocomplete."""
    input: str = Field(..., min_length=2, max_length=200, description="Search input for autocomplete")
    types: Optional[str] = Field(None, description="Place types filter", examples=["establishment", "geocode", "address"])
    latitude: Optional[float] = Field(None, ge=-90, le=90, description="Bias latitude")
    longitude: Optional[float] = Field(None, ge=-180, le=180, description="Bias longitude")
    radius_meters: Optional[int] = Field(None, ge=1, le=50000, description="Bias radius")


class ExportFormat(str, Enum):
    """Supported export formats."""
    JSON = "json"
    CSV = "csv"
    EXCEL = "xlsx"
    JSON_LINES = "jsonl"


# ============================================================================
# Response Models for Extended Features
# ============================================================================

class ReviewItem(BaseModel):
    """Model for a single review."""
    author_name: str = Field(..., description="Reviewer name")
    author_url: Optional[str] = Field(None, description="Link to reviewer profile")
    rating: int = Field(..., ge=1, le=5, description="Star rating")
    text: str = Field(..., description="Review text")
    time: str = Field(..., description="Review timestamp")
    relative_time: Optional[str] = Field(None, description="Relative time (e.g., '3 days ago')")
    language: Optional[str] = Field(None, description="Review language")
    owner_response: Optional[Dict[str, str]] = Field(None, description="Business owner response")


class PhotoItem(BaseModel):
    """Model for a photo."""
    url: str = Field(..., description="Photo URL")
    width: Optional[int] = Field(None, description="Image width")
    height: Optional[int] = Field(None, description="Image height")
    contributor: Optional[str] = Field(None, description="Photo contributor")
    category: Optional[str] = Field(None, description="Photo category")


class QAItem(BaseModel):
    """Model for a Q&A pair."""
    question: str = Field(..., description="Question text")
    question_author: Optional[str] = Field(None, description="Question author")
    question_time: Optional[str] = Field(None, description="Question timestamp")
    answers: Optional[List[Dict[str, Any]]] = Field(None, description="List of answers")
    answer_count: int = Field(0, description="Number of answers")


class AutocompleteResult(BaseModel):
    """Model for autocomplete result."""
    description: str = Field(..., description="Full place description")
    place_id: Optional[str] = Field(None, description="Place ID")
    main_text: str = Field(..., description="Main text (place name)")
    secondary_text: Optional[str] = Field(None, description="Secondary text (location)")
    types: Optional[List[str]] = Field(None, description="Place types")


class DirectionsStep(BaseModel):
    """Model for a directions step."""
    instruction: str = Field(..., description="Navigation instruction")
    distance: str = Field(..., description="Distance for this step")
    duration: str = Field(..., description="Duration for this step")
    travel_mode: str = Field(..., description="Travel mode")


class DirectionsRoute(BaseModel):
    """Model for a directions route."""
    summary: str = Field(..., description="Route summary")
    distance: str = Field(..., description="Total distance")
    duration: str = Field(..., description="Total duration")
    steps: List[DirectionsStep] = Field(..., description="Navigation steps")
    polyline: Optional[str] = Field(None, description="Encoded polyline")


class GeocodeResult(BaseModel):
    """Model for a geocode result."""
    address: str = Field(..., description="Input address")
    latitude: Optional[float] = Field(None, description="Result latitude")
    longitude: Optional[float] = Field(None, description="Result longitude")
    formatted_address: Optional[str] = Field(None, description="Formatted address")
    place_id: Optional[str] = Field(None, description="Place ID")
    success: bool = Field(..., description="Whether geocoding succeeded")
    error: Optional[str] = Field(None, description="Error message if failed")


class MenuItem(BaseModel):
    """Model for a menu item."""
    name: str = Field(..., description="Item name")
    description: Optional[str] = Field(None, description="Item description")
    price: Optional[str] = Field(None, description="Item price")
    category: Optional[str] = Field(None, description="Menu category")
    dietary_info: Optional[List[str]] = Field(None, description="Dietary information")


class CompetitorResult(BaseModel):
    """Model for a competitor in analysis."""
    name: str = Field(..., description="Business name")
    rating: Optional[float] = Field(None, description="Average rating")
    review_count: Optional[int] = Field(None, description="Total reviews")
    price_level: Optional[str] = Field(None, description="Price level")
    distance_meters: Optional[int] = Field(None, description="Distance from center")
    strengths: Optional[List[str]] = Field(None, description="Identified strengths")
    weaknesses: Optional[List[str]] = Field(None, description="Identified weaknesses")


class MonitorStatus(BaseModel):
    """Model for monitor status."""
    monitor_id: str = Field(..., description="Monitor ID")
    place_id: str = Field(..., description="Monitored place ID")
    status: str = Field(..., description="Monitor status", examples=["active", "paused", "deleted"])
    last_check: Optional[str] = Field(None, description="Last check timestamp")
    next_check: Optional[str] = Field(None, description="Next scheduled check")
    changes_detected: int = Field(0, description="Number of changes detected")


class WebhookStatus(BaseModel):
    """Model for webhook status."""
    webhook_id: str = Field(..., description="Webhook ID")
    url: str = Field(..., description="Webhook URL")
    events: List[str] = Field(..., description="Subscribed events")
    status: str = Field(..., description="Webhook status")
    last_triggered: Optional[str] = Field(None, description="Last trigger timestamp")
    success_count: int = Field(0, description="Successful deliveries")
    failure_count: int = Field(0, description="Failed deliveries")


# ============================================================================
# Health and Status Endpoints
# ============================================================================

@google_maps_router.get(
    "/health",
    summary="Check Google Maps scraper health",
    response_description="Health status of the Google Maps scraper service"
)
async def check_health():
    """
    Check if the Google Maps scraper service is healthy and responding.

    Uses native Playwright browser automation for scraping.
    Returns the health status, mode (native-playwright), and any error information.
    """
    health = await google_maps_service.health_check()
    return {
        "service": "google-maps-scraper",
        "healthy": health.get("healthy", False),
        "timestamp": datetime.now().isoformat(),
        "details": health
    }


# ============================================================================
# Search Endpoints
# ============================================================================

@google_maps_router.post(
    "/search",
    summary="Search Google Maps places",
    response_description="Search results with place details",
    responses={
        200: {"description": "Search results"},
        400: {"description": "Invalid parameters"},
        401: {"description": "Invalid API key"},
        503: {"description": "Google Maps scraper unavailable"}
    }
)
async def search_places(
    request: SearchRequest,
    wait_for_results: bool = Query(
        True,
        description="Wait for results (True) or return job ID immediately (False)"
    ),
    timeout: int = Query(
        300,
        ge=30,
        le=600,
        description="Maximum seconds to wait for results (if wait_for_results=True)"
    ),
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit)
):
    """
    Search for places on Google Maps.

    **Features:**
    - Full-text search across Google Maps
    - Up to 100 results per search
    - Comprehensive place details extraction
    - Coordinate-based search centering

    **Data Extracted:**
    - **Basic Info:** Name, address, phone, website, category
    - **Location:** Coordinates, Plus Code, Google Maps URL
    - **Reviews:** Rating, count, star breakdown, topics/keywords, sample quotes
    - **Service Options:** Dine-in, Drive-through, Delivery, Takeout, Curbside pickup
    - **Hours:** Operating hours by day, open/closed status
    - **Popular Times:** Hourly busy percentages (when available)
    - **Links:** Menu, online ordering, reservations
    - **Related:** "People also search for" suggestions
    - **Contact:** Emails and social media (with email_extraction=true)

    **Usage Examples:**
    - `{"query": "restaurants in New York"}` - Basic search
    - `{"query": "coffee near me", "geo_coordinates": "40.7128,-74.0060"}` - Location-based
    - `{"query": "hotels in Paris", "email_extraction": true}` - With email extraction
    - `{"query": "Starbucks Portland Oregon", "max_results": 5}` - Specific business search
    """
    logger.info(f"Google Maps search: {request.query}")

    # Check service health first
    health = await google_maps_service.health_check()
    if not health.get("healthy"):
        raise HTTPException(
            status_code=503,
            detail="Google Maps scraper service is unavailable"
        )

    try:
        if wait_for_results:
            # Synchronous search - wait for results
            result = await google_maps_service.search_and_wait(
                query=request.query,
                language=request.language,
                max_results=request.max_results,
                depth=request.depth,
                email_extraction=request.email_extraction,
                zoom=request.zoom,
                geo_coordinates=request.geo_coordinates,
                timeout=timeout
            )

            if result.get("error"):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("message", "Search failed")
                )

            # Process the results
            raw_places = result.get("results") or result.get("data") or result.get("places") or []
            if isinstance(raw_places, list):
                places = google_maps_service.process_place_data(raw_places)
            else:
                places = []

            return {
                "success": True,
                "query": request.query,
                "total_results": len(places),
                "places": places,
                "job_id": result.get("job_id"),
                "timestamp": datetime.now().isoformat()
            }
        else:
            # Async search - return job ID immediately
            job_result = await google_maps_service.create_search_job(
                query=request.query,
                language=request.language,
                max_results=request.max_results,
                depth=request.depth,
                email_extraction=request.email_extraction,
                zoom=request.zoom,
                geo_coordinates=request.geo_coordinates
            )

            if job_result.get("error"):
                raise HTTPException(
                    status_code=500,
                    detail=job_result.get("message", "Failed to create search job")
                )

            return {
                "success": True,
                "job_id": job_result.get("job_id") or job_result.get("id"),
                "status": "pending",
                "message": "Search job created. Use /jobs/{job_id} to check status.",
                "estimated_time": f"~{request.max_results * 2} seconds",
                "timestamp": datetime.now().isoformat()
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@google_maps_router.get(
    "/search",
    summary="Search Google Maps places (GET)",
    response_description="Search results with place details"
)
async def search_places_get(
    query: str = Query(
        ...,
        min_length=3,
        max_length=500,
        description="Search query",
        examples=["restaurants in New York"]
    ),
    language: str = Query("en", description="Language code"),
    max_results: int = Query(20, ge=1, le=100, description="Maximum results"),
    depth: int = Query(1, ge=1, le=3, description="Crawl depth"),
    email_extraction: bool = Query(False, description="Extract emails"),
    zoom: int = Query(15, ge=1, le=21, description="Map zoom level"),
    geo_coordinates: Optional[str] = Query(None, description="Search center (lat,lng)"),
    wait_for_results: bool = Query(True, description="Wait for results"),
    timeout: int = Query(300, ge=30, le=600, description="Timeout in seconds"),
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit)
):
    """
    Search for places on Google Maps (GET version).

    Same functionality as POST /search but using query parameters.
    Returns comprehensive place data including service options, review topics,
    operating hours, and related places.
    """
    request = SearchRequest(
        query=query,
        language=language,
        max_results=max_results,
        depth=depth,
        email_extraction=email_extraction,
        zoom=zoom,
        geo_coordinates=geo_coordinates
    )
    return await search_places(
        request=request,
        wait_for_results=wait_for_results,
        timeout=timeout,
        api_key=api_key,
        rate_limit_check=rate_limit_check
    )


# ============================================================================
# Job Management Endpoints
# ============================================================================

@google_maps_router.get(
    "/jobs",
    summary="List all scraping jobs",
    response_description="List of jobs with their status"
)
async def list_jobs(
    status: Optional[str] = Query(
        None,
        description="Filter by status (pending, running, completed, failed)"
    ),
    limit: int = Query(50, ge=1, le=100, description="Maximum jobs to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    api_key: str = Depends(get_api_key)
):
    """
    List all scraping jobs with optional status filtering.

    Use this to monitor long-running searches or retrieve past results.
    """
    result = await google_maps_service.list_jobs(
        status=status,
        limit=limit,
        offset=offset
    )

    # gosom returns a list on success, dict on error
    if isinstance(result, dict) and result.get("error"):
        raise HTTPException(
            status_code=500,
            detail=result.get("message", "Failed to list jobs")
        )

    # If result is a list, use it directly as jobs
    jobs = result if isinstance(result, list) else result.get("jobs", [])

    return {
        "success": True,
        "jobs": jobs,
        "total": len(jobs),
        "limit": limit,
        "offset": offset,
        "timestamp": datetime.now().isoformat()
    }


@google_maps_router.get(
    "/jobs/{job_id}",
    summary="Get job status",
    response_description="Job status and progress information"
)
async def get_job_status(
    job_id: str = Path(..., description="Job ID to check"),
    api_key: str = Depends(get_api_key)
):
    """
    Get the status of a specific scraping job.

    Returns progress information and completion status.
    """
    result = await google_maps_service.get_job_status(job_id)

    if result.get("error"):
        if result.get("status_code") == 404:
            raise HTTPException(status_code=404, detail="Job not found")
        raise HTTPException(
            status_code=500,
            detail=result.get("message", "Failed to get job status")
        )

    return {
        "success": True,
        "job_id": job_id,
        "status": result.get("status"),
        "progress": result.get("progress"),
        "details": result,
        "timestamp": datetime.now().isoformat()
    }


@google_maps_router.get(
    "/jobs/{job_id}/results",
    summary="Get job results",
    response_description="Search results from completed job"
)
async def get_job_results(
    job_id: str = Path(..., description="Job ID to get results for"),
    format: str = Query("json", description="Output format (json, csv)"),
    api_key: str = Depends(get_api_key)
):
    """
    Get the results of a completed scraping job.

    Returns comprehensive place data including:
    - Basic info (name, address, phone, website)
    - Reviews and ratings with star breakdown
    - Service options (dine-in, drive-through, delivery)
    - Review topics and keywords with mention counts
    - Operating hours and open/closed status
    - Menu, order, and reservation links
    - Related places ("People also search for")
    """
    # First check job status
    status_result = await google_maps_service.get_job_status(job_id)

    if status_result.get("error"):
        if status_result.get("status_code") == 404:
            raise HTTPException(status_code=404, detail="Job not found")
        raise HTTPException(
            status_code=500,
            detail=status_result.get("message", "Failed to get job status")
        )

    job_status = status_result.get("status", "").lower()

    if job_status == "pending" or job_status == "running":
        return {
            "success": False,
            "job_id": job_id,
            "status": job_status,
            "message": "Job is still running. Please check back later.",
            "progress": status_result.get("progress"),
            "timestamp": datetime.now().isoformat()
        }

    if job_status == "failed":
        raise HTTPException(
            status_code=500,
            detail=f"Job failed: {status_result.get('error', 'Unknown error')}"
        )

    # Get results
    result = await google_maps_service.get_job_results(job_id, format=format)

    if result.get("error"):
        raise HTTPException(
            status_code=500,
            detail=result.get("message", "Failed to get job results")
        )

    if format == "csv":
        return {
            "success": True,
            "job_id": job_id,
            "format": "csv",
            "data": result.get("data"),
            "timestamp": datetime.now().isoformat()
        }

    # Process JSON results
    raw_places = result.get("results") or result.get("data") or result.get("places") or []
    if isinstance(raw_places, list):
        places = google_maps_service.process_place_data(raw_places)
    else:
        places = []

    return {
        "success": True,
        "job_id": job_id,
        "status": "completed",
        "total_results": len(places),
        "places": places,
        "timestamp": datetime.now().isoformat()
    }


@google_maps_router.delete(
    "/jobs/{job_id}",
    summary="Delete a job",
    response_description="Deletion confirmation"
)
async def delete_job(
    job_id: str = Path(..., description="Job ID to delete"),
    api_key: str = Depends(get_api_key)
):
    """
    Delete a job and its results.

    Use this to clean up completed or failed jobs.
    """
    result = await google_maps_service.delete_job(job_id)

    if result.get("error"):
        if result.get("status_code") == 404:
            raise HTTPException(status_code=404, detail="Job not found")
        raise HTTPException(
            status_code=500,
            detail=result.get("message", "Failed to delete job")
        )

    return {
        "success": True,
        "job_id": job_id,
        "message": "Job deleted successfully",
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# Place Lookup Endpoints
# ============================================================================

@google_maps_router.get(
    "/place/{place_id}",
    summary="Get place details by ID",
    response_description="Comprehensive place details"
)
async def get_place_by_id(
    place_id: str = Path(..., description="Google Place ID (CID) or URL-encoded place identifier"),
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit)
):
    """
    Get detailed information for a specific place by its ID.

    **Supported ID Formats:**
    - CID: `0x89c259af18b60947:0x8c5e3c1d36e36e0a`
    - ChIJ format: `ChIJN1t_tDeuEmsRUsoyG83frY4`

    Returns comprehensive place data including reviews, hours, service options, and more.
    """
    logger.info(f"Place lookup by ID: {place_id}")

    try:
        result = await google_maps_service.get_place_by_id(place_id)

        if result.get("error"):
            raise HTTPException(
                status_code=result.get("status_code", 500),
                detail=result.get("message", "Failed to get place details")
            )

        return {
            "success": True,
            "place_id": place_id,
            "place": result.get("place"),
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Place lookup error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@google_maps_router.post(
    "/place/lookup",
    summary="Lookup place by URL or ID",
    response_description="Place details"
)
async def lookup_place(
    request: PlaceLookupRequest,
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit)
):
    """
    Look up a place by Google Maps URL or Place ID.

    **Examples:**
    - By URL: `{"url": "https://www.google.com/maps/place/..."}`
    - By ID: `{"place_id": "0x89c259af18b60947:0x8c5e3c1d36e36e0a"}`

    Returns comprehensive place details.
    """
    if not request.url and not request.place_id:
        raise HTTPException(
            status_code=400,
            detail="Either 'url' or 'place_id' must be provided"
        )

    try:
        result = await google_maps_service.lookup_place(
            url=request.url,
            place_id=request.place_id
        )

        if result.get("error"):
            raise HTTPException(
                status_code=result.get("status_code", 500),
                detail=result.get("message", "Failed to lookup place")
            )

        return {
            "success": True,
            "place": result.get("place"),
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Place lookup error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Nearby Search Endpoints
# ============================================================================

@google_maps_router.post(
    "/nearby",
    summary="Search nearby places",
    response_description="Places within radius"
)
async def nearby_search(
    request: NearbySearchRequest,
    wait_for_results: bool = Query(True, description="Wait for results"),
    timeout: int = Query(300, ge=30, le=600, description="Timeout in seconds"),
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit)
):
    """
    Search for places near a specific location.

    **Features:**
    - Coordinate-based search center
    - Configurable search radius (100m - 50km)
    - Optional category/query filter
    - Full place details for each result

    **Example:**
    ```json
    {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "radius_meters": 1000,
        "query": "coffee shops"
    }
    ```
    """
    logger.info(f"Nearby search at {request.latitude},{request.longitude} radius={request.radius_meters}m")

    try:
        result = await google_maps_service.nearby_search(
            latitude=request.latitude,
            longitude=request.longitude,
            radius_meters=request.radius_meters,
            query=request.query,
            language=request.language,
            max_results=request.max_results,
            timeout=timeout if wait_for_results else None
        )

        if result.get("error"):
            raise HTTPException(
                status_code=500,
                detail=result.get("message", "Nearby search failed")
            )

        places = result.get("places", [])
        if isinstance(places, list):
            places = google_maps_service.process_place_data(places)

        return {
            "success": True,
            "center": {
                "latitude": request.latitude,
                "longitude": request.longitude
            },
            "radius_meters": request.radius_meters,
            "query": request.query,
            "total_results": len(places),
            "places": places,
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Nearby search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@google_maps_router.get(
    "/nearby",
    summary="Search nearby places (GET)",
    response_description="Places within radius"
)
async def nearby_search_get(
    latitude: float = Query(..., ge=-90, le=90, description="Center latitude"),
    longitude: float = Query(..., ge=-180, le=180, description="Center longitude"),
    radius_meters: int = Query(1000, ge=100, le=50000, description="Search radius"),
    query: Optional[str] = Query(None, description="Filter query"),
    language: str = Query("en", description="Language code"),
    max_results: int = Query(20, ge=1, le=100, description="Maximum results"),
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit)
):
    """
    Search for places near a location (GET version).

    Same as POST /nearby but using query parameters.
    """
    request = NearbySearchRequest(
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius_meters,
        query=query,
        language=language,
        max_results=max_results
    )
    return await nearby_search(
        request=request,
        wait_for_results=True,
        timeout=300,
        api_key=api_key,
        rate_limit_check=rate_limit_check
    )


# ============================================================================
# Advanced Geo-Targeting Endpoints
# ============================================================================

class GridSearchRequest(BaseModel):
    """Request model for grid-based search."""
    query: str = Field(
        ...,
        description="Search query (e.g., 'restaurants')",
        min_length=1,
        max_length=500
    )
    center_lat: float = Field(
        ...,
        ge=-90, le=90,
        description="Center latitude"
    )
    center_lng: float = Field(
        ...,
        ge=-180, le=180,
        description="Center longitude"
    )
    radius_km: float = Field(
        default=5.0,
        ge=0.1, le=50,
        description="Search radius in kilometers"
    )
    grid_size: int = Field(
        default=5,
        ge=3, le=11,
        description="Grid dimension (5 = 5x5 = 25 search points)"
    )
    max_results_per_point: int = Field(
        default=10,
        ge=1, le=20,
        description="Maximum results per grid point"
    )
    language: str = Field(
        default="en",
        description="Language code"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "restaurants",
                "center_lat": 45.3807,
                "center_lng": -122.5940,
                "radius_km": 2.0,
                "grid_size": 5,
                "max_results_per_point": 10,
                "language": "en"
            }
        }


class BoundingBoxRequest(BaseModel):
    """Request model for bounding box search."""
    query: str = Field(..., description="Search query", min_length=1, max_length=500)
    north_lat: float = Field(..., ge=-90, le=90, description="Top boundary (max latitude)")
    south_lat: float = Field(..., ge=-90, le=90, description="Bottom boundary (min latitude)")
    east_lng: float = Field(..., ge=-180, le=180, description="Right boundary (max longitude)")
    west_lng: float = Field(..., ge=-180, le=180, description="Left boundary (min longitude)")
    grid_density: int = Field(default=5, ge=3, le=11, description="Grid points per side")
    max_results_per_point: int = Field(default=10, ge=1, le=20, description="Max results per point")
    language: str = Field(default="en", description="Language code")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "coffee shops",
                "north_lat": 45.42,
                "south_lat": 45.35,
                "east_lng": -122.55,
                "west_lng": -122.65,
                "grid_density": 5,
                "max_results_per_point": 10
            }
        }


class LocationSearchRequest(BaseModel):
    """Request model for location-based search."""
    query: str = Field(..., description="Search query", min_length=1, max_length=500)
    location: str = Field(
        ...,
        description="Location name (city, address, or ZIP code)",
        examples=["Portland, OR", "97027", "123 Main St, Seattle, WA"]
    )
    radius_km: float = Field(default=5.0, ge=0.1, le=50, description="Search radius in km")
    grid_size: int = Field(default=5, ge=3, le=11, description="Grid dimension")
    max_results_per_point: int = Field(default=10, ge=1, le=20, description="Max results per point")
    language: str = Field(default="en", description="Language code")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "restaurants",
                "location": "Gladstone, OR",
                "radius_km": 2.0,
                "grid_size": 5
            }
        }


@google_maps_router.post(
    "/grid-search",
    summary="Grid-based search for comprehensive area coverage",
    response_description="Aggregated results from multiple grid points"
)
async def grid_search(
    request: GridSearchRequest,
    timeout: int = Query(600, ge=60, le=1800, description="Timeout in seconds"),
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit)
):
    """
    Search across a grid of coordinates for comprehensive area coverage.

    Like DataForSEO's calculate_rectangles, this searches multiple viewpoints
    to find ALL businesses in an area, not just those visible from one map view.

    **Grid Size Examples:**
    - 3x3 = 9 search points (fast, basic coverage)
    - 5x5 = 25 search points (balanced, good coverage)
    - 7x7 = 49 search points (thorough coverage)
    - 11x11 = 121 search points (maximum coverage, slower)

    **Use Cases:**
    - Comprehensive business discovery
    - Local SEO rank tracking across an area
    - Market analysis and competitor mapping
    - Finding businesses not visible from a single viewpoint

    **Returns:**
    - Deduplicated places from all grid points
    - Grid metadata showing results count per point
    - grid_positions for each place showing which grid points found it
    """
    try:
        result = await google_maps_service.grid_search(
            query=request.query,
            center_lat=request.center_lat,
            center_lng=request.center_lng,
            radius_km=request.radius_km,
            grid_size=request.grid_size,
            max_results_per_point=request.max_results_per_point,
            language=request.language,
            timeout=timeout
        )

        if result.get("error"):
            raise HTTPException(status_code=500, detail=result.get("message"))

        result["timestamp"] = datetime.now().isoformat()
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Grid search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@google_maps_router.post(
    "/bounding-box-search",
    summary="Search within a bounding box",
    response_description="Places within the specified rectangular area"
)
async def bounding_box_search(
    request: BoundingBoxRequest,
    timeout: int = Query(600, ge=60, le=1800, description="Timeout in seconds"),
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit)
):
    """
    Search within a rectangular bounding box defined by corner coordinates.

    Internally creates a grid based on the bounding box dimensions and
    searches each grid point for comprehensive coverage.

    **Use Cases:**
    - Search within a specific neighborhood or district
    - Custom area mapping
    - GIS integration workflows

    **Example bounding box for Gladstone, OR:**
    - north_lat: 45.42, south_lat: 45.35
    - east_lng: -122.55, west_lng: -122.65
    """
    try:
        result = await google_maps_service.bounding_box_search(
            query=request.query,
            north_lat=request.north_lat,
            south_lat=request.south_lat,
            east_lng=request.east_lng,
            west_lng=request.west_lng,
            grid_density=request.grid_density,
            max_results_per_point=request.max_results_per_point,
            language=request.language,
            timeout=timeout
        )

        if result.get("error"):
            raise HTTPException(status_code=500, detail=result.get("message"))

        result["bounding_box"] = {
            "north_lat": request.north_lat,
            "south_lat": request.south_lat,
            "east_lng": request.east_lng,
            "west_lng": request.west_lng
        }
        result["timestamp"] = datetime.now().isoformat()
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bounding box search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@google_maps_router.post(
    "/location-search",
    summary="Search by location name",
    response_description="Grid search results with resolved coordinates"
)
async def location_search(
    request: LocationSearchRequest,
    timeout: int = Query(600, ge=60, le=1800, description="Timeout in seconds"),
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit)
):
    """
    Search using a location name instead of coordinates.

    Resolves location names (city, address, ZIP code) to coordinates
    using geocoding, then performs a grid search for comprehensive coverage.

    **Supported Location Formats:**
    - City, State: "Portland, OR", "Seattle, WA"
    - ZIP Code: "97027", "98101"
    - Address: "123 Main St, Portland, OR"
    - Landmark: "Pioneer Courthouse Square"

    **Returns:**
    - resolved_location: Shows what coordinates the location resolved to
    - All grid search results with deduplicated places
    """
    try:
        result = await google_maps_service.location_search(
            query=request.query,
            location=request.location,
            radius_km=request.radius_km,
            grid_size=request.grid_size,
            max_results_per_point=request.max_results_per_point,
            language=request.language,
            timeout=timeout
        )

        if result.get("error"):
            raise HTTPException(status_code=500, detail=result.get("message"))

        result["timestamp"] = datetime.now().isoformat()
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Location search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@google_maps_router.get(
    "/grid-search",
    summary="Grid-based search (GET)",
    response_description="Aggregated results from grid search"
)
async def grid_search_get(
    query: str = Query(..., min_length=1, max_length=500, description="Search query"),
    center_lat: float = Query(..., ge=-90, le=90, description="Center latitude"),
    center_lng: float = Query(..., ge=-180, le=180, description="Center longitude"),
    radius_km: float = Query(5.0, ge=0.1, le=50, description="Radius in km"),
    grid_size: int = Query(5, ge=3, le=11, description="Grid dimension"),
    max_results_per_point: int = Query(10, ge=1, le=20, description="Results per point"),
    language: str = Query("en", description="Language code"),
    timeout: int = Query(600, ge=60, le=1800, description="Timeout"),
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit)
):
    """GET version of grid search with query parameters."""
    request = GridSearchRequest(
        query=query,
        center_lat=center_lat,
        center_lng=center_lng,
        radius_km=radius_km,
        grid_size=grid_size,
        max_results_per_point=max_results_per_point,
        language=language
    )
    return await grid_search(
        request=request,
        timeout=timeout,
        api_key=api_key,
        rate_limit_check=rate_limit_check
    )


@google_maps_router.get(
    "/location-search",
    summary="Search by location name (GET)",
    response_description="Grid search results with resolved coordinates"
)
async def location_search_get(
    query: str = Query(..., min_length=1, max_length=500, description="Search query"),
    location: str = Query(..., description="Location name (city, ZIP, address)"),
    radius_km: float = Query(5.0, ge=0.1, le=50, description="Radius in km"),
    grid_size: int = Query(5, ge=3, le=11, description="Grid dimension"),
    max_results_per_point: int = Query(10, ge=1, le=20, description="Results per point"),
    language: str = Query("en", description="Language code"),
    timeout: int = Query(600, ge=60, le=1800, description="Timeout"),
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit)
):
    """GET version of location search with query parameters."""
    request = LocationSearchRequest(
        query=query,
        location=location,
        radius_km=radius_km,
        grid_size=grid_size,
        max_results_per_point=max_results_per_point,
        language=language
    )
    return await location_search(
        request=request,
        timeout=timeout,
        api_key=api_key,
        rate_limit_check=rate_limit_check
    )


# ============================================================================
# Reviews Endpoints
# ============================================================================

@google_maps_router.get(
    "/place/{place_id}/reviews",
    summary="Get place reviews",
    response_description="Paginated reviews with owner responses"
)
async def get_place_reviews(
    place_id: str = Path(..., description="Place ID"),
    sort_by: str = Query("most_relevant", description="Sort order"),
    limit: int = Query(50, ge=1, le=200, description="Number of reviews"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    min_rating: Optional[int] = Query(None, ge=1, le=5, description="Minimum rating filter"),
    include_owner_responses: bool = Query(True, description="Include owner responses"),
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit)
):
    """
    Get reviews for a specific place.

    **Sort Options:**
    - `most_relevant` - Google's relevance ranking (default)
    - `newest` - Most recent first
    - `highest_rating` - 5 stars first
    - `lowest_rating` - 1 star first

    **Filtering:**
    - Use `min_rating` to filter by minimum star rating
    - Use `include_owner_responses` to include business replies

    Returns paginated reviews with full text, ratings, timestamps, and optional owner responses.
    """
    logger.info(f"Get reviews for place: {place_id}")

    try:
        result = await google_maps_service.get_place_reviews(
            place_id=place_id,
            sort_by=sort_by,
            limit=limit,
            offset=offset,
            min_rating=min_rating,
            include_owner_responses=include_owner_responses
        )

        if result.get("error"):
            raise HTTPException(
                status_code=result.get("status_code", 500),
                detail=result.get("message", "Failed to get reviews")
            )

        return {
            "success": True,
            "place_id": place_id,
            "total_reviews": result.get("total_reviews", 0),
            "average_rating": result.get("average_rating"),
            "reviews": result.get("reviews", []),
            "pagination": {
                "limit": limit,
                "offset": offset,
                "has_more": result.get("has_more", False)
            },
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get reviews error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Photos Endpoints
# ============================================================================

@google_maps_router.get(
    "/place/{place_id}/photos",
    summary="Get place photos",
    response_description="Photo URLs with metadata"
)
async def get_place_photos(
    place_id: str = Path(..., description="Place ID"),
    max_photos: int = Query(20, ge=1, le=100, description="Maximum photos"),
    size: str = Query("large", description="Photo size (thumbnail, medium, large, original)"),
    category: Optional[str] = Query(None, description="Photo category filter"),
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit)
):
    """
    Get photos for a specific place.

    **Size Options:**
    - `thumbnail` - 100x100
    - `medium` - 400x300
    - `large` - 800x600 (default)
    - `original` - Full resolution

    **Category Filter:**
    - `all` - All photos (default)
    - `food` - Food/menu photos
    - `interior` - Inside the business
    - `exterior` - Outside/storefront
    - `menu` - Menu photos

    Returns photo URLs with contributor information when available.
    """
    logger.info(f"Get photos for place: {place_id}")

    try:
        result = await google_maps_service.get_place_photos(
            place_id=place_id,
            max_photos=max_photos,
            size=size,
            category=category
        )

        if result.get("error"):
            raise HTTPException(
                status_code=result.get("status_code", 500),
                detail=result.get("message", "Failed to get photos")
            )

        return {
            "success": True,
            "place_id": place_id,
            "total_photos": result.get("total_photos", 0),
            "photos": result.get("photos", []),
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get photos error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Q&A Endpoints
# ============================================================================

@google_maps_router.get(
    "/place/{place_id}/qa",
    summary="Get place Q&A",
    response_description="Questions and answers"
)
async def get_place_qa(
    place_id: str = Path(..., description="Place ID"),
    limit: int = Query(20, ge=1, le=100, description="Maximum Q&A pairs"),
    include_answers: bool = Query(True, description="Include answers"),
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit)
):
    """
    Get Questions & Answers for a specific place.

    Returns the Q&A section from the Google Maps listing including:
    - Questions asked by users
    - Answers from the business owner and community
    - Answer counts and timestamps
    """
    logger.info(f"Get Q&A for place: {place_id}")

    try:
        result = await google_maps_service.get_place_qa(
            place_id=place_id,
            limit=limit,
            include_answers=include_answers
        )

        if result.get("error"):
            raise HTTPException(
                status_code=result.get("status_code", 500),
                detail=result.get("message", "Failed to get Q&A")
            )

        return {
            "success": True,
            "place_id": place_id,
            "total_questions": result.get("total_questions", 0),
            "questions": result.get("questions", []),
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get Q&A error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Autocomplete Endpoint
# ============================================================================

@google_maps_router.get(
    "/autocomplete",
    summary="Place autocomplete",
    response_description="Autocomplete suggestions"
)
async def autocomplete(
    input: str = Query(..., min_length=2, max_length=200, description="Search input"),
    types: Optional[str] = Query(None, description="Place types filter"),
    latitude: Optional[float] = Query(None, ge=-90, le=90, description="Bias latitude"),
    longitude: Optional[float] = Query(None, ge=-180, le=180, description="Bias longitude"),
    radius_meters: Optional[int] = Query(None, ge=1, le=50000, description="Bias radius"),
    language: str = Query("en", description="Language code"),
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit)
):
    """
    Get place autocomplete suggestions.

    **Type Filters:**
    - `establishment` - Businesses
    - `geocode` - Addresses and locations
    - `address` - Street addresses only
    - `(regions)` - Larger areas
    - `(cities)` - Cities only

    **Location Bias:**
    Provide latitude, longitude, and radius to bias results toward a location.

    Returns suggestions with place IDs for further lookup.
    """
    logger.info(f"Autocomplete: {input}")

    try:
        result = await google_maps_service.autocomplete(
            input=input,
            types=types,
            latitude=latitude,
            longitude=longitude,
            radius_meters=radius_meters,
            language=language
        )

        if result.get("error"):
            raise HTTPException(
                status_code=result.get("status_code", 500),
                detail=result.get("message", "Autocomplete failed")
            )

        return {
            "success": True,
            "input": input,
            "predictions": result.get("predictions", []),
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Autocomplete error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Bulk Search Endpoint
# ============================================================================

@google_maps_router.post(
    "/bulk-search",
    summary="Bulk search places",
    response_description="Results for multiple queries"
)
async def bulk_search(
    request: BulkSearchRequest,
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit)
):
    """
    Execute multiple search queries in a single request.

    **Features:**
    - Up to 50 queries per request
    - Parallel execution for faster results
    - Individual error handling per query
    - Combined results in single response

    **Example:**
    ```json
    {
        "queries": [
            "coffee shops in Seattle",
            "restaurants in Portland",
            "hotels in San Francisco"
        ],
        "max_results_per_query": 10
    }
    ```
    """
    logger.info(f"Bulk search: {len(request.queries)} queries")

    try:
        result = await google_maps_service.bulk_search(
            queries=request.queries,
            language=request.language,
            max_results_per_query=request.max_results_per_query
        )

        if result.get("error"):
            raise HTTPException(
                status_code=500,
                detail=result.get("message", "Bulk search failed")
            )

        return {
            "success": True,
            "total_queries": len(request.queries),
            "successful_queries": result.get("successful_queries", 0),
            "failed_queries": result.get("failed_queries", 0),
            "results": result.get("results", []),
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Export Endpoints
# ============================================================================

@google_maps_router.get(
    "/jobs/{job_id}/export",
    summary="Export job results",
    response_description="Results in specified format"
)
async def export_job_results(
    job_id: str = Path(..., description="Job ID"),
    format: ExportFormat = Query(ExportFormat.JSON, description="Export format"),
    api_key: str = Depends(get_api_key)
):
    """
    Export job results in various formats.

    **Supported Formats:**
    - `json` - Standard JSON (default)
    - `csv` - Comma-separated values
    - `xlsx` - Microsoft Excel
    - `jsonl` - JSON Lines (one record per line)

    For CSV and Excel, complex fields (like hours, reviews) are serialized as JSON strings.
    """
    logger.info(f"Export job {job_id} as {format.value}")

    try:
        # Get job results
        result = await google_maps_service.get_job_results(job_id)

        if result.get("error"):
            if result.get("status_code") == 404:
                raise HTTPException(status_code=404, detail="Job not found")
            raise HTTPException(
                status_code=500,
                detail=result.get("message", "Failed to get results")
            )

        raw_places = result.get("results") or result.get("data") or result.get("places") or []
        if isinstance(raw_places, list):
            places = google_maps_service.process_place_data(raw_places)
        else:
            places = []

        if format == ExportFormat.CSV:
            # Generate CSV
            output = io.StringIO()
            if places:
                # Flatten nested fields for CSV
                flat_places = []
                for p in places:
                    flat = {}
                    for k, v in p.items():
                        if isinstance(v, (dict, list)):
                            flat[k] = json.dumps(v) if v else ""
                        else:
                            flat[k] = v if v is not None else ""
                    flat_places.append(flat)

                writer = csv.DictWriter(output, fieldnames=flat_places[0].keys())
                writer.writeheader()
                writer.writerows(flat_places)

            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=results_{job_id}.csv"}
            )

        elif format == ExportFormat.JSON_LINES:
            # Generate JSON Lines
            lines = [json.dumps(p) for p in places]
            content = "\n".join(lines)
            return StreamingResponse(
                iter([content]),
                media_type="application/x-ndjson",
                headers={"Content-Disposition": f"attachment; filename=results_{job_id}.jsonl"}
            )

        elif format == ExportFormat.EXCEL:
            # For Excel, we'll return JSON with a note (full Excel would need openpyxl)
            return {
                "success": True,
                "job_id": job_id,
                "format": "xlsx",
                "message": "Excel export - use CSV format and import to Excel, or integrate openpyxl for native xlsx",
                "data_preview": places[:5],
                "total_records": len(places),
                "timestamp": datetime.now().isoformat()
            }

        else:
            # JSON format
            return {
                "success": True,
                "job_id": job_id,
                "format": "json",
                "total_results": len(places),
                "places": places,
                "timestamp": datetime.now().isoformat()
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Export error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Review Analytics Endpoint
# ============================================================================

@google_maps_router.get(
    "/place/{place_id}/analytics",
    summary="Get review analytics",
    response_description="Review analysis and insights"
)
async def get_review_analytics(
    place_id: str = Path(..., description="Place ID"),
    time_period: str = Query("all", description="Time period"),
    include_sentiment: bool = Query(True, description="Include sentiment analysis"),
    include_trends: bool = Query(True, description="Include rating trends"),
    include_keywords: bool = Query(True, description="Include keyword extraction"),
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit)
):
    """
    Get analytics and insights for a place's reviews.

    **Analysis Includes:**
    - Rating distribution and trends
    - Sentiment analysis (positive/negative/neutral)
    - Keyword extraction and frequency
    - Response rate from owner
    - Peak review times

    **Time Periods:**
    - `week` - Last 7 days
    - `month` - Last 30 days
    - `quarter` - Last 90 days
    - `year` - Last 365 days
    - `all` - All time (default)
    """
    logger.info(f"Get analytics for place: {place_id}")

    try:
        result = await google_maps_service.get_review_analytics(
            place_id=place_id,
            time_period=time_period,
            include_sentiment=include_sentiment,
            include_trends=include_trends,
            include_keywords=include_keywords
        )

        if result.get("error"):
            raise HTTPException(
                status_code=result.get("status_code", 500),
                detail=result.get("message", "Failed to get analytics")
            )

        return {
            "success": True,
            "place_id": place_id,
            "time_period": time_period,
            "analytics": result.get("analytics", {}),
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analytics error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Competitor Analysis Endpoint
# ============================================================================

@google_maps_router.post(
    "/competitors",
    summary="Analyze competitors",
    response_description="Competitor comparison"
)
async def analyze_competitors(
    request: CompetitorRequest,
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit)
):
    """
    Find and analyze competitors in an area.

    **Analysis Includes:**
    - Nearby businesses in same category
    - Rating comparisons
    - Review volume comparison
    - Price level comparison
    - Identified strengths/weaknesses

    **Example:**
    ```json
    {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "category": "coffee shops",
        "radius_meters": 2000,
        "max_competitors": 10
    }
    ```
    """
    logger.info(f"Competitor analysis at {request.latitude},{request.longitude} for {request.category}")

    try:
        result = await google_maps_service.analyze_competitors(
            latitude=request.latitude,
            longitude=request.longitude,
            category=request.category,
            radius_meters=request.radius_meters,
            max_competitors=request.max_competitors
        )

        if result.get("error"):
            raise HTTPException(
                status_code=500,
                detail=result.get("message", "Competitor analysis failed")
            )

        return {
            "success": True,
            "center": {
                "latitude": request.latitude,
                "longitude": request.longitude
            },
            "category": request.category,
            "radius_meters": request.radius_meters,
            "competitors": result.get("competitors", []),
            "summary": result.get("summary", {}),
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Competitor analysis error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Place Monitoring Endpoints
# ============================================================================

@google_maps_router.post(
    "/monitors",
    summary="Create place monitor",
    response_description="Monitor creation status"
)
async def create_monitor(
    request: MonitorRequest,
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit)
):
    """
    Create a monitor to track changes to a place.

    **Trackable Fields:**
    - `rating` - Average rating changes
    - `review_count` - New reviews
    - `hours` - Operating hours changes
    - `phone` - Phone number changes
    - `website` - Website URL changes
    - `status` - Open/closed status

    **Notifications:**
    Provide a `webhook_url` to receive notifications when changes are detected.
    """
    if not request.place_id and not request.url:
        raise HTTPException(
            status_code=400,
            detail="Either 'place_id' or 'url' must be provided"
        )

    logger.info(f"Create monitor for place: {request.place_id or request.url}")

    try:
        result = await google_maps_service.create_monitor(
            place_id=request.place_id,
            url=request.url,
            webhook_url=request.webhook_url,
            check_interval_hours=request.check_interval_hours,
            track_fields=request.track_fields
        )

        if result.get("error"):
            raise HTTPException(
                status_code=500,
                detail=result.get("message", "Failed to create monitor")
            )

        return {
            "success": True,
            "monitor_id": result.get("monitor_id"),
            "place_id": result.get("place_id"),
            "status": "active",
            "check_interval_hours": request.check_interval_hours,
            "track_fields": request.track_fields,
            "next_check": result.get("next_check"),
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create monitor error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@google_maps_router.get(
    "/monitors",
    summary="List monitors",
    response_description="Active monitors"
)
async def list_monitors(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum monitors"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    api_key: str = Depends(get_api_key)
):
    """
    List all place monitors.

    **Status Filters:**
    - `active` - Currently monitoring
    - `paused` - Temporarily paused
    - `deleted` - Marked for deletion
    """
    try:
        result = await google_maps_service.list_monitors(
            status=status,
            limit=limit,
            offset=offset
        )

        if result.get("error"):
            raise HTTPException(
                status_code=500,
                detail=result.get("message", "Failed to list monitors")
            )

        return {
            "success": True,
            "monitors": result.get("monitors", []),
            "total": result.get("total", 0),
            "pagination": {
                "limit": limit,
                "offset": offset
            },
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List monitors error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@google_maps_router.get(
    "/monitors/{monitor_id}",
    summary="Get monitor status",
    response_description="Monitor details and history"
)
async def get_monitor(
    monitor_id: str = Path(..., description="Monitor ID"),
    include_history: bool = Query(True, description="Include change history"),
    api_key: str = Depends(get_api_key)
):
    """
    Get details and change history for a specific monitor.
    """
    try:
        result = await google_maps_service.get_monitor(
            monitor_id=monitor_id,
            include_history=include_history
        )

        if result.get("error"):
            if result.get("status_code") == 404:
                raise HTTPException(status_code=404, detail="Monitor not found")
            raise HTTPException(
                status_code=500,
                detail=result.get("message", "Failed to get monitor")
            )

        return {
            "success": True,
            "monitor": result.get("monitor"),
            "history": result.get("history", []) if include_history else None,
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get monitor error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@google_maps_router.delete(
    "/monitors/{monitor_id}",
    summary="Delete monitor",
    response_description="Deletion confirmation"
)
async def delete_monitor(
    monitor_id: str = Path(..., description="Monitor ID"),
    api_key: str = Depends(get_api_key)
):
    """
    Delete a place monitor.
    """
    try:
        result = await google_maps_service.delete_monitor(monitor_id)

        if result.get("error"):
            if result.get("status_code") == 404:
                raise HTTPException(status_code=404, detail="Monitor not found")
            raise HTTPException(
                status_code=500,
                detail=result.get("message", "Failed to delete monitor")
            )

        return {
            "success": True,
            "monitor_id": monitor_id,
            "message": "Monitor deleted successfully",
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete monitor error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Webhook Endpoints
# ============================================================================

@google_maps_router.post(
    "/webhooks",
    summary="Register webhook",
    response_description="Webhook registration"
)
async def register_webhook(
    request: WebhookRequest,
    api_key: str = Depends(get_api_key)
):
    """
    Register a webhook to receive notifications.

    **Available Events:**
    - `job.completed` - Search job completed
    - `job.failed` - Search job failed
    - `monitor.changed` - Monitored place changed

    **Webhook Payload:**
    ```json
    {
        "event": "job.completed",
        "timestamp": "2024-01-15T10:30:00Z",
        "data": { ... }
    }
    ```
    """
    logger.info(f"Register webhook: {request.url}")

    try:
        result = await google_maps_service.register_webhook(
            url=request.url,
            events=request.events,
            secret=request.secret
        )

        if result.get("error"):
            raise HTTPException(
                status_code=500,
                detail=result.get("message", "Failed to register webhook")
            )

        return {
            "success": True,
            "webhook_id": result.get("webhook_id"),
            "url": request.url,
            "events": request.events,
            "status": "active",
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Register webhook error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@google_maps_router.get(
    "/webhooks",
    summary="List webhooks",
    response_description="Registered webhooks"
)
async def list_webhooks(
    api_key: str = Depends(get_api_key)
):
    """
    List all registered webhooks.
    """
    try:
        result = await google_maps_service.list_webhooks()

        if result.get("error"):
            raise HTTPException(
                status_code=500,
                detail=result.get("message", "Failed to list webhooks")
            )

        return {
            "success": True,
            "webhooks": result.get("webhooks", []),
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List webhooks error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@google_maps_router.delete(
    "/webhooks/{webhook_id}",
    summary="Delete webhook",
    response_description="Deletion confirmation"
)
async def delete_webhook(
    webhook_id: str = Path(..., description="Webhook ID"),
    api_key: str = Depends(get_api_key)
):
    """
    Delete a registered webhook.
    """
    try:
        result = await google_maps_service.delete_webhook(webhook_id)

        if result.get("error"):
            if result.get("status_code") == 404:
                raise HTTPException(status_code=404, detail="Webhook not found")
            raise HTTPException(
                status_code=500,
                detail=result.get("message", "Failed to delete webhook")
            )

        return {
            "success": True,
            "webhook_id": webhook_id,
            "message": "Webhook deleted successfully",
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete webhook error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Directions Endpoint
# ============================================================================

@google_maps_router.post(
    "/directions",
    summary="Get directions",
    response_description="Route information"
)
async def get_directions(
    request: DirectionsRequest,
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit)
):
    """
    Get directions between two locations.

    **Travel Modes:**
    - `driving` - By car (default)
    - `walking` - On foot
    - `transit` - Public transportation
    - `bicycling` - By bicycle

    **Avoid Options:**
    - `tolls` - Avoid toll roads
    - `highways` - Avoid highways
    - `ferries` - Avoid ferries

    Returns route with step-by-step directions, distance, and duration.
    """
    logger.info(f"Get directions: {request.origin_lat},{request.origin_lng} to {request.destination_lat},{request.destination_lng}")

    try:
        result = await google_maps_service.get_directions(
            origin_lat=request.origin_lat,
            origin_lng=request.origin_lng,
            destination_lat=request.destination_lat,
            destination_lng=request.destination_lng,
            mode=request.mode,
            alternatives=request.alternatives,
            avoid=request.avoid
        )

        if result.get("error"):
            raise HTTPException(
                status_code=500,
                detail=result.get("message", "Failed to get directions")
            )

        return {
            "success": True,
            "origin": {
                "latitude": request.origin_lat,
                "longitude": request.origin_lng
            },
            "destination": {
                "latitude": request.destination_lat,
                "longitude": request.destination_lng
            },
            "mode": request.mode,
            "routes": result.get("routes", []),
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Directions error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@google_maps_router.get(
    "/directions",
    summary="Get directions (GET)",
    response_description="Route information"
)
async def get_directions_get(
    origin_lat: float = Query(..., ge=-90, le=90, description="Origin latitude"),
    origin_lng: float = Query(..., ge=-180, le=180, description="Origin longitude"),
    destination_lat: float = Query(..., ge=-90, le=90, description="Destination latitude"),
    destination_lng: float = Query(..., ge=-180, le=180, description="Destination longitude"),
    mode: str = Query("driving", description="Travel mode"),
    alternatives: bool = Query(False, description="Return alternatives"),
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit)
):
    """
    Get directions between two locations (GET version).
    """
    request = DirectionsRequest(
        origin_lat=origin_lat,
        origin_lng=origin_lng,
        destination_lat=destination_lat,
        destination_lng=destination_lng,
        mode=mode,
        alternatives=alternatives
    )
    return await get_directions(request=request, api_key=api_key, rate_limit_check=rate_limit_check)


# ============================================================================
# Street View Endpoint
# ============================================================================

@google_maps_router.get(
    "/place/{place_id}/streetview",
    summary="Get Street View",
    response_description="Street View image URLs"
)
async def get_streetview(
    place_id: str = Path(..., description="Place ID"),
    width: int = Query(640, ge=100, le=2048, description="Image width"),
    height: int = Query(480, ge=100, le=2048, description="Image height"),
    heading: Optional[int] = Query(None, ge=0, le=360, description="Camera heading"),
    pitch: Optional[int] = Query(None, ge=-90, le=90, description="Camera pitch"),
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit)
):
    """
    Get Street View image URLs for a place.

    **Parameters:**
    - `width`, `height` - Image dimensions
    - `heading` - Camera direction (0-360 degrees, 0=North)
    - `pitch` - Up/down angle (-90 to 90 degrees)

    Returns URLs to Street View images from available angles.
    """
    logger.info(f"Get Street View for place: {place_id}")

    try:
        result = await google_maps_service.get_streetview(
            place_id=place_id,
            width=width,
            height=height,
            heading=heading,
            pitch=pitch
        )

        if result.get("error"):
            raise HTTPException(
                status_code=result.get("status_code", 500),
                detail=result.get("message", "Failed to get Street View")
            )

        return {
            "success": True,
            "place_id": place_id,
            "available": result.get("available", False),
            "images": result.get("images", []),
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Street View error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Menu Extraction Endpoint
# ============================================================================

@google_maps_router.get(
    "/place/{place_id}/menu",
    summary="Extract menu",
    response_description="Structured menu data"
)
async def extract_menu(
    place_id: str = Path(..., description="Place ID"),
    include_prices: bool = Query(True, description="Include prices"),
    include_descriptions: bool = Query(True, description="Include descriptions"),
    categorize: bool = Query(True, description="Categorize items"),
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit)
):
    """
    Extract and structure menu information for a restaurant.

    **Extraction Includes:**
    - Menu item names
    - Prices (when available)
    - Descriptions
    - Categories (appetizers, mains, desserts, etc.)
    - Dietary information (vegetarian, gluten-free, etc.)

    Note: Menu availability depends on whether the business has uploaded menu data.
    """
    logger.info(f"Extract menu for place: {place_id}")

    try:
        result = await google_maps_service.extract_menu(
            place_id=place_id,
            include_prices=include_prices,
            include_descriptions=include_descriptions,
            categorize=categorize
        )

        if result.get("error"):
            raise HTTPException(
                status_code=result.get("status_code", 500),
                detail=result.get("message", "Failed to extract menu")
            )

        return {
            "success": True,
            "place_id": place_id,
            "menu_available": result.get("menu_available", False),
            "menu": result.get("menu", []),
            "categories": result.get("categories", []),
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Menu extraction error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Batch Geocoding Endpoint
# ============================================================================

@google_maps_router.post(
    "/geocode",
    summary="Batch geocode addresses",
    response_description="Coordinates for addresses"
)
async def batch_geocode(
    request: GeocodeRequest,
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit)
):
    """
    Convert multiple addresses to coordinates.

    **Features:**
    - Up to 100 addresses per request
    - Returns coordinates and formatted addresses
    - Individual error handling per address
    - Place IDs for further lookups

    **Example:**
    ```json
    {
        "addresses": [
            "1600 Amphitheatre Parkway, Mountain View, CA",
            "350 5th Avenue, New York, NY"
        ]
    }
    ```
    """
    logger.info(f"Batch geocode: {len(request.addresses)} addresses")

    try:
        result = await google_maps_service.batch_geocode(
            addresses=request.addresses
        )

        if result.get("error"):
            raise HTTPException(
                status_code=500,
                detail=result.get("message", "Geocoding failed")
            )

        return {
            "success": True,
            "total_addresses": len(request.addresses),
            "successful": result.get("successful", 0),
            "failed": result.get("failed", 0),
            "results": result.get("results", []),
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Geocode error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@google_maps_router.get(
    "/geocode",
    summary="Geocode address (GET)",
    response_description="Coordinates for address"
)
async def geocode_get(
    address: str = Query(..., min_length=5, max_length=500, description="Address to geocode"),
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit)
):
    """
    Convert a single address to coordinates.
    """
    result = await batch_geocode(
        request=GeocodeRequest(addresses=[address]),
        api_key=api_key,
        rate_limit_check=rate_limit_check
    )

    if result.get("results"):
        return {
            "success": True,
            "address": address,
            "result": result["results"][0],
            "timestamp": datetime.now().isoformat()
        }
    else:
        return {
            "success": False,
            "address": address,
            "error": "Geocoding failed",
            "timestamp": datetime.now().isoformat()
        }


# ============================================================================
# Place Attributes Endpoint
# ============================================================================

@google_maps_router.get(
    "/place/{place_id}/attributes",
    summary="Get place attributes",
    response_description="Detailed place attributes"
)
async def get_place_attributes(
    place_id: str = Path(..., description="Place ID"),
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit)
):
    """
    Get detailed attributes for a place.

    **Attribute Categories:**
    - **Accessibility:** Wheelchair access, elevators, parking
    - **Amenities:** WiFi, restrooms, outdoor seating
    - **Payments:** Accepted payment methods
    - **Service Options:** Dine-in, takeout, delivery, etc.
    - **Highlights:** Featured attributes
    - **Crowd:** Typical crowd information
    - **Planning:** Reservation requirements, wait times
    """
    logger.info(f"Get attributes for place: {place_id}")

    try:
        result = await google_maps_service.get_place_attributes(
            place_id=place_id
        )

        if result.get("error"):
            raise HTTPException(
                status_code=result.get("status_code", 500),
                detail=result.get("message", "Failed to get attributes")
            )

        return {
            "success": True,
            "place_id": place_id,
            "attributes": result.get("attributes", {}),
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get attributes error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Historical Data Endpoint
# ============================================================================

@google_maps_router.get(
    "/place/{place_id}/history",
    summary="Get place history",
    response_description="Historical data for place"
)
async def get_place_history(
    place_id: str = Path(..., description="Place ID"),
    field: Optional[str] = Query(None, description="Specific field to get history for"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit)
):
    """
    Get historical data for a monitored place.

    **Requires:** Active monitor for the place.

    **Trackable Fields:**
    - `rating` - Rating changes over time
    - `review_count` - Review count changes
    - `hours` - Operating hours changes
    - `all` - All tracked fields

    Returns timestamped snapshots of the tracked fields.
    """
    logger.info(f"Get history for place: {place_id}")

    try:
        result = await google_maps_service.get_place_history(
            place_id=place_id,
            field=field,
            start_date=start_date,
            end_date=end_date
        )

        if result.get("error"):
            raise HTTPException(
                status_code=result.get("status_code", 500),
                detail=result.get("message", "Failed to get history")
            )

        return {
            "success": True,
            "place_id": place_id,
            "field": field or "all",
            "history": result.get("history", []),
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get history error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Reservation Availability Endpoint
# ============================================================================

@google_maps_router.get(
    "/place/{place_id}/availability",
    summary="Check reservation availability",
    response_description="Available reservation times"
)
async def check_availability(
    place_id: str = Path(..., description="Place ID"),
    date: str = Query(..., description="Date to check (YYYY-MM-DD)"),
    party_size: int = Query(2, ge=1, le=20, description="Number of guests"),
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit)
):
    """
    Check reservation availability for a restaurant.

    **Note:** Availability data depends on whether the restaurant
    has integrated reservation systems (Reserve with Google).

    Returns available time slots for the specified date and party size.
    """
    logger.info(f"Check availability for place: {place_id} on {date}")

    try:
        result = await google_maps_service.check_availability(
            place_id=place_id,
            date=date,
            party_size=party_size
        )

        if result.get("error"):
            raise HTTPException(
                status_code=result.get("status_code", 500),
                detail=result.get("message", "Failed to check availability")
            )

        return {
            "success": True,
            "place_id": place_id,
            "date": date,
            "party_size": party_size,
            "reservations_available": result.get("reservations_available", False),
            "time_slots": result.get("time_slots", []),
            "booking_url": result.get("booking_url"),
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Check availability error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
