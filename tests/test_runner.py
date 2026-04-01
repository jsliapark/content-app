"""Tests for shared runner and event queue registry."""

import asyncio

import pytest

from content_app.runner import (
    get_event_queue,
    get_run_result,
    is_run_queue_end,
    run_pipeline_blocking,
    start_run_async,
)


@pytest.fixture(autouse=True)
async def clear_runner_registry():
    import content_app.runner as runner_mod

    async with runner_mod._registry_lock:
        runner_mod._event_queues.clear()
        runner_mod._run_results.clear()
        runner_mod._event_history.clear()
        runner_mod._run_phase.clear()
    yield
    async with runner_mod._registry_lock:
        runner_mod._event_queues.clear()
        runner_mod._run_results.clear()
        runner_mod._event_history.clear()
        runner_mod._run_phase.clear()


async def _drain_until_sentinel(queue: asyncio.Queue, timeout: float = 5.0) -> list:
    items = []
    while True:
        item = await asyncio.wait_for(queue.get(), timeout=timeout)
        if is_run_queue_end(item):
            break
        items.append(item)
    return items


@pytest.mark.asyncio
async def test_start_run_async_registers_queue_and_emits_sentinel(mocker):
    async def fake_execute(initial_state: dict, event_queue):
        if event_queue is not None:
            await event_queue.put(
                {"run_id": initial_state["run_id"], "type": "test_marker"},
            )
        return {
            "run_id": initial_state["run_id"],
            "status": "done",
            "draft": "ok",
        }

    mocker.patch("content_app.runner._execute_pipeline", side_effect=fake_execute)
    mocker.patch("content_app.runner.init_db", new_callable=mocker.AsyncMock)

    run_id = await start_run_async("topic", "linkedin", "tone")

    q = await get_event_queue(run_id)
    assert q is not None

    items = await _drain_until_sentinel(q)
    assert any(i.get("type") == "test_marker" for i in items)

    await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_run_pipeline_blocking_does_not_register_queue(mocker):
    async def fake_execute(initial_state: dict, event_queue):
        assert event_queue is None
        return {"run_id": initial_state["run_id"], "status": "done", "draft": "x"}

    mocker.patch("content_app.runner._execute_pipeline", side_effect=fake_execute)
    mocker.patch("content_app.runner.init_db", new_callable=mocker.AsyncMock)

    result = await run_pipeline_blocking("t", "twitter", "casual")
    assert result["status"] == "done"

    q = await get_event_queue(result["run_id"])
    assert q is None


@pytest.mark.asyncio
async def test_execute_pipeline_stores_result_for_get_run_result(mocker):
    """Real _execute_pipeline must persist into _run_results (used by future GET /runs/{id})."""
    from content_app.runner import _execute_pipeline

    mocker.patch("content_app.runner.save_run", new_callable=mocker.AsyncMock)

    mock_graph = mocker.AsyncMock()
    mock_graph.ainvoke = mocker.AsyncMock(
        return_value={
            "run_id": "rid-1",
            "status": "done",
            "alignment_score": 88,
            "retry_count": 1,
        },
    )
    mocker.patch("content_app.runner.build_graph", return_value=mock_graph)
    mocker.patch("content_app.runner.ClaudeProvider")

    class _FakeBrandvoiceCM:
        async def __aenter__(self):
            return mocker.MagicMock()

        async def __aexit__(self, *args):
            return None

    mocker.patch("content_app.runner.BrandvoiceClient", return_value=_FakeBrandvoiceCM())

    initial = {
        "run_id": "rid-1",
        "topic": "x",
        "platform": "linkedin",
        "tone": "y",
        "max_retries": 3,
    }
    await _execute_pipeline(initial, event_queue=None)

    stored = await get_run_result("rid-1")
    assert stored is not None
    assert stored["alignment_score"] == 88


@pytest.mark.asyncio
async def test_background_run_puts_run_failed_on_exception(mocker):
    async def fake_execute(initial_state: dict, event_queue):
        raise RuntimeError("boom")

    mocker.patch("content_app.runner._execute_pipeline", side_effect=fake_execute)
    mocker.patch("content_app.runner.init_db", new_callable=mocker.AsyncMock)

    run_id = await start_run_async("t", "linkedin", "tone")
    q = await get_event_queue(run_id)
    items = await _drain_until_sentinel(q)

    assert any(i.get("type") == "run_failed" for i in items)
