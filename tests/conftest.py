"""Shared fixtures for tests."""

import pytest
from pathlib import Path


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temporary directory as a Path."""
    return tmp_path


@pytest.fixture
def default_options():
    """Default processing options."""
    return {
        "flatten": True,
        "comments": True,
        "macros": True,
        "bibliography": True,
        "encoding": "utf-8",
        "verbose": False,
    }
