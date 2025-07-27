"""Test configuration and fixtures for whiskey_jobs."""

from typing import Any

import pytest
from whiskey import Whiskey

from whiskey_jobs import configure_jobs


@pytest.fixture
def app() -> Whiskey:
    """Create a test Whiskey application."""
    return Whiskey()


@pytest.fixture
def app_with_jobs(app: Whiskey) -> Whiskey:
    """Create a Whiskey app with jobs extension."""
    app.use(configure_jobs(auto_start=False))  # Don't auto-start for tests
    return app


@pytest.fixture
async def running_app(app_with_jobs: Whiskey) -> Whiskey:
    """Create a running Whiskey app with jobs extension."""
    await app_with_jobs.jobs.start()
    yield app_with_jobs
    await app_with_jobs.jobs.stop()


@pytest.fixture
def mock_service() -> Any:
    """Create a mock service for testing DI."""

    class MockService:
        def __init__(self):
            self.calls = []

        async def process(self, data: Any) -> dict:
            self.calls.append(data)
            return {"processed": True, "data": data}

    return MockService()


@pytest.fixture
async def cleanup_jobs(app_with_jobs: Whiskey):
    """Cleanup any jobs after tests."""
    yield
    # Clear all queues
    await app_with_jobs.jobs.clear_queue()
    # Ensure everything is stopped
    if app_with_jobs.jobs._running:
        await app_with_jobs.jobs.stop()
