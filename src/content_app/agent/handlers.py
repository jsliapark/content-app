"""Runtime implementations for draft-agent tools (non–draft_content)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from content_app.config import get_settings
from content_app.mcp.brandvoice import BrandvoiceClient

logger = logging.getLogger(__name__)


async def handle_web_search(query: str) -> str:
    """Search the web via Tavily when ``TAVILY_API_KEY`` is configured."""
    settings = get_settings()
    if not settings.tavily_api_key:
        return (
            f"[Web search unavailable — no TAVILY_API_KEY configured. Query was: {query}]"
        )

    try:
        from tavily import AsyncTavilyClient

        client = AsyncTavilyClient(api_key=settings.tavily_api_key)
        response = await client.search(query, max_results=3)
    except Exception as exc:
        logger.warning("Tavily search failed: %s", exc)
        return f"[Web search failed for {query!r}. Try again later.]"

    results = []
    for r in response.get("results", []):
        title = r.get("title", "")
        content = r.get("content", "")[:200]
        results.append(f"- {title}: {content}")

    return "\n".join(results) if results else f"No results found for: {query}"


def build_get_writing_examples_handler(
    client: BrandvoiceClient,
) -> Callable[[str], Awaitable[str]]:
    """Return a handler that pulls voice-context text for a topic-focused task."""

    async def get_writing_examples(topic: str) -> str:
        try:
            task = f"Find writing examples and voice patterns related to: {topic}"
            return await client.get_voice_context(task)
        except Exception as exc:
            logger.warning("get_writing_examples failed: %s", exc)
            return "No relevant writing examples found."

    return get_writing_examples
