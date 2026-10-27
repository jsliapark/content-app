"""Tests for MCP client (BrandvoiceClient)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestBrandvoiceClient:
    """Tests for BrandvoiceClient."""

    async def test_raises_error_when_not_initialized(self):
        """Test that methods raise RuntimeError when called without async with."""
        from content_app.mcp.brandvoice import BrandvoiceClient

        client = BrandvoiceClient()

        with pytest.raises(RuntimeError, match="not initialized"):
            await client.get_voice_context("test task")

        with pytest.raises(RuntimeError, match="not initialized"):
            await client.check_alignment("test content")

    @patch("content_app.mcp.brandvoice.stdio_client")
    @patch("content_app.mcp.brandvoice.ClientSession")
    async def test_context_manager_initializes_session(self, mock_session_class, mock_stdio):
        """Test that async with properly initializes the MCP session."""
        from content_app.mcp.brandvoice import BrandvoiceClient

        # Setup mocks
        mock_read = AsyncMock()
        mock_write = AsyncMock()

        # Mock stdio_client as async context manager
        mock_stdio_cm = AsyncMock()
        mock_stdio_cm.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))
        mock_stdio_cm.__aexit__ = AsyncMock(return_value=None)
        mock_stdio.return_value = mock_stdio_cm

        # Mock ClientSession as async context manager
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session_cm

        async with BrandvoiceClient() as client:
            assert client._session is not None

    @patch("content_app.mcp.brandvoice.stdio_client")
    @patch("content_app.mcp.brandvoice.ClientSession")
    async def test_get_voice_context_calls_tool(self, mock_session_class, mock_stdio):
        """Test that get_voice_context calls the correct MCP tool."""
        from content_app.mcp.brandvoice import BrandvoiceClient

        # Setup mocks
        mock_read = AsyncMock()
        mock_write = AsyncMock()

        mock_stdio_cm = AsyncMock()
        mock_stdio_cm.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))
        mock_stdio_cm.__aexit__ = AsyncMock(return_value=None)
        mock_stdio.return_value = mock_stdio_cm

        # Mock the tool result
        mock_result = MagicMock(isError=False)
        mock_content = MagicMock()
        mock_content.text = "Voice context string"
        mock_result.content = [mock_content]

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value=mock_result)

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session_cm

        async with BrandvoiceClient() as client:
            result = await client.get_voice_context("Write a LinkedIn post")

        assert result == "Voice context string"
        mock_session.call_tool.assert_called_once_with(
            "get_voice_context",
            {"task": "Write a LinkedIn post", "platform": "general"},
        )

    @patch("content_app.mcp.brandvoice.stdio_client")
    @patch("content_app.mcp.brandvoice.ClientSession")
    async def test_check_alignment_parses_json(self, mock_session_class, mock_stdio):
        """Test that check_alignment correctly parses the JSON response."""
        from content_app.mcp.brandvoice import BrandvoiceClient
        import json

        # Setup mocks
        mock_read = AsyncMock()
        mock_write = AsyncMock()

        mock_stdio_cm = AsyncMock()
        mock_stdio_cm.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))
        mock_stdio_cm.__aexit__ = AsyncMock(return_value=None)
        mock_stdio.return_value = mock_stdio_cm

        # Mock the tool result with JSON
        mock_result = MagicMock(isError=False)
        mock_content = MagicMock()
        mock_content.text = json.dumps({"score": 75, "feedback": "Good but could improve"})
        mock_result.content = [mock_content]

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value=mock_result)

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session_cm

        async with BrandvoiceClient() as client:
            result = await client.check_alignment("Some content to check")

        assert result == {"score": 75, "feedback": "Good but could improve"}
        mock_session.call_tool.assert_called_once_with(
            "check_alignment",
            {"content": "Some content to check", "platform": "general"},
        )


@pytest.mark.parametrize("method, kwargs, tool, payload", [
    ("get_voice_context", {"task_description": "topic", "platform": "twitter"}, "get_voice_context", {"task": "topic", "platform": "twitter"}),
    ("check_alignment", {"content": "draft", "platform": "blog"}, "check_alignment", {"content": "draft", "platform": "blog"}),
    ("set_guidelines", {"guidelines": "Be clear"}, "set_guidelines", {"custom_instructions": "Be clear"}),
    ("delete_samples", {"sample_ids": None, "delete_all": True}, "delete_samples", {"delete_all": True}),
    ("delete_samples", {"sample_ids": ["id"], "delete_all": False}, "delete_samples", {"sample_ids": ["id"]}),
])
async def test_tool_arguments(method, kwargs, tool, payload):
    from content_app.mcp.brandvoice import BrandvoiceClient
    client = BrandvoiceClient()
    client._session = AsyncMock()
    client._session.call_tool.return_value = MagicMock(isError=False, content=[MagicMock(text='{}')])
    await getattr(client, method)(**kwargs)
    client._session.call_tool.assert_awaited_once_with(tool, payload)


@pytest.mark.parametrize("method, kwargs", [
    ("get_voice_context", {"task_description": "topic"}),
    ("get_profile", {}), ("list_samples", {}),
    ("ingest_samples", {"content": "sample"}),
    ("set_guidelines", {"guidelines": "clear"}),
    ("delete_samples", {"sample_ids": None, "delete_all": True}),
    ("check_alignment", {"content": "draft"}),
])
@pytest.mark.parametrize("is_error, content, message", [
    (True, [MagicMock(text="server failed")], "server failed"),
    (False, [], "Empty tool response"),
])
async def test_tool_failures_raise(method, kwargs, is_error, content, message):
    from content_app.mcp.brandvoice import BrandvoiceClient
    client = BrandvoiceClient()
    client._session = AsyncMock()
    client._session.call_tool.return_value = MagicMock(isError=is_error, content=content)
    with pytest.raises(RuntimeError, match=f"{method}: {message}"):
        await getattr(client, method)(**kwargs)


async def test_alignment_preserves_full_feedback():
    import json
    from content_app.mcp.brandvoice import BrandvoiceClient
    client = BrandvoiceClient()
    client._session = AsyncMock()
    flags = [{"category": "tone", "issue": f"issue {i}"} for i in range(4)]
    client._session.call_tool.return_value = MagicMock(isError=False, content=[MagicMock(text=json.dumps({
        "alignment_score": 45, "verdict": "off_brand", "drift_flags": flags,
        "suggestions": ["Use simpler words", "Shorten sentences"],
        "rewrite_hints": "Start with a concrete example",
    }))])
    result = await client.check_alignment("draft")
    assert result == {"score": 45, "feedback":
        "tone: issue 0; tone: issue 1; tone: issue 2; tone: issue 3; "
        "Use simpler words; Shorten sentences; Start with a concrete example"}
