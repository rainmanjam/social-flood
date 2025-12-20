"""
Background task management for DataForSEO async APIs.

Handles:
- Tracking pending review tasks
- Polling for completed tasks
- Caching completed results in Redis
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any, List, Set
from dataclasses import dataclass, field

from app.core.cache_manager import cache_manager

logger = logging.getLogger("uvicorn")

# Task tracking namespace
TASK_NAMESPACE = "dataforseo:tasks"

# Polling configuration
POLL_INTERVAL_SECONDS = 10     # How often to check for ready tasks
POLL_MAX_AGE_HOURS = 24        # Stop polling tasks older than this
TASK_TTL_SECONDS = 86400       # 24 hours


@dataclass
class TrackedTask:
    """A pending review task being tracked."""
    task_id: str
    place_id: Optional[str]
    cid: Optional[str]
    keyword: Optional[str]
    created_at: float = field(default_factory=time.time)
    poll_count: int = 0
    status: str = "pending"


class ReviewsTaskManager:
    """
    Manages async review tasks with background polling.

    When a review task is submitted, it's tracked here. A background
    task periodically checks for completed tasks and caches results.
    """

    def __init__(self):
        """Initialize the task manager."""
        self._tracked_tasks: Dict[str, TrackedTask] = {}
        self._poll_task: Optional[asyncio.Task] = None
        self._running = False
        self._client = None  # Will be set when started

        # Stats
        self._stats = {
            "tasks_tracked": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "poll_cycles": 0
        }

    async def start(self, client):
        """
        Start the background polling task.

        Args:
            client: DataForSEO client instance
        """
        if self._running:
            return

        self._client = client
        self._running = True

        # Load any tracked tasks from Redis
        await self._load_tracked_tasks()

        # Start polling
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info("Reviews task manager started")

    async def stop(self):
        """Stop the background polling task."""
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        logger.info("Reviews task manager stopped")

    async def track_task(
        self,
        task_id: str,
        place_id: Optional[str] = None,
        cid: Optional[str] = None,
        keyword: Optional[str] = None
    ):
        """
        Start tracking a new review task.

        Args:
            task_id: DataForSEO task ID
            place_id: Google Place ID (optional)
            cid: Google CID (optional)
            keyword: Search keyword (optional)
        """
        task = TrackedTask(
            task_id=task_id,
            place_id=place_id,
            cid=cid,
            keyword=keyword
        )

        self._tracked_tasks[task_id] = task
        self._stats["tasks_tracked"] += 1

        # Persist to Redis
        await self._save_tracked_task(task)

        logger.info(f"Tracking review task: {task_id}")

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a tracked task.

        Returns cached results if available, otherwise current status.

        Args:
            task_id: Task ID to check

        Returns:
            Task status and results (if completed)
        """
        # Check cache first (completed tasks)
        cached = await self._get_cached_result(task_id)
        if cached:
            return cached

        # Check if we're tracking it
        if task_id in self._tracked_tasks:
            task = self._tracked_tasks[task_id]
            return {
                "task_id": task_id,
                "status": task.status,
                "poll_count": task.poll_count,
                "age_seconds": time.time() - task.created_at,
                "from_cache": False
            }

        return None

    async def _poll_loop(self):
        """Background polling loop."""
        while self._running:
            try:
                await self._poll_ready_tasks()
                self._stats["poll_cycles"] += 1
            except Exception as e:
                logger.error(f"Poll loop error: {e}")

            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def _poll_ready_tasks(self):
        """Check for completed tasks and cache results."""
        if not self._client or not self._tracked_tasks:
            return

        # Get list of ready tasks from DataForSEO
        try:
            ready_task_ids = await self._client.check_reviews_task_ready()
        except Exception as e:
            logger.error(f"Error checking ready tasks: {e}")
            return

        # Process ready tasks
        for task_id in ready_task_ids:
            if task_id in self._tracked_tasks:
                await self._process_completed_task(task_id)

        # Clean up old tasks
        await self._cleanup_old_tasks()

    async def _process_completed_task(self, task_id: str):
        """Fetch and cache results for a completed task."""
        task = self._tracked_tasks.get(task_id)
        if not task:
            return

        try:
            # Fetch results
            result = await self._client.get_reviews_task(task_id)

            if result.get("status") == "completed":
                # Cache the result
                await self._cache_result(task_id, result, task)

                # Update stats
                self._stats["tasks_completed"] += 1
                task.status = "completed"

                logger.info(f"Cached completed review task: {task_id}")

            elif result.get("status") == "error":
                task.status = "error"
                self._stats["tasks_failed"] += 1
                logger.error(f"Review task failed: {task_id}")

            else:
                # Still processing
                task.poll_count += 1

        except Exception as e:
            logger.error(f"Error processing task {task_id}: {e}")
            task.poll_count += 1

    async def _cache_result(
        self,
        task_id: str,
        result: Dict[str, Any],
        task: TrackedTask
    ):
        """Cache completed task results."""
        # Cache by task ID
        await cache_manager.set(
            f"task:{task_id}",
            result,
            ttl=TASK_TTL_SECONDS,
            namespace=TASK_NAMESPACE
        )

        # Also cache by place_id/cid for quick lookup
        if task.place_id:
            await cache_manager.set(
                f"place:{task.place_id}",
                result,
                ttl=TASK_TTL_SECONDS,
                namespace=TASK_NAMESPACE
            )

        if task.cid:
            await cache_manager.set(
                f"cid:{task.cid}",
                result,
                ttl=TASK_TTL_SECONDS,
                namespace=TASK_NAMESPACE
            )

        # Remove from active tracking
        del self._tracked_tasks[task_id]

        # Remove from Redis tracking
        await cache_manager.delete(f"tracked:{task_id}", namespace=TASK_NAMESPACE)

    async def _get_cached_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get cached result for a task."""
        result = await cache_manager.get(
            f"task:{task_id}",
            namespace=TASK_NAMESPACE
        )
        if result:
            result["from_cache"] = True
        return result

    async def _cleanup_old_tasks(self):
        """Remove tasks that are too old."""
        max_age = POLL_MAX_AGE_HOURS * 3600
        now = time.time()

        to_remove = []
        for task_id, task in self._tracked_tasks.items():
            if now - task.created_at > max_age:
                to_remove.append(task_id)
                logger.warning(f"Removing stale task: {task_id}")

        for task_id in to_remove:
            del self._tracked_tasks[task_id]
            await cache_manager.delete(f"tracked:{task_id}", namespace=TASK_NAMESPACE)

    async def _save_tracked_task(self, task: TrackedTask):
        """Save tracked task to Redis for persistence."""
        await cache_manager.set(
            f"tracked:{task.task_id}",
            {
                "task_id": task.task_id,
                "place_id": task.place_id,
                "cid": task.cid,
                "keyword": task.keyword,
                "created_at": task.created_at,
                "status": task.status
            },
            ttl=TASK_TTL_SECONDS,
            namespace=TASK_NAMESPACE
        )

    async def _load_tracked_tasks(self):
        """Load tracked tasks from Redis on startup."""
        try:
            # This would need the cache manager to support pattern scanning
            # For now, we start fresh each time
            logger.info("Task manager starting fresh (no persistent state)")
        except Exception as e:
            logger.error(f"Error loading tracked tasks: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get task manager statistics."""
        return {
            "running": self._running,
            "active_tasks": len(self._tracked_tasks),
            "poll_interval_seconds": POLL_INTERVAL_SECONDS,
            **self._stats
        }


# Global task manager instance
reviews_task_manager = ReviewsTaskManager()
