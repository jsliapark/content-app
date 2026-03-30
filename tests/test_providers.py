"""Tests for LLM providers."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from content_app.providers.claude import ClaudeProvider
from content_app.providers.openai import OpenAIProvider


class TestClaudeProvider:
    """Tests for ClaudeProvider."""

    @patch("content_app.providers.claude.AsyncAnthropic")
    async def test_generate_extracts_text_from_response(self, mock_anthropic_class):
        """Test that generate correctly extracts text from Claude response."""
        # Setup mock
        mock_client = AsyncMock()
        mock_anthropic_class.return_value = mock_client

        mock_response = MagicMock()
        mock_content_block = MagicMock()
        mock_content_block.type = "text"
        mock_content_block.text = "Generated content here"
        mock_response.content = [mock_content_block]
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        # Test
        provider = ClaudeProvider()
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Write something."},
        ]
        result = await provider.generate(messages)

        assert result == "Generated content here"

    @patch("content_app.providers.claude.AsyncAnthropic")
    async def test_generate_separates_system_message(self, mock_anthropic_class):
        """Test that system message is extracted and passed separately."""
        mock_client = AsyncMock()
        mock_anthropic_class.return_value = mock_client

        mock_response = MagicMock()
        mock_content_block = MagicMock()
        mock_content_block.type = "text"
        mock_content_block.text = "Response"
        mock_response.content = [mock_content_block]
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        provider = ClaudeProvider()
        messages = [
            {"role": "system", "content": "System prompt here"},
            {"role": "user", "content": "User message"},
        ]
        await provider.generate(messages)

        # Verify the API was called correctly
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["system"] == "System prompt here"
        assert call_kwargs["messages"] == [{"role": "user", "content": "User message"}]

    @patch("content_app.providers.claude.AsyncAnthropic")
    async def test_generate_raises_on_empty_response(self, mock_anthropic_class):
        """Test that empty response raises ValueError."""
        mock_client = AsyncMock()
        mock_anthropic_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = []
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        provider = ClaudeProvider()
        with pytest.raises(ValueError, match="empty response"):
            await provider.generate([{"role": "user", "content": "Hi"}])

    @patch("content_app.providers.claude.AsyncAnthropic")
    async def test_generate_raises_on_non_text_block(self, mock_anthropic_class):
        """Test that non-text block raises ValueError."""
        mock_client = AsyncMock()
        mock_anthropic_class.return_value = mock_client

        mock_response = MagicMock()
        mock_content_block = MagicMock()
        mock_content_block.type = "tool_use"
        mock_response.content = [mock_content_block]
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        provider = ClaudeProvider()
        with pytest.raises(ValueError, match="Expected text block"):
            await provider.generate([{"role": "user", "content": "Hi"}])


class TestOpenAIProvider:
    """Tests for OpenAIProvider stub."""

    async def test_raises_not_implemented(self):
        """Test that OpenAIProvider raises NotImplementedError."""
        provider = OpenAIProvider()
        with pytest.raises(NotImplementedError, match="coming soon"):
            await provider.generate([])
