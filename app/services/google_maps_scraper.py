"""
Native Google Maps Scraper using Playwright.

This module provides direct Google Maps scraping without requiring
the gosom Docker sidecar. It uses Playwright for browser automation.

Three defects this module previously shipped, and how they are addressed here:

1. **Jobs were global.** ``JobStore`` was a process-local dict with no owner
   parameter, so any valid API key could read, list and delete every other
   caller's jobs, and every job vanished on restart or was invisible to a
   sibling ``--workers`` process. Persistence now goes through
   :mod:`app.services.record_store`, which makes ``owner`` part of the key.

2. **Unbounded browser fan-out.** Nothing capped how many Chromium instances
   could be alive at once; an 11x11 grid search meant 121 of them at ~100 MB
   resident each. A permit from :func:`_browser_semaphore` is now held for the
   whole life of a browser, and :func:`cap_fanout` gives callers a hard
   fan-out ceiling.

3. **Failures became successful empty results.** Every selector was wrapped in
   ``except Exception: pass``, so a Google DOM rotation produced
   ``{"success": true, "places": []}`` -- indistinguishable from a genuine
   no-results search. Optional fields still degrade gracefully, but they are
   now *recorded* (see :meth:`GoogleMapsScraper._optional`), required fields
   raise :class:`PlaceExtractionError`, and a search that finds candidate
   places but extracts none of them raises :class:`SelectorsStaleError`.
"""
import asyncio
import contextlib
import logging
import os
import re
import weakref
from typing import Optional, List, Dict, Any, Sequence, TypeVar
from datetime import datetime
from dataclasses import dataclass, field, asdict
from enum import Enum

