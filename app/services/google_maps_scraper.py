"""
Native Google Maps Scraper using Playwright.

This module provides direct Google Maps scraping without requiring
the gosom Docker sidecar. It uses Playwright for browser automation.
"""
import asyncio
import logging
import re
import json
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Status of a scraping job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ScrapeJob:
    """Represents a scraping job."""
    id: str
    name: str
    query: str
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    results: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    progress: int = 0
    total: int = 0

    # Job parameters
    language: str = "en"
    max_results: int = 20
    zoom: int = 15
    geo_coordinates: Optional[str] = None
    email_extraction: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "ID": self.id,  # gosom compatibility
            "name": self.name,
            "Name": self.name,
            "query": self.query,
            "status": self.status.value,
            "Status": "ok" if self.status == JobStatus.COMPLETED else self.status.value,
            "created_at": self.created_at.isoformat(),
            "Date": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress": self.progress,
            "total": self.total,
            "error": self.error,
            "Data": {
                "keywords": [self.query],
                "lang": self.language,
                "zoom": self.zoom,
            }
        }


class JobStore:
    """In-memory job storage with thread-safe access."""

    def __init__(self):
        self._jobs: Dict[str, ScrapeJob] = {}
        self._lock = asyncio.Lock()

    async def create(self, job: ScrapeJob) -> ScrapeJob:
        """Create a new job."""
        async with self._lock:
            self._jobs[job.id] = job
            return job

    async def get(self, job_id: str) -> Optional[ScrapeJob]:
        """Get a job by ID."""
        async with self._lock:
            return self._jobs.get(job_id)

    async def update(self, job: ScrapeJob) -> ScrapeJob:
        """Update a job."""
        async with self._lock:
            self._jobs[job.id] = job
            return job

    async def delete(self, job_id: str) -> bool:
        """Delete a job."""
        async with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                return True
            return False

    async def list_all(self, status: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[ScrapeJob]:
        """List all jobs with optional filtering."""
        async with self._lock:
            jobs = list(self._jobs.values())
            if status:
                jobs = [j for j in jobs if j.status.value == status]
            # Sort by created_at descending
            jobs.sort(key=lambda x: x.created_at, reverse=True)
            return jobs[offset:offset + limit]


class GoogleMapsScraper:
    """
    Google Maps scraper using Playwright.

    Extracts business data including:
    - Name, address, phone, website
    - Ratings and reviews
    - Operating hours
    - Location coordinates
    - Category and price level
    """

    # Google Maps base URL
    MAPS_URL = "https://www.google.com/maps"
    SEARCH_URL = "https://www.google.com/maps/search/"

    def __init__(self, proxy: Optional[str] = None, headless: bool = True):
        """
        Initialize the scraper.

        Args:
            proxy: Optional proxy URL (e.g., "http://user:pass@host:port")
            headless: Run browser in headless mode
        """
        self.proxy = proxy
        self.headless = headless
        self._browser = None
        self._playwright = None

    async def _init_browser(self):
        """Initialize Playwright browser."""
        if self._browser is not None:
            return

        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()

        # Browser launch options
        launch_options = {
            "headless": self.headless,
            "args": [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--disable-gpu",
                "--window-size=1920,1080",
            ]
        }

        # Add proxy if configured
        if self.proxy:
            # Parse proxy URL to extract credentials if present
            # Format: http://user:pass@host:port or http://host:port
            from urllib.parse import urlparse
            parsed = urlparse(self.proxy)

            proxy_config = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}

            if parsed.username and parsed.password:
                proxy_config["username"] = parsed.username
                proxy_config["password"] = parsed.password

            launch_options["proxy"] = proxy_config
            logger.info(f"Using proxy: {parsed.hostname}:{parsed.port}")

        self._browser = await self._playwright.chromium.launch(**launch_options)
        logger.info("Browser initialized successfully")

    async def close(self):
        """Close the browser and cleanup."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("Browser closed")

    async def _create_page(self, language: str = "en"):
        """Create a new browser page with appropriate settings."""
        await self._init_browser()

        context = await self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale=language,
            timezone_id="America/Los_Angeles",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        page = await context.new_page()

        # Set extra headers to appear more legitimate
        await page.set_extra_http_headers({
            "Accept-Language": f"{language},en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        })

        return page, context

    async def search(
        self,
        query: str,
        language: str = "en",
        max_results: int = 20,
        zoom: int = 15,
        geo_coordinates: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search Google Maps for businesses.

        Args:
            query: Search query (e.g., "restaurants in New York")
            language: Language code
            max_results: Maximum number of results to return
            zoom: Map zoom level
            geo_coordinates: Optional coordinates "lat,lng"

        Returns:
            List of place dictionaries
        """
        page, context = await self._create_page(language)
        results = []

        try:
            # Build search URL
            search_query = query.replace(" ", "+")
            url = f"{self.SEARCH_URL}{search_query}"

            # Add coordinates if provided
            if geo_coordinates:
                try:
                    lat, lng = geo_coordinates.split(",")
                    url += f"/@{lat.strip()},{lng.strip()},{zoom}z"
                except ValueError:
                    logger.warning(f"Invalid geo_coordinates: {geo_coordinates}")

            logger.info(f"Searching Google Maps: {query}")
            logger.info(f"URL: {url}")

            # Navigate to search
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            logger.info("Page loaded (domcontentloaded)")

            # Wait for the page to be fully interactive
            await asyncio.sleep(3)

            # Accept cookies if dialog appears (multiple possible selectors)
            try:
                for selector in [
                    "button:has-text('Accept all')",
                    "button:has-text('Accept')",
                    "button:has-text('Alle akzeptieren')",
                    "[aria-label='Accept all']"
                ]:
                    accept_btn = page.locator(selector)
                    if await accept_btn.count() > 0:
                        await accept_btn.first.click()
                        logger.debug("Clicked cookie consent button")
                        await asyncio.sleep(2)
                        break
            except Exception as e:
                logger.debug(f"No cookie dialog or error: {e}")

            # Wait for results to load - try multiple selectors
            results_loaded = False
            for selector in [
                "div[role='feed']",
                "div[role='main'] div[jsaction*='mouseover']",
                "a[href*='/maps/place/']"
            ]:
                try:
                    await page.wait_for_selector(selector, timeout=10000)
                    results_loaded = True
                    logger.info(f"Found results with selector: {selector}")
                    break
                except Exception as e:
                    logger.info(f"Selector {selector} not found: {e}")
                    continue

            if not results_loaded:
                # Log page content for debugging
                title = await page.title()
                logger.warning(f"No results found. Page title: {title}")
                page_url = page.url
                logger.warning(f"Current URL: {page_url}")
                # Check for blocking/CAPTCHA
                if "sorry" in page_url.lower() or "consent" in page_url.lower():
                    logger.error("Possible blocking or CAPTCHA detected")

            # Check if we have a results list or a single place
            results_feed = page.locator("div[role='feed']")
            feed_count = await results_feed.count()
            logger.info(f"Results feed count: {feed_count}")

            if feed_count > 0:
                # We have a list of results - scroll to load more
                results = await self._extract_search_results(page, max_results)
            else:
                # Check for direct place links
                place_links = page.locator("a[href*='/maps/place/']")
                link_count = await place_links.count()
                logger.info(f"Direct place links count: {link_count}")

                if link_count > 0:
                    # Extract from place links
                    results = await self._extract_from_place_links(page, place_links, max_results)
                else:
                    # Single place result - extract directly
                    place_data = await self._extract_place_details(page)
                    if place_data:
                        results = [place_data]

            logger.info(f"Found {len(results)} places for query: {query}")

        except Exception as e:
            logger.error(f"Search error: {e}", exc_info=True)
            raise
        finally:
            await context.close()

        return results

    async def _extract_from_place_links(self, page, place_links, max_results: int) -> List[Dict[str, Any]]:
        """Extract places from direct place links on the page."""
        results = []
        seen_names = set()
        link_count = await place_links.count()

        for i in range(min(link_count, max_results)):
            try:
                link = place_links.nth(i)
                href = await link.get_attribute("href")
                name = await link.get_attribute("aria-label") or ""

                if not name or name in seen_names:
                    continue
                seen_names.add(name)

                # Click the link to get details
                await link.click()
                await asyncio.sleep(1.5)

                place_data = await self._extract_place_details(page)
                if place_data:
                    results.append(place_data)
                    logger.debug(f"Extracted: {place_data.get('title', 'Unknown')}")

                # Go back
                await page.go_back()
                await asyncio.sleep(1)

            except Exception as e:
                logger.debug(f"Error extracting link {i}: {e}")
                continue

        return results

    async def _extract_search_results(self, page, max_results: int) -> List[Dict[str, Any]]:
        """Extract places from search results list."""
        results = []
        seen_names = set()
        scroll_count = 0
        max_scrolls = max(5, max_results // 4)  # Estimate scrolls needed

        while len(results) < max_results and scroll_count < max_scrolls:
            # Find all place cards in the feed
            place_cards = page.locator("div[role='feed'] > div > div[jsaction]")
            card_count = await place_cards.count()

            for i in range(card_count):
                if len(results) >= max_results:
                    break

                try:
                    card = place_cards.nth(i)

                    # Get the link/anchor element
                    link = card.locator("a[href*='/maps/place/']").first
                    if await link.count() == 0:
                        continue

                    # Extract name from aria-label or text
                    name = await link.get_attribute("aria-label") or ""
                    if not name:
                        continue

                    # Skip duplicates
                    if name in seen_names:
                        continue
                    seen_names.add(name)

                    # Click to get details
                    await link.click()
                    await asyncio.sleep(1.5)  # Wait for details panel

                    # Extract detailed info
                    place_data = await self._extract_place_details(page)
                    if place_data:
                        results.append(place_data)
                        logger.debug(f"Extracted: {place_data.get('title', 'Unknown')}")

                    # Go back to results
                    await page.go_back()
                    await asyncio.sleep(1)

                except Exception as e:
                    logger.debug(f"Error extracting card {i}: {e}")
                    continue

            # Scroll to load more results
            scroll_count += 1
            try:
                feed = page.locator("div[role='feed']")
                await feed.evaluate("el => el.scrollTop = el.scrollHeight")
                await asyncio.sleep(1.5)
            except Exception:
                break

        return results

    async def _extract_place_details(self, page) -> Optional[Dict[str, Any]]:
        """Extract detailed information from a place page."""
        try:
            # Wait longer for content to fully load
            await asyncio.sleep(2)

            # Wait for the main details panel
            try:
                await page.wait_for_selector("div[role='main']", timeout=5000)
            except Exception:
                pass

            # Scroll down the details panel to load dynamic content
            # (popular times, reviews, related places are loaded on scroll)
            try:
                main_panel = page.locator("div[role='main']").first
                if await main_panel.count() > 0:
                    # Scroll down in steps to trigger lazy loading
                    for scroll_step in range(6):
                        await main_panel.evaluate("el => el.scrollBy(0, 800)")
                        await asyncio.sleep(0.7)
                    await asyncio.sleep(1)
                    # Scroll back to top
                    await main_panel.evaluate("el => el.scrollTop = 0")
                    await asyncio.sleep(0.5)
            except Exception:
                pass

            # Initialize place data with all available fields
            place = {
                "title": None,
                "cid": None,
                "link": None,
                "address": None,
                "phone": None,
                "website": None,
                "latitude": None,
                "longitude": None,
                "plus_code": None,
                "category": None,
                "review_rating": None,
                "review_count": None,
                "price_range": None,
                "price_per_person": None,
                "open_hours": None,
                "is_open_now": None,
                "description": None,
                "photos": [],
                "menu_link": None,
                "order_link": None,
                "reserve_link": None,
                "amenities": [],
                "service_options": [],
                "accessibility": [],
                "popular_times": {},
                "review_summary": None,
                "review_topics": [],
                "sample_reviews": [],
                "related_places": [],
            }

            # Get current URL for link and coordinates
            current_url = page.url
            place["link"] = current_url

            # Extract CID from URL (data ID)
            cid_match = re.search(r'!1s(0x[a-f0-9]+:0x[a-f0-9]+)', current_url)
            if cid_match:
                place["cid"] = cid_match.group(1)

            # Extract coordinates from URL
            coord_match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', current_url)
            if coord_match:
                place["latitude"] = coord_match.group(1)
                place["longitude"] = coord_match.group(2)

            # Extract title (business name) from URL first as it's most reliable
            # URL format: /maps/place/Business+Name/@...
            title_from_url = re.search(r'/maps/place/([^/@]+)', current_url)
            if title_from_url:
                # Decode URL-encoded name
                from urllib.parse import unquote_plus
                place["title"] = unquote_plus(title_from_url.group(1))

            # Also try to get from the page for a cleaner name
            # Look for the h1 in the details panel (not the search header)
            try:
                # Wait for the place name to appear in the panel
                await page.wait_for_selector("h1.DUwDvf", timeout=3000)
                title_el = page.locator("h1.DUwDvf").first
                if await title_el.count() > 0:
                    page_title = await title_el.text_content()
                    if page_title and page_title.lower() != "results":
                        place["title"] = page_title.strip()
            except Exception:
                pass

            # Fallback: try generic h1 in main content area
            if not place["title"] or place["title"].lower() == "results":
                try:
                    title_el = page.locator("div[role='main'] h1").first
                    if await title_el.count() > 0:
                        page_title = await title_el.text_content()
                        if page_title and page_title.lower() != "results":
                            place["title"] = page_title.strip()
                except Exception:
                    pass

            # Extract rating and review count
            rating_el = page.locator("div.F7nice span[aria-hidden='true']").first
            if await rating_el.count() > 0:
                rating_text = await rating_el.text_content()
                try:
                    place["review_rating"] = float(rating_text.replace(",", "."))
                except (ValueError, AttributeError):
                    pass

            # Review count - look for text like "(123)"
            review_count_el = page.locator("div.F7nice span[aria-label*='review']").first
            if await review_count_el.count() > 0:
                rc_text = await review_count_el.get_attribute("aria-label") or ""
                rc_match = re.search(r'([\d,]+)', rc_text.replace(",", ""))
                if rc_match:
                    place["review_count"] = rc_match.group(1)

            # Category
            category_el = page.locator("button[jsaction*='category']").first
            if await category_el.count() > 0:
                place["category"] = await category_el.text_content()

            # Price level
            price_el = page.locator("span[aria-label*='Price']").first
            if await price_el.count() > 0:
                place["price_range"] = await price_el.get_attribute("aria-label")

            # Address - look for data-item-id containing "address"
            addr_el = page.locator("button[data-item-id*='address']").first
            if await addr_el.count() > 0:
                addr_text = await addr_el.get_attribute("aria-label")
                if addr_text:
                    place["address"] = addr_text.replace("Address: ", "")

            # Phone
            phone_el = page.locator("button[data-item-id*='phone']").first
            if await phone_el.count() > 0:
                phone_text = await phone_el.get_attribute("aria-label")
                if phone_text:
                    place["phone"] = phone_text.replace("Phone: ", "")

            # Website
            website_el = page.locator("a[data-item-id='authority']").first
            if await website_el.count() > 0:
                place["website"] = await website_el.get_attribute("href")

            # Plus code
            pluscode_el = page.locator("button[data-item-id*='oloc']").first
            if await pluscode_el.count() > 0:
                pc_text = await pluscode_el.get_attribute("aria-label")
                if pc_text:
                    place["plus_code"] = pc_text.replace("Plus code: ", "")

            # Hours - try to click and expand for full schedule
            try:
                hours_btn = page.locator("button[data-item-id*='oh']").first
                if await hours_btn.count() > 0:
                    # Check if currently open or closed
                    hours_text = await hours_btn.text_content()
                    if hours_text:
                        if "Open" in hours_text:
                            place["is_open_now"] = True
                        elif "Closed" in hours_text:
                            place["is_open_now"] = False

                    # Get the hours text/aria-label
                    hours_label = await hours_btn.get_attribute("aria-label")
                    if hours_label:
                        place["open_hours"] = self._parse_hours_label(hours_label)

                    # Try to click to expand full hours table
                    try:
                        await hours_btn.click()
                        await asyncio.sleep(0.5)

                        # Look for the expanded hours table
                        hours_table = page.locator("table.eK4R0e, table.WgFkxc, div[aria-label*='hours'] table")
                        if await hours_table.count() > 0:
                            expanded_hours = await self._extract_expanded_hours(page)
                            if expanded_hours:
                                place["open_hours"] = expanded_hours

                        # Close the expanded view by pressing Escape
                        await page.keyboard.press("Escape")
                        await asyncio.sleep(0.3)
                    except Exception:
                        pass
            except Exception:
                pass

            # Extract photos from the carousel
            try:
                photo_elements = page.locator("button[jsaction*='heroHeaderImage'] img, div[jsaction*='photo'] img, img.Uf0tqf")
                photo_count = await photo_elements.count()
                for i in range(min(photo_count, 10)):  # Limit to 10 photos
                    photo = photo_elements.nth(i)
                    src = await photo.get_attribute("src")
                    if src and "googleusercontent.com" in src:
                        # Get higher resolution version
                        high_res_src = re.sub(r'=w\d+-h\d+', '=w800-h600', src)
                        place["photos"].append(high_res_src)
            except Exception:
                pass

            # Menu link
            try:
                menu_el = page.locator("a[data-item-id*='menu'], a[aria-label*='Menu']").first
                if await menu_el.count() > 0:
                    place["menu_link"] = await menu_el.get_attribute("href")
            except Exception:
                pass

            # Order online link
            try:
                order_el = page.locator("a[data-item-id*='order'], a[aria-label*='Order']").first
                if await order_el.count() > 0:
                    place["order_link"] = await order_el.get_attribute("href")
            except Exception:
                pass

            # Reserve table link
            try:
                reserve_el = page.locator("a[data-item-id*='reserve'], a[aria-label*='Reserve']").first
                if await reserve_el.count() > 0:
                    place["reserve_link"] = await reserve_el.get_attribute("href")
            except Exception:
                pass

            # Extract amenities and service options
            try:
                # Service options (Dine-in, Takeout, Delivery, etc.)
                service_els = page.locator("div[aria-label*='Service options'] span, div[data-tooltip*='Service']")
                service_count = await service_els.count()
                for i in range(service_count):
                    text = await service_els.nth(i).text_content()
                    if text and text.strip():
                        place["service_options"].append(text.strip())
            except Exception:
                pass

            try:
                # Accessibility options
                access_els = page.locator("div[aria-label*='Accessibility'] span, span[aria-label*='Wheelchair']")
                access_count = await access_els.count()
                for i in range(access_count):
                    text = await access_els.nth(i).text_content()
                    if text and text.strip():
                        place["accessibility"].append(text.strip())
            except Exception:
                pass

            try:
                # General amenities (from About tab or highlights)
                amenity_els = page.locator("div[aria-label*='Highlights'] span, div[data-attrid*='highlights'] span")
                amenity_count = await amenity_els.count()
                for i in range(amenity_count):
                    text = await amenity_els.nth(i).text_content()
                    if text and text.strip() and len(text.strip()) < 50:
                        place["amenities"].append(text.strip())
            except Exception:
                pass

            # Extract description/about from the About region
            try:
                # Look for the About region button which contains the description
                about_region = page.locator("region[aria-label*='About']")
                if await about_region.count() > 0:
                    about_btn = about_region.locator("button").first
                    if await about_btn.count() > 0:
                        about_text = await about_btn.text_content()
                        if about_text:
                            # Extract just the description part (before service options markers)
                            # Split on common patterns that indicate end of description
                            desc_text = about_text
                            for marker in ["·", "Serves", "Has ", "Dine-in", "Drive-through", "Delivery"]:
                                if marker in desc_text:
                                    desc_text = desc_text.split(marker)[0]
                            desc_text = desc_text.strip()
                            if desc_text and len(desc_text) > 10:
                                place["description"] = desc_text
            except Exception:
                pass

            # Fallback description extraction
            if not place["description"]:
                try:
                    # Try to find description in various common locations
                    desc_selectors = [
                        "div[data-attrid='description'] span",
                        "div.PYvSYb span",
                        "button:has-text('known for')",
                    ]
                    for selector in desc_selectors:
                        desc_el = page.locator(selector).first
                        if await desc_el.count() > 0:
                            desc = await desc_el.text_content()
                            if desc and len(desc) > 20 and desc.lower() != "learn more":
                                # Clean up the description
                                for marker in ["·", "Serves", "Has "]:
                                    if marker in desc:
                                        desc = desc.split(marker)[0]
                                place["description"] = desc.strip()
                                break
                except Exception:
                    pass

            # Extract price per person
            try:
                price_btn = page.locator("button[aria-label*='per person'], button:has-text('per person')").first
                if await price_btn.count() > 0:
                    price_text = await price_btn.text_content()
                    if price_text:
                        # Extract price range like "$1–10 per person"
                        price_match = re.search(r'\$[\d,]+[–-]\$?[\d,]+', price_text)
                        if price_match:
                            place["price_per_person"] = price_match.group(0)
            except Exception:
                pass

            # Extract service options (Dine-in, Drive-through, Delivery, etc.)
            try:
                # Look for service option groups with role="group"
                service_groups = page.locator("[role='group'][aria-label*='Serves'], [role='group'][aria-label*='Has']")
                service_count = await service_groups.count()

                # Try alternative - look for groups in the main panel
                if service_count == 0:
                    service_groups = page.locator("div[role='main'] span[role='group'], div[role='main'] [aria-label*='dine-in'], div[role='main'] [aria-label*='drive-through']")
                    service_count = await service_groups.count()

                for i in range(service_count):
                    label = await service_groups.nth(i).get_attribute("aria-label")
                    if label:
                        # Extract just the service name from "Serves dine-in" or "Has drive-through"
                        if "Serves" in label:
                            service = label.replace("Serves ", "").strip()
                        elif "Has" in label:
                            service = label.replace("Has ", "").strip()
                        else:
                            service = label
                        place["service_options"].append(service.title())

                # Fallback: look for text within the About section
                if not place["service_options"]:
                    about_section = page.locator("region[aria-label*='About']")
                    if await about_section.count() > 0:
                        about_text = await about_section.text_content()
                        if about_text:
                            service_texts = ["Dine-in", "Drive-through", "Takeout", "Delivery", "No-contact delivery", "Curbside pickup"]
                            for svc in service_texts:
                                if svc.lower() in about_text.lower():
                                    place["service_options"].append(svc)
            except Exception:
                pass

            # Extract popular times data
            try:
                popular_times_section = page.locator("region[aria-label*='Popular times'], div:has(heading:has-text('Popular times'))")
                pt_count = await popular_times_section.count()

                # Also try alternative selectors
                busy_imgs_direct = page.locator("img[aria-label*='busy']")
                busy_count_direct = await busy_imgs_direct.count()

                if pt_count > 0 or busy_count_direct > 0:
                    # Get the day selector button
                    day_btn = page.locator("button[aria-label*='days'], button:has-text('Saturdays'), button:has-text('Sundays'), button:has-text('Mondays')").first

                    current_day = "Unknown"
                    if await day_btn.count() > 0:
                        day_text = await day_btn.text_content()
                        if day_text:
                            current_day = day_text.strip()

                    # Get the hourly busy percentages
                    busy_imgs = page.locator("img[aria-label*='busy at'], img[aria-label*='% busy']")
                    img_count = await busy_imgs.count()

                    hourly_data = []
                    for i in range(img_count):
                        label = await busy_imgs.nth(i).get_attribute("aria-label")
                        if label:
                            # Parse "93% busy at 10 AM." or "79% busy at 10 AM"
                            match = re.search(r'(\d+)%\s+busy\s+at\s+(\d+\s*(?:AM|PM))', label, re.IGNORECASE)
                            if match:
                                hourly_data.append({
                                    "hour": match.group(2),
                                    "busy_percent": int(match.group(1))
                                })
                    if hourly_data:
                        place["popular_times"][current_day] = hourly_data
            except Exception:
                pass

            # Extract live wait time and current busyness
            try:
                # Initialize wait time fields
                place["wait_time_minutes"] = None
                place["wait_time_raw"] = None
                place["live_busyness"] = None
                place["typical_busyness"] = None

                # Look for live busyness indicator (e.g., "Live: Busier than usual")
                live_busy_selectors = [
                    "span:has-text('Live:')",
                    "div:has-text('Busier than usual')",
                    "div:has-text('Less busy than usual')",
                    "div:has-text('As busy as it gets')",
                    "div:has-text('Not too busy')",
                    "[aria-label*='Live']"
                ]

                for selector in live_busy_selectors:
                    live_elem = page.locator(selector).first
                    if await live_elem.count() > 0:
                        live_text = await live_elem.text_content()
                        if live_text and "Live" in live_text:
                            place["live_busyness"] = live_text.strip()
                            break

                # Look for wait time specifically (e.g., "Usually 15 min wait")
                wait_selectors = [
                    "span:has-text('min wait')",
                    "div:has-text('min wait')",
                    "[aria-label*='wait']",
                    "span:has-text('minute wait')"
                ]

                for selector in wait_selectors:
                    wait_elem = page.locator(selector).first
                    if await wait_elem.count() > 0:
                        wait_text = await wait_elem.text_content()
                        if wait_text:
                            # Parse "Usually 15 min wait" or "Live: 20 min wait"
                            match = re.search(r'(\d+)\s*min(?:ute)?\s*wait', wait_text, re.IGNORECASE)
                            if match:
                                place["wait_time_minutes"] = int(match.group(1))
                                place["wait_time_raw"] = wait_text.strip()
                            break

                # Extract typical busyness messages (e.g., "Usually not too busy")
                typical_selectors = [
                    "span:has-text('Usually not too busy')",
                    "span:has-text('Usually a little busy')",
                    "span:has-text('Usually not busy')",
                    "span:has-text('Usually busy')",
                    "div:has-text('Usually')"
                ]

                for selector in typical_selectors:
                    typical_elem = page.locator(selector).first
                    if await typical_elem.count() > 0:
                        typical_text = await typical_elem.text_content()
                        if typical_text and "Usually" in typical_text and "wait" not in typical_text.lower():
                            place["typical_busyness"] = typical_text.strip()
                            break

            except Exception:
                pass

            # Extract review summary (star breakdown)
            try:
                review_table = page.locator("table img[aria-label*='stars']")
                table_count = await review_table.count()

                # Try alternative selector
                if table_count == 0:
                    review_table = page.locator("img[aria-label*='stars'][aria-label*='reviews']")
                    table_count = await review_table.count()

                if table_count > 0:
                    review_summary = {}
                    for i in range(table_count):
                        label = await review_table.nth(i).get_attribute("aria-label")
                        if label:
                            # Parse "5 stars, 474 reviews" or "5 stars, 691 reviews"
                            match = re.search(r'(\d+)\s*stars?,\s*([\d,]+)\s*reviews?', label, re.IGNORECASE)
                            if match:
                                stars = match.group(1)
                                count = match.group(2).replace(",", "")
                                review_summary[f"{stars}_star"] = int(count)
                    if review_summary:
                        place["review_summary"] = review_summary
            except Exception:
                pass

            # Extract review topics/keywords
            try:
                # Look for radio buttons in the review filter section
                topic_radios = page.locator("[role='radio'][aria-label*='mentioned in']")
                topic_count = await topic_radios.count()

                # Try alternative selector
                if topic_count == 0:
                    topic_radios = page.locator("div[role='radio'][aria-label*='reviews'], button[aria-label*='mentioned']")
                    topic_count = await topic_radios.count()

                for i in range(min(topic_count, 10)):  # Limit to 10 topics
                    label = await topic_radios.nth(i).get_attribute("aria-label")
                    if label:
                        # Parse "drive thru, mentioned in 102 reviews"
                        match = re.search(r'([^,]+),\s*mentioned\s+in\s+(\d+)\s+reviews?', label, re.IGNORECASE)
                        if match:
                            place["review_topics"].append({
                                "topic": match.group(1).strip(),
                                "count": int(match.group(2))
                            })
            except Exception:
                pass

            # Extract sample reviews (quotes shown at top of reviews section)
            try:
                # Look for buttons containing quoted review text
                all_buttons = page.locator("button")
                btn_count = await all_buttons.count()
                for i in range(min(btn_count, 50)):  # Check first 50 buttons
                    if len(place["sample_reviews"]) >= 3:
                        break
                    try:
                        btn = all_buttons.nth(i)
                        text = await btn.text_content()
                        if text and text.startswith('"') and len(text) > 20:
                            # Clean up the quote
                            clean_text = text.strip('"').strip()
                            if clean_text and clean_text not in place["sample_reviews"]:
                                place["sample_reviews"].append(clean_text)
                    except Exception:
                        continue
            except Exception:
                pass

            # Extract related places ("People also search for")
            try:
                # Look for links with aria-label containing stars and reviews
                related_links = page.locator("a[aria-label*='stars'][aria-label*='reviews']")
                related_count = await related_links.count()

                # Skip the first one if it's the current place
                start_idx = 1 if related_count > 1 else 0
                for i in range(start_idx, min(related_count, 6)):  # Limit to 5 related places
                    label = await related_links.nth(i).get_attribute("aria-label")
                    if label:
                        # Parse "Burger King · 3.3 stars · 1,084 reviews · Restaurant"
                        parts = label.split(" · ")
                        if len(parts) >= 3:
                            related = {"name": parts[0]}
                            for part in parts[1:]:
                                if "stars" in part.lower():
                                    rating_match = re.search(r'([\d.]+)', part)
                                    if rating_match:
                                        related["rating"] = float(rating_match.group(1))
                                elif "reviews" in part.lower():
                                    count_match = re.search(r'([\d,]+)', part)
                                    if count_match:
                                        related["review_count"] = int(count_match.group(1).replace(",", ""))
                                else:
                                    related["category"] = part
                            place["related_places"].append(related)
            except Exception:
                pass

            # Clean up empty lists/dicts
            if not place["photos"]:
                place["photos"] = None
            if not place["amenities"]:
                place["amenities"] = None
            if not place["service_options"]:
                place["service_options"] = None
            if not place["accessibility"]:
                place["accessibility"] = None
            if not place["popular_times"]:
                place["popular_times"] = None
            if not place["review_topics"]:
                place["review_topics"] = None
            if not place["sample_reviews"]:
                place["sample_reviews"] = None
            if not place["related_places"]:
                place["related_places"] = None

            # Only return if we have at least a title
            if place.get("title"):
                logger.info(f"Extracted place: {place.get('title')} with {len([v for v in place.values() if v])} fields populated")
                return place

            return None

        except Exception as e:
            logger.debug(f"Error extracting place details: {e}")
            return None

    async def _extract_expanded_hours(self, page) -> Optional[Dict[str, List[str]]]:
        """Extract hours from expanded hours table."""
        try:
            hours = {}
            # Look for table rows with day and time info
            rows = page.locator("table tr, div[role='listitem']")
            row_count = await rows.count()

            days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

            for i in range(row_count):
                row = rows.nth(i)
                row_text = await row.text_content()
                if row_text:
                    for day in days:
                        if day in row_text:
                            # Extract time portion
                            time_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:AM|PM)\s*[–-]\s*\d{1,2}(?::\d{2})?\s*(?:AM|PM)|Closed|Open 24 hours)', row_text, re.IGNORECASE)
                            if time_match:
                                hours[day] = [time_match.group(0)]
                            break

            return hours if hours else None
        except Exception:
            return None

    def _parse_hours_label(self, label: str) -> Optional[Dict[str, List[str]]]:
        """Parse hours from aria-label into structured format."""
        if not label:
            return None

        # Try to parse common patterns like "Monday, 9 AM to 5 PM; Tuesday, 9 AM to 5 PM"
        hours = {}
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        for day in days:
            if day in label:
                # Find the time for this day
                pattern = rf"{day}[,:]?\s*([^;]+)"
                match = re.search(pattern, label, re.IGNORECASE)
                if match:
                    time_str = match.group(1).strip()
                    # Clean up the time string
                    time_str = re.sub(r'\.\s*$', '', time_str)
                    time_str = time_str.replace(" to ", "–")
                    hours[day] = [time_str]

        return hours if hours else None


# Global job store
_job_store = JobStore()


async def get_job_store() -> JobStore:
    """Get the global job store."""
    return _job_store


async def run_scrape_job(
    job: ScrapeJob,
    proxy: Optional[str] = None
):
    """
    Run a scrape job in the background.

    Args:
        job: The job to run
        proxy: Optional proxy URL
    """
    store = await get_job_store()
    scraper = GoogleMapsScraper(proxy=proxy, headless=True)

    try:
        # Update job status
        job.status = JobStatus.RUNNING
        await store.update(job)
        logger.info(f"Starting job {job.id}: {job.query}")

        # Run the search
        results = await scraper.search(
            query=job.query,
            language=job.language,
            max_results=job.max_results,
            zoom=job.zoom,
            geo_coordinates=job.geo_coordinates
        )

        # Update job with results
        job.results = results
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now()
        job.total = len(results)
        job.progress = len(results)
        await store.update(job)

        logger.info(f"Job {job.id} completed with {len(results)} results")

    except Exception as e:
        # Handle failure
        job.status = JobStatus.FAILED
        job.error = str(e)
        job.completed_at = datetime.now()
        await store.update(job)
        logger.error(f"Job {job.id} failed: {e}")

    finally:
        await scraper.close()
