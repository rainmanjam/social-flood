"""
Google Maps API Endpoints.

Provides FastAPI endpoints using DataForSEO API for:
- Place search (SERP API)
- Place details (My Business Info API)
- Reviews extraction (Reviews API - async task workflow)
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException, Depends, Path

from app.core.auth import get_api_key
from app.core.cache_manager import generate_cache_key, get_cached_or_fetch
from app.core.rate_limiter import rate_limit

from app.api.google_maps.models import (
    SortOrder,
    TaskStatus,
    PlaceSearchResponse,
    PlaceSearchResult,
    PlaceDetailsResponse,
    PlaceDetails,
    ReviewsTaskSubmitResponse,
    ReviewsTaskStatusResponse,
    ReviewsTasksReadyResponse,
    Review,
    ReviewAuthor,
    Coordinates,
    OpeningHours,
)
from app.api.google_maps.dataforseo_client import get_dataforseo_client

logger = logging.getLogger("uvicorn")
google_maps_router = APIRouter(tags=["Google Maps API"])


# ============ Search Endpoint ============

@google_maps_router.get(
    "/search",
    response_model=PlaceSearchResponse,
    summary="Search Places",
    responses={
        200: {"description": "Search results"},
        400: {"description": "Invalid parameters"},
        500: {"description": "Server error"},
    }
)
async def search_places(
    query: str = Query(..., min_length=1, description="Search query", example="restaurants"),
    location: Optional[str] = Query(None, description="Location name filter", example="New York, NY, USA"),
    location_code: Optional[int] = Query(None, description="DataForSEO location code (preferred over location name)", example=1023191),
    max_results: int = Query(20, ge=1, le=100, description="Max results (1-100)"),
    language_code: str = Query("en", description="Language code"),
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit),
):
    """
    Search for places on Google Maps using DataForSEO SERP API.

    Returns a list of places matching the search query and optional location filter.
    Each result includes basic info: name, address, rating, reviews count, and coordinates.

    **Pricing:** ~$0.002 per request (Live mode)
    """
    cache_key = generate_cache_key(
        "google_maps:search:v3",
        query=query,
        location=location,
        location_code=location_code,
        max_results=max_results,
        language_code=language_code
    )

    async def fetch_results():
        try:
            client = get_dataforseo_client()
            data = await client.search_places(
                query=query,
                location=location,
                location_code=location_code,
                language_code=language_code,
                depth=max_results
            )

            if not data.get("success"):
                return PlaceSearchResponse(
                    success=False,
                    query=query,
                    location=location,
                    error=data.get("error", "Unknown error")
                )

            # Convert to response model
            search_results = []
            for r in data.get("results", []):
                coords = None
                if r.get("coordinates"):
                    coords = Coordinates(
                        latitude=r["coordinates"].get("latitude", 0),
                        longitude=r["coordinates"].get("longitude", 0)
                    )

                search_results.append(PlaceSearchResult(
                    place_id=r.get("place_id") or r.get("cid") or "",
                    name=r.get("name", ""),
                    address=r.get("address", ""),
                    rating=r.get("rating"),
                    reviews_count=r.get("reviews_count"),
                    category=r.get("category"),
                    phone=r.get("phone"),
                    website=r.get("website"),
                    coordinates=coords,
                    thumbnail=r.get("thumbnail"),
                    google_maps_url=r.get("google_maps_url"),
                ))

            return PlaceSearchResponse(
                success=True,
                query=query,
                location=location,
                total_results=len(search_results),
                results=search_results,
                has_more=len(search_results) >= max_results,
            )

        except Exception as e:
            logger.error(f"Search error: {e}")
            return PlaceSearchResponse(
                success=False,
                query=query,
                location=location,
                error=str(e)
            )

    return await get_cached_or_fetch(cache_key, fetch_results)


# ============ Details Endpoint ============

@google_maps_router.get(
    "/details",
    response_model=PlaceDetailsResponse,
    summary="Get Place Details",
    responses={
        200: {"description": "Place details"},
        400: {"description": "Invalid parameters"},
        404: {"description": "Place not found"},
        500: {"description": "Server error"},
    }
)
async def get_place_details(
    place_id: Optional[str] = Query(None, description="Google Place ID"),
    cid: Optional[str] = Query(None, description="Google CID"),
    keyword: Optional[str] = Query(None, description="Business name to search"),
    location: Optional[str] = Query(None, description="Location context", example="New York, NY, USA"),
    location_code: Optional[int] = Query(None, description="DataForSEO location code (preferred over location name)", example=1023191),
    language_code: str = Query("en", description="Language code"),
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit),
):
    """
    Get detailed information about a place using DataForSEO My Business Info API.

    Provide at least one of: `place_id`, `cid`, or `keyword`.
    Returns comprehensive details including address, phone, website, hours, photos, etc.

    **Pricing:** ~$0.002 per request (Live mode)
    """
    if not place_id and not cid and not keyword:
        raise HTTPException(
            status_code=400,
            detail="At least one of 'place_id', 'cid', or 'keyword' must be provided"
        )

    cache_key = generate_cache_key(
        "google_maps:details:v3",
        place_id=place_id,
        cid=cid,
        keyword=keyword,
        location=location,
        location_code=location_code,
        language_code=language_code
    )

    async def fetch_details():
        try:
            client = get_dataforseo_client()
            data = await client.get_business_info(
                keyword=keyword,
                place_id=place_id,
                cid=cid,
                location=location,
                location_code=location_code,
                language_code=language_code
            )

            if not data.get("success"):
                return PlaceDetailsResponse(
                    success=False,
                    error=data.get("error", "Unknown error")
                )

            place_data = data.get("place")
            if not place_data:
                return PlaceDetailsResponse(
                    success=False,
                    error="Place not found"
                )

            # Build coordinates
            coords = None
            if place_data.get("coordinates"):
                coords = Coordinates(
                    latitude=place_data["coordinates"].get("latitude", 0),
                    longitude=place_data["coordinates"].get("longitude", 0)
                )

            # Build opening hours
            hours = None
            if place_data.get("opening_hours"):
                hours = OpeningHours(**place_data["opening_hours"])

            place = PlaceDetails(
                place_id=place_data.get("place_id") or place_data.get("cid") or "",
                name=place_data.get("name", ""),
                address=place_data.get("address", ""),
                phone=place_data.get("phone"),
                website=place_data.get("website"),
                google_maps_url=place_data.get("google_maps_url"),
                rating=place_data.get("rating"),
                reviews_count=place_data.get("reviews_count"),
                category=place_data.get("category"),
                categories=place_data.get("categories", []),
                coordinates=coords,
                plus_code=place_data.get("plus_code"),
                opening_hours=hours,
                price_level=place_data.get("price_level"),
                popular_times=place_data.get("popular_times"),
                attributes=place_data.get("attributes", []),
                photos=place_data.get("photos", []),
                data_id=None,
                cid=place_data.get("cid"),
            )

            return PlaceDetailsResponse(success=True, place=place)

        except Exception as e:
            logger.error(f"Details error: {e}")
            return PlaceDetailsResponse(success=False, error=str(e))

    return await get_cached_or_fetch(cache_key, fetch_details)


# ============ Reviews Endpoints (Async Task Workflow) ============

@google_maps_router.post(
    "/reviews/submit",
    response_model=ReviewsTaskSubmitResponse,
    summary="Submit Reviews Collection Task",
    responses={
        200: {"description": "Task submitted successfully"},
        400: {"description": "Invalid parameters"},
        500: {"description": "Server error"},
    }
)
async def submit_reviews_task(
    place_id: Optional[str] = Query(None, description="Google Place ID"),
    cid: Optional[str] = Query(None, description="Google CID"),
    keyword: Optional[str] = Query(None, description="Business name to search"),
    location: Optional[str] = Query(None, description="Location context", example="New York, NY, USA"),
    location_code: Optional[int] = Query(None, description="DataForSEO location code (preferred over location name)", example=1023191),
    language_code: str = Query("en", description="Language code"),
    max_reviews: int = Query(100, ge=1, le=4490, description="Max reviews to collect (1-4490)"),
    sort_by: SortOrder = Query(SortOrder.NEWEST, description="Sort order"),
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit),
):
    """
    Submit a reviews collection task (async).

    This endpoint queues a task to collect reviews. Use `GET /reviews/{task_id}`
    to retrieve results once the task is complete (typically 5-45 seconds).

    Provide at least one of: `place_id`, `cid`, or `keyword`.

    **Pricing:** ~$0.00075 per 10 reviews collected

    **Workflow:**
    1. POST /reviews/submit → returns task_id
    2. GET /reviews/{task_id} → returns results when ready
    """
    if not place_id and not cid and not keyword:
        raise HTTPException(
            status_code=400,
            detail="At least one of 'place_id', 'cid', or 'keyword' must be provided"
        )

    try:
        client = get_dataforseo_client()
        data = await client.submit_reviews_task(
            keyword=keyword,
            place_id=place_id,
            cid=cid,
            location=location,
            location_code=location_code,
            language_code=language_code,
            depth=max_reviews,
            sort_by=sort_by.value
        )

        if not data.get("success"):
            return ReviewsTaskSubmitResponse(
                success=False,
                status=TaskStatus.ERROR,
                error=data.get("error", "Unknown error")
            )

        return ReviewsTaskSubmitResponse(
            success=True,
            task_id=data.get("task_id"),
            status=TaskStatus.PENDING,
            message=data.get("message", "Task submitted successfully"),
            cost=data.get("cost")
        )

    except Exception as e:
        logger.error(f"Reviews submit error: {e}")
        return ReviewsTaskSubmitResponse(
            success=False,
            status=TaskStatus.ERROR,
            error=str(e)
        )


@google_maps_router.get(
    "/reviews/{task_id}",
    response_model=ReviewsTaskStatusResponse,
    summary="Get Reviews Task Results",
    responses={
        200: {"description": "Task results or status"},
        404: {"description": "Task not found"},
        500: {"description": "Server error"},
    }
)
async def get_reviews_task(
    task_id: str = Path(..., description="Task ID from submit endpoint"),
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit),
):
    """
    Get results for a reviews collection task.

    Returns the reviews if the task is complete, or the current status if still processing.

    **Status values:**
    - `pending`: Task queued but not started
    - `processing`: Task is running
    - `completed`: Results available
    - `error`: Task failed
    """
    try:
        client = get_dataforseo_client()
        data = await client.get_reviews_task(task_id)

        if not data.get("success"):
            status = TaskStatus(data.get("status", "error"))
            return ReviewsTaskStatusResponse(
                success=False,
                task_id=task_id,
                status=status,
                error=data.get("error"),
                message=data.get("message")
            )

        # Convert status string to enum
        status_str = data.get("status", "completed")
        try:
            status = TaskStatus(status_str)
        except ValueError:
            status = TaskStatus.PROCESSING if status_str == "processing" else TaskStatus.COMPLETED

        # If still processing, return status only
        if status in [TaskStatus.PENDING, TaskStatus.PROCESSING]:
            return ReviewsTaskStatusResponse(
                success=True,
                task_id=task_id,
                status=status,
                message=data.get("message", "Task is still processing")
            )

        # Parse reviews
        reviews = []
        for r in data.get("reviews", []):
            author_data = r.get("author", {})
            author = ReviewAuthor(
                name=author_data.get("name", "Anonymous"),
                profile_url=author_data.get("profile_url"),
                photo_url=author_data.get("photo_url"),
                reviews_count=author_data.get("reviews_count"),
                photos_count=author_data.get("photos_count"),
                is_local_guide=author_data.get("is_local_guide", False),
                local_guide_level=author_data.get("local_guide_level"),
            )

            reviews.append(Review(
                author=author,
                rating=r.get("rating") or 0,
                text=r.get("text") or r.get("original_text"),
                time_ago=r.get("time_ago") or "",
                published_date=r.get("published_date"),
                likes=r.get("likes", 0),
                response=r.get("response"),
                response_time=r.get("response_time"),
                photos=r.get("photos", []),
            ))

        return ReviewsTaskStatusResponse(
            success=True,
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            place_id=data.get("place_id"),
            place_name=data.get("place_name"),
            total_reviews=data.get("total_reviews", 0),
            average_rating=data.get("average_rating"),
            rating_distribution=data.get("rating_distribution", {}),
            reviews=reviews,
            cost=data.get("cost")
        )

    except Exception as e:
        logger.error(f"Reviews get error: {e}")
        return ReviewsTaskStatusResponse(
            success=False,
            task_id=task_id,
            status=TaskStatus.ERROR,
            error=str(e)
        )


@google_maps_router.get(
    "/reviews/tasks/ready",
    response_model=ReviewsTasksReadyResponse,
    summary="Check Ready Review Tasks",
    responses={
        200: {"description": "List of ready task IDs"},
        500: {"description": "Server error"},
    }
)
async def get_ready_review_tasks(
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit),
):
    """
    Check which review tasks are ready for retrieval.

    Returns a list of task IDs that have completed and are ready to be fetched.
    Useful for batch processing multiple review requests.
    """
    try:
        client = get_dataforseo_client()
        ready_tasks = await client.check_reviews_task_ready()

        return ReviewsTasksReadyResponse(
            success=True,
            ready_tasks=ready_tasks,
            count=len(ready_tasks)
        )

    except Exception as e:
        logger.error(f"Ready tasks error: {e}")
        return ReviewsTasksReadyResponse(
            success=False,
            ready_tasks=[],
            count=0
        )


# ============ Batch Endpoints ============

@google_maps_router.post(
    "/batch/search",
    response_model=List[PlaceSearchResponse],
    summary="Batch Search Places",
    responses={
        200: {"description": "Batch search results"},
        400: {"description": "Invalid parameters"},
        500: {"description": "Server error"},
    }
)
async def batch_search_places(
    queries: List[str] = Query(..., min_length=1, max_length=10, description="Search queries (max 10)"),
    location: Optional[str] = Query(None, description="Location filter for all queries"),
    location_code: Optional[int] = Query(None, description="DataForSEO location code (preferred over location name)", example=1023191),
    max_results: int = Query(10, ge=1, le=50, description="Max results per query"),
    language_code: str = Query("en", description="Language code"),
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit),
):
    """
    Batch search for multiple queries.

    Performs searches for up to 10 queries.
    Each query returns its own set of results.

    **Pricing:** ~$0.002 per query
    """
    import asyncio

    async def search_single(query: str) -> PlaceSearchResponse:
        try:
            client = get_dataforseo_client()
            data = await client.search_places(
                query=query,
                location=location,
                location_code=location_code,
                language_code=language_code,
                depth=max_results
            )

            if not data.get("success"):
                return PlaceSearchResponse(
                    success=False,
                    query=query,
                    location=location,
                    error=data.get("error")
                )

            search_results = []
            for r in data.get("results", []):
                coords = None
                if r.get("coordinates"):
                    coords = Coordinates(
                        latitude=r["coordinates"].get("latitude", 0),
                        longitude=r["coordinates"].get("longitude", 0)
                    )

                search_results.append(PlaceSearchResult(
                    place_id=r.get("place_id") or r.get("cid") or "",
                    name=r.get("name", ""),
                    address=r.get("address", ""),
                    rating=r.get("rating"),
                    reviews_count=r.get("reviews_count"),
                    category=r.get("category"),
                    phone=r.get("phone"),
                    website=r.get("website"),
                    coordinates=coords,
                    thumbnail=r.get("thumbnail"),
                    google_maps_url=r.get("google_maps_url"),
                ))

            return PlaceSearchResponse(
                success=True,
                query=query,
                location=location,
                total_results=len(search_results),
                results=search_results,
                has_more=len(search_results) >= max_results,
            )

        except Exception as e:
            logger.error(f"Batch search error for '{query}': {e}")
            return PlaceSearchResponse(
                success=False,
                query=query,
                location=location,
                error=str(e)
            )

    tasks = [search_single(q) for q in queries]
    results = await asyncio.gather(*tasks)

    return list(results)


@google_maps_router.post(
    "/batch/details",
    response_model=List[PlaceDetailsResponse],
    summary="Batch Get Details",
    responses={
        200: {"description": "Batch details results"},
        400: {"description": "Invalid parameters"},
        500: {"description": "Server error"},
    }
)
async def batch_get_details(
    place_ids: List[str] = Query(..., min_length=1, max_length=10, description="Place IDs (max 10)"),
    location: Optional[str] = Query(None, description="Location context"),
    location_code: Optional[int] = Query(None, description="DataForSEO location code (preferred over location name)", example=1023191),
    language_code: str = Query("en", description="Language code"),
    api_key: str = Depends(get_api_key),
    rate_limit_check: None = Depends(rate_limit),
):
    """
    Batch get details for multiple places.

    Fetches details for up to 10 place IDs.

    **Pricing:** ~$0.002 per place
    """
    import asyncio

    async def get_single(place_id: str) -> PlaceDetailsResponse:
        try:
            client = get_dataforseo_client()
            data = await client.get_business_info(
                place_id=place_id,
                location=location,
                location_code=location_code,
                language_code=language_code
            )

            if not data.get("success"):
                return PlaceDetailsResponse(
                    success=False,
                    error=data.get("error")
                )

            place_data = data.get("place")
            if not place_data:
                return PlaceDetailsResponse(
                    success=False,
                    error="Place not found"
                )

            coords = None
            if place_data.get("coordinates"):
                coords = Coordinates(
                    latitude=place_data["coordinates"].get("latitude", 0),
                    longitude=place_data["coordinates"].get("longitude", 0)
                )

            hours = None
            if place_data.get("opening_hours"):
                hours = OpeningHours(**place_data["opening_hours"])

            place = PlaceDetails(
                place_id=place_data.get("place_id") or place_data.get("cid") or "",
                name=place_data.get("name", ""),
                address=place_data.get("address", ""),
                phone=place_data.get("phone"),
                website=place_data.get("website"),
                google_maps_url=place_data.get("google_maps_url"),
                rating=place_data.get("rating"),
                reviews_count=place_data.get("reviews_count"),
                category=place_data.get("category"),
                categories=place_data.get("categories", []),
                coordinates=coords,
                plus_code=place_data.get("plus_code"),
                opening_hours=hours,
                price_level=place_data.get("price_level"),
                popular_times=place_data.get("popular_times"),
                attributes=place_data.get("attributes", []),
                photos=place_data.get("photos", []),
                data_id=None,
                cid=place_data.get("cid"),
            )

            return PlaceDetailsResponse(success=True, place=place)

        except Exception as e:
            logger.error(f"Batch details error for '{place_id}': {e}")
            return PlaceDetailsResponse(success=False, error=str(e))

    tasks = [get_single(pid) for pid in place_ids]
    results = await asyncio.gather(*tasks)

    return list(results)


# ============ Statistics Endpoint ============

@google_maps_router.get(
    "/stats",
    summary="Get API Statistics",
    responses={
        200: {"description": "Cache, batch, and task statistics"},
    }
)
async def get_api_stats(
    api_key: str = Depends(get_api_key),
):
    """
    Get statistics about caching, batching, and background tasks.

    Returns:
    - **cache**: Cache hit/miss rates and estimated cost savings
    - **batch_queues**: Batch queue sizes and API calls saved
    - **review_tasks**: Background task polling statistics

    This endpoint is useful for monitoring the efficiency of the caching
    and batching systems.
    """
    try:
        client = get_dataforseo_client()
        return client.get_all_stats()
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))


@google_maps_router.post(
    "/cache/clear",
    summary="Clear Cache",
    responses={
        200: {"description": "Cache cleared successfully"},
    }
)
async def clear_cache(
    api_key: str = Depends(get_api_key),
):
    """
    Clear all cached DataForSEO responses.

    Use this if you need fresh data or suspect stale cache entries.
    """
    from app.api.google_maps.dataforseo_cache import dataforseo_cache

    try:
        await dataforseo_cache.clear_all()
        return {"success": True, "message": "Cache cleared successfully"}
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))
