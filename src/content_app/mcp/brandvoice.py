import logging
from contextlib import AsyncExitStack
from typing import Any

import json

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from content_app.config import get_settings, parse_brandvoice_args

logger = logging.getLogger(__name__)


class BrandvoiceClient:
    """MCP client for brandvoice-mcp (stdio transport)."""

    def __init__(self):
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    async def __aenter__(self) -> "BrandvoiceClient":
        settings = get_settings()
        server_params = StdioServerParameters(
            command=settings.brandvoice_command,
            args=parse_brandvoice_args(settings.brandvoice_args),
            env={
                "ANTHROPIC_API_KEY": settings.anthropic_api_key,
                "OPENAI_API_KEY": settings.openai_api_key,
            },
        )
        self._stack = AsyncExitStack()
        await self._stack.__aenter__()

        read, write = await self._stack.enter_async_context(stdio_client(server_params))

        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._stack:
            await self._stack.__aexit__(exc_type, exc_val, exc_tb)

    def _require_session(self) -> ClientSession:
        if not self._session:
            raise RuntimeError("BrandvoiceClient not initialized. Use 'async with BrandvoiceClient() as client:'")
        return self._session

    def _tool_text(self, tool_name: str, result: Any) -> str:
        text = "\n".join(
            block.text for block in result.content if getattr(block, "text", None)
        )
        if result.isError or not text:
            raise RuntimeError(f"{tool_name}: {text or 'Empty tool response'}")
        return text

    async def get_voice_context(self, task_description: str, platform: str = "general") -> str:
        session = self._require_session()
        result = await session.call_tool(
            "get_voice_context",
            {"task": task_description, "platform": platform},
        )
        return self._tool_text("get_voice_context", result)

    async def get_profile(self) -> dict[str, Any]:
        session = self._require_session()
        result = await session.call_tool("get_profile", {})
        text = self._tool_text("get_profile", result)
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        return {"data": parsed}

    async def list_samples(self) -> dict[str, Any]:
        session = self._require_session()
        result = await session.call_tool("list_samples", {})
        text = self._tool_text("list_samples", result)
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            return {"samples": parsed}
        return {"result": parsed}

    async def ingest_samples(self, content: str) -> dict[str, Any]:
        session = self._require_session()
        result = await session.call_tool("ingest_samples", {"content": content})
        text = self._tool_text("ingest_samples", result)
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        return {"result": parsed}

    async def set_guidelines(self, guidelines: str) -> dict[str, Any]:
        session = self._require_session()
        result = await session.call_tool("set_guidelines", {"custom_instructions": guidelines})
        text = self._tool_text("set_guidelines", result)
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        return {"result": parsed}

    async def delete_samples(
        self,
        *,
        sample_ids: list[str] | None,
        delete_all: bool,
    ) -> dict[str, Any]:
        session = self._require_session()
        if delete_all:
            payload: dict[str, Any] = {"delete_all": True}
        else:
            payload = {"sample_ids": list(sample_ids or [])}
        result = await session.call_tool("delete_samples", payload)
        text = self._tool_text("delete_samples", result)
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        return {"result": parsed}

    async def check_alignment(self, content: str, platform: str = "general") -> dict[str, Any]:
        session = self._require_session()

        result = await session.call_tool("check_alignment", {
            "content": content,
            "platform": platform,
        })

        text = self._tool_text("check_alignment", result)
        try:
            parsed = json.loads(text)
            if not isinstance(parsed, dict):
                raise ValueError("check_alignment JSON is not an object")

            # Handle both formats: {"score", "feedback"} or {"alignment_score", "verdict", "drift_flags"}
            if "alignment_score" in parsed:
                drift_summary = ""
                if "drift_flags" in parsed and parsed["drift_flags"]:
                    drift_summary = "; ".join(
                        f"{d.get('category', 'unknown')}: {d.get('issue', '')}"
                        for d in parsed["drift_flags"]
                    )
                feedback = [drift_summary or parsed.get("verdict", "No feedback")]
                feedback.extend(parsed.get("suggestions") or [])
                if parsed.get("rewrite_hints"):
                    feedback.append(parsed["rewrite_hints"])
                return {
                    "score": parsed["alignment_score"],
                    "feedback": "; ".join(feedback),
                }
            if "score" in parsed:
                return {
                    "score": parsed["score"],
                    "feedback": parsed.get("feedback", "No feedback"),
                }
            logger.warning(
                "check_alignment returned unexpected format: %s",
                text[:200] if len(text) > 200 else text,
            )
            return {
                "score": 0,
                "feedback": "Unable to check alignment — no voice profile configured",
            }

        except (json.JSONDecodeError, IndexError, AttributeError, ValueError, TypeError) as e:
            logger.warning("Failed to parse check_alignment response: %s", e)
            return {
                "score": 0,
                "feedback": "Unable to check alignment — no voice profile configured",
            }
