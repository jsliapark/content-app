import logging
from typing import Any

from anthropic import AsyncAnthropic
from anthropic.types import Message

from content_app.config import get_settings

logger = logging.getLogger(__name__)


class ClaudeProvider:
    """Claude LLM provider using the Anthropic SDK."""

    def __init__(self, model: str | None = None):
        settings = get_settings()
        self.model = model or settings.default_model
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def generate(self, messages: list[dict], **kwargs) -> str:
        """Generate a completion using Claude.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
                      The first message with role='system' is extracted as
                      the system prompt (Anthropic API requirement).
            **kwargs: Options like max_tokens (default 16000).

        Returns:
            The generated text content.

        Raises:
            anthropic.APIError: On API failures.
        """
        system_prompt = None
        chat_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                chat_messages.append(msg)

        logger.debug(
            "Calling Claude",
            extra={
                "model": self.model,
                "message_count": len(chat_messages),
                "has_system": system_prompt is not None,
            },
        )

        DEFAULT_MAX_TOKENS = 16000  # covers adaptive thinking + text on Sonnet 5.5
        response = await self.client.messages.create(
            model=self.model,
            messages=chat_messages,
            system=system_prompt or "",
            max_tokens=kwargs.get("max_tokens", DEFAULT_MAX_TOKENS),
        )

        if not response.content:
            raise ValueError("Claude returned empty response (no content blocks)")

        # Sonnet 5.5 thinks by default, so text may follow thinking blocks
        content = "".join(b.text for b in response.content if b.type == "text")
        if not content:
            types = [b.type for b in response.content]
            raise ValueError(f"Expected text block, got {types}")
        logger.debug("Claude response received", extra={"length": len(content)})

        return content

    async def generate_with_tools(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int = 16000,
    ) -> Message:
        """Call Claude with ``tool_use`` enabled; returns the full message for the agent loop."""
        logger.debug(
            "Calling Claude with tools",
            extra={"model": self.model, "tool_count": len(tools)},
        )
        return await self.client.messages.create(
            model=self.model,
            system=system,
            messages=messages,
            tools=tools,
            max_tokens=max_tokens,
        )
