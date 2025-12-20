"""
DataForSEO Client for Google Maps data.

Provides access to:
- Google Maps SERP API (search)
- Google My Business Info API (details)
- Google Reviews API (reviews)

Uses httpx for async HTTP requests instead of the synchronous dataforseo-client library.

Features:
- Redis caching for API responses (1 hour TTL)
- Batch request queuing (up to 10 requests per batch)
- Background polling for async review tasks
"""

import os
import base64
import httpx
import logging
from typing import Optional, Dict, Any, List

from app.api.google_maps.dataforseo_cache import (
    dataforseo_cache,
    CACHE_TTL_SEARCH,
    CACHE_TTL_DETAILS,
    CACHE_TTL_REVIEWS
)
from app.api.google_maps.dataforseo_batch import (
    batch_queue_manager,
    RequestType,
    BATCH_SIZE_THRESHOLD
)
from app.api.google_maps.dataforseo_tasks import reviews_task_manager

logger = logging.getLogger("uvicorn")

# DataForSEO API base URL
DATAFORSEO_API_BASE = "https://api.dataforseo.com/v3"


class DataForSEOClient:
    """
    Async client for DataForSEO APIs.

    Uses httpx for direct async HTTP requests.
    """

    def __init__(self, login: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize the DataForSEO client.

        Args:
            login: DataForSEO login (email). Defaults to DATAFORSEO_LOGIN env var.
            password: DataForSEO password. Defaults to DATAFORSEO_PASSWORD env var.
        """
        self.login = login or os.getenv("DATAFORSEO_LOGIN")
        self.password = password or os.getenv("DATAFORSEO_PASSWORD")

        if not self.login or not self.password:
            raise ValueError(
                "DataForSEO credentials required. Set DATAFORSEO_LOGIN and "
                "DATAFORSEO_PASSWORD environment variables."
            )

        # Check for placeholder values
        if "your_dataforseo" in self.login.lower() or "your_dataforseo" in self.password.lower():
            raise ValueError(
                "DataForSEO credentials not configured. Please update DATAFORSEO_LOGIN "
                "and DATAFORSEO_PASSWORD with your actual credentials."
            )

        # Create auth header
        auth_str = f"{self.login}:{self.password}"
        auth_bytes = base64.b64encode(auth_str.encode()).decode()
        self._auth_header = f"Basic {auth_bytes}"

        # Shared HTTP client
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": self._auth_header
                }
            )
        return self._client

    async def _request(self, method: str, endpoint: str, data: Any = None) -> Dict[str, Any]:
        """Make an API request."""
        client = await self._get_client()
        url = f"{DATAFORSEO_API_BASE}{endpoint}"

        try:
            if method.upper() == "GET":
                response = await client.get(url)
            else:
                response = await client.post(url, json=data)

            response.raise_for_status()
            return response.json()

        except httpx.TimeoutException:
            logger.error(f"DataForSEO request timeout: {endpoint}")
            raise Exception("Request timeout")
        except httpx.HTTPStatusError as e:
            logger.error(f"DataForSEO HTTP error: {e.response.status_code}")
            raise Exception(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"DataForSEO request error: {e}")
            raise

    async def search_places(
        self,
        query: str,
        location: Optional[str] = None,
        location_code: Optional[int] = None,
        language_code: str = "en",
        depth: int = 20,
        skip_cache: bool = False
    ) -> Dict[str, Any]:
        """
        Search for places using Google Maps SERP API.

        Args:
            query: Search query (e.g., "restaurants", "hotels near me")
            location: Location name (e.g., "New York, NY, USA") - optional
            location_code: DataForSEO location code (e.g., 1023191 for NYC) - preferred
            language_code: Language code (default: "en")
            depth: Number of results to return (default: 20)
            skip_cache: If True, bypass cache and fetch fresh data

        Returns:
            Dict with search results
        """
        # Check cache first
        if not skip_cache:
            cached = await dataforseo_cache.get_cached_search(
                query, location, location_code, language_code, depth
            )
            if cached is not None:
                cached["from_cache"] = True
                logger.debug(f"Cache hit for search: {query}")
                return cached

        try:
            # Build request - prefer location_code over location_name
            request_data = {
                "keyword": query,
                "language_code": language_code,
                "depth": depth
            }

            if location_code:
                request_data["location_code"] = location_code
            elif location:
                request_data["location_name"] = location
            else:
                # Default to USA location code
                request_data["location_code"] = 2840

            response = await self._request(
                "POST",
                "/serp/google/maps/live/advanced",
                [request_data]
            )

            # Parse response
            if response.get("status_code") != 20000:
                raise Exception(f"API error: {response.get('status_message')}")

            results = []
            tasks = response.get("tasks", [])
            if tasks and len(tasks) > 0:
                task = tasks[0]
                if task.get("status_code") != 20000:
                    raise Exception(f"Task error: {task.get('status_message')}")

                task_results = task.get("result", [])
                if task_results and len(task_results) > 0:
                    items = task_results[0].get("items", [])
                    for place in items:
                        results.append(self._parse_search_result(place))

            result = {
                "success": True,
                "query": query,
                "location": location,
                "location_code": location_code,
                "total_results": len(results),
                "results": results,
                "cost": response.get("cost"),
                "from_cache": False
            }

            # Cache the result
            await dataforseo_cache.set_cached_search(
                result, query, location, location_code, language_code, depth
            )

            return result

        except Exception as e:
            logger.error(f"DataForSEO search error: {e}")
            return {
                "success": False,
                "query": query,
                "location": location,
                "error": str(e),
                "results": [],
                "from_cache": False
            }

    def _parse_search_result(self, item: Dict) -> Dict[str, Any]:
        """Parse a single search result item."""
        result = {
            "place_id": item.get("place_id"),
            "cid": item.get("cid"),
            "name": item.get("title", ""),
            "address": item.get("address", ""),
            "rating": None,
            "reviews_count": None,
            "category": item.get("category"),
            "phone": item.get("phone"),
            "website": item.get("url"),
            "coordinates": None,
            "thumbnail": item.get("main_image"),
            "google_maps_url": None,
        }

        # Parse rating
        rating = item.get("rating")
        if rating:
            result["rating"] = rating.get("value")
            result["reviews_count"] = rating.get("votes_count")

        # Parse coordinates
        lat = item.get("latitude")
        lng = item.get("longitude")
        if lat is not None and lng is not None:
            result["coordinates"] = {
                "latitude": lat,
                "longitude": lng
            }

        # Build Google Maps URL
        if result["place_id"]:
            result["google_maps_url"] = f"https://www.google.com/maps/place/?q=place_id:{result['place_id']}"
        elif result["cid"]:
            result["google_maps_url"] = f"https://www.google.com/maps?cid={result['cid']}"

        return result

    async def get_business_info(
        self,
        keyword: Optional[str] = None,
        place_id: Optional[str] = None,
        cid: Optional[str] = None,
        location: Optional[str] = None,
        location_code: Optional[int] = None,
        language_code: str = "en",
        skip_cache: bool = False
    ) -> Dict[str, Any]:
        """
        Get business details using Google My Business Info API (Live).

        Args:
            keyword: Business name to search for
            place_id: Google Place ID
            cid: Google CID
            location: Location name for context
            location_code: DataForSEO location code
            language_code: Language code (default: "en")
            skip_cache: If True, bypass cache and fetch fresh data

        Returns:
            Dict with business details
        """
        # Check cache first
        if not skip_cache:
            cached = await dataforseo_cache.get_cached_details(
                keyword, place_id, cid, location_code
            )
            if cached is not None:
                cached["from_cache"] = True
                logger.debug(f"Cache hit for details: {place_id or cid or keyword}")
                return cached

        try:
            # Build request - need at least one identifier
            request_data = {
                "language_code": language_code
            }

            # Set location
            if location_code:
                request_data["location_code"] = location_code
            elif location:
                request_data["location_name"] = location
            else:
                request_data["location_code"] = 2840  # Default to USA

            # Set keyword/identifier
            if place_id:
                request_data["keyword"] = f"place_id:{place_id}"
            elif cid:
                request_data["keyword"] = f"cid:{cid}"
            elif keyword:
                request_data["keyword"] = keyword
            else:
                raise ValueError("Must provide keyword, place_id, or cid")

            response = await self._request(
                "POST",
                "/business_data/google/my_business_info/live",
                [request_data]
            )

            # Parse response
            if response.get("status_code") != 20000:
                raise Exception(f"API error: {response.get('status_message')}")

            business = None
            tasks = response.get("tasks", [])
            if tasks and len(tasks) > 0:
                task = tasks[0]
                task_status = task.get("status_code")

                # 40102 = "No Search Results" - not an error, just no results
                if task_status == 40102:
                    return {
                        "success": True,
                        "place": None,
                        "cost": response.get("cost"),
                        "message": "No results found for the given search criteria"
                    }

                if task_status != 20000:
                    raise Exception(f"Task error: {task.get('status_message')}")

                task_results = task.get("result", [])
                if task_results and len(task_results) > 0:
                    # Check if items exist
                    result_data = task_results[0]
                    items = result_data.get("items")
                    if items and len(items) > 0:
                        business = self._parse_business_info(items[0])

            result = {
                "success": True,
                "place": business,
                "cost": response.get("cost"),
                "from_cache": False
            }

            # Cache the result
            await dataforseo_cache.set_cached_details(
                result, keyword, place_id, cid, location_code
            )

            return result

        except Exception as e:
            logger.error(f"DataForSEO business info error: {e}")
            return {
                "success": False,
                "error": str(e),
                "place": None,
                "from_cache": False
            }

    def _parse_business_info(self, item: Dict) -> Dict[str, Any]:
        """Parse business info response."""
        result = {
            "place_id": item.get("place_id"),
            "cid": item.get("cid"),
            "name": item.get("title", ""),
            "address": item.get("address", ""),
            "phone": item.get("phone"),
            "website": item.get("url"),
            "domain": item.get("domain"),
            "google_maps_url": None,
            "rating": None,
            "reviews_count": None,
            "category": item.get("category"),
            "categories": [],
            "coordinates": None,
            "plus_code": item.get("plus_code"),
            "opening_hours": None,
            "price_level": item.get("price_level"),
            "popular_times": item.get("popular_times"),
            "attributes": [],
            "photos": [],
            "description": item.get("description"),
            "is_claimed": item.get("is_claimed"),
            "local_business_links": item.get("local_business_links"),
        }

        # Parse rating
        rating = item.get("rating")
        if rating:
            result["rating"] = rating.get("value")
            result["reviews_count"] = rating.get("votes_count")

        # Parse rating distribution
        rating_dist = item.get("rating_distribution")
        if rating_dist:
            result["rating_distribution"] = {
                str(k): v for k, v in rating_dist.items()
                if str(k).isdigit()
            }

        # Parse coordinates
        lat = item.get("latitude")
        lng = item.get("longitude")
        if lat is not None and lng is not None:
            result["coordinates"] = {
                "latitude": lat,
                "longitude": lng
            }

        # Parse additional categories
        additional_cats = item.get("additional_categories")
        if result["category"]:
            result["categories"] = [result["category"]]
        if additional_cats:
            result["categories"].extend(additional_cats)

        # Parse opening hours
        work_time = item.get("work_time")
        if work_time:
            result["opening_hours"] = self._parse_work_time(work_time)

        # Parse attributes
        attributes = item.get("attributes")
        if attributes:
            result["attributes"] = self._parse_attributes(attributes)

        # Parse photos
        main_image = item.get("main_image")
        if main_image:
            result["photos"].append(main_image)
        logo = item.get("logo")
        if logo:
            result["photos"].append(logo)

        # Build Google Maps URL
        if result["place_id"]:
            result["google_maps_url"] = f"https://www.google.com/maps/place/?q=place_id:{result['place_id']}"
        elif result["cid"]:
            result["google_maps_url"] = f"https://www.google.com/maps?cid={result['cid']}"

        return result

    def _parse_work_time(self, work_time: Dict) -> Optional[Dict[str, Any]]:
        """Parse work time / opening hours."""
        hours = {}
        timetable = work_time.get("timetable")
        if timetable:
            day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            for day in day_names:
                times = timetable.get(day)
                if times and isinstance(times, list) and len(times) > 0:
                    first_slot = times[0]
                    open_time = first_slot.get("open", {}).get("time", "")
                    close_time = first_slot.get("close", {}).get("time", "")
                    hours[day] = f"{open_time} - {close_time}"

        current_status = work_time.get("current_status")
        if current_status:
            hours["is_open_now"] = current_status == "open"

        return hours if hours else None

    def _parse_attributes(self, attributes: Any) -> List[str]:
        """Parse business attributes."""
        result = []
        if isinstance(attributes, dict):
            for category, items in attributes.items():
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            name = item.get("name", item.get("attribute", ""))
                            if name:
                                result.append(name)
                        elif isinstance(item, str):
                            result.append(item)
        return result

    async def submit_reviews_task(
        self,
        keyword: Optional[str] = None,
        place_id: Optional[str] = None,
        cid: Optional[str] = None,
        location: Optional[str] = None,
        location_code: Optional[int] = None,
        language_code: str = "en",
        depth: int = 100,
        sort_by: str = "newest"
    ) -> Dict[str, Any]:
        """
        Submit a reviews collection task (async).

        Args:
            keyword: Business name
            place_id: Google Place ID
            cid: Google CID
            location: Location name
            location_code: DataForSEO location code
            language_code: Language code
            depth: Number of reviews to collect (max 4490)
            sort_by: Sort order (newest, highest_rating, lowest_rating, relevant)

        Returns:
            Dict with task_id for later retrieval
        """
        try:
            # Map sort options
            sort_map = {
                "newest": "newest",
                "highest": "highest_rating",
                "lowest": "lowest_rating",
                "relevant": "relevant"
            }

            # Build request
            request_data = {
                "language_code": language_code,
                "depth": min(depth, 4490),
                "sort_by": sort_map.get(sort_by, "newest")
            }

            # Set location
            if location_code:
                request_data["location_code"] = location_code
            elif location:
                request_data["location_name"] = location
            else:
                request_data["location_code"] = 2840

            # Set keyword/identifier
            if place_id:
                request_data["keyword"] = f"place_id:{place_id}"
            elif cid:
                request_data["keyword"] = f"cid:{cid}"
            elif keyword:
                request_data["keyword"] = keyword
            else:
                raise ValueError("Must provide keyword, place_id, or cid")

            response = await self._request(
                "POST",
                "/business_data/google/reviews/task_post",
                [request_data]
            )

            # Parse response
            if response.get("status_code") != 20000:
                raise Exception(f"API error: {response.get('status_message')}")

            task_id = None
            tasks = response.get("tasks", [])
            if tasks and len(tasks) > 0:
                task = tasks[0]
                task_id = task.get("id")

            if not task_id:
                raise Exception("No task ID returned")

            # Track the task for background polling
            await reviews_task_manager.track_task(
                task_id=task_id,
                place_id=place_id,
                cid=cid,
                keyword=keyword
            )

            return {
                "success": True,
                "task_id": task_id,
                "status": "pending",
                "message": "Task submitted. Use GET /reviews/{task_id} to retrieve results.",
                "cost": response.get("cost")
            }

        except Exception as e:
            logger.error(f"DataForSEO reviews submit error: {e}")
            return {
                "success": False,
                "error": str(e),
                "task_id": None
            }

    async def get_reviews_task(self, task_id: str, skip_cache: bool = False) -> Dict[str, Any]:
        """
        Get results for a reviews collection task.

        Args:
            task_id: Task ID from submit_reviews_task
            skip_cache: If True, bypass cache and fetch from API

        Returns:
            Dict with reviews data or task status
        """
        # Check cache first (completed tasks are cached)
        if not skip_cache:
            cached = await dataforseo_cache.get_cached_reviews(task_id)
            if cached is not None:
                cached["from_cache"] = True
                logger.debug(f"Cache hit for reviews task: {task_id}")
                return cached

        try:
            response = await self._request(
                "GET",
                f"/business_data/google/reviews/task_get/{task_id}"
            )

            # Parse response
            status_code = response.get("status_code")
            if status_code != 20000:
                # Check if task is still processing
                if status_code == 40602:
                    return {
                        "success": True,
                        "task_id": task_id,
                        "status": "processing",
                        "message": "Task is still processing. Try again in a few seconds."
                    }
                raise Exception(f"API error: {response.get('status_message')}")

            # Parse results
            result = {
                "success": True,
                "task_id": task_id,
                "status": "completed",
                "place_id": None,
                "place_name": None,
                "total_reviews": 0,
                "average_rating": None,
                "rating_distribution": {},
                "reviews": [],
                "cost": response.get("cost")
            }

            tasks = response.get("tasks", [])
            if tasks and len(tasks) > 0:
                task = tasks[0]
                task_results = task.get("result", [])
                if task_results and len(task_results) > 0:
                    item = task_results[0]

                    result["place_id"] = item.get("place_id")
                    result["place_name"] = item.get("title")
                    result["total_reviews"] = item.get("reviews_count", 0)

                    # Parse rating
                    rating = item.get("rating")
                    if rating:
                        result["average_rating"] = rating.get("value")

                    # Parse rating distribution
                    rating_dist = item.get("rating_distribution")
                    if rating_dist:
                        for star in ["1", "2", "3", "4", "5"]:
                            result["rating_distribution"][star] = rating_dist.get(star, 0) or 0

                    # Parse reviews
                    items = item.get("items", [])
                    for review in items:
                        result["reviews"].append(self._parse_review(review))

            # Cache completed results
            result["from_cache"] = False
            await dataforseo_cache.set_cached_reviews(task_id, result)

            return result

        except Exception as e:
            logger.error(f"DataForSEO reviews get error: {e}")
            return {
                "success": False,
                "task_id": task_id,
                "status": "error",
                "error": str(e)
            }

    def _parse_review(self, item: Dict) -> Dict[str, Any]:
        """Parse a single review item."""
        review = {
            "review_id": item.get("review_id"),
            "author": {
                "name": item.get("profile_name", "Anonymous"),
                "profile_url": item.get("profile_url"),
                "photo_url": item.get("profile_image_url"),
                "reviews_count": item.get("reviews_count"),
                "photos_count": item.get("photos_count"),
                "is_local_guide": item.get("local_guide", False),
                "local_guide_level": None,
            },
            "rating": None,
            "text": item.get("review_text"),
            "original_text": item.get("original_review_text"),
            "time_ago": item.get("time_ago"),
            "published_date": item.get("timestamp"),
            "likes": 0,
            "response": item.get("owner_answer"),
            "response_time": item.get("owner_timestamp"),
            "photos": [],
            "review_url": item.get("review_url"),
        }

        # Parse rating
        rating = item.get("rating")
        if rating:
            if isinstance(rating, dict):
                review["rating"] = rating.get("value")
                review["likes"] = rating.get("votes_count", 0) or 0
            else:
                review["rating"] = rating

        # Parse photos
        images = item.get("images")
        if images:
            for img in images:
                if isinstance(img, dict):
                    url = img.get("url", img.get("image_url"))
                    if url:
                        review["photos"].append(url)
                elif isinstance(img, str):
                    review["photos"].append(img)

        return review

    async def check_reviews_task_ready(self) -> List[str]:
        """
        Check which review tasks are ready.

        Returns:
            List of task IDs that are ready
        """
        try:
            response = await self._request(
                "GET",
                "/business_data/google/reviews/tasks_ready"
            )

            ready_tasks = []
            tasks = response.get("tasks", [])
            for task in tasks:
                task_results = task.get("result", [])
                for item in task_results:
                    task_id = item.get("id")
                    if task_id:
                        ready_tasks.append(task_id)

            return ready_tasks

        except Exception as e:
            logger.error(f"DataForSEO tasks ready error: {e}")
            return []

    async def close(self):
        """Close the API client."""
        if self._client:
            try:
                await self._client.aclose()
            except Exception:
                pass
            self._client = None

    async def start_background_tasks(self):
        """Start background tasks (review polling, etc.)."""
        await reviews_task_manager.start(self)
        logger.info("DataForSEO background tasks started")

    async def stop_background_tasks(self):
        """Stop background tasks."""
        await reviews_task_manager.stop()
        logger.info("DataForSEO background tasks stopped")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return dataforseo_cache.get_stats()

    def get_batch_stats(self) -> Dict[str, Any]:
        """Get batch queue statistics."""
        return batch_queue_manager.get_all_stats()

    def get_task_stats(self) -> Dict[str, Any]:
        """Get review task manager statistics."""
        return reviews_task_manager.get_stats()

    def get_all_stats(self) -> Dict[str, Any]:
        """Get all statistics (cache, batch, tasks)."""
        return {
            "cache": self.get_cache_stats(),
            "batch_queues": self.get_batch_stats(),
            "review_tasks": self.get_task_stats()
        }


# Singleton instance
_client: Optional[DataForSEOClient] = None
_client_error: Optional[str] = None


def get_dataforseo_client() -> DataForSEOClient:
    """Get the DataForSEO client singleton."""
    global _client, _client_error

    # If we previously failed to create client, raise the cached error
    if _client_error:
        raise ValueError(_client_error)

    if _client is None:
        try:
            _client = DataForSEOClient()
        except ValueError as e:
            _client_error = str(e)
            raise

    return _client


def reset_dataforseo_client():
    """Reset the client singleton (useful for testing or credential updates)."""
    global _client, _client_error
    _client = None
    _client_error = None
