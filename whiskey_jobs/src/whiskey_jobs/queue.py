"""Queue implementations for whiskey_jobs."""

from __future__ import annotations

import asyncio
import heapq
from abc import ABC, abstractmethod
from collections import deque

from .job import Job


class JobQueue(ABC):
    """Abstract base class for job queues."""

    @abstractmethod
    async def push(self, job: Job) -> None:
        """Add a job to the queue."""
        pass

    @abstractmethod
    async def pop(self) -> Job | None:
        """Remove and return a job from the queue."""
        pass

    @abstractmethod
    async def peek(self) -> Job | None:
        """Return the next job without removing it."""
        pass

    @abstractmethod
    def size(self) -> int:
        """Get the number of jobs in the queue."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all jobs from the queue."""
        pass


class MemoryQueue(JobQueue):
    """In-memory FIFO job queue."""

    def __init__(self):
        """Initialize the queue."""
        self._queue: deque[Job] = deque()
        self._lock = asyncio.Lock()

    async def push(self, job: Job) -> None:
        """Add a job to the queue."""
        async with self._lock:
            self._queue.append(job)

    async def pop(self) -> Job | None:
        """Remove and return a job from the queue."""
        async with self._lock:
            if self._queue:
                return self._queue.popleft()
            return None

    async def peek(self) -> Job | None:
        """Return the next job without removing it."""
        async with self._lock:
            if self._queue:
                return self._queue[0]
            return None

    def size(self) -> int:
        """Get the number of jobs in the queue."""
        return len(self._queue)

    def clear(self) -> None:
        """Clear all jobs from the queue."""
        self._queue.clear()


class PriorityQueue(JobQueue):
    """In-memory priority queue for jobs."""

    def __init__(self):
        """Initialize the priority queue."""
        self._heap: list[tuple[int, int, Job]] = []
        self._counter = 0  # For stable sorting of same priority
        self._lock = asyncio.Lock()

    async def push(self, job: Job) -> None:
        """Add a job to the queue."""
        async with self._lock:
            # Use negative priority for max heap behavior
            priority = -job.priority.value
            self._counter += 1
            heapq.heappush(self._heap, (priority, self._counter, job))

    async def pop(self) -> Job | None:
        """Remove and return the highest priority job."""
        async with self._lock:
            if self._heap:
                _, _, job = heapq.heappop(self._heap)
                return job
            return None

    async def peek(self) -> Job | None:
        """Return the highest priority job without removing it."""
        async with self._lock:
            if self._heap:
                _, _, job = self._heap[0]
                return job
            return None

    def size(self) -> int:
        """Get the number of jobs in the queue."""
        return len(self._heap)

    def clear(self) -> None:
        """Clear all jobs from the queue."""
        self._heap.clear()
        self._counter = 0


class MultiQueue:
    """Manages multiple named queues."""

    def __init__(self, queue_factory: type[JobQueue] = MemoryQueue):
        """Initialize the multi-queue.

        Args:
            queue_factory: Factory class for creating queues
        """
        self._queues: dict[str, JobQueue] = {}
        self._queue_factory = queue_factory
        self._lock = asyncio.Lock()

    async def get_queue(self, name: str) -> JobQueue:
        """Get or create a named queue.

        Args:
            name: Queue name

        Returns:
            The queue instance
        """
        async with self._lock:
            if name not in self._queues:
                self._queues[name] = self._queue_factory()
            return self._queues[name]

    async def push(self, job: Job) -> None:
        """Add a job to its designated queue."""
        queue = await self.get_queue(job.queue)
        await queue.push(job)

    async def pop(self, queue_name: str) -> Job | None:
        """Remove and return a job from a specific queue."""
        queue = await self.get_queue(queue_name)
        return await queue.pop()

    def list_queues(self) -> list[str]:
        """List all queue names."""
        return list(self._queues.keys())

    def size(self, queue_name: str | None = None) -> int:
        """Get the size of a specific queue or all queues.

        Args:
            queue_name: Optional queue name (all queues if None)

        Returns:
            Total number of jobs
        """
        if queue_name:
            queue = self._queues.get(queue_name)
            return queue.size() if queue else 0
        else:
            return sum(q.size() for q in self._queues.values())

    def clear(self, queue_name: str | None = None) -> None:
        """Clear jobs from a specific queue or all queues.

        Args:
            queue_name: Optional queue name (all queues if None)
        """
        if queue_name:
            queue = self._queues.get(queue_name)
            if queue:
                queue.clear()
        else:
            for queue in self._queues.values():
                queue.clear()
