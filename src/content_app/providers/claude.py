import logging

from anthropic import AsyncAnthropic

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
            **kwargs: Options like max_tokens (default 4096), temperature, etc.

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

        DEFAULT_MAX_TOKENS = 4096
        DEFAULT_TEMPERATURE = 0.7
        response = await self.client.messages.create(
            model=self.model,
            messages=chat_messages,
            system=system_prompt or "",
            max_tokens=kwargs.get("max_tokens", DEFAULT_MAX_TOKENS),
            temperature=kwargs.get("temperature", DEFAULT_TEMPERATURE),
        )

        if not response.content:
            raise ValueError("Claude returned empty response (no content blocks)")

        first_block = response.content[0]
        if first_block.type != "text":
            raise ValueError(f"Expected text block, got {first_block.type}")

        content = first_block.text
        logger.debug("Claude response received", extra={"length": len(content)})

        return content
