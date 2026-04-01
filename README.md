# content-app

Agentic content generation: a **LangGraph** pipeline that pulls brand voice context from **[brandvoice-mcp](https://github.com/jinsungpark/brandvoice-mcp)** (stdio), drafts with **Claude**, checks alignment, and retries with feedback until the score clears the threshold or max retries.

**Phase 1:** CLI + graph + SQLite + pytest (mocked MCP/LLM).  
**Phase 2:** FastAPI + run registry + SSE (`/api/runs/.../events`) + snapshot; node-level **`node_start` / `node_end`** events on the event stream.

---

## Requirements

- **Python 3.12+**
- **[uv](https://github.com/astral-sh/uv)** for installs and running commands
- **`uvx brandvoice-mcp`** available on your machine (same as brandvoice-mcp’s docs)
- **`.env`** with API keys (see [Setup](#setup))

---

## Project layout

```
content-app/
├── pyproject.toml
├── uv.lock
├── .env.example
├── README.md
├── src/
│   └── content_app/
│       ├── __init__.py
│       ├── cli.py                 # Click CLI → run_pipeline_blocking
│       ├── runner.py              # Queue + history + start_run_async / blocking run
│       ├── config.py              # Pydantic Settings (.env)
│       ├── api/
│       │   ├── app.py             # FastAPI factory + /health
│       │   ├── schemas.py         # Request/response models
│       │   └── routes_runs.py     # POST/GET runs, SSE events
│       ├── graph/
│       │   ├── state.py           # ContentState (TypedDict + reducers)
│       │   ├── nodes.py           # create_nodes(..., emit=...)
│       │   └── builder.py         # build_graph(..., emit=...)
│       ├── providers/
│       │   ├── protocol.py        # LLMProvider
│       │   ├── claude.py          # ClaudeProvider (Anthropic)
│       │   └── openai.py          # OpenAIProvider stub (Phase 3+)
│       ├── mcp/
│       │   └── brandvoice.py      # BrandvoiceClient (stdio MCP)
│       └── db/
│           └── sqlite.py          # init_db, save_run, get_run, list_runs
└── tests/
    ├── test_api.py
    ├── test_graph.py
    ├── test_runner.py
    ├── test_providers.py
    ├── test_mcp.py
    └── test_db.py
```

The console script **`content-app`** points at `content_app.cli:main`.

---

## Setup

```bash
uv sync
cp .env.example .env
```

Edit `.env` and set:

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | Claude in **content-app** and (forwarded) **brandvoice-mcp** |
| `OPENAI_API_KEY` | Forwarded to **brandvoice-mcp** for embeddings (Chroma / RAG) |

Optional settings (see `.env.example`): `BRANDVOICE_COMMAND`, `BRANDVOICE_ARGS`, `DEFAULT_MODEL`, `MAX_RETRIES`, `ALIGNMENT_THRESHOLD`, `DATABASE_URL`, `LOG_LEVEL`.

**Voice profile:** Ingest writing samples in brandvoice-mcp for meaningful `get_voice_context` / `check_alignment`. Without a profile, alignment may be weak or generic; the MCP client normalizes `check_alignment` JSON (`alignment_score` / `drift_flags` vs `score` / `feedback`) and falls back safely on parse errors.

---

## Run the CLI

Use **`uv run`** so the editable package and venv are used.

```bash
uv run content-app --topic "AI trends" --platform linkedin --tone professional
```

`--platform` must be one of: `linkedin`, `twitter`, `blog`.

Runs persist to SQLite (default `sqlite:///content_app.db`).

---

## Run the HTTP API (Phase 2)

```bash
uv run uvicorn content_app.api.app:app --reload --host 0.0.0.0 --port 8000
```

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Liveness |
| `POST /api/runs` | Body: `{"topic","platform","tone"}` → `201` + `{ "run_id" }` (pipeline runs in a **background asyncio task**) |
| `GET /api/runs/{run_id}/events` | **SSE** stream (JSON lines in `data:`); includes `run_started`, per-node `node_start` / `node_end`, `run_complete` or `run_failed` |
| `GET /api/runs/{run_id}` | Snapshot: `phase`, `result` (if any), and `events` (history) |

The SSE handler replays from an in-memory **event history** (and short-polls until `phase` is `complete` or `failed`). A per-run **asyncio.Queue** remains for compatibility with the runner; subscribers should use the SSE endpoint rather than reading the queue directly.

---

## Tests

```bash
uv run pytest
```

- Unit tests mock **BrandvoiceClient** and **Claude** where needed; no real subprocess or API calls.
- The **`integration`** marker is registered for future opt-in tests (`uv run pytest -m integration`).

---

## Architecture

```
User input (topic, platform, tone)
  → fetch_voice_context   (brandvoice-mcp over stdio)
  → generate_draft        (Claude via LLMProvider)
  → check_alignment       (brandvoice-mcp; normalized to score + feedback)
  → score ≥ threshold? → done
  → else retry (inject feedback + previous draft) until max_retries
```

API runs use the same graph with an optional **`emit`** callback so each node emits **`node_start`** / **`node_end`** (plus **`run_started`** / **`run_complete`** from the runner).

---

## Roadmap

- **Phase 3:** React UI (pipeline visualizer, editor, alignment panel)  
- **Phase 4 (optional):** Gmail / Calendar MCP  
