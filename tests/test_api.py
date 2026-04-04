"""FastAPI routes (Phase 2)."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from content_app.api.app import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_post_runs_created(mocker, client: TestClient) -> None:
    mocker.patch(
        "content_app.api.routes_runs.start_run_async",
        new_callable=AsyncMock,
        return_value="run-id-abc",
    )
    r = client.post(
        "/api/runs",
        json={"topic": "AI", "platform": "linkedin", "tone": "professional"},
    )
    assert r.status_code == 201
    assert r.json() == {"run_id": "run-id-abc"}


def test_post_runs_validation(client: TestClient) -> None:
    r = client.post(
        "/api/runs",
        json={"topic": "AI", "platform": "invalid", "tone": "x"},
    )
    assert r.status_code == 422


def test_get_run_not_found(client: TestClient) -> None:
    r = client.get("/api/runs/does-not-exist-000")
    assert r.status_code == 404


def test_get_events_not_found(client: TestClient) -> None:
    r = client.get("/api/runs/does-not-exist-000/events")
    assert r.status_code == 404


def test_get_events_stream(mocker, client: TestClient) -> None:
    mocker.patch(
        "content_app.api.routes_runs.snapshot_run",
        new_callable=AsyncMock,
        return_value={"run_id": "r1", "phase": "running", "result": None, "events": []},
    )
    mocker.patch(
        "content_app.api.routes_runs.get_event_history",
        new_callable=AsyncMock,
        side_effect=[
            [{"type": "run_started", "run_id": "r1"}],
            [{"type": "run_started", "run_id": "r1"}, {"type": "run_complete", "run_id": "r1"}],
        ],
    )
    mocker.patch(
        "content_app.api.routes_runs.get_run_phase",
        new_callable=AsyncMock,
        side_effect=["running", "complete"],
    )

    with client.stream("GET", "/api/runs/r1/events") as r:
        assert r.status_code == 200
        body = r.read().decode()
        assert "run_started" in body
        assert "run_complete" in body


def test_list_runs(mocker, client: TestClient) -> None:
    mocker.patch(
        "content_app.api.routes_runs.db_list_runs",
        new_callable=AsyncMock,
        return_value=[
            {
                "run_id": "r1",
                "topic": "AI",
                "platform": "linkedin",
                "tone": "professional",
                "alignment_score": 72,
                "status": "complete",
                "created_at": "2025-01-01 12:00:00",
                "draft": "Hello",
                "voice_context": None,
                "previous_drafts": [],
                "alignment_feedback": None,
                "retry_count": 0,
                "updated_at": "2025-01-01 12:00:00",
            }
        ],
    )
    r = client.get("/api/runs?limit=5")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["run_id"] == "r1"
    assert data[0]["topic"] == "AI"


def test_get_run_snapshot_ok(mocker, client: TestClient) -> None:
    mocker.patch(
        "content_app.api.routes_runs.snapshot_run",
        new_callable=AsyncMock,
        return_value={
            "run_id": "r1",
            "phase": "complete",
            "result": {"draft": "hi", "status": "done"},
            "events": [],
        },
    )
    r = client.get("/api/runs/r1")
    assert r.status_code == 200
    data = r.json()
    assert data["run_id"] == "r1"
    assert data["result"]["status"] == "done"


def test_brand_overview(mocker, client: TestClient) -> None:
    mock_inner = mocker.AsyncMock()
    mock_inner.get_profile = AsyncMock(return_value={"tone": "pro"})
    mock_inner.list_samples = AsyncMock(return_value={"samples": []})
    cm = mocker.MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_inner)
    cm.__aexit__ = AsyncMock(return_value=None)
    mocker.patch("content_app.api.routes_brand.BrandvoiceClient", return_value=cm)

    r = client.get("/api/brand/overview")
    assert r.status_code == 200
    data = r.json()
    assert data["profile"] == {"tone": "pro"}
    assert data["samples"] == []
    mock_inner.get_profile.assert_awaited_once()
    mock_inner.list_samples.assert_awaited_once()


def test_brand_profile(mocker, client: TestClient) -> None:
    mock_inner = mocker.AsyncMock()
    mock_inner.get_profile = AsyncMock(return_value={"guidelines": "Be brief."})
    cm = mocker.MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_inner)
    cm.__aexit__ = AsyncMock(return_value=None)
    mocker.patch("content_app.api.routes_brand.BrandvoiceClient", return_value=cm)

    r = client.get("/api/brand/profile")
    assert r.status_code == 200
    assert r.json() == {"guidelines": "Be brief."}


def test_brand_ingest_samples(mocker, client: TestClient) -> None:
    mock_inner = mocker.AsyncMock()
    mock_inner.ingest_samples = AsyncMock(return_value={"ingested": 1})
    cm = mocker.MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_inner)
    cm.__aexit__ = AsyncMock(return_value=None)
    mocker.patch("content_app.api.routes_brand.BrandvoiceClient", return_value=cm)

    r = client.post("/api/brand/samples", json={"content": "sample text here"})
    assert r.status_code == 200
    assert r.json() == {"ingested": 1}
    mock_inner.ingest_samples.assert_awaited_once_with("sample text here")


def test_brand_set_guidelines(mocker, client: TestClient) -> None:
    mock_inner = mocker.AsyncMock()
    mock_inner.set_guidelines = AsyncMock(return_value={"ok": True})
    cm = mocker.MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_inner)
    cm.__aexit__ = AsyncMock(return_value=None)
    mocker.patch("content_app.api.routes_brand.BrandvoiceClient", return_value=cm)

    r = client.put("/api/brand/guidelines", json={"guidelines": "Use active voice."})
    assert r.status_code == 200
    mock_inner.set_guidelines.assert_awaited_once_with("Use active voice.")
