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
