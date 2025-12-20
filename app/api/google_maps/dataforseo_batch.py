"""
Batch request queue for DataForSEO API.

Collects multiple requests and sends them in batches to reduce API calls.
DataForSEO supports up to 100 tasks per request.

Features:
- Size-based batching (sends when threshold reached)
- Request deduplication
- Async result waiting
- Automatic timeout handling
"""

import asyncio
import logging
import time
import hashlib
import json
from typing import Optional, Dict, Any, List, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("uvicorn")

# Batch configuration
BATCH_SIZE_THRESHOLD = 10      # Send batch when this many requests queued
BATCH_TIMEOUT_SECONDS = 5.0    # Maximum wait time before sending partial batch
MAX_BATCH_SIZE = 100           # DataForSEO API limit


class RequestType(str, Enum):
    """Types of batchable requests."""
    SEARCH = "search"
    DETAILS = "details"
    REVIEWS_SUBMIT = "reviews_submit"


@dataclass
class PendingRequest:
    """A pending request waiting for batch processing."""
    request_id: str
    request_type: RequestType
    params: Dict[str, Any]
    future: asyncio.Future
    created_at: float = field(default_factory=time.time)

    def get_cache_key(self) -> str:
        """Generate a cache key for deduplication."""
        key_data = {
            "type": self.request_type.value,
            **self.params
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()


class BatchQueue:
    """
    Queue for collecting and batching DataForSEO API requests.

    When the queue reaches BATCH_SIZE_THRESHOLD or BATCH_TIMEOUT_SECONDS
    elapses, all pending requests are sent in a single API call.
    """

    def __init__(
        self,
        batch_processor: Callable[[List[Dict]], Awaitable[Dict]],
        request_type: RequestType,
        batch_size: int = BATCH_SIZE_THRESHOLD,
        timeout: float = BATCH_TIMEOUT_SECONDS
    ):
        """
        Initialize the batch queue.

        Args:
            batch_processor: Async function to process a batch of requests
            request_type: Type of requests this queue handles
            batch_size: Number of requests to trigger a batch
            timeout: Maximum seconds to wait before processing partial batch
        """
        self._processor = batch_processor
        self._request_type = request_type
        self._batch_size = min(batch_size, MAX_BATCH_SIZE)
        self._timeout = timeout

        self._queue: List[PendingRequest] = []
        self._lock = asyncio.Lock()
        self._pending_keys: Dict[str, PendingRequest] = {}  # For deduplication
        self._timer_task: Optional[asyncio.Task] = None

        # Stats
        self._stats = {
            "requests_queued": 0,
            "batches_sent": 0,
            "requests_deduplicated": 0,
            "total_api_calls_saved": 0
        }

    async def add_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add a request to the batch queue.

        If an identical request is already pending, returns the same future
        to deduplicate API calls.

        Args:
            params: Request parameters

        Returns:
            Result of the API call (waits for batch processing)
        """
        async with self._lock:
            # Create request
            request = PendingRequest(
                request_id=f"{self._request_type.value}_{time.time()}_{len(self._queue)}",
                request_type=self._request_type,
                params=params,
                future=asyncio.get_event_loop().create_future()
            )

            # Check for duplicate
            cache_key = request.get_cache_key()
            if cache_key in self._pending_keys:
                existing = self._pending_keys[cache_key]
                self._stats["requests_deduplicated"] += 1
                logger.debug(f"Request deduplicated: {cache_key}")
                # Return the existing future (will resolve with same result)
                return await existing.future

            # Add to queue
            self._queue.append(request)
            self._pending_keys[cache_key] = request
            self._stats["requests_queued"] += 1

            queue_size = len(self._queue)
            logger.debug(f"Request added to batch queue: {queue_size}/{self._batch_size}")

            # Check if we should process
            if queue_size >= self._batch_size:
                # Process immediately
                await self._process_batch()
            elif self._timer_task is None or self._timer_task.done():
                # Start timeout timer
                self._timer_task = asyncio.create_task(self._timeout_handler())

        # Wait for result
        return await request.future

    async def _timeout_handler(self):
        """Handle batch timeout - process partial batch if threshold not reached."""
        await asyncio.sleep(self._timeout)

        async with self._lock:
            if self._queue:
                logger.debug(f"Batch timeout reached, processing {len(self._queue)} requests")
                await self._process_batch()

    async def _process_batch(self):
        """Process all pending requests in a single batch."""
        if not self._queue:
            return

        # Take all pending requests
        batch = self._queue.copy()
        self._queue.clear()
        self._pending_keys.clear()

        # Cancel timer
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
        self._timer_task = None

        # Calculate savings
        savings = len(batch) - 1  # All but one call saved
        self._stats["total_api_calls_saved"] += max(0, savings)
        self._stats["batches_sent"] += 1

        logger.info(
            f"Processing batch: {len(batch)} requests in 1 API call "
            f"(saved {savings} API calls)"
        )

        try:
            # Build batch request
            batch_params = [req.params for req in batch]

            # Call the processor
            results = await self._processor(batch_params)

            # Distribute results to waiting futures
            self._distribute_results(batch, results)

        except Exception as e:
            # On error, reject all futures
            error_result = {"success": False, "error": str(e)}
            for request in batch:
                if not request.future.done():
                    request.future.set_result(error_result)
            logger.error(f"Batch processing error: {e}")

    def _distribute_results(
        self,
        batch: List[PendingRequest],
        results: Dict[str, Any]
    ):
        """Distribute batch results to individual request futures."""
        # DataForSEO returns results in "tasks" array matching request order
        tasks = results.get("tasks", [])

        for i, request in enumerate(batch):
            if request.future.done():
                continue

            try:
                if i < len(tasks):
                    task_result = tasks[i]
                    # Wrap in standard response format
                    request.future.set_result({
                        "success": task_result.get("status_code") == 20000,
                        "result": task_result.get("result", []),
                        "cost": task_result.get("cost"),
                        "from_batch": True,
                        "batch_size": len(batch)
                    })
                else:
                    request.future.set_result({
                        "success": False,
                        "error": "No result for this request in batch",
                        "from_batch": True
                    })
            except Exception as e:
                request.future.set_result({
                    "success": False,
                    "error": str(e),
                    "from_batch": True
                })

    async def flush(self):
        """Force processing of any pending requests."""
        async with self._lock:
            if self._queue:
                await self._process_batch()

    def get_stats(self) -> Dict[str, Any]:
        """Get batch queue statistics."""
        return {
            "queue_type": self._request_type.value,
            "current_queue_size": len(self._queue),
            "batch_threshold": self._batch_size,
            "timeout_seconds": self._timeout,
            **self._stats,
            "estimated_cost_savings_usd": f"${self._stats['total_api_calls_saved'] * 0.01:.2f}"
        }


class BatchQueueManager:
    """
    Manages multiple batch queues for different request types.
    """

    def __init__(self):
        """Initialize the batch queue manager."""
        self._queues: Dict[RequestType, BatchQueue] = {}
        self._lock = asyncio.Lock()

    def register_queue(
        self,
        request_type: RequestType,
        processor: Callable[[List[Dict]], Awaitable[Dict]],
        batch_size: int = BATCH_SIZE_THRESHOLD,
        timeout: float = BATCH_TIMEOUT_SECONDS
    ):
        """
        Register a new batch queue for a request type.

        Args:
            request_type: Type of requests
            processor: Async function to process batched requests
            batch_size: Batch size threshold
            timeout: Batch timeout
        """
        self._queues[request_type] = BatchQueue(
            batch_processor=processor,
            request_type=request_type,
            batch_size=batch_size,
            timeout=timeout
        )
        logger.info(f"Registered batch queue for {request_type.value}")

    async def add_request(
        self,
        request_type: RequestType,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Add a request to the appropriate batch queue.

        Args:
            request_type: Type of request
            params: Request parameters

        Returns:
            Result of the API call

        Raises:
            ValueError: If no queue registered for request type
        """
        if request_type not in self._queues:
            raise ValueError(f"No batch queue registered for {request_type.value}")

        return await self._queues[request_type].add_request(params)

    async def flush_all(self):
        """Flush all pending requests in all queues."""
        for queue in self._queues.values():
            await queue.flush()

    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all queues."""
        return {
            request_type.value: queue.get_stats()
            for request_type, queue in self._queues.items()
        }


# Global batch queue manager
batch_queue_manager = BatchQueueManager()
