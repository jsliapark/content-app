"""FastAPI entry point for Docker / uvicorn (``src.main:app``).

Registers all API routes and is the target for supervisord:
    /app/.venv/bin/uvicorn src.main:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from content_app.api.routes_brand import router as brand_router
from content_app.config import configure_logging
from content_app.db.sqlite import list_runs as db_list_runs
from content_app.runner import (
    get_event_history,
    get_event_queue,
    get_run_phase,
    is_run_queue_end,
    snapshot_run,
    start_run_async,
)

logger = logging.getLogger(__name__)


# ── Pydantic models ───────────────────────────────────────────────────────────

class StartRunRequest(BaseModel):
    topic: str
    platform: str
    tone: str


class StartRunResponse(BaseModel):
    run_id: str


class RunSnapshot(BaseModel):
    run_id: str
    phase: str
    result: dict[str, Any] | None
    events: list[dict[str, Any]]


# ── App factory ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging()
    yield


app = FastAPI(title="content-app", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Brand routes (profile, samples, guidelines) — reuse existing router
app.include_router(brand_router, prefix="/api")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/runs", response_model=StartRunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(body: StartRunRequest) -> StartRunResponse:
    run_id = await start_run_async(body.topic, body.platform, body.tone)
    logger.debug("Started run %s", run_id)
    return StartRunResponse(run_id=run_id)


@app.get("/api/runs", response_model=list[dict])
async def list_runs(limit: int = 20) -> list[dict]:
    return await db_list_runs(limit=limit)


@app.get("/api/runs/{run_id}", response_model=RunSnapshot)
async def get_run(run_id: str) -> RunSnapshot:
    snap = await snapshot_run(run_id)
    if snap is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return RunSnapshot(**snap)


@app.get("/api/runs/{run_id}/events")
async def stream_run_events(run_id: str) -> EventSourceResponse:
    """Polling-based SSE — replays history then tails live events."""
    if await snapshot_run(run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    _POLL_INTERVAL_S = 0.05

    async def event_generator() -> AsyncIterator[dict[str, str]]:
        last_len = 0
        try:
            while True:
                hist = await get_event_history(run_id)
                phase = await get_run_phase(run_id)
                for ev in hist[last_len:]:
                    yield {"data": json.dumps(ev)}
                last_len = len(hist)
                if phase in ("complete", "failed"):
                    break
                await asyncio.sleep(_POLL_INTERVAL_S)
        except asyncio.CancelledError:
            raise

    return EventSourceResponse(event_generator())


@app.get("/api/runs/{run_id}/stream")
async def stream_run(run_id: str) -> EventSourceResponse:
    """Queue-based SSE stream — delivers events as they happen in real time."""
    queue = await get_event_queue(run_id)
    if queue is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found or already finished",
        )

    async def event_generator() -> AsyncIterator[dict[str, str]]:
        try:
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    # Heartbeat keeps the connection alive through idle periods
                    yield {"data": json.dumps({"type": "heartbeat"})}
                    continue
                if is_run_queue_end(item):
                    break
                yield {"data": json.dumps(item)}
        except asyncio.CancelledError:
            raise

    return EventSourceResponse(
        event_generator(),
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
