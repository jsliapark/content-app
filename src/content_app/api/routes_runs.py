"""Run lifecycle: start pipeline, SSE events, snapshot."""

from __future__ import annotations

import asyncio
import json
from fastapi import APIRouter, HTTPException, status
from sse_starlette.sse import EventSourceResponse

from content_app.api.schemas import StartRunRequest, StartRunResponse
from content_app.db.sqlite import list_runs as db_list_runs
from content_app.runner import (
    get_event_history,
    get_run_phase,
    snapshot_run,
    start_run_async,
)

router = APIRouter(prefix="/runs", tags=["runs"])

_SSE_POLL_S = 0.05


@router.post("", response_model=StartRunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(body: StartRunRequest) -> StartRunResponse:
    run_id = await start_run_async(body.topic, body.platform, body.tone)
    return StartRunResponse(run_id=run_id)


@router.get("", response_model=list[dict])
async def list_all_runs(limit: int = 20) -> list[dict]:
    """List recent runs from SQLite (newest first)."""
    return await db_list_runs(limit=limit)


@router.get("/{run_id}/events")
async def stream_run_events(run_id: str) -> EventSourceResponse:
    if await snapshot_run(run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    async def event_generator():
        last_len = 0
        try:
            while True:
                hist = await get_event_history(run_id)
                phase = await get_run_phase(run_id)
                while last_len < len(hist):
                    yield {"data": json.dumps(hist[last_len])}
                    last_len += 1
                if phase in ("complete", "failed"):
                    break
                await asyncio.sleep(_SSE_POLL_S)
        except asyncio.CancelledError:
            raise

    return EventSourceResponse(event_generator())


@router.get("/{run_id}")
async def get_run_snapshot(run_id: str):
    snap = await snapshot_run(run_id)
    if snap is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return snap
