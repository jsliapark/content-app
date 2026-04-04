"""Shared pipeline execution: blocking CLI runs and background API runs with event queues."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from content_app.config import get_settings
from content_app.db.sqlite import get_run as db_get_run
from content_app.db.sqlite import init_db, save_run
from content_app.graph.builder import build_graph
from content_app.mcp.brandvoice import BrandvoiceClient
from content_app.providers.claude import ClaudeProvider

logger = logging.getLogger(__name__)

type SSEPayload = dict[str, Any]


class _RunQueueEndSentinel:
    """Single instance marks end of streamed events for one run."""

_RUN_QUEUE_END = _RunQueueEndSentinel()

type RunQueueItem = SSEPayload | _RunQueueEndSentinel

_run_phase: dict[str, str] = {}  # "running" | "complete" | "failed"
_event_history: dict[str, list[SSEPayload]] = {}
_event_queues: dict[str, asyncio.Queue[RunQueueItem]] = {}
_run_results: dict[str, dict[str, Any]] = {}
_registry_lock = asyncio.Lock()


def is_run_queue_end(item: object) -> bool:
    """True if *item* is the sentinel marking end of events for this run."""
    return item is _RUN_QUEUE_END


def _utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _push_event(run_id: str, payload: dict[str, Any]) -> None:
    """Append to history and notify live SSE consumers via the run queue."""
    event: SSEPayload = {"run_id": run_id, "ts": _utc_ts(), **payload}
    async with _registry_lock:
        _event_history.setdefault(run_id, []).append(event)
        q = _event_queues.get(run_id)
    if q is not None:
        await q.put(event)


async def get_event_queue(run_id: str) -> asyncio.Queue[RunQueueItem] | None:
    """Return the asyncio.Queue for *run_id*, or None if not registered."""
    async with _registry_lock:
        return _event_queues.get(run_id)


async def register_run_queue(run_id: str, queue: asyncio.Queue[RunQueueItem]) -> None:
    async with _registry_lock:
        _event_queues[run_id] = queue


async def unregister_run_queue(run_id: str) -> None:
    async with _registry_lock:
        _event_queues.pop(run_id, None)


async def get_run_result(run_id: str) -> dict[str, Any] | None:
    """Final graph result for *run_id*, if the run finished successfully."""
    async with _registry_lock:
        return _run_results.get(run_id)


async def get_event_history(run_id: str) -> list[SSEPayload]:
    """Snapshot of all non-sentinel events emitted for *run_id*."""
    async with _registry_lock:
        return list(_event_history.get(run_id, []))


async def get_run_phase(run_id: str) -> str | None:
    async with _registry_lock:
        return _run_phase.get(run_id)


def build_graph_event_emitter(run_id: str) -> Callable[[dict[str, Any]], Awaitable[None]]:
    """Callback passed into the graph so nodes can emit ``node_start`` / ``node_end``."""

    async def emit(payload: dict[str, Any]) -> None:
        await _push_event(run_id, payload)

    return emit


def _build_initial_state(run_id: str, topic: str, platform: str, tone: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "topic": topic,
        "platform": platform,
        "tone": tone,
        "max_retries": get_settings().max_retries,
    }


async def _execute_pipeline(
    initial_state: dict[str, Any],
    event_queue: asyncio.Queue[RunQueueItem] | None,
) -> dict[str, Any]:
    """Run LangGraph once, persist to SQLite, optionally push SSE-shaped events."""
    run_id = initial_state["run_id"]
    stream = event_queue is not None

    if stream:
        await _push_event(run_id, {"type": "run_started"})

    emit = build_graph_event_emitter(run_id) if stream else None

    async with BrandvoiceClient() as client:
        provider = ClaudeProvider()
        graph = build_graph(client, provider, emit=emit)
        result = await graph.ainvoke(initial_state)

    await save_run(result)

    async with _registry_lock:
        _run_results[run_id] = result

    if stream:
        await _push_event(
            run_id,
            {
                "type": "run_complete",
                "status": result.get("status"),
                "alignment_score": result.get("alignment_score"),
                "retry_count": result.get("retry_count"),
            },
        )
    return result


async def _background_run(
    run_id: str,
    initial_state: dict[str, Any],
    event_queue: asyncio.Queue[RunQueueItem],
) -> None:
    try:
        await _execute_pipeline(initial_state, event_queue)
        async with _registry_lock:
            _run_phase[run_id] = "complete"
    except Exception:
        logger.exception("Background run failed run_id=%s", run_id)
        async with _registry_lock:
            _run_phase[run_id] = "failed"
        await _push_event(
            run_id,
            {"type": "run_failed", "error": "Pipeline error; see server logs."},
        )
    finally:
        await event_queue.put(_RUN_QUEUE_END)


async def run_pipeline_blocking(topic: str, platform: str, tone: str) -> dict[str, Any]:
    """Run the full pipeline and wait for completion (CLI). No event queue or node emits."""
    await init_db()
    run_id = str(uuid.uuid4())
    initial_state = _build_initial_state(run_id, topic, platform, tone)
    return await _execute_pipeline(initial_state, event_queue=None)


async def start_run_async(topic: str, platform: str, tone: str) -> str:
    """Schedule the pipeline; returns *run_id* immediately."""
    await init_db()
    run_id = str(uuid.uuid4())
    queue: asyncio.Queue[RunQueueItem] = asyncio.Queue()
    await register_run_queue(run_id, queue)
    async with _registry_lock:
        _event_history.setdefault(run_id, [])
        _run_phase[run_id] = "running"
    initial_state = _build_initial_state(run_id, topic, platform, tone)

    asyncio.create_task(
        _background_run(run_id, initial_state, queue),
        name=f"content-run-{run_id[:8]}",
    )
    return run_id


async def snapshot_run(run_id: str) -> dict[str, Any] | None:
    """Resolve a run for GET /api/runs/{id}: memory result, running state, or DB row."""
    phase = await get_run_phase(run_id)
    result = await get_run_result(run_id)
    if result is not None:
        return {
            "run_id": run_id,
            "phase": phase or "complete",
            "result": result,
            "events": await get_event_history(run_id),
        }
    if phase == "running":
        return {
            "run_id": run_id,
            "phase": "running",
            "result": None,
            "events": await get_event_history(run_id),
        }
    if phase == "failed":
        return {
            "run_id": run_id,
            "phase": "failed",
            "result": None,
            "events": await get_event_history(run_id),
        }
    row = await db_get_run(run_id)
    if row is not None:
        return {
            "run_id": run_id,
            "phase": "complete",
            "result": row,
            "events": [],
        }
    return None
