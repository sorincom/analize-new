"""Pytest configuration and fixtures."""

import tempfile
from pathlib import Path

import pytest

from analize.app import create_app
from analize.dal import Database


@pytest.fixture
def app():
    """Create application for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        app = create_app("development")
        app.config["TESTING"] = True
        app.config["DATA_DB_PATH"] = tmpdir_path / "test_data.db"
        app.config["CONFIG_DB_PATH"] = tmpdir_path / "test_config.db"
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
    return Database(app.config["DATA_DB_PATH"], app.config["CONFIG_DB_PATH"])


@pytest.fixture
def sample_user(db):
    """Create a sample user."""
    user_id = db.create_user(name="Test User", sex="M", date_of_birth="1994-01-01")
    return db.get_user(user_id)
