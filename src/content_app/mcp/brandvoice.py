import logging
from contextlib import AsyncExitStack

import json

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from content_app.config import get_settings

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
            args=settings.brandvoice_args,
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

    async def get_voice_context(self, task_description: str) -> str:
        if not self._session:
            raise RuntimeError("BrandvoiceClient not initialized. Use 'async with BrandvoiceClient() as client:'")

        result = await self._session.call_tool("get_voice_context", {
            "task_description": task_description,
        })
        return result.content[0].text

    async def check_alignment(self, content: str) -> dict:
        if not self._session:
            raise RuntimeError("BrandvoiceClient not initialized. Use 'async with BrandvoiceClient() as client:'")
        
        result = await self._session.call_tool("check_alignment", {
            "content": content,
        })
        return json.loads(result.content[0].text)
