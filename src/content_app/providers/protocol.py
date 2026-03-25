from typing import Protocol


class LLMProvider(Protocol):
    """Protocol for LLM providers. Implement this to add new models."""

    async def generate(self, messages: list[dict], **kwargs) -> str:
        """Generate a completion from the given messages.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            **kwargs: Provider-specific options (max_tokens, temperature, etc.)

        Returns:
            The generated text content.
        """
        ...
