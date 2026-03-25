# content-app

A full-stack agentic content generation app. Provide a topic, platform, and tone — a LangGraph-orchestrated pipeline fetches your brand voice context via [brandvoice-mcp](https://github.com/jinsungpark/brandvoice-mcp), generates a draft via Claude, checks alignment against your voice profile, and retries with feedback injection if the score is below threshold.

## Phase 1 (Current): CLI + LangGraph Core Loop

```bash
python -m content_app.cli --topic "AI trends" --platform linkedin --tone professional
```

## Setup

```bash
uv sync
cp .env.example .env
# Fill in your ANTHROPIC_API_KEY in .env
```

## Running Tests

```bash
# Unit tests only (mocked MCP + LLM)
uv run pytest

# Include integration tests (requires brandvoice-mcp subprocess)
uv run pytest -m integration
```

## Architecture

```
User input (topic, platform, tone)
  → fetch_voice_context  (brandvoice-mcp stdio)
  → generate_draft       (Claude via LLMProvider)
  → check_alignment      (brandvoice-mcp stdio)
  → score ≥ 70? → done
  → score < 70?  → inject feedback + previous draft → retry (max 3)
```
