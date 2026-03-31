"""Tests for the LangGraph pipeline."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from content_app.graph.state import ContentState
from content_app.graph.nodes import create_nodes, ALIGNMENT_THRESHOLD
from content_app.graph.builder import build_graph


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

        # Check that generate was called with messages containing feedback
        call_args = mock_provider.generate.call_args[0][0]  # First positional arg (messages)
        user_message = call_args[1]["content"]

        assert "55/100" in user_message
        assert "Too casual, needs more authority" in user_message
        assert "First draft that was too casual." in user_message
        assert "Please revise" in user_message

    async def test_handles_error_gracefully(self, mock_client, mock_provider, initial_state):
        mock_provider.generate = AsyncMock(side_effect=Exception("API rate limit"))
        nodes = create_nodes(mock_client, mock_provider)
        state = {**initial_state, "voice_context": "Write professionally."}
        result = await nodes["generate_draft"](state)

        assert result["status"] == "failed"


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

        # Verify generate was called only once
        assert mock_provider.generate.call_count == 1

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

        # Verify generate was called twice (initial + 1 retry)
        assert mock_provider.generate.call_count == 2

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

        # Verify generate was called 3 times (initial + 2 retries)
        assert mock_provider.generate.call_count == 3

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

        # Check the second call to generate included feedback
        second_call_messages = mock_provider.generate.call_args_list[1][0][0]
        user_message = second_call_messages[1]["content"]

        assert "45/100" in user_message
        assert "Way too informal, add more data points" in user_message
