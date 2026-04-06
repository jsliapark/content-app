"""ReAct-style tool loop for draft generation (Claude ``tool_use``)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from content_app.agent.tools import AGENT_TOOLS

logger = logging.getLogger(__name__)


def _assistant_blocks_to_api(content: Any) -> list[dict[str, Any]]:
    """Serialize Anthropic assistant content blocks to API-shaped dicts."""
    out: list[dict[str, Any]] = []
    for block in content or []:
        t = getattr(block, "type", None)
        if t == "text":
            out.append({"type": "text", "text": getattr(block, "text", "")})
        elif t == "tool_use":
            inp = getattr(block, "input", None)
            if not isinstance(inp, dict):
                inp = {}
            out.append(
                {
                    "type": "tool_use",
                    "id": getattr(block, "id", ""),
                    "name": getattr(block, "name", ""),
                    "input": inp,
                }
            )
    return out


async def run_draft_agent(
    *,
    provider: Any,
    system_prompt: str,
    user_message: str,
    tool_handlers: dict[str, Callable[..., Awaitable[Any]]],
    max_iterations: int = 6,
    on_tool_call: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> str:
    """Run tool-use loop until ``draft_content`` or text-only ``end_turn``."""
    gen = getattr(provider, "generate_with_tools", None)
    if gen is None:
        raise RuntimeError("LLM provider does not support generate_with_tools")

    messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]

    for i in range(max_iterations):
        response = await gen(
            system=system_prompt,
            messages=messages,
            tools=AGENT_TOOLS,
        )

        stop = getattr(response, "stop_reason", None)
        blocks = list(response.content or [])

        if stop == "tool_use":
            tool_results: list[dict[str, Any]] = []
            assistant_payload = _assistant_blocks_to_api(blocks)

            for block in blocks:
                if getattr(block, "type", None) != "tool_use":
                    continue
                name = getattr(block, "name", "") or ""
                raw_in = getattr(block, "input", None)
                inp: dict[str, Any] = raw_in if isinstance(raw_in, dict) else {}

                if name == "draft_content":
                    raw = inp.get("content", "")
                    return raw if isinstance(raw, str) else str(raw)

                if on_tool_call:
                    await on_tool_call(
                        {
                            "type": "agent_tool_call",
                            "node": "generate_draft",
                            "tool": name,
                            "input": inp,
                            "iteration": i + 1,
                        }
                    )

                handler = tool_handlers.get(name)
                if handler:
                    try:
                        result = await handler(**inp)
                    except TypeError:
                        logger.warning("Tool %s input mismatch %s", name, inp)
                        result = f"Tool input error for {name}"
                else:
                    result = f"Unknown tool: {name}"

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": getattr(block, "id", ""),
                        "content": str(result),
                    }
                )

            messages.append({"role": "assistant", "content": assistant_payload})
            messages.append({"role": "user", "content": tool_results})
            continue

        for block in blocks:
            if getattr(block, "type", None) == "text":
                text = getattr(block, "text", "") or ""
                if text.strip():
                    logger.warning(
                        "Agent ended with text instead of draft_content; using text as draft"
                    )
                    return text
        return "Agent produced no output."

    return "Agent reached max iterations without calling draft_content."
