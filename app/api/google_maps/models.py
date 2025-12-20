"""
Pydantic models for Google Maps API.

Defines request and response models for place search, details, and reviews.
Uses DataForSEO API for data retrieval.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class SortOrder(str, Enum):
    """Sort order for reviews."""
    NEWEST = "newest"
    HIGHEST = "highest"
    LOWEST = "lowest"
    RELEVANT = "relevant"


class TaskStatus(str, Enum):
    """Status of an async task."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


# ============ Coordinate Models ============

class Coordinates(BaseModel):
    """Geographic coordinates."""
    latitude: float = Field(..., description="Latitude coordinate")
    longitude: float = Field(..., description="Longitude coordinate")


# ============ Review Models ============

class ReviewAuthor(BaseModel):
    """Review author information."""
    name: str = Field(..., description="Author name")
    profile_url: Optional[str] = Field(None, description="Author profile URL")
    photo_url: Optional[str] = Field(None, description="Author photo URL")
    reviews_count: Optional[int] = Field(None, description="Total reviews by author")
    photos_count: Optional[int] = Field(None, description="Total photos by author")
    is_local_guide: bool = Field(False, description="Is Local Guide")
    local_guide_level: Optional[int] = Field(None, description="Local Guide level (1-10)")


class Review(BaseModel):
    """Individual review."""
    author: ReviewAuthor = Field(..., description="Review author")
    rating: int = Field(..., ge=1, le=5, description="Star rating (1-5)")
    text: Optional[str] = Field(None, description="Review text")
    time_ago: str = Field(..., description="Relative time (e.g., '2 months ago')")
    published_date: Optional[str] = Field(None, description="Absolute date if available")
    likes: int = Field(0, description="Number of likes")
    response: Optional[str] = Field(None, description="Owner response")
    response_time: Optional[str] = Field(None, description="Owner response time")
    photos: List[str] = Field(default_factory=list, description="Review photo URLs")


class ReviewsResponse(BaseModel):
    """Response for reviews endpoint."""
    place_id: str = Field(..., description="Google Place ID")
    place_name: str = Field(..., description="Place name")
    total_reviews: int = Field(..., description="Total review count")
    average_rating: float = Field(..., description="Average rating")
    rating_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Rating distribution (1-5 stars)"
    )
    reviews: List[Review] = Field(default_factory=list, description="List of reviews")
    has_more: bool = Field(False, description="More reviews available")
    limited_view: bool = Field(
        False,
        description="True if Google Maps is in limited view mode (reviews not accessible)"
    )
    message: Optional[str] = Field(
        None,
        description="Status message about review availability"
    )


# ============ Place Detail Models ============

class OpeningHours(BaseModel):
    """Opening hours for a place."""
    monday: Optional[str] = Field(None, description="Monday hours")
    tuesday: Optional[str] = Field(None, description="Tuesday hours")
    wednesday: Optional[str] = Field(None, description="Wednesday hours")
    thursday: Optional[str] = Field(None, description="Thursday hours")
    friday: Optional[str] = Field(None, description="Friday hours")
    saturday: Optional[str] = Field(None, description="Saturday hours")
    sunday: Optional[str] = Field(None, description="Sunday hours")
    is_open_now: Optional[bool] = Field(None, description="Currently open")


class PlaceDetails(BaseModel):
    """Detailed place information."""
    place_id: str = Field(..., description="Google Place ID")
    name: str = Field(..., description="Place name")
    address: str = Field("", description="Full address")
    phone: Optional[str] = Field(None, description="Phone number")
    website: Optional[str] = Field(None, description="Website URL")
    google_maps_url: Optional[str] = Field(None, description="Google Maps URL")

    # Ratings
    rating: Optional[float] = Field(None, description="Average rating (1-5)")
    reviews_count: Optional[int] = Field(None, description="Total reviews")

    # Category
    category: Optional[str] = Field(None, description="Primary category")
    categories: List[str] = Field(default_factory=list, description="All categories")

    # Location
    coordinates: Optional[Coordinates] = Field(None, description="Lat/lng coordinates")
    plus_code: Optional[str] = Field(None, description="Plus code")

    # Hours
    opening_hours: Optional[OpeningHours] = Field(None, description="Opening hours")

    # Additional info
    price_level: Optional[str] = Field(None, description="Price level ($-$$$$)")
    popular_times: Optional[Dict[str, Any]] = Field(None, description="Popular times data")
    attributes: List[str] = Field(default_factory=list, description="Place attributes")

    # Photos
    photos: List[str] = Field(default_factory=list, description="Photo URLs")

    # Metadata
    data_id: Optional[str] = Field(None, description="Internal data ID")
    cid: Optional[str] = Field(None, description="Google CID")