from app.services.record_store import (
    RecordStore,
    get_record_store,
    # Re-exported so callers can derive a job owner without also having to know
    # about the record-store module: `from ...google_maps_scraper import
    # owner_id_for_api_key`.
    owner_id_for_api_key,  # noqa: F401
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Declared explicitly so the re-export above is machine-readable intent rather
# than something a linter has to be told to ignore: `owner_id_for_api_key` is
# part of this module's public surface on purpose.
__all__ = [
    "JobStatus",
    "ScrapeJob",
    "JobStore",
    "GoogleMapsScraper",
    "get_job_store",
    "run_scrape_job",
    "owner_id_for_api_key",
    "cap_fanout",
    "ScraperError",
    "SelectorsStaleError",
    "PlaceExtractionError",
    "JOB_NAMESPACE",
]

#: Namespace for scrape jobs in the owner-scoped record store.
JOB_NAMESPACE = "maps:jobs"

# -- Concurrency limits -------------------------------------------------------
#
# Chromium is roughly 100 MB resident per instance. These are deliberately
# small: the failure mode of too low a cap is a slow request, the failure mode
# of too high a cap is the container being OOM-killed mid-request.
#
# Configured via environment rather than ``Settings`` so that this module does
# not have to be edited in lockstep with ``app/core/config.py``. If/when a
# ``Settings`` field is added, point these defaults at it.

DEFAULT_MAX_CONCURRENT_BROWSERS = 4

#: Hard ceiling on grid/bulk fan-out, regardless of what a caller requests.
#: An 11x11 grid is 121 points; that is allowed as a *request*, but the number
#: of points actually visited is clamped to this.
DEFAULT_MAX_FANOUT = 25


def _env_int(name: str, default: int) -> int:
    """Read a positive int from the environment, falling back to ``default``.

    A malformed or non-positive value is a configuration error, not a licence
    to run unbounded, so it logs and uses the safe default.
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("%s=%r is not an integer; using %d", name, raw, default)
        return default
    if value < 1:
        logger.warning("%s=%d must be >= 1; using %d", name, value, default)
        return default
    return value


_max_concurrent_browsers = _env_int(
    "GOOGLE_MAPS_MAX_CONCURRENT_BROWSERS", DEFAULT_MAX_CONCURRENT_BROWSERS
)
_max_fanout = _env_int("GOOGLE_MAPS_MAX_FANOUT", DEFAULT_MAX_FANOUT)

# Semaphores are per event loop: a single module-level Semaphore binds to the
# first loop that awaits it, and reusing it from another loop (pytest creates
# one per test, uvicorn one per worker) raises or silently fails to bound.
_browser_semaphores: "weakref.WeakKeyDictionary[Any, asyncio.Semaphore]" = (
    weakref.WeakKeyDictionary()
)


def get_max_concurrent_browsers() -> int:
    """Current cap on simultaneously-live Chromium instances in this process."""
    return _max_concurrent_browsers


def get_max_fanout() -> int:
    """Current hard ceiling on grid/bulk fan-out."""
    return _max_fanout


def configure_limits(
    *,
    max_concurrent_browsers: Optional[int] = None,
    max_fanout: Optional[int] = None,
) -> None:
    """Override the concurrency limits (startup configuration and tests).

    Changing ``max_concurrent_browsers`` discards the existing semaphores, so
    the new cap applies to browsers acquired from now on.
    """
    global _max_concurrent_browsers, _max_fanout
    if max_concurrent_browsers is not None:
        if max_concurrent_browsers < 1:
            raise ValueError("max_concurrent_browsers must be >= 1")
        _max_concurrent_browsers = max_concurrent_browsers
        _browser_semaphores.clear()
    if max_fanout is not None:
        if max_fanout < 1:
            raise ValueError("max_fanout must be >= 1")
        _max_fanout = max_fanout


def _browser_semaphore() -> asyncio.Semaphore:
    """Return this event loop's browser-acquisition semaphore."""
    loop = asyncio.get_running_loop()
    sem = _browser_semaphores.get(loop)
    if sem is None:
        sem = asyncio.Semaphore(_max_concurrent_browsers)
        _browser_semaphores[loop] = sem
    return sem


def cap_fanout(items: Sequence[T], *, kind: str = "fan-out") -> List[T]:
    """Clamp a fan-out list (grid points, bulk queries) to the hard ceiling.

    Callers that build a work list -- ``grid_search``, ``bulk_search`` -- must
    pass it through here before iterating. Truncating loudly is preferable to
    either silently accepting 121 browser launches or rejecting the request
    outright, but the log line makes the truncation auditable.
    """
    limit = _max_fanout
    if len(items) <= limit:
        return list(items)
    logger.warning(
        "%s requested %d points; truncated to the %d-point limit "
        "(raise GOOGLE_MAPS_MAX_FANOUT to allow more)",
        kind,
        len(items),
        limit,
    )
    return list(items[:limit])


# -- Failure signals ----------------------------------------------------------


class ScraperError(RuntimeError):
    """Base class for scraper failures that must not look like empty success."""

    status_code = 502


class PlaceExtractionError(ScraperError):
    """A single place could not be extracted (required fields missing).

    Attributes:
        missing: Required field names that no selector matched.
    """

    status_code = 502

    def __init__(self, message: str, *, missing: Optional[Sequence[str]] = None) -> None:
        super().__init__(message)
        self.missing = list(missing or [])


class SelectorsStaleError(ScraperError):
    """Every candidate place failed to extract -- the page shape has changed.

    This is the error that exists so a total scraping outage cannot be
    reported as ``{"success": true, "places": []}``. Routers should map it to
    503: the upstream is present but this service can no longer read it.

    Attributes:
        attempted: Number of candidate places the scraper tried to extract.
        extracted: Number it succeeded on (zero, or this is not raised).
        missing: Union of required fields that failed to match.
    """

    status_code = 503

    def __init__(
        self,
        message: str,
        *,
        attempted: int = 0,
        extracted: int = 0,
        missing: Optional[Sequence[str]] = None,
    ) -> None:
        super().__init__(message)
        self.attempted = attempted
        self.extracted = extracted
        self.missing = list(missing or [])

    def to_dict(self) -> Dict[str, Any]:
        """Structured payload a router can return alongside a 503."""
        return {
            "error": True,
            "selectors_stale": True,
            "message": str(self),
            "attempted": self.attempted,
            "extracted": self.extracted,
            "missing_fields": self.missing,
        }


#: A place is worthless without these; if none match, the DOM has changed.
REQUIRED_PLACE_FIELDS = ("title",)

#: At least one of these must match for a place to be considered fully
#: extracted. A record with a title scraped out of the URL but no address, no
#: phone, no website and no rating means the details panel did not parse.
CORE_PLACE_FIELDS = (
    "address",
    "phone",
    "website",
    "category",
    "review_rating",
    "review_count",
    "open_hours",
)


class JobStatus(str, Enum):
    """Status of a scraping job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ScrapeJob:
    """Represents a scraping job.

    ``owner`` is the field that makes cross-tenant access impossible rather
    than merely unlikely: it becomes part of the storage key, so one caller
    cannot address another caller's job at all. It defaults to empty only so
    that the dataclass stays keyword-constructible; :class:`JobStore` refuses
    to persist a job without one rather than quietly filing it under a shared
    partition.
    """
    id: str
    name: str
    query: str
    owner: str = ""
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    results: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    #: True when the job failed because Google's markup changed rather than
    #: because of a transient error; routers should surface this as 503.
    selectors_stale: bool = False
    #: True when the job completed with zero results that could NOT be
    #: confirmed as a genuine zero (the results feed rendered but nothing
    #: inside it matched). The job is not failed, but callers must not treat
    #: the empty list as authoritative.
    empty_unverified: bool = False
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
            # Lets a router turn a markup-rotation failure into a 503 rather
            # than reporting a job that merely "found nothing".
            "selectors_stale": self.selectors_stale,
            "empty_unverified": self.empty_unverified,
            "Data": {
                "keywords": [self.query],
                "lang": self.language,
                "zoom": self.zoom,
            }
        }

    def to_record(self) -> Dict[str, Any]:
        """Full, lossless payload for the record store.

        Distinct from :meth:`to_dict`, which is the lossy gosom-compatible API
        shape. Persisting ``to_dict`` would drop ``results``, ``owner`` and the
        job parameters, so a job reloaded after a restart would come back
        empty -- exactly the silent data loss this change exists to stop.
        """
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["created_at"] = self.created_at.isoformat()
        payload["completed_at"] = (
            self.completed_at.isoformat() if self.completed_at else None
        )
        return payload

    @classmethod
    def from_record(cls, payload: Dict[str, Any]) -> "ScrapeJob":
        """Rebuild a job from :meth:`to_record` output."""
        data = dict(payload)
        data["status"] = JobStatus(data.get("status", JobStatus.PENDING.value))
        created_at = data.get("created_at")
        data["created_at"] = (
            datetime.fromisoformat(created_at) if created_at else datetime.now()
        )
        completed_at = data.get("completed_at")
        data["completed_at"] = (
            datetime.fromisoformat(completed_at) if completed_at else None
        )
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


class JobStore:
    """Owner-scoped, durable job storage.

    Every method takes the owner explicitly (or reads it off the job), and
    there is deliberately no ``list_all``: the previous implementation had one,
    and it was the vulnerability -- ``list_jobs``/``delete_job`` authenticated
    the caller and then operated on the whole keyspace.

    Durability and cross-worker visibility come from
    :class:`~app.services.record_store.RecordStore`, which uses Redis when it
    is configured and an explicitly non-durable dict when it is not. The
    previous in-process dict and its ``asyncio.Lock`` are gone; the record
    store keeps the equivalent locking for its own memory backend.
    """

    def __init__(self, store: Optional[RecordStore] = None) -> None:
        self._store = store if store is not None else get_record_store(JOB_NAMESPACE)

    @staticmethod
    def _require_owner(job: ScrapeJob) -> str:
        if not job.owner:
            raise ValueError(
                "ScrapeJob.owner is required; derive it with "
                "owner_id_for_api_key(api_key) before creating a job"
            )
        return job.owner

    async def is_durable(self) -> bool:
        """True when jobs survive a restart and are visible to sibling workers."""
        return await self._store.is_durable()

    async def create(self, job: ScrapeJob) -> ScrapeJob:
        """Create a job. The owner is taken from ``job.owner`` and required."""
        owner = self._require_owner(job)
        await self._store.put(owner, job.id, job.to_record())
        return job

    async def get(self, owner: str, job_id: str) -> Optional[ScrapeJob]:
        """Return the job only if ``owner`` owns it, else None.

        A job belonging to someone else is indistinguishable from one that does
        not exist, so a caller cannot probe for other tenants' job ids.
        """
        record = await self._store.get(owner, job_id)
        if record is None:
            return None
        return ScrapeJob.from_record(record.data)

    async def update(self, job: ScrapeJob) -> ScrapeJob:
        """Persist a mutated job under its own owner."""
        owner = self._require_owner(job)
        await self._store.put(owner, job.id, job.to_record())
        return job

    async def delete(self, owner: str, job_id: str) -> bool:
        """Delete one of ``owner``'s jobs. False if they do not have it."""
        return await self._store.delete(owner, job_id)

    async def list_for_owner(
        self,
        owner: str,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ScrapeJob]:
        """List ``owner``'s jobs, newest first, optionally filtered by status."""
        predicate = None
        if status:
            predicate = lambda record: record.data.get("status") == status  # noqa: E731
        records = await self._store.list_for_owner(
            owner, limit=limit, offset=offset, predicate=predicate
        )
        return [ScrapeJob.from_record(r.data) for r in records]


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
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._init_lock = asyncio.Lock()
        # Per-search extraction bookkeeping; see _assert_selectors_fresh.
        self._candidates = 0
        self._unverified_empty = False
        self._attempted = 0
        self._extracted = 0
        self._partial = 0
        self._required_misses: List[str] = []

    @contextlib.contextmanager
    def _optional(self, misses: List[str], field_name: str):
        """Run an optional-field extraction, recording rather than hiding misses.

        This replaces 23 bare ``except Exception: pass`` blocks. The behaviour
        for a genuinely absent optional field is unchanged -- extraction
        continues -- but the miss is appended to ``misses`` and logged, so that
        "this restaurant has no menu link" and "the menu selector no longer
        matches anything on any page" stop looking identical.
        """
        try:
            yield
        except Exception as exc:
            misses.append(field_name)
            logger.debug("Optional field %r not extracted: %s", field_name, exc)

    async def _init_browser(self):
        """Initialize Playwright browser, bounded by the global cap.

        The semaphore is held for the whole life of the browser, not just for
        the launch call: what has to be bounded is the number of Chromium
        processes *resident* at once (~100 MB each), not the launch rate. It is
        released in :meth:`close`, which every acquisition path already calls
        from a ``finally``.
        """
        if self._browser is not None:
            return

        from playwright.async_api import async_playwright

        # The check-then-acquire below is not atomic across awaits, so two
        # coroutines sharing one scraper could each take a permit and only one
        # would ever be released. The instance lock makes initialisation
        # single-entry.
        async with self._init_lock:
            if self._browser is not None or self._semaphore is not None:
                return

            semaphore = _browser_semaphore()
            await semaphore.acquire()
            self._semaphore = semaphore
            try:
                await self._launch(async_playwright)
            except BaseException:
                # Never leak a permit on a failed launch, or the cap ratchets
                # down to zero and every later request deadlocks.
                self._semaphore = None
                semaphore.release()
                raise

    def _release_semaphore(self) -> None:
        """Give back the browser permit, at most once."""
        semaphore, self._semaphore = self._semaphore, None
        if semaphore is not None:
            semaphore.release()

    async def _launch(self, async_playwright):
        """Start Playwright and launch Chromium with the configured options."""
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
        """Close the browser and release its concurrency permit.

        The permit is released in a ``finally`` so that a browser that fails to
        shut down cleanly still frees its slot; otherwise one hung Chromium
        would permanently shrink the pool.
        """
        try:
            if self._browser:
                await self._browser.close()
                self._browser = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
            logger.info("Browser closed")
        finally:
            self._release_semaphore()

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
        # Reset per-search extraction bookkeeping. ``attempted`` counts places
        # we found a card/link for and tried to open; ``extracted`` counts the
        # ones that yielded a usable record. attempted > 0 with extracted == 0
        # is the fingerprint of a DOM rotation, not of an empty area.
        self._candidates = 0
        self._unverified_empty = False
        self._attempted = 0
        self._extracted = 0
        self._partial = 0
        self._required_misses: List[str] = []

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
                    self._candidates += 1
                    self._attempted += 1
                    try:
                        place_data = await self._extract_place_details(page)
                    except PlaceExtractionError as exc:
                        self._required_misses.extend(exc.missing)
                        place_data = None
                    if place_data:
                        self._extracted += 1
                        self._partial += bool(place_data.get("partial"))
                        results = [place_data]

            self._assert_selectors_fresh(query, results_loaded)
            logger.info(f"Found {len(results)} places for query: {query}")

        except ScraperError:
            # Already a precise, non-empty-looking failure. Do not downgrade it
            # into a logged-and-swallowed empty result.
            raise
        except Exception as e:
            logger.error(f"Search error: {e}", exc_info=True)
            raise
        finally:
            await context.close()

        return results

    def _assert_selectors_fresh(self, query: str, results_loaded: bool) -> None:
        """Raise if this search's emptiness is a parser failure, not a real zero.

        Two distinguishable situations produce zero places:

        * The area genuinely has no matching businesses. Google renders a
          results container and it is empty, so ``attempted`` is 0 and
          ``results_loaded`` is True. That is a legitimate ``[]``.
        * Google changed its markup. Either no results container matched at all
          (``results_loaded`` False), or cards were found and every single one
          failed to yield a record (``attempted > 0, extracted == 0``).

        Before this check, both returned ``{"success": true, "places": []}``.
        """
        if not results_loaded and self._extracted == 0:
            raise SelectorsStaleError(
                f"No results container matched for {query!r}: none of the known "
                f"result selectors were present, so an empty result cannot be "
                f"distinguished from a markup change or a block page",
                attempted=self._attempted,
                extracted=0,
                missing=["div[role='feed']", "a[href*='/maps/place/']"],
            )

        # ``candidates`` rather than ``attempted``: a card that was visible but
        # never reached extraction -- because its link selector matched
        # nothing, or clicking it threw -- is still evidence that results exist
        # and we cannot read them. Keying off ``attempted`` alone would let a
        # link-selector rotation return a successful empty list.
        if self._candidates > 0 and self._extracted == 0:
            raise SelectorsStaleError(
                f"Found {self._candidates} candidate place(s) for {query!r} but "
                f"extracted none of them ({self._attempted} reached the details "
                f"panel); Google Maps markup has likely changed",
                attempted=self._attempted,
                extracted=self._extracted,
                missing=sorted(set(self._required_misses)) or list(REQUIRED_PLACE_FIELDS),
            )

        # Every place came back title-only. A title is recoverable from the URL
        # without touching the details panel, so this is a parsed-nothing run
        # dressed up as a successful one.
        if self._extracted > 0 and self._partial == self._extracted:
            raise SelectorsStaleError(
                f"All {self._extracted} place(s) for {query!r} were extracted "
                f"without a single core field ({', '.join(CORE_PLACE_FIELDS)}); "
                f"the place details panel selectors are stale",
                attempted=self._attempted,
                extracted=self._extracted,
                missing=list(CORE_PLACE_FIELDS),
            )

    async def _extract_from_place_links(self, page, place_links, max_results: int) -> List[Dict[str, Any]]:
        """Extract places from direct place links on the page."""
        results = []
        seen_names = set()
        link_count = await place_links.count()
        # Every link is a candidate; extracting none of them is a stale-selector
        # signal, not an empty result. See _assert_selectors_fresh.
        self._candidates = max(self._candidates, min(link_count, max_results))

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

                self._attempted += 1
                try:
                    place_data = await self._extract_place_details(page)
                except PlaceExtractionError as exc:
                    # Recorded, not swallowed: search() turns an all-fail run
                    # into SelectorsStaleError rather than an empty success.
                    self._required_misses.extend(exc.missing)
                    logger.warning("Place link %d failed to extract: %s", i, exc)
                    place_data = None

                if place_data:
                    self._extracted += 1
                    self._partial += bool(place_data.get("partial"))
                    results.append(place_data)
                    logger.debug(f"Extracted: {place_data.get('title', 'Unknown')}")

                # Go back
                await page.go_back()
                await asyncio.sleep(1)

            except Exception as e:
                logger.warning(f"Error extracting link {i}: {e}")
                continue

        return results

    async def _extract_search_results(self, page, max_results: int) -> List[Dict[str, Any]]:
        """Extract places from search results list.

        Raises:
            SelectorsStaleError: The feed rendered and contains place links,
                but the card selector matched none of them. Returning ``[]``
                here would report a card-markup change as an empty area.
        """
        results = []
        seen_names = set()
        scroll_count = 0
        max_scrolls = max(5, max_results // 4)  # Estimate scrolls needed

        while len(results) < max_results and scroll_count < max_scrolls:
            # Find all place cards in the feed
            place_cards = page.locator("div[role='feed'] > div > div[jsaction]")
            card_count = await place_cards.count()

            if card_count == 0 and not results:
                # The feed exists but our card selector sees nothing in it.
                # Place links are how a result manifests regardless of the
                # surrounding card markup, so they discriminate the two cases:
                # links present means our selector went stale; no links means
                # the area really is empty.
                stray_links = await page.locator("a[href*='/maps/place/']").count()
                if stray_links > 0:
                    raise SelectorsStaleError(
                        f"The results feed contains {stray_links} place link(s) "
                        f"but the card selector matched none of them; the "
                        f"result-card markup has changed",
                        attempted=0,
                        extracted=0,
                        missing=["div[role='feed'] > div > div[jsaction]"],
                    )

                # Neither cards nor place links matched inside a feed that did
                # render. This is genuinely ambiguous -- an empty area looks
                # exactly like a wholesale markup rotation -- so raising would
                # turn every legitimately empty search into a 503. Instead the
                # emptiness is labelled as unverified and carried out to the
                # caller, so it is never presented as a *confirmed* zero.
                self._unverified_empty = True
                logger.error(
                    "Results feed rendered but neither the card selector nor "
                    "any place link matched; returning an EMPTY result that "
                    "could not be verified as a genuine zero"
                )
                break

            # Candidates are cards we can see. If we can see candidates and
            # extract nothing from any of them, search() treats that as stale
            # rather than as an empty result -- see _assert_selectors_fresh.
            self._candidates = max(self._candidates, card_count)

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
                    self._attempted += 1
                    try:
                        place_data = await self._extract_place_details(page)
                    except PlaceExtractionError as exc:
                        # Recorded, not swallowed: search() turns an all-fail
                        # run into SelectorsStaleError, not an empty success.
                        self._required_misses.extend(exc.missing)
                        logger.warning("Card %d failed to extract: %s", i, exc)
                        place_data = None

                    if place_data:
                        self._extracted += 1
                        self._partial += bool(place_data.get("partial"))
                        results.append(place_data)
                        logger.debug(f"Extracted: {place_data.get('title', 'Unknown')}")

                    # Go back to results
                    await page.go_back()
                    await asyncio.sleep(1)

                except Exception as e:
                    logger.warning(f"Error extracting card {i}: {e}")
                    continue

            # Scroll to load more results
            scroll_count += 1
            try:
                feed = page.locator("div[role='feed']")
                await feed.evaluate("el => el.scrollTop = el.scrollHeight")
                await asyncio.sleep(1.5)
            except Exception as exc:
                # Justified broad catch: a scroll failure means "no more
                # results to load", which is a legitimate stop condition. It is
                # logged rather than passed, and it cannot manufacture a
                # successful empty result -- search() still checks whether the
                # places already attempted actually extracted.
                logger.info("Stopped scrolling the results feed: %s", exc)
                break

        return results

    async def _extract_place_details(self, page) -> Optional[Dict[str, Any]]:
        """Extract detailed information from a place page.

        Returns:
            The place dict. It always carries ``partial``, ``selectors_stale``
            and ``missing_fields`` keys so a caller can tell a thin-but-real
            record from a parse failure.

        Raises:
            PlaceExtractionError: No required field (see
                :data:`REQUIRED_PLACE_FIELDS`) could be extracted. Previously
                this returned ``None`` and the caller dropped it silently,
                which is how a total parser failure became an empty success.
        """
        misses: List[str] = []
        try:
            # Wait longer for content to fully load
            await asyncio.sleep(2)

            # Wait for the main details panel
            with self._optional(misses, "details_panel"):
                await page.wait_for_selector("div[role='main']", timeout=5000)

            # Scroll down the details panel to load dynamic content
            # (popular times, reviews, related places are loaded on scroll)
            with self._optional(misses, "lazy_load_scroll"):
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
            with self._optional(misses, "title_h1"):
                # Wait for the place name to appear in the panel
                await page.wait_for_selector("h1.DUwDvf", timeout=3000)
                title_el = page.locator("h1.DUwDvf").first
                if await title_el.count() > 0:
                    page_title = await title_el.text_content()
                    if page_title and page_title.lower() != "results":
                        place["title"] = page_title.strip()

            # Fallback: try generic h1 in main content area
            if not place["title"] or place["title"].lower() == "results":
                with self._optional(misses, "title_h1_fallback"):
                    title_el = page.locator("div[role='main'] h1").first
                    if await title_el.count() > 0:
                        page_title = await title_el.text_content()
                        if page_title and page_title.lower() != "results":
                            place["title"] = page_title.strip()

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
            with self._optional(misses, "hours"):
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
                    with self._optional(misses, "hours_expand"):
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

            # Extract photos from the carousel
            with self._optional(misses, "photos"):
                photo_elements = page.locator("button[jsaction*='heroHeaderImage'] img, div[jsaction*='photo'] img, img.Uf0tqf")
                photo_count = await photo_elements.count()
                for i in range(min(photo_count, 10)):  # Limit to 10 photos
                    photo = photo_elements.nth(i)
                    src = await photo.get_attribute("src")
                    if src and "googleusercontent.com" in src:
                        # Get higher resolution version
                        high_res_src = re.sub(r'=w\d+-h\d+', '=w800-h600', src)
                        place["photos"].append(high_res_src)

            # Menu link
            with self._optional(misses, "menu_link"):
                menu_el = page.locator("a[data-item-id*='menu'], a[aria-label*='Menu']").first
                if await menu_el.count() > 0:
                    place["menu_link"] = await menu_el.get_attribute("href")

            # Order online link
            with self._optional(misses, "order_link"):
                order_el = page.locator("a[data-item-id*='order'], a[aria-label*='Order']").first
                if await order_el.count() > 0:
                    place["order_link"] = await order_el.get_attribute("href")

            # Reserve table link
            with self._optional(misses, "reserve_link"):
                reserve_el = page.locator("a[data-item-id*='reserve'], a[aria-label*='Reserve']").first
                if await reserve_el.count() > 0:
                    place["reserve_link"] = await reserve_el.get_attribute("href")

            # Extract amenities and service options
            with self._optional(misses, "service_options"):
                # Service options (Dine-in, Takeout, Delivery, etc.)
                service_els = page.locator("div[aria-label*='Service options'] span, div[data-tooltip*='Service']")
                service_count = await service_els.count()
                for i in range(service_count):
                    text = await service_els.nth(i).text_content()
                    if text and text.strip():
                        place["service_options"].append(text.strip())

            with self._optional(misses, "accessibility"):
                # Accessibility options
                access_els = page.locator("div[aria-label*='Accessibility'] span, span[aria-label*='Wheelchair']")
                access_count = await access_els.count()
                for i in range(access_count):
                    text = await access_els.nth(i).text_content()
                    if text and text.strip():
                        place["accessibility"].append(text.strip())

            with self._optional(misses, "amenities"):
                # General amenities (from About tab or highlights)
                amenity_els = page.locator("div[aria-label*='Highlights'] span, div[data-attrid*='highlights'] span")
                amenity_count = await amenity_els.count()
                for i in range(amenity_count):
                    text = await amenity_els.nth(i).text_content()
                    if text and text.strip() and len(text.strip()) < 50:
                        place["amenities"].append(text.strip())

            # Extract description/about from the About region
            with self._optional(misses, "description"):
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

            # Fallback description extraction
            if not place["description"]:
                with self._optional(misses, "description_fallback"):
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

            # Extract price per person
            with self._optional(misses, "price_per_person"):
                price_btn = page.locator("button[aria-label*='per person'], button:has-text('per person')").first
                if await price_btn.count() > 0:
                    price_text = await price_btn.text_content()
                    if price_text:
                        # Extract price range like "$1–10 per person"
                        price_match = re.search(r'\$[\d,]+[–-]\$?[\d,]+', price_text)
                        if price_match:
                            place["price_per_person"] = price_match.group(0)

            # Extract service options (Dine-in, Drive-through, Delivery, etc.)
            with self._optional(misses, "service_option_groups"):
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

            # Extract popular times data
            with self._optional(misses, "popular_times"):
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

            # Extract live wait time and current busyness
            with self._optional(misses, "live_busyness"):
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


            # Extract review summary (star breakdown)
            with self._optional(misses, "review_summary"):
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

            # Extract review topics/keywords
            with self._optional(misses, "review_topics"):
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

            # Extract sample reviews (quotes shown at top of reviews section)
            with self._optional(misses, "sample_reviews"):
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
                    except Exception as exc:
                        # Justified: one detached button out of 50 must not
                        # abort the scan of the other 49. Sample reviews are an
                        # optional field, and the enclosing _optional() records
                        # a wholesale failure of the section.
                        logger.debug("Sample review button %d unreadable: %s", i, exc)
                        continue

            # Extract related places ("People also search for")
            with self._optional(misses, "related_places"):
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

            return self._finalise_place(place, misses)

        except ScraperError:
            raise
        except Exception as e:
            # A hard failure here used to become `return None`, which the
            # callers turned into an empty-but-successful result set. Surface
            # it instead; search() decides whether one bad place matters.
            logger.warning("Error extracting place details: %s", e, exc_info=True)
            raise PlaceExtractionError(
                f"Place details extraction raised {type(e).__name__}: {e}",
                missing=list(REQUIRED_PLACE_FIELDS),
            ) from e

    def _finalise_place(
        self, place: Dict[str, Any], misses: List[str]
    ) -> Dict[str, Any]:
        """Attach freshness metadata and enforce the required fields.

        Args:
            place: The partially populated place dict.
            misses: Optional-field names whose extraction raised.

        Returns:
            ``place``, with ``missing_fields``, ``partial`` and
            ``selectors_stale`` set.

        Raises:
            PlaceExtractionError: When a required field is absent.
        """
        missing_required = [f for f in REQUIRED_PLACE_FIELDS if not place.get(f)]
        if missing_required:
            raise PlaceExtractionError(
                "No required field could be extracted "
                f"(missing: {', '.join(missing_required)}); the place panel "
                "selectors no longer match",
                missing=missing_required,
            )

        # A title is recoverable from the URL alone, so a record carrying a
        # title and nothing else is evidence that the details panel did not
        # parse -- not evidence of a business with no address or phone.
        core_present = [f for f in CORE_PLACE_FIELDS if place.get(f)]
        place["missing_fields"] = sorted(set(misses))
        place["partial"] = not core_present
        place["selectors_stale"] = not core_present

        if not core_present:
            logger.error(
                "Place %r extracted with no core field (%s); treating as a "
                "stale-selector partial result",
                place.get("title"),
                ", ".join(CORE_PLACE_FIELDS),
            )
        elif misses:
            logger.info(
                "Place %r extracted with %d optional field(s) unmatched: %s",
                place.get("title"),
                len(set(misses)),
                ", ".join(sorted(set(misses))),
            )
        else:
            logger.info(
                "Extracted place: %s with %d fields populated",
                place.get("title"),
                len([v for v in place.values() if v]),
            )
        return place

    async def _extract_expanded_hours(self, page) -> Optional[Dict[str, List[str]]]:
        """Extract hours from expanded hours table.

        Returns None when no hours row parses -- opening hours are optional and
        plenty of listings have none. A locator that *raises* is deliberately
        not caught here: the caller runs this inside :meth:`_optional`, which
        records the miss, so swallowing it locally would hide it again.
        """
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


# Global job store, backed by the owner-scoped record store.
_job_store = JobStore()


async def get_job_store() -> JobStore:
    """Get the global job store.

    The accessor signature is unchanged, but the returned store is now
    owner-scoped: see :class:`JobStore` for the method signatures, which
    changed (``get``/``delete`` take an owner, ``list_all`` is gone).
    """
    return _job_store


async def run_scrape_job(
    job: ScrapeJob,
    proxy: Optional[str] = None
):
    """
    Run a scrape job in the background.

    Args:
        job: The job to run. ``job.owner`` must be set.
        proxy: Optional proxy URL

    A scraping failure -- including a stale-selector failure, where Google's
    markup changed and nothing could be parsed -- marks the job FAILED with the
    real error. It must never complete with an empty result list, because a
    caller cannot tell that apart from a genuinely empty area.
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
        # An empty result the scraper could not verify is reported as such
        # rather than as a confirmed zero.
        job.empty_unverified = bool(scraper._unverified_empty and not results)
        await store.update(job)

        logger.info(f"Job {job.id} completed with {len(results)} results")

    except SelectorsStaleError as e:
        job.status = JobStatus.FAILED
        job.error = str(e)
        job.selectors_stale = True
        job.completed_at = datetime.now()
        await store.update(job)
        logger.error(
            "Job %s failed: Google Maps selectors are stale (%d attempted, "
            "%d extracted): %s",
            job.id, e.attempted, e.extracted, e,
        )

    except Exception as e:
        # Handle failure
        job.status = JobStatus.FAILED
        job.error = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
        job.completed_at = datetime.now()
        await store.update(job)
        logger.error(f"Job {job.id} failed: {e}", exc_info=True)

    finally:
        await scraper.close()
