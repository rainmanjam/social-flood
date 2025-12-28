"""
Google Maps Service.

This module provides Google Maps data extraction using native Python
with Playwright for browser automation. No external Docker sidecar required.

Features:
- Business details (name, address, phone, website)
- Ratings and review counts
- Operating hours
- Location coordinates and plus codes
- Category and price level
"""
import logging
import asyncio
import uuid
import math
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from app.core.config import get_settings
from app.core.proxy import ENABLE_PROXY, get_proxy

logger = logging.getLogger(__name__)


class GoogleMapsService:
    """
    Service class for Google Maps operations using native Playwright scraping.

    This replaces the previous gosom Docker sidecar approach with direct
    browser automation.
    """

    def __init__(self):
        """Initialize the service."""
        self._scraper_module = None
        self._initialized = False

    async def _ensure_initialized(self):
        """Lazily initialize the scraper module."""
        if not self._initialized:
            # Import here to avoid circular imports and allow lazy loading
            from app.services import google_maps_scraper
            self._scraper_module = google_maps_scraper
            self._initialized = True

    async def health_check(self) -> Dict[str, Any]:
        """
        Check if the scraping service is healthy.

        Returns:
            Health status dictionary
        """
        try:
            await self._ensure_initialized()

            # For native scraping, we just verify Playwright can be imported
            try:
                from playwright.async_api import async_playwright
                return {
                    "healthy": True,
                    "status_code": 200,
                    "service": "google-maps-native-scraper",
                    "mode": "native-playwright"
                }
            except ImportError:
                return {
                    "healthy": False,
                    "error": "Playwright not installed",
                    "service": "google-maps-native-scraper"
                }

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "healthy": False,
                "error": str(e),
                "service": "google-maps-native-scraper"
            }

    async def create_search_job(
        self,
        query: str,
        language: str = "en",
        max_results: int = 20,
        depth: int = 1,
        email_extraction: bool = False,
        zoom: int = 15,
        geo_coordinates: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new Google Maps search job.

        The job runs asynchronously in the background.

        Args:
            query: Search query (e.g., "restaurants in New York")
            language: Language code (default: "en")
            max_results: Maximum number of results (default: 20)
            depth: Crawl depth (default: 1) - not used in native mode
            email_extraction: Whether to extract emails - not yet implemented
            zoom: Map zoom level (1-21, default: 15)
            geo_coordinates: Optional geo coordinates for search center

        Returns:
            Job creation response with job_id
        """
        try:
            await self._ensure_initialized()

            # Create job
            job_id = str(uuid.uuid4())
            job_name = f"search_{query[:30].replace(' ', '_')}"

            job = self._scraper_module.ScrapeJob(
                id=job_id,
                name=job_name,
                query=query,
                language=language,
                max_results=max_results,
                zoom=zoom,
                geo_coordinates=geo_coordinates,
                email_extraction=email_extraction
            )

            # Store job
            store = await self._scraper_module.get_job_store()
            await store.create(job)

            # Get proxy if enabled
            proxy = None
            if ENABLE_PROXY:
                proxy = await get_proxy()
                if proxy:
                    logger.info(f"Using proxy for Google Maps scraping")

            # Start background task
            asyncio.create_task(
                self._scraper_module.run_scrape_job(job, proxy=proxy)
            )

            logger.info(f"Created job {job_id} for query: {query}")

            return {
                "job_id": job_id,
                "id": job_id,
                "status": "pending",
                "message": "Job created and started"
            }

        except Exception as e:
            logger.error(f"Error creating search job: {e}")
            return {
                "error": True,
                "message": str(e)
            }

    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get the status of a scraping job.

        Args:
            job_id: The job ID to check

        Returns:
            Job status information
        """
        try:
            await self._ensure_initialized()

            store = await self._scraper_module.get_job_store()
            job = await store.get(job_id)

            if not job:
                return {
                    "error": True,
                    "status_code": 404,
                    "message": "Job not found"
                }

            # Map internal status to expected format
            status_map = {
                "pending": "pending",
                "running": "working",
                "completed": "completed",
                "failed": "failed"
            }

            return {
                "job_id": job.id,
                "status": status_map.get(job.status.value, job.status.value),
                "progress": job.progress,
                "total": job.total,
                "error": job.error,
                "created_at": job.created_at.isoformat(),
                "completed_at": job.completed_at.isoformat() if job.completed_at else None
            }

        except Exception as e:
            logger.error(f"Error getting job status: {e}")
            return {
                "error": True,
                "message": str(e)
            }

    async def get_job_results(
        self,
        job_id: str,
        format: str = "json"
    ) -> Dict[str, Any]:
        """
        Get the results of a completed job.

        Args:
            job_id: The job ID to get results for
            format: Output format (json, csv)

        Returns:
            Job results with place data
        """
        try:
            await self._ensure_initialized()

            store = await self._scraper_module.get_job_store()
            job = await store.get(job_id)

            if not job:
                return {
                    "error": True,
                    "status_code": 404,
                    "message": "Job not found"
                }

            if job.status != self._scraper_module.JobStatus.COMPLETED:
                return {
                    "error": True,
                    "message": f"Job not completed. Current status: {job.status.value}"
                }

            if format == "csv":
                # Convert to CSV format
                import csv
                import io
                if job.results:
                    output = io.StringIO()
                    writer = csv.DictWriter(output, fieldnames=job.results[0].keys())
                    writer.writeheader()
                    writer.writerows(job.results)
                    return {"data": output.getvalue(), "format": "csv"}
                return {"data": "", "format": "csv"}

            return {
                "results": job.results,
                "format": "json",
                "count": len(job.results),
                "job_id": job_id
            }

        except Exception as e:
            logger.error(f"Error getting job results: {e}")
            return {
                "error": True,
                "message": str(e)
            }

    async def list_jobs(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List all jobs with optional filtering.

        Args:
            status: Filter by job status
            limit: Maximum number of jobs to return
            offset: Pagination offset

        Returns:
            List of jobs
        """
        try:
            await self._ensure_initialized()

            store = await self._scraper_module.get_job_store()
            jobs = await store.list_all(status=status, limit=limit, offset=offset)

            # Return in gosom-compatible format
            return [job.to_dict() for job in jobs]

        except Exception as e:
            logger.error(f"Error listing jobs: {e}")
            return {
                "error": True,
                "message": str(e)
            }

    async def delete_job(self, job_id: str) -> Dict[str, Any]:
        """
        Delete a job and its results.

        Args:
            job_id: The job ID to delete

        Returns:
            Deletion confirmation
        """
        try:
            await self._ensure_initialized()

            store = await self._scraper_module.get_job_store()
            deleted = await store.delete(job_id)

            if deleted:
                return {"success": True, "job_id": job_id}
            else:
                return {
                    "error": True,
                    "status_code": 404,
                    "message": "Job not found"
                }

        except Exception as e:
            logger.error(f"Error deleting job: {e}")
            return {
                "error": True,
                "message": str(e)
            }

    async def search_and_wait(
        self,
        query: str,
        language: str = "en",
        max_results: int = 20,
        depth: int = 1,
        email_extraction: bool = False,
        zoom: int = 15,
        geo_coordinates: Optional[str] = None,
        timeout: int = 300,
        poll_interval: int = 2
    ) -> Dict[str, Any]:
        """
        Create a search job and wait for results.

        This is a convenience method that creates a job, polls for completion,
        and returns the results.

        Args:
            query: Search query
            language: Language code
            max_results: Maximum results
            depth: Crawl depth (not used in native mode)
            email_extraction: Extract emails from websites
            zoom: Map zoom level
            geo_coordinates: Search center coordinates
            timeout: Maximum wait time in seconds
            poll_interval: Seconds between status checks

        Returns:
            Search results or error
        """
        # Create the job
        job_response = await self.create_search_job(
            query=query,
            language=language,
            max_results=max_results,
            depth=depth,
            email_extraction=email_extraction,
            zoom=zoom,
            geo_coordinates=geo_coordinates
        )

        if job_response.get("error"):
            return job_response

        job_id = job_response.get("job_id") or job_response.get("id")
        if not job_id:
            return {
                "error": True,
                "message": "No job_id in response",
                "response": job_response
            }

        # Poll for completion
        elapsed = 0
        while elapsed < timeout:
            status_response = await self.get_job_status(job_id)

            if status_response.get("error"):
                # If it's a real error (not just job not found during creation)
                if status_response.get("status_code") != 404:
                    return status_response

            status = status_response.get("status", "").lower()

            if status == "completed":
                # Get results
                return await self.get_job_results(job_id)
            elif status == "failed":
                return {
                    "error": True,
                    "status": "failed",
                    "job_id": job_id,
                    "details": status_response
                }

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        return {
            "error": True,
            "status": "timeout",
            "job_id": job_id,
            "message": f"Job did not complete within {timeout} seconds"
        }

    def process_place_data(self, raw_data: List[Dict]) -> List[Dict[str, Any]]:
        """
        Process and normalize place data from scraper results.

        Args:
            raw_data: Raw place data from scraper

        Returns:
            Normalized place data
        """
        processed = []

        for place in raw_data:
            processed_place = {
                # Basic info - native scraper uses 'title', 'link', 'cid'
                "place_id": place.get("cid") or place.get("place_id") or place.get("data_id"),
                "name": place.get("title") or place.get("name"),
                "address": place.get("address") or place.get("full_address"),
                "phone": place.get("phone") or place.get("phone_number"),
                "website": place.get("website") or place.get("web"),

                # Location
                "latitude": place.get("latitude") or place.get("lat"),
                "longitude": place.get("longitude") or place.get("lng"),
                "plus_code": place.get("plus_code"),

                # Business info
                "category": place.get("category") or place.get("categories"),
                "rating": place.get("review_rating") or place.get("rating") or place.get("stars"),
                "review_count": place.get("review_count") or place.get("reviews_count") or place.get("reviews"),
                "price_level": place.get("price_range") or place.get("price_level") or place.get("price"),
                "price_per_person": place.get("price_per_person"),

                # Hours
                "hours": place.get("open_hours") or place.get("hours") or place.get("opening_hours") or place.get("working_hours"),
                "is_open_now": place.get("is_open_now") or place.get("open_now"),

                # Additional details
                "description": place.get("description") or place.get("about"),
                "photos": place.get("photos") or place.get("images"),
                "google_maps_url": place.get("link") or place.get("google_maps_url") or place.get("url"),

                # Action links
                "menu_link": place.get("menu_link"),
                "order_link": place.get("order_link"),
                "reserve_link": place.get("reserve_link"),

                # Service options and amenities
                "service_options": place.get("service_options") or [],
                "accessibility": place.get("accessibility") or [],
                "amenities": place.get("amenities") or [],

                # Popular times
                "popular_times": place.get("popular_times") or {},

                # Review details
                "reviews": place.get("reviews_data") or place.get("review_list"),
                "review_summary": place.get("review_summary"),
                "review_topics": place.get("review_topics") or [],
                "sample_reviews": place.get("sample_reviews") or [],

                # Related places
                "related_places": place.get("related_places") or [],

                # Contact info (from email extraction)
                "emails": place.get("emails") or place.get("email"),
                "social_media": {
                    "facebook": place.get("facebook"),
                    "instagram": place.get("instagram"),
                    "twitter": place.get("twitter"),
                    "linkedin": place.get("linkedin"),
                    "youtube": place.get("youtube")
                }
            }

            # Clean up None values in social_media
            processed_place["social_media"] = {
                k: v for k, v in processed_place["social_media"].items() if v
            } or None

            # Clean up empty lists/dicts
            for key in ["service_options", "accessibility", "amenities", "review_topics", "sample_reviews", "related_places"]:
                if not processed_place.get(key):
                    processed_place[key] = None
            if not processed_place.get("popular_times"):
                processed_place["popular_times"] = None

            processed.append(processed_place)

        return processed


    # =========================================================================
    # Extended Feature Methods
    # =========================================================================

    async def get_place_by_id(self, place_id: str) -> Dict[str, Any]:
        """
        Get place details by Place ID.

        Args:
            place_id: Google Place ID (CID or ChIJ format)

        Returns:
            Place details or error
        """
        try:
            await self._ensure_initialized()

            # Construct URL from place_id
            if place_id.startswith("0x"):
                # CID format - use data parameter
                url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
            else:
                # ChIJ format
                url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"

            return await self.lookup_place(url=url)

        except Exception as e:
            logger.error(f"Error getting place by ID: {e}")
            return {"error": True, "message": str(e)}

    async def lookup_place(
        self,
        url: Optional[str] = None,
        place_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Look up a place by URL or Place ID.

        Args:
            url: Google Maps URL
            place_id: Google Place ID

        Returns:
            Place details or error
        """
        try:
            await self._ensure_initialized()

            if place_id and not url:
                return await self.get_place_by_id(place_id)

            if not url:
                return {"error": True, "message": "URL or place_id required"}

            # Create a scraper and extract place details
            from app.services.google_maps_scraper import GoogleMapsScraper
            from app.core.proxy import ENABLE_PROXY, get_proxy

            proxy = None
            if ENABLE_PROXY:
                proxy = await get_proxy()

            scraper = GoogleMapsScraper(proxy=proxy, headless=True)
            try:
                page, context = await scraper._create_page("en")

                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(3)

                place_data = await scraper._extract_place_details(page)

                await context.close()

                if place_data:
                    processed = self.process_place_data([place_data])
                    return {"place": processed[0] if processed else None}
                else:
                    return {"error": True, "status_code": 404, "message": "Place not found"}

            finally:
                await scraper.close()

        except Exception as e:
            logger.error(f"Error looking up place: {e}")
            return {"error": True, "message": str(e)}

    async def nearby_search(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int = 1000,
        query: Optional[str] = None,
        language: str = "en",
        max_results: int = 20,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Search for places near a location.

        Args:
            latitude: Center latitude
            longitude: Center longitude
            radius_meters: Search radius in meters
            query: Optional filter query
            language: Language code
            max_results: Maximum results
            timeout: Optional timeout

        Returns:
            Search results or error
        """
        try:
            await self._ensure_initialized()

            # Build search query with location
            search_query = query if query else "places"
            geo_coords = f"{latitude},{longitude}"

            # Use existing search with coordinates
            result = await self.search_and_wait(
                query=search_query,
                language=language,
                max_results=max_results,
                geo_coordinates=geo_coords,
                zoom=self._radius_to_zoom(radius_meters),
                timeout=timeout or 300
            )

            if result.get("error"):
                return result

            return {
                "places": result.get("results", []),
                "center": {"latitude": latitude, "longitude": longitude}
            }

        except Exception as e:
            logger.error(f"Nearby search error: {e}")
            return {"error": True, "message": str(e)}

    def _radius_to_zoom(self, radius_meters: int) -> int:
        """Convert radius in meters to appropriate zoom level."""
        if radius_meters <= 500:
            return 17
        elif radius_meters <= 1000:
            return 16
        elif radius_meters <= 2000:
            return 15
        elif radius_meters <= 5000:
            return 14
        elif radius_meters <= 10000:
            return 13
        elif radius_meters <= 20000:
            return 12
        elif radius_meters <= 50000:
            return 11
        else:
            return 10

    def _calculate_grid_coordinates(
        self,
        center_lat: float,
        center_lng: float,
        radius_km: float,
        grid_size: int = 5
    ) -> List[Tuple[float, float]]:
        """
        Generate a grid of coordinates around a center point.

        This enables DataForSEO-style grid-based search for comprehensive
        area coverage, finding all businesses not just those visible from
        a single viewpoint.

        Args:
            center_lat: Center latitude
            center_lng: Center longitude
            radius_km: Radius in kilometers (distance from center to edge)
            grid_size: Number of points per side (e.g., 5 for 5x5 = 25 points)

        Returns:
            List of (lat, lng) tuples
        """
        # Calculate the step size between grid points
        step_km = (radius_km * 2) / (grid_size - 1) if grid_size > 1 else 0

        # Convert km to degrees (approximate)
        # 1 degree lat = 111.32 km
        lat_step = step_km / 111.32
        lng_step = step_km / (111.32 * math.cos(math.radians(center_lat)))

        coordinates = []

        # Calculate starting point (top-left corner)
        start_lat = center_lat + (radius_km / 111.32)
        start_lng = center_lng - (radius_km / (111.32 * math.cos(math.radians(center_lat))))

        for row in range(grid_size):
            for col in range(grid_size):
                lat = start_lat - (row * lat_step)
                lng = start_lng + (col * lng_step)
                coordinates.append((round(lat, 7), round(lng, 7)))

        return coordinates

    async def grid_search(
        self,
        query: str,
        center_lat: float,
        center_lng: float,
        radius_km: float = 5.0,
        grid_size: int = 5,
        max_results_per_point: int = 10,
        language: str = "en",
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Search across a grid of coordinates for comprehensive area coverage.

        Like DataForSEO's calculate_rectangles, this searches multiple viewpoints
        to find ALL businesses in an area, not just those visible from one map view.

        Args:
            query: Search query (e.g., "restaurants")
            center_lat: Center latitude
            center_lng: Center longitude
            radius_km: Search radius in km (default 5km)
            grid_size: Grid dimension (5 = 5x5 = 25 points, max 11x11 = 121)
            max_results_per_point: Max results per grid point
            language: Language code
            timeout: Optional timeout in seconds

        Returns:
            Aggregated results with grid metadata and deduplicated places
        """
        try:
            await self._ensure_initialized()

            # Validate grid size
            grid_size = min(max(grid_size, 3), 11)  # 3x3 to 11x11

            grid_coords = self._calculate_grid_coordinates(
                center_lat, center_lng, radius_km, grid_size
            )

            all_results = {}
            grid_data = []

            logger.info(f"Starting grid search: {query} with {len(grid_coords)} grid points")

            for idx, (lat, lng) in enumerate(grid_coords):
                try:
                    # Use higher zoom for more focused local results
                    zoom = 16 if radius_km <= 2 else 15

                    result = await self.search_and_wait(
                        query=query,
                        language=language,
                        max_results=max_results_per_point,
                        geo_coordinates=f"{lat},{lng}",
                        zoom=zoom,
                        timeout=timeout or 60
                    )

                    results_count = 0
                    if not result.get("error"):
                        places = result.get("results", [])
                        results_count = len(places)

                        # Dedupe by place_id
                        for place in places:
                            place_id = place.get("place_id")
                            if place_id and place_id not in all_results:
                                place["grid_positions"] = [idx]
                                all_results[place_id] = place
                            elif place_id:
                                all_results[place_id]["grid_positions"].append(idx)

                    grid_data.append({
                        "grid_index": idx,
                        "lat": lat,
                        "lng": lng,
                        "results_count": results_count
                    })

                except Exception as e:
                    logger.warning(f"Grid point {idx} ({lat}, {lng}) failed: {e}")
                    grid_data.append({
                        "grid_index": idx,
                        "lat": lat,
                        "lng": lng,
                        "results_count": 0,
                        "error": str(e)
                    })

            return {
                "success": True,
                "query": query,
                "center": {"lat": center_lat, "lng": center_lng},
                "radius_km": radius_km,
                "grid_size": grid_size,
                "total_grid_points": len(grid_coords),
                "unique_places": len(all_results),
                "grid_metadata": grid_data,
                "places": list(all_results.values())
            }

        except Exception as e:
            logger.error(f"Grid search error: {e}")
            return {"error": True, "message": str(e)}

    async def bounding_box_search(
        self,
        query: str,
        north_lat: float,
        south_lat: float,
        east_lng: float,
        west_lng: float,
        grid_density: int = 5,
        max_results_per_point: int = 10,
        language: str = "en",
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Search within a bounding box by creating a grid.

        Args:
            query: Search query
            north_lat: Top boundary (max latitude)
            south_lat: Bottom boundary (min latitude)
            east_lng: Right boundary (max longitude)
            west_lng: Left boundary (min longitude)
            grid_density: Points per side for grid
            max_results_per_point: Max results per grid point
            language: Language code
            timeout: Optional timeout

        Returns:
            Aggregated results with grid metadata
        """
        try:
            # Calculate center and radius
            center_lat = (north_lat + south_lat) / 2
            center_lng = (east_lng + west_lng) / 2

            # Calculate radius from center to corner (in km)
            lat_diff = abs(north_lat - south_lat) / 2
            lng_diff = abs(east_lng - west_lng) / 2

            # Convert to km (approximate)
            lat_km = lat_diff * 111.32
            lng_km = lng_diff * 111.32 * math.cos(math.radians(center_lat))
            radius_km = max(lat_km, lng_km)

            return await self.grid_search(
                query=query,
                center_lat=center_lat,
                center_lng=center_lng,
                radius_km=radius_km,
                grid_size=grid_density,
                max_results_per_point=max_results_per_point,
                language=language,
                timeout=timeout
            )

        except Exception as e:
            logger.error(f"Bounding box search error: {e}")
            return {"error": True, "message": str(e)}

    async def location_search(
        self,
        query: str,
        location: str,
        radius_km: float = 5.0,
        grid_size: int = 5,
        max_results_per_point: int = 10,
        language: str = "en",
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Search using a location name instead of coordinates.

        Resolves location names (city, address, ZIP) to coordinates
        using geocoding, then performs a grid search.

        Args:
            query: Search query (e.g., "restaurants")
            location: Location name (e.g., "Portland, OR", "97027", "123 Main St")
            radius_km: Search radius in km
            grid_size: Grid dimension for comprehensive coverage
            max_results_per_point: Max results per grid point
            language: Language code
            timeout: Optional timeout

        Returns:
            Aggregated results with grid metadata
        """
        try:
            await self._ensure_initialized()

            # First, geocode the location
            geocode_result = await self.geocode(location, language=language)

            if geocode_result.get("error"):
                return geocode_result

            coords = geocode_result.get("coordinates", {})
            lat = coords.get("latitude")
            lng = coords.get("longitude")

            if not lat or not lng:
                return {"error": True, "message": f"Could not resolve location: {location}"}

            # Perform grid search with resolved coordinates
            result = await self.grid_search(
                query=query,
                center_lat=float(lat),
                center_lng=float(lng),
                radius_km=radius_km,
                grid_size=grid_size,
                max_results_per_point=max_results_per_point,
                language=language,
                timeout=timeout
            )

            # Add location resolution info to result
            if not result.get("error"):
                result["resolved_location"] = {
                    "input": location,
                    "resolved_address": geocode_result.get("address"),
                    "latitude": lat,
                    "longitude": lng
                }

            return result

        except Exception as e:
            logger.error(f"Location search error: {e}")
            return {"error": True, "message": str(e)}

    async def get_place_reviews(
        self,
        place_id: str,
        sort_by: str = "most_relevant",
        limit: int = 50,
        offset: int = 0,
        min_rating: Optional[int] = None,
        include_owner_responses: bool = True
    ) -> Dict[str, Any]:
        """
        Get reviews for a place.

        Currently returns reviews from the main place data.
        Full pagination would require additional scraping.
        """
        try:
            await self._ensure_initialized()

            # Get place data first
            place_result = await self.get_place_by_id(place_id)

            if place_result.get("error"):
                return place_result

            place = place_result.get("place", {})

            return {
                "total_reviews": place.get("review_count") or 0,
                "average_rating": place.get("rating"),
                "reviews": place.get("reviews") or [],
                "review_summary": place.get("review_summary"),
                "review_topics": place.get("review_topics"),
                "has_more": False,
                "message": "Full review pagination requires place-specific scraping"
            }

        except Exception as e:
            logger.error(f"Get reviews error: {e}")
            return {"error": True, "message": str(e)}

    async def get_place_photos(
        self,
        place_id: str,
        max_photos: int = 20,
        size: str = "large",
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get photos for a place.

        Returns photos extracted during place scraping.
        """
        try:
            await self._ensure_initialized()

            # Get place data
            place_result = await self.get_place_by_id(place_id)

            if place_result.get("error"):
                return place_result

            place = place_result.get("place", {})
            photos = place.get("photos") or []

            # Apply size transformation
            size_map = {
                "thumbnail": "=w100-h100",
                "medium": "=w400-h300",
                "large": "=w800-h600",
                "original": "=w0"
            }
            size_suffix = size_map.get(size, "=w800-h600")

            sized_photos = []
            for photo_url in photos[:max_photos]:
                if "googleusercontent.com" in photo_url:
                    # Replace size in URL
                    import re
                    new_url = re.sub(r'=w\d+-h\d+', size_suffix, photo_url)
                    sized_photos.append({"url": new_url})
                else:
                    sized_photos.append({"url": photo_url})

            return {
                "total_photos": len(photos),
                "photos": sized_photos
            }

        except Exception as e:
            logger.error(f"Get photos error: {e}")
            return {"error": True, "message": str(e)}

    async def get_place_qa(
        self,
        place_id: str,
        limit: int = 20,
        include_answers: bool = True
    ) -> Dict[str, Any]:
        """
        Get Q&A for a place.

        Note: Q&A extraction requires navigating to the Q&A tab.
        Currently returns placeholder - full implementation would need
        additional scraping logic.
        """
        try:
            await self._ensure_initialized()

            return {
                "total_questions": 0,
                "questions": [],
                "message": "Q&A extraction requires dedicated scraping implementation"
            }

        except Exception as e:
            logger.error(f"Get Q&A error: {e}")
            return {"error": True, "message": str(e)}

    async def autocomplete(
        self,
        input: str,
        types: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        radius_meters: Optional[int] = None,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Get place autocomplete suggestions.

        Note: This would require integration with Google's autocomplete
        or scraping the autocomplete dropdown.
        """
        try:
            await self._ensure_initialized()

            # Perform a quick search and return top results as suggestions
            result = await self.search_and_wait(
                query=input,
                language=language,
                max_results=5,
                geo_coordinates=f"{latitude},{longitude}" if latitude and longitude else None,
                timeout=30
            )

            if result.get("error"):
                return result

            predictions = []
            for place in result.get("results", [])[:5]:
                predictions.append({
                    "description": f"{place.get('title', '')} - {place.get('address', '')}",
                    "place_id": place.get("cid"),
                    "main_text": place.get("title", ""),
                    "secondary_text": place.get("address", "")
                })

            return {"predictions": predictions}

        except Exception as e:
            logger.error(f"Autocomplete error: {e}")
            return {"error": True, "message": str(e)}

    async def bulk_search(
        self,
        queries: List[str],
        language: str = "en",
        max_results_per_query: int = 10
    ) -> Dict[str, Any]:
        """
        Execute multiple search queries.

        Args:
            queries: List of search queries
            language: Language code
            max_results_per_query: Max results per query

        Returns:
            Combined results
        """
        try:
            await self._ensure_initialized()

            results = []
            successful = 0
            failed = 0

            for query in queries:
                try:
                    result = await self.search_and_wait(
                        query=query,
                        language=language,
                        max_results=max_results_per_query,
                        timeout=120
                    )

                    if result.get("error"):
                        failed += 1
                        results.append({
                            "query": query,
                            "success": False,
                            "error": result.get("message"),
                            "places": []
                        })
                    else:
                        successful += 1
                        places = result.get("results", [])
                        results.append({
                            "query": query,
                            "success": True,
                            "count": len(places),
                            "places": self.process_place_data(places)
                        })

                except Exception as e:
                    failed += 1
                    results.append({
                        "query": query,
                        "success": False,
                        "error": str(e),
                        "places": []
                    })

            return {
                "results": results,
                "successful_queries": successful,
                "failed_queries": failed
            }

        except Exception as e:
            logger.error(f"Bulk search error: {e}")
            return {"error": True, "message": str(e)}

    async def get_review_analytics(
        self,
        place_id: str,
        time_period: str = "all",
        include_sentiment: bool = True,
        include_trends: bool = True,
        include_keywords: bool = True
    ) -> Dict[str, Any]:
        """
        Get analytics for a place's reviews.

        Returns analysis based on available review data.
        """
        try:
            await self._ensure_initialized()

            # Get place data
            place_result = await self.get_place_by_id(place_id)

            if place_result.get("error"):
                return place_result

            place = place_result.get("place", {})

            analytics = {
                "rating_distribution": place.get("review_summary") or {},
                "average_rating": place.get("rating"),
                "total_reviews": place.get("review_count"),
                "keywords": place.get("review_topics") or []
            }

            if include_sentiment:
                # Simple sentiment based on rating
                rating = place.get("rating") or 0
                if rating >= 4.0:
                    analytics["overall_sentiment"] = "positive"
                elif rating >= 3.0:
                    analytics["overall_sentiment"] = "neutral"
                else:
                    analytics["overall_sentiment"] = "negative"

            return {"analytics": analytics}

        except Exception as e:
            logger.error(f"Analytics error: {e}")
            return {"error": True, "message": str(e)}

    async def analyze_competitors(
        self,
        latitude: float,
        longitude: float,
        category: str,
        radius_meters: int = 2000,
        max_competitors: int = 10
    ) -> Dict[str, Any]:
        """
        Find and analyze competitors in an area.
        """
        try:
            await self._ensure_initialized()

            # Search for businesses in the category
            result = await self.nearby_search(
                latitude=latitude,
                longitude=longitude,
                radius_meters=radius_meters,
                query=category,
                max_results=max_competitors
            )

            if result.get("error"):
                return result

            places = result.get("places", [])
            processed = self.process_place_data(places) if places else []

            # Calculate summary statistics
            ratings = [float(p.get("rating")) for p in processed if p.get("rating")]
            review_counts = []
            for p in processed:
                rc = p.get("review_count")
                if rc:
                    try:
                        review_counts.append(int(str(rc).replace(",", "")))
                    except (ValueError, TypeError):
                        pass

            def get_rating(x):
                try:
                    return float(x.get("rating") or 0)
                except (ValueError, TypeError):
                    return 0

            def get_review_count(x):
                try:
                    return int(str(x.get("review_count") or 0).replace(",", ""))
                except (ValueError, TypeError):
                    return 0

            summary = {
                "total_competitors": len(processed),
                "average_rating": sum(ratings) / len(ratings) if ratings else None,
                "total_reviews": sum(review_counts) if review_counts else 0,
                "highest_rated": max(processed, key=get_rating).get("name") if processed else None,
                "most_reviewed": max(processed, key=get_review_count).get("name") if processed else None
            }

            return {
                "competitors": processed,
                "summary": summary
            }

        except Exception as e:
            logger.error(f"Competitor analysis error: {e}")
            return {"error": True, "message": str(e)}

    async def create_monitor(
        self,
        place_id: Optional[str] = None,
        url: Optional[str] = None,
        webhook_url: Optional[str] = None,
        check_interval_hours: int = 24,
        track_fields: List[str] = None
    ) -> Dict[str, Any]:
        """
        Create a monitor for a place.

        Note: Full implementation would require background task scheduling
        and persistent storage.
        """
        try:
            await self._ensure_initialized()

            import uuid
            from datetime import timedelta

            monitor_id = str(uuid.uuid4())

            return {
                "monitor_id": monitor_id,
                "place_id": place_id,
                "status": "active",
                "next_check": (datetime.now() + timedelta(hours=check_interval_hours)).isoformat(),
                "message": "Monitor created. Note: Full monitoring requires background scheduler."
            }

        except Exception as e:
            logger.error(f"Create monitor error: {e}")
            return {"error": True, "message": str(e)}

    async def list_monitors(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """List all monitors."""
        return {"monitors": [], "total": 0, "message": "Monitor storage not implemented"}

    async def get_monitor(
        self,
        monitor_id: str,
        include_history: bool = True
    ) -> Dict[str, Any]:
        """Get monitor details."""
        return {"error": True, "status_code": 404, "message": "Monitor not found"}

    async def delete_monitor(self, monitor_id: str) -> Dict[str, Any]:
        """Delete a monitor."""
        return {"error": True, "status_code": 404, "message": "Monitor not found"}

    async def register_webhook(
        self,
        url: str,
        events: List[str],
        secret: Optional[str] = None
    ) -> Dict[str, Any]:
        """Register a webhook."""
        import uuid
        return {
            "webhook_id": str(uuid.uuid4()),
            "message": "Webhook registered. Note: Full webhook delivery requires background processing."
        }

    async def list_webhooks(self) -> Dict[str, Any]:
        """List registered webhooks."""
        return {"webhooks": [], "message": "Webhook storage not implemented"}

    async def delete_webhook(self, webhook_id: str) -> Dict[str, Any]:
        """Delete a webhook."""
        return {"error": True, "status_code": 404, "message": "Webhook not found"}

    async def get_directions(
        self,
        origin_lat: float,
        origin_lng: float,
        destination_lat: float,
        destination_lng: float,
        mode: str = "driving",
        alternatives: bool = False,
        avoid: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get directions between two points.

        Note: Full implementation would require scraping Google Maps directions
        or using the Directions API.
        """
        try:
            await self._ensure_initialized()

            # Calculate approximate distance
            from math import radians, sin, cos, sqrt, atan2

            lat1, lon1 = radians(origin_lat), radians(origin_lng)
            lat2, lon2 = radians(destination_lat), radians(destination_lng)

            dlat = lat2 - lat1
            dlon = lon2 - lon1

            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * atan2(sqrt(a), sqrt(1-a))
            distance_km = 6371 * c

            # Estimate duration based on mode
            speeds = {"driving": 50, "walking": 5, "bicycling": 15, "transit": 30}
            speed = speeds.get(mode, 50)
            duration_hours = distance_km / speed

            return {
                "routes": [{
                    "summary": f"{mode.title()} route",
                    "distance": f"{distance_km:.1f} km",
                    "duration": f"{int(duration_hours * 60)} mins",
                    "steps": [],
                    "message": "Approximate calculation. Full directions require Maps Directions API."
                }]
            }

        except Exception as e:
            logger.error(f"Directions error: {e}")
            return {"error": True, "message": str(e)}

    async def get_streetview(
        self,
        place_id: str,
        width: int = 640,
        height: int = 480,
        heading: Optional[int] = None,
        pitch: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get Street View images for a place.

        Note: Full implementation would require Street View API integration.
        """
        try:
            await self._ensure_initialized()

            # Get place to get coordinates
            place_result = await self.get_place_by_id(place_id)

            if place_result.get("error"):
                return place_result

            place = place_result.get("place", {})

            if place.get("latitude") and place.get("longitude"):
                return {
                    "available": True,
                    "images": [],
                    "message": "Street View image URLs require Google Street View API integration"
                }

            return {
                "available": False,
                "images": [],
                "message": "Coordinates not available for Street View"
            }

        except Exception as e:
            logger.error(f"Street View error: {e}")
            return {"error": True, "message": str(e)}

    async def extract_menu(
        self,
        place_id: str,
        include_prices: bool = True,
        include_descriptions: bool = True,
        categorize: bool = True
    ) -> Dict[str, Any]:
        """
        Extract menu from a place.

        Note: Full menu extraction would require navigating to the menu tab
        and scraping menu items.
        """
        try:
            await self._ensure_initialized()

            # Get place to check for menu link
            place_result = await self.get_place_by_id(place_id)

            if place_result.get("error"):
                return place_result

            place = place_result.get("place", {})
            menu_link = place.get("menu_link")

            return {
                "menu_available": bool(menu_link),
                "menu_link": menu_link,
                "menu": [],
                "categories": [],
                "message": "Full menu extraction requires dedicated scraping of menu pages"
            }

        except Exception as e:
            logger.error(f"Menu extraction error: {e}")
            return {"error": True, "message": str(e)}

    async def batch_geocode(
        self,
        addresses: List[str]
    ) -> Dict[str, Any]:
        """
        Geocode multiple addresses.

        Uses Google Maps search to find coordinates for addresses.
        """
        try:
            await self._ensure_initialized()

            results = []
            successful = 0
            failed = 0

            for address in addresses:
                try:
                    # Search for the address
                    result = await self.search_and_wait(
                        query=address,
                        max_results=1,
                        timeout=30
                    )

                    if result.get("error") or not result.get("results"):
                        failed += 1
                        results.append({
                            "address": address,
                            "success": False,
                            "error": "Address not found"
                        })
                    else:
                        successful += 1
                        place = result["results"][0]
                        results.append({
                            "address": address,
                            "success": True,
                            "latitude": place.get("latitude"),
                            "longitude": place.get("longitude"),
                            "formatted_address": place.get("address"),
                            "place_id": place.get("cid")
                        })

                except Exception as e:
                    failed += 1
                    results.append({
                        "address": address,
                        "success": False,
                        "error": str(e)
                    })

            return {
                "results": results,
                "successful": successful,
                "failed": failed
            }

        except Exception as e:
            logger.error(f"Geocode error: {e}")
            return {"error": True, "message": str(e)}

    async def get_place_attributes(
        self,
        place_id: str
    ) -> Dict[str, Any]:
        """
        Get detailed attributes for a place.

        Returns attributes from the main place data.
        """
        try:
            await self._ensure_initialized()

            # Get place data
            place_result = await self.get_place_by_id(place_id)

            if place_result.get("error"):
                return place_result

            place = place_result.get("place", {})

            attributes = {
                "service_options": place.get("service_options") or [],
                "accessibility": place.get("accessibility") or [],
                "amenities": place.get("amenities") or [],
                "highlights": place.get("description"),
                "price_level": place.get("price_level"),
                "price_per_person": place.get("price_per_person")
            }

            return {"attributes": attributes}

        except Exception as e:
            logger.error(f"Get attributes error: {e}")
            return {"error": True, "message": str(e)}

    async def get_place_history(
        self,
        place_id: str,
        field: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get historical data for a place.

        Note: Requires active monitor with historical data storage.
        """
        return {
            "history": [],
            "message": "Historical data requires active monitor with persistent storage"
        }

    async def check_availability(
        self,
        place_id: str,
        date: str,
        party_size: int
    ) -> Dict[str, Any]:
        """
        Check reservation availability.

        Note: Would require integration with Reserve with Google.
        """
        try:
            await self._ensure_initialized()

            # Get place to check for reserve link
            place_result = await self.get_place_by_id(place_id)

            if place_result.get("error"):
                return place_result

            place = place_result.get("place", {})
            reserve_link = place.get("reserve_link")

            return {
                "reservations_available": bool(reserve_link),
                "booking_url": reserve_link,
                "time_slots": [],
                "message": "Real-time availability requires Reserve with Google integration"
            }

        except Exception as e:
            logger.error(f"Check availability error: {e}")
            return {"error": True, "message": str(e)}


# Singleton instance
google_maps_service = GoogleMapsService()
