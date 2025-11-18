"""Pytest configuration and fixtures."""

import tempfile
from pathlib import Path

import pytest

from analize.app import create_app
from analize.mcp import DatabaseMCP


@pytest.fixture
def app():
    """Create application for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        app = create_app("development")
        app.config["TESTING"] = True
        app.config["DATABASE_PATH"] = tmpdir_path / "test.db"
        app.config["UPLOAD_DIR"] = tmpdir_path / "uploads"
        app.config["UPLOAD_DIR"].mkdir()

        yield app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def db(app):
    """Create database instance."""
    return DatabaseMCP(app.config["DATABASE_PATH"])


@pytest.fixture
def sample_user(db):
    """Create a sample user."""
    user_id = db.create_user(name="Test User", sex="M", age=30)
    return db.get_user(user_id)
