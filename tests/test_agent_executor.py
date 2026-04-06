"""Unit tests for the draft agent executor (mocked Claude responses)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from content_app.agent.executor import run_draft_agent


def _tool_block(
    *,
    name: str,
    id_: str,
    input_data: dict,
) -> MagicMock:
    b = MagicMock()
    b.type = "tool_use"
    b.name = name
    b.id = id_
    b.input = input_data
    return b


def _msg_tool_use(*blocks: MagicMock) -> MagicMock:
    m = MagicMock()
    m.stop_reason = "tool_use"
    m.content = list(blocks)
    return m


def _msg_text(text: str) -> MagicMock:
    tb = MagicMock()
    tb.type = "text"
    tb.text = text
    m = MagicMock()
    m.stop_reason = "end_turn"
    m.content = [tb]
    return m


@pytest.mark.asyncio
async def test_run_draft_agent_exits_on_draft_content() -> None:
    draft_block = _tool_block(
        name="draft_content",
        id_="tu_1",
        input_data={"content": "Hello from agent."},
    )
    provider = MagicMock()
    provider.generate_with_tools = AsyncMock(return_value=_msg_tool_use(draft_block))

    out = await run_draft_agent(
        provider=provider,
        system_prompt="sys",
        user_message="user",
        tool_handlers={},
        max_iterations=6,
        on_tool_call=None,
    )
    assert out == "Hello from agent."
    provider.generate_with_tools.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_draft_agent_runs_tool_then_draft() -> None:
    search = _tool_block(
        name="web_search",
        id_="tu_1",
        input_data={"query": "AI trends"},
    )
    draft = _tool_block(
        name="draft_content",
        id_="tu_2",
        input_data={"content": "Final post."},
    )
    provider = MagicMock()
    provider.generate_with_tools = AsyncMock(
        side_effect=[_msg_tool_use(search), _msg_tool_use(draft)]
    )

    calls: list[str] = []

    async def web_search(query: str) -> str:
        calls.append(query)
        return f"results:{query}"

    out = await run_draft_agent(
        provider=provider,
        system_prompt="sys",
        user_message="user",
        tool_handlers={"web_search": web_search},
        max_iterations=6,
        on_tool_call=None,
    )
    assert out == "Final post."
    assert calls == ["AI trends"]
    assert provider.generate_with_tools.await_count == 2


@pytest.mark.asyncio
async def test_run_draft_agent_end_turn_text() -> None:
    provider = MagicMock()
    provider.generate_with_tools = AsyncMock(return_value=_msg_text("Plain reply."))

    out = await run_draft_agent(
        provider=provider,
        system_prompt="sys",
        user_message="user",
        tool_handlers={},
        max_iterations=6,
        on_tool_call=None,
    )
    assert out == "Plain reply."
