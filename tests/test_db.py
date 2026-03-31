"""Tests for SQLite database operations."""

import os
import pytest
from unittest.mock import patch

from content_app.db.sqlite import init_db, save_run, get_run, list_runs


@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary database path."""
    db_path = str(tmp_path / "test.db")
    with patch("content_app.db.sqlite._get_db_path", return_value=db_path):
        yield db_path


class TestDatabase:
    """Tests for database operations."""

    async def test_init_db_creates_table(self, temp_db_path):
        """Test that init_db creates the runs table."""
        with patch("content_app.db.sqlite._get_db_path", return_value=temp_db_path):
            await init_db()
            assert os.path.exists(temp_db_path)

    async def test_save_and_get_run(self, temp_db_path):
        """Test saving and retrieving a run."""
        with patch("content_app.db.sqlite._get_db_path", return_value=temp_db_path):
            await init_db()

            run_data = {
                "run_id": "test-123",
                "topic": "AI trends",
                "platform": "linkedin",
                "tone": "professional",
                "voice_context": "Write professionally.",
                "draft": "Here is some content about AI.",
                "previous_drafts": ["draft1", "draft2"],
                "alignment_score": 85,
                "alignment_feedback": "Good alignment",
                "retry_count": 2,
                "status": "done",
            }

            await save_run(run_data)
            result = await get_run("test-123")

            assert result is not None
            assert result["run_id"] == "test-123"
            assert result["topic"] == "AI trends"
            assert result["platform"] == "linkedin"
            assert result["alignment_score"] == 85
            assert result["previous_drafts"] == ["draft1", "draft2"]
            assert result["status"] == "done"

    async def test_get_run_returns_none_for_missing(self, temp_db_path):
        """Test that get_run returns None for non-existent run."""
        with patch("content_app.db.sqlite._get_db_path", return_value=temp_db_path):
            await init_db()
            result = await get_run("nonexistent-id")
            assert result is None

    async def test_list_runs_returns_recent(self, temp_db_path):
        """Test listing recent runs."""
        with patch("content_app.db.sqlite._get_db_path", return_value=temp_db_path):
            await init_db()

            for i in range(5):
                await save_run({
                    "run_id": f"run-{i}",
                    "topic": f"Topic {i}",
                    "platform": "linkedin",
                    "tone": "casual",
                    "status": "done",
                })

            results = await list_runs(limit=3)
            assert len(results) == 3

    async def test_list_runs_empty_database(self, temp_db_path):
        """Test list_runs on empty database."""
        with patch("content_app.db.sqlite._get_db_path", return_value=temp_db_path):
            await init_db()
            results = await list_runs()
            assert results == []

    async def test_previous_drafts_json_serialization(self, temp_db_path):
        """Test that previous_drafts list is properly serialized/deserialized."""
        with patch("content_app.db.sqlite._get_db_path", return_value=temp_db_path):
            await init_db()

            drafts = ["First attempt", "Second attempt", "Third attempt"]
            await save_run({
                "run_id": "json-test",
                "previous_drafts": drafts,
                "status": "done",
            })

            result = await get_run("json-test")
            assert result["previous_drafts"] == drafts
            assert isinstance(result["previous_drafts"], list)
