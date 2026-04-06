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

    async def get_voice_context(self, task_description: str) -> str:
        session = self._require_session()
        result = await session.call_tool(
            "get_voice_context",
            {"task_description": task_description},
        )
        return result.content[0].text

    async def get_profile(self) -> dict[str, Any]:
        session = self._require_session()
        result = await session.call_tool("get_profile", {})
        text = result.content[0].text
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        return {"data": parsed}

    async def list_samples(self) -> dict[str, Any]:
        session = self._require_session()
        result = await session.call_tool("list_samples", {})
        text = result.content[0].text
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            return {"samples": parsed}
        return {"result": parsed}

    async def ingest_samples(self, content: str) -> dict[str, Any]:
        session = self._require_session()
        result = await session.call_tool("ingest_samples", {"content": content})
        text = result.content[0].text
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        return {"result": parsed}

    async def set_guidelines(self, guidelines: str) -> dict[str, Any]:
        session = self._require_session()
        result = await session.call_tool("set_guidelines", {"guidelines": guidelines})
        text = result.content[0].text
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
            payload: dict[str, Any] = {"all": True}
        else:
            payload = {"sample_ids": list(sample_ids or [])}
        result = await session.call_tool("delete_samples", payload)
        text = result.content[0].text
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        return {"result": parsed}

    async def check_alignment(self, content: str) -> dict[str, Any]:
        session = self._require_session()

        result = await session.call_tool("check_alignment", {
            "content": content,
        })

        try:
            text = result.content[0].text
            parsed = json.loads(text)
            if not isinstance(parsed, dict):
                raise ValueError("check_alignment JSON is not an object")

            # Handle both formats: {"score", "feedback"} or {"alignment_score", "verdict", "drift_flags"}
            if "alignment_score" in parsed:
                drift_summary = ""
                if "drift_flags" in parsed and parsed["drift_flags"]:
                    drift_summary = "; ".join(
                        f"{d.get('category', 'unknown')}: {d.get('issue', '')}"
                        for d in parsed["drift_flags"][:3]
                    )
                return {
                    "score": parsed["alignment_score"],
                    "feedback": drift_summary or parsed.get("verdict", "No feedback"),
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
