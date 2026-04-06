"""Pytest hooks and shared fixtures."""

import os

# Before test modules import ``content_app``, force a threshold that matches graph test scores (85, 80, …).
os.environ["ALIGNMENT_THRESHOLD"] = "70"


def pytest_configure() -> None:
    """Clear settings cache so the env override wins over any earlier ``get_settings()`` call."""
    try:
        from content_app.config import get_settings

        get_settings.cache_clear()
    except ImportError:
        pass
