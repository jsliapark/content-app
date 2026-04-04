"""Brand dashboard: proxy selected tools to brandvoice-mcp (stdio)."""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, HTTPException, status

from content_app.api.schemas import DeleteSamplesRequest, GuidelinesRequest, IngestRequest
from content_app.mcp.brandvoice import BrandvoiceClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/brand", tags=["brand"])


def _overview_samples_value(samples: dict[str, Any]) -> Any:
    """Unwrap list_samples()'s {'samples': [...]} so overview isn't { samples: { samples: [...] } }."""
    if len(samples) == 1 and isinstance(samples.get("samples"), list):
        return samples["samples"]
    return samples


async def _with_brand_client(
    fn: Callable[[BrandvoiceClient], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    try:
        async with BrandvoiceClient() as client:
            return await fn(client)
    except json.JSONDecodeError as e:
        logger.warning("brand MCP JSON decode error: %s", e)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail="Invalid JSON from brandvoice-mcp",
        ) from e
    except Exception as e:
        logger.exception("brand MCP request failed")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        ) from e


@router.get("/overview")
async def get_brand_overview() -> dict[str, Any]:
    async def _load(client: BrandvoiceClient) -> dict[str, Any]:
        profile = await client.get_profile()
        samples = await client.list_samples()
        return {"profile": profile, "samples": _overview_samples_value(samples)}

    return await _with_brand_client(_load)


@router.get("/profile")
async def get_profile() -> dict[str, Any]:
    return await _with_brand_client(lambda c: c.get_profile())


@router.get("/samples")
async def list_samples() -> dict[str, Any]:
    return await _with_brand_client(lambda c: c.list_samples())


@router.post("/samples")
async def ingest_samples(body: IngestRequest) -> dict[str, Any]:
    return await _with_brand_client(lambda c: c.ingest_samples(body.content))


@router.post("/samples/delete")
async def delete_samples(body: DeleteSamplesRequest) -> dict[str, Any]:
    return await _with_brand_client(
        lambda c: c.delete_samples(
            sample_ids=body.sample_ids,
            delete_all=body.delete_all,
        )
    )


@router.put("/guidelines")
async def set_guidelines(body: GuidelinesRequest) -> dict[str, Any]:
    return await _with_brand_client(lambda c: c.set_guidelines(body.guidelines))
