"""Tests for the LangGraph pipeline."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from content_app.graph.builder import build_graph
from content_app.graph.nodes import create_nodes
from content_app.graph.state import ContentState


def _draft_tool_message(
    text: str = "This is a generated draft about AI trends.",
) -> MagicMock:
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "draft_content"
    tool_block.id = "toolu_test_01"
    tool_block.input = {"content": text}
    msg = MagicMock()
    msg.stop_reason = "tool_use"
    msg.content = [tool_block]
    return msg


@pytest.fixture
def mock_client():
    """Create a mock BrandvoiceClient."""
    client = AsyncMock()
    client.get_voice_context = AsyncMock(return_value="Write in a professional, authoritative tone.")
    client.check_alignment = AsyncMock(return_value={"score": 85, "feedback": "Good alignment"})
    return client


@pytest.fixture
def mock_provider():
    """Create a mock ClaudeProvider."""
    provider = AsyncMock()
    provider.generate = AsyncMock(return_value="This is a generated draft about AI trends.")
    provider.generate_with_tools = AsyncMock(
        return_value=_draft_tool_message("This is a generated draft about AI trends.")
    )
    return provider


@pytest.fixture
def initial_state() -> ContentState:
    """Create initial state for testing."""
    return {
        "run_id": "test-run-123",
        "topic": "AI trends",
        "platform": "linkedin",
        "tone": "professional",
        "max_retries": 3,
    }


class TestFetchVoiceContext:
    """Tests for fetch_voice_context node."""

    async def test_fetches_voice_context_successfully(self, mock_client, mock_provider, initial_state):
        nodes = create_nodes(mock_client, mock_provider)
        result = await nodes["fetch_voice_context"](initial_state)

        assert result["voice_context"] == "Write in a professional, authoritative tone."
        assert result["status"] == "generating"
        mock_client.get_voice_context.assert_called_once()

    async def test_handles_error_gracefully(self, mock_client, mock_provider, initial_state):
        mock_client.get_voice_context = AsyncMock(side_effect=Exception("MCP connection failed"))
        nodes = create_nodes(mock_client, mock_provider)
        result = await nodes["fetch_voice_context"](initial_state)

        assert result["status"] == "failed"


class TestGenerateDraft:
    """Tests for generate_draft node."""

    async def test_generates_draft_successfully(self, mock_client, mock_provider, initial_state):
        nodes = create_nodes(mock_client, mock_provider)
        state = {**initial_state, "voice_context": "Write professionally."}
        result = await nodes["generate_draft"](state)

        gw = mock_provider.generate_with_tools
        assert gw.await_count == 1
        user_message = gw.call_args.kwargs["messages"][0]["content"]
        assert "Do not include any preamble" in user_message
        assert "Start directly with the content itself" in user_message

        assert result["draft"] == "This is a generated draft about AI trends."
        assert result["previous_drafts"] == ["This is a generated draft about AI trends."]
        assert result["status"] == "checking"

    async def test_injects_feedback_on_retry(self, mock_client, mock_provider, initial_state):
        """Verify that alignment feedback is injected into the prompt on retry."""
        nodes = create_nodes(mock_client, mock_provider)
        state = {
            **initial_state,
            "voice_context": "Write professionally.",
            "alignment_score": 55,
            "alignment_feedback": "Too casual, needs more authority",
            "previous_drafts": ["First draft that was too casual."],
            "retry_count": 1,
        }

        await nodes["generate_draft"](state)

        user_message = mock_provider.generate_with_tools.call_args.kwargs["messages"][0]["content"]

        assert "55/100" in user_message
        assert "Too casual, needs more authority" in user_message
        assert "First draft that was too casual." in user_message
        assert "Please revise" in user_message

    async def test_handles_error_gracefully(self, mock_client, mock_provider, initial_state):
        mock_provider.generate_with_tools = AsyncMock(side_effect=Exception("tool use failed"))
        mock_provider.generate = AsyncMock(side_effect=Exception("API rate limit"))
        nodes = create_nodes(mock_client, mock_provider)
        state = {**initial_state, "voice_context": "Write professionally."}
        result = await nodes["generate_draft"](state)

        assert result["status"] == "failed"

    async def test_falls_back_when_agent_returns_failure_message(
        self, mock_client, mock_provider, initial_state
    ) -> None:
        tb = MagicMock()
        tb.type = "text"
        tb.text = "Agent reached max iterations without calling draft_content."
        bad_msg = MagicMock()
        bad_msg.stop_reason = "end_turn"
        bad_msg.content = [tb]
        mock_provider.generate_with_tools = AsyncMock(return_value=bad_msg)
        mock_provider.generate = AsyncMock(return_value="Fallback draft.")
        nodes = create_nodes(mock_client, mock_provider)
        state = {**initial_state, "voice_context": "Write professionally."}
        result = await nodes["generate_draft"](state)

        assert result["draft"] == "Fallback draft."
        assert result["status"] == "checking"
        mock_provider.generate.assert_awaited_once()


class TestCheckAlignment:
    """Tests for check_alignment node."""

    async def test_passes_when_score_above_threshold(self, mock_client, mock_provider, initial_state):
        mock_client.check_alignment = AsyncMock(return_value={"score": 85, "feedback": "Great alignment"})
        nodes = create_nodes(mock_client, mock_provider)
        state = {**initial_state, "draft": "Some draft content"}
        result = await nodes["check_alignment"](state)

        assert result["alignment_score"] == 85
        assert result["alignment_feedback"] == "Great alignment"
        assert result["status"] == "done"
        assert result["retry_count"] == 1

    async def test_triggers_retry_when_score_below_threshold(self, mock_client, mock_provider, initial_state):
        mock_client.check_alignment = AsyncMock(return_value={"score": 55, "feedback": "Needs improvement"})
        nodes = create_nodes(mock_client, mock_provider)
        state = {**initial_state, "draft": "Some draft content", "retry_count": 0}
        result = await nodes["check_alignment"](state)

        assert result["alignment_score"] == 55
        assert result["status"] == "generating"  # Triggers retry
        assert result["retry_count"] == 1

    async def test_fails_when_max_retries_exceeded(self, mock_client, mock_provider, initial_state):
        mock_client.check_alignment = AsyncMock(return_value={"score": 55, "feedback": "Still needs work"})
        nodes = create_nodes(mock_client, mock_provider)
        state = {**initial_state, "draft": "Some draft content", "retry_count": 2, "max_retries": 3}
        result = await nodes["check_alignment"](state)

        assert result["status"] == "failed"
        assert result["retry_count"] == 3

    async def test_handles_error_gracefully(self, mock_client, mock_provider, initial_state):
        mock_client.check_alignment = AsyncMock(side_effect=Exception("MCP error"))
        nodes = create_nodes(mock_client, mock_provider)
        state = {**initial_state, "draft": "Some draft content"}
        result = await nodes["check_alignment"](state)

        assert result["status"] == "failed"


class TestFullPipeline:
    """Integration tests for the full LangGraph pipeline."""

    async def test_happy_path_passes_on_first_try(self, mock_client, mock_provider, initial_state):
        """Scenario 1: Alignment score passes on first try."""
        mock_client.check_alignment = AsyncMock(return_value={"score": 85, "feedback": "Excellent"})

        graph = build_graph(mock_client, mock_provider)
        result = await graph.ainvoke(initial_state)

        assert result["status"] == "done"
        assert result["alignment_score"] == 85
        assert result["retry_count"] == 1
        assert result["draft"] is not None

        # Verify agent path used once (draft_content tool)
        assert mock_provider.generate_with_tools.await_count == 1
        assert mock_provider.generate.await_count == 0

    async def test_retry_path_passes_on_second_try(self, mock_client, mock_provider, initial_state):
        """Scenario 2: First score below threshold, second passes."""
        mock_client.check_alignment = AsyncMock(
            side_effect=[
                {"score": 55, "feedback": "Too casual"},
                {"score": 80, "feedback": "Much better"},
            ]
        )

        graph = build_graph(mock_client, mock_provider)
        result = await graph.ainvoke(initial_state)

        assert result["status"] == "done"
        assert result["alignment_score"] == 80
        assert result["retry_count"] == 2

        assert mock_provider.generate_with_tools.await_count == 2
        assert mock_provider.generate.await_count == 0

    async def test_failure_path_max_retries_exceeded(self, mock_client, mock_provider, initial_state):
        """Scenario 3: Max retries exceeded, all scores below threshold."""
        mock_client.check_alignment = AsyncMock(
            return_value={"score": 50, "feedback": "Still not good enough"}
        )

        graph = build_graph(mock_client, mock_provider)
        result = await graph.ainvoke(initial_state)

        assert result["status"] == "failed"
        assert result["alignment_score"] == 50
        assert result["retry_count"] == 3  # max_retries reached

        assert mock_provider.generate_with_tools.await_count == 3
        assert mock_provider.generate.await_count == 0

    async def test_retry_injects_feedback_into_prompt(self, mock_client, mock_provider, initial_state):
        """Scenario 4: Verify feedback injection on retry."""
        mock_client.check_alignment = AsyncMock(
            side_effect=[
                {"score": 45, "feedback": "Way too informal, add more data points"},
                {"score": 90, "feedback": "Perfect"},
            ]
        )

        graph = build_graph(mock_client, mock_provider)
        await graph.ainvoke(initial_state)

        second_kw = mock_provider.generate_with_tools.call_args_list[1].kwargs
        user_message = second_kw["messages"][0]["content"]

        assert "45/100" in user_message
        assert "Way too informal, add more data points" in user_message


class TestNodeEvents:
    """node_start / node_end emissions for SSE (Phase 2)."""

    async def test_fetch_voice_context_emits_start_end(self, mocker, mock_client, mock_provider, initial_state):
        emit = mocker.AsyncMock()
        nodes = create_nodes(mock_client, mock_provider, emit=emit)
        await nodes["fetch_voice_context"](initial_state)

        payloads = [c.args[0] for c in emit.call_args_list]
        assert any(
            p.get("type") == "node_start" and p.get("node") == "fetch_voice_context" for p in payloads
        )
        assert any(
            p.get("type") == "node_end" and p.get("node") == "fetch_voice_context" for p in payloads
        )

    async def test_emit_skipped_when_none(self, mock_client, mock_provider, initial_state):
        nodes = create_nodes(mock_client, mock_provider, emit=None)
        await nodes["fetch_voice_context"](initial_state)
        # no crash; provider still called
        mock_client.get_voice_context.assert_called_once()

    async def test_generate_draft_emits_agent_tool_calls(
        self, mocker, mock_client, mock_provider, initial_state
    ) -> None:
        search = MagicMock()
        search.type = "tool_use"
        search.name = "web_search"
        search.id = "tu_1"
        search.input = {"query": "AI trends stats"}
        msg1 = MagicMock()
        msg1.stop_reason = "tool_use"
        msg1.content = [search]
        draft_b = MagicMock()
        draft_b.type = "tool_use"
        draft_b.name = "draft_content"
        draft_b.id = "tu_2"
        draft_b.input = {"content": "Final draft body."}
        msg2 = MagicMock()
        msg2.stop_reason = "tool_use"
        msg2.content = [draft_b]
        mock_provider.generate_with_tools = AsyncMock(side_effect=[msg1, msg2])

        emit = mocker.AsyncMock()
        nodes = create_nodes(mock_client, mock_provider, emit=emit)
        state = {**initial_state, "voice_context": "Voice guidelines here."}
        result = await nodes["generate_draft"](state)

        assert result["draft"] == "Final draft body."
        agent_events = [
            c.args[0]
            for c in emit.call_args_list
            if c.args[0].get("type") == "agent_tool_call"
        ]
        assert len(agent_events) == 1
        assert agent_events[0]["tool"] == "web_search"
        assert agent_events[0]["input"] == {"query": "AI trends stats"}

    async def test_check_alignment_node_end_includes_score_and_retry_count(
        self, mocker, mock_client, mock_provider, initial_state
    ):
        emit = mocker.AsyncMock()
        mock_client.check_alignment = AsyncMock(
            return_value={"score": 44, "feedback": "Too informal"}
        )
        nodes = create_nodes(mock_client, mock_provider, emit=emit)
        state = {
            **initial_state,
            "draft": "Some draft text",
            "retry_count": 0,
        }
        await nodes["check_alignment"](state)

        end_events = [
            c.args[0]
            for c in emit.call_args_list
            if c.args[0].get("type") == "node_end"
            and c.args[0].get("node") == "check_alignment"
        ]
        assert len(end_events) == 1
        assert end_events[0]["alignment_score"] == 44
        assert end_events[0]["retry_count"] == 1
