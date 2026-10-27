"""Real stdio contract; requires brandvoice-mcp importable in this interpreter."""

import os
import sys
from unittest.mock import patch

import pytest
from mcp.client.stdio import stdio_client

from content_app.config import Settings
from content_app.mcp.brandvoice import BrandvoiceClient


@pytest.mark.integration
async def test_brandvoice_stdio_contract(tmp_path):
    pytest.importorskip("brandvoice_mcp")
    settings = Settings(
        _env_file=None,
        anthropic_api_key="dummy",
        openai_api_key="dummy",
        brandvoice_command=sys.executable,
        brandvoice_args='["-m", "brandvoice_mcp"]',
    )

    def test_stdio(params):
        # The client forwards API keys explicitly; supply test-only server settings
        # at the transport boundary while still launching the real server.
        params.env = {
            **params.env,
            "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
            "BRANDVOICE_EMBEDDING_MODEL": "test",
            "BRANDVOICE_ANALYSIS_MODEL": "test",
            "BRANDVOICE_DATA_DIR": str(tmp_path),
            "ANONYMIZED_TELEMETRY": "False",
        }
        return stdio_client(params)

    with patch("content_app.mcp.brandvoice.get_settings", return_value=settings), patch(
        "content_app.mcp.brandvoice.stdio_client", side_effect=test_stdio
    ):
        async with BrandvoiceClient() as client:
            sample = "We build small tools for real problems. Keep your work clear and useful. " * 8
            ingested = await client.ingest_samples(sample)
            assert {"samples_stored", "total_samples", "style_snapshot"} <= ingested.keys()
            assert ingested["samples_stored"] > 0
            assert ingested["style_snapshot"]["profile_source"] == "heuristic"
            guidelines = await client.set_guidelines("Keep it clear and practical.")
            assert guidelines["current_guidelines"]["custom_instructions"] == "Keep it clear and practical."
            assert guidelines["updated_fields"] == ["custom_instructions"]
            profile = await client.get_profile()
            assert {"learned_style", "explicit_guidelines", "total_samples"} <= profile.keys()
            samples = await client.list_samples()
            assert {"samples", "total", "offset", "limit"} <= samples.keys()
            assert samples["total"] > 0
            context = await client.get_voice_context("Write about useful tools", platform="linkedin")
            assert "<voice_context>" in context
            alignment = await client.check_alignment(sample, platform="linkedin")
            assert set(alignment) == {"score", "feedback"}
            assert 0 <= alignment["score"] <= 100
            assert isinstance(alignment["feedback"], str)
            deleted = await client.delete_samples(sample_ids=None, delete_all=True)
            assert deleted == {"deleted_count": samples["total"], "remaining_count": 0}
