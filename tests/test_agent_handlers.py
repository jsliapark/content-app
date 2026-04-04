"""Tests for draft-agent tool handlers."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from content_app.agent.handlers import handle_web_search


@pytest.mark.asyncio
async def test_handle_web_search_no_api_key(mocker):
    mocker.patch(
        "content_app.agent.handlers.get_settings",
        return_value=MagicMock(tavily_api_key=""),
    )
    out = await handle_web_search("AI trends")
    assert "TAVILY_API_KEY" in out
    assert "AI trends" in out


@pytest.mark.asyncio
async def test_handle_web_search_tavily_success(mocker):
    mocker.patch(
        "content_app.agent.handlers.get_settings",
        return_value=MagicMock(tavily_api_key="secret"),
    )
    mock_instance = MagicMock()
    mock_instance.search = AsyncMock(
        return_value={
            "results": [
                {"title": "One", "content": "First snippet text."},
                {"title": "Two", "content": "x" * 250},
            ]
        }
    )
    mocker.patch("tavily.AsyncTavilyClient", return_value=mock_instance)

    out = await handle_web_search("my query")

    mock_instance.search.assert_awaited_once_with("my query", max_results=3)
    assert "- One: First snippet text." in out
    assert "- Two: " in out
    assert "x" * 200 in out  # 250-char content truncated to 200


@pytest.mark.asyncio
async def test_handle_web_search_tavily_empty_results(mocker):
    mocker.patch(
        "content_app.agent.handlers.get_settings",
        return_value=MagicMock(tavily_api_key="secret"),
    )
    mock_instance = MagicMock()
    mock_instance.search = AsyncMock(return_value={"results": []})
    mocker.patch("tavily.AsyncTavilyClient", return_value=mock_instance)

    out = await handle_web_search("obscure")
    assert "No results found" in out


@pytest.mark.asyncio
async def test_handle_web_search_tavily_error_graceful(mocker):
    mocker.patch(
        "content_app.agent.handlers.get_settings",
        return_value=MagicMock(tavily_api_key="secret"),
    )
    mock_instance = MagicMock()
    mock_instance.search = AsyncMock(side_effect=RuntimeError("network"))
    mocker.patch("tavily.AsyncTavilyClient", return_value=mock_instance)

    out = await handle_web_search("q")
    assert "Web search failed" in out
