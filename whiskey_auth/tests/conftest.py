"""Common test fixtures for whiskey_auth."""

import pytest

from whiskey import Whiskey
from whiskey_auth import auth_extension


@pytest.fixture
def app():
    """Create a Whiskey app with auth extension."""
    app = Whiskey()
    app.use(auth_extension)
    return app


@pytest.fixture
def clean_app():
    """Create a clean Whiskey app without extensions."""
    return Whiskey()