class PlaceDetailsResponse(BaseModel):
    """Response for place details endpoint."""
    success: bool = Field(..., description="Request success")
    place: Optional[PlaceDetails] = Field(None, description="Place details")
    error: Optional[str] = Field(None, description="Error message if failed")


# ============ Search Models ============

class PlaceSearchResult(BaseModel):
    """Individual search result."""
    place_id: str = Field(..., description="Google Place ID")
    name: str = Field(..., description="Place name")
    address: str = Field(..., description="Address")
    rating: Optional[float] = Field(None, description="Rating (1-5)")
    reviews_count: Optional[int] = Field(None, description="Review count")
    category: Optional[str] = Field(None, description="Primary category")
    phone: Optional[str] = Field(None, description="Phone number")
    website: Optional[str] = Field(None, description="Website URL")
    coordinates: Optional[Coordinates] = Field(None, description="Coordinates")
    thumbnail: Optional[str] = Field(None, description="Thumbnail URL")
    google_maps_url: Optional[str] = Field(None, description="Google Maps URL")


class PlaceSearchResponse(BaseModel):
    """Response for place search endpoint."""
    success: bool = Field(..., description="Request success")
    query: str = Field(..., description="Original search query")
    location: Optional[str] = Field(None, description="Location filter")
    total_results: int = Field(0, description="Number of results")
    results: List[PlaceSearchResult] = Field(default_factory=list, description="Search results")
    has_more: bool = Field(False, description="More results available")
    error: Optional[str] = Field(None, description="Error message if failed")


# ============ Coordinates Lookup Models ============

class CoordinatesLookupResponse(BaseModel):
    """Response for coordinates lookup endpoint."""
    success: bool = Field(..., description="Request success")
    query: str = Field(..., description="Search query or place name")
    place_id: Optional[str] = Field(None, description="Google Place ID")
    name: Optional[str] = Field(None, description="Place name")
    address: Optional[str] = Field(None, description="Full address")
    coordinates: Optional[Coordinates] = Field(None, description="Lat/lng coordinates")
    plus_code: Optional[str] = Field(None, description="Plus code")
    error: Optional[str] = Field(None, description="Error message if failed")


# ============ Batch Request Models ============

class BatchSearchRequest(BaseModel):
    """Batch search request."""
    queries: List[str] = Field(..., min_length=1, max_length=10, description="List of search queries")
    location: Optional[str] = Field(None, description="Location filter for all queries")


class BatchDetailsRequest(BaseModel):
    """Batch details request."""
    place_ids: List[str] = Field(..., min_length=1, max_length=10, description="List of place IDs")


# ============ Reviews Task Models (Async Workflow) ============

class ReviewsTaskSubmitResponse(BaseModel):
    """Response for reviews task submission."""
    success: bool = Field(..., description="Request success")
    task_id: Optional[str] = Field(None, description="Task ID for retrieval")
    status: TaskStatus = Field(TaskStatus.PENDING, description="Task status")
    message: Optional[str] = Field(None, description="Status message")
    error: Optional[str] = Field(None, description="Error message if failed")
    cost: Optional[float] = Field(None, description="API cost in USD")


class ReviewsTaskStatusResponse(BaseModel):
    """Response for reviews task status/results."""
    success: bool = Field(..., description="Request success")
    task_id: str = Field(..., description="Task ID")
    status: TaskStatus = Field(..., description="Task status")
    place_id: Optional[str] = Field(None, description="Google Place ID")
    place_name: Optional[str] = Field(None, description="Place name")
    total_reviews: int = Field(0, description="Total review count")
    average_rating: Optional[float] = Field(None, description="Average rating")
    rating_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Rating distribution (1-5 stars)"
    )
    reviews: List[Review] = Field(default_factory=list, description="List of reviews")
    message: Optional[str] = Field(None, description="Status message")
    error: Optional[str] = Field(None, description="Error message if failed")
    cost: Optional[float] = Field(None, description="API cost in USD")


class ReviewsTasksReadyResponse(BaseModel):
    """Response for checking ready tasks."""
    success: bool = Field(..., description="Request success")
    ready_tasks: List[str] = Field(default_factory=list, description="List of ready task IDs")
    count: int = Field(0, description="Number of ready tasks")
