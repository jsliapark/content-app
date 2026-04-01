# content-app

Agentic content generation: a **LangGraph** pipeline that pulls brand voice context from **[brandvoice-mcp](https://github.com/jinsungpark/brandvoice-mcp)** (stdio), drafts with **Claude**, checks alignment, and retries with feedback until the score clears the threshold or max retries.

**Phase 1 (current):** CLI + graph + SQLite persistence + pytest (mocked MCP/LLM).

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
│       ├── cli.py                 # Click CLI → asyncio pipeline
│       ├── config.py              # Pydantic Settings (.env)
│       ├── graph/
│       │   ├── state.py           # ContentState (TypedDict + reducers)
│       │   ├── nodes.py           # create_nodes(client, provider)
│       │   └── builder.py         # build_graph → compiled StateGraph
│       ├── providers/
│       │   ├── protocol.py        # LLMProvider
│       │   ├── claude.py          # ClaudeProvider (Anthropic)
│       │   └── openai.py          # OpenAIProvider stub (Phase 3+)
│       ├── mcp/
│       │   └── brandvoice.py      # BrandvoiceClient (stdio MCP)
│       └── db/
│           └── sqlite.py          # init_db, save_run, get_run, list_runs
└── tests/
    ├── test_graph.py
    ├── test_providers.py
    ├── test_mcp.py
    └── test_db.py
```

The installable package lives under `src/content_app/`. The console script **`content-app`** is defined in `pyproject.toml` and points at `content_app.cli:main`.

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

Use **`uv run`** so the editable package and venv are used (plain `python -m content_app.cli` may fail if the package is not installed on that interpreter).

```bash
uv run content-app --topic "AI trends" --platform linkedin --tone professional
```

Equivalent:

```bash
uv run python -m content_app.cli --topic "AI trends" --platform linkedin --tone professional
```

`--platform` must be one of: `linkedin`, `twitter`, `blog`.

Runs persist to SQLite (default `sqlite:///content_app.db` → `content_app.db` in the current working directory unless you override `DATABASE_URL`).

---

## Tests

```bash
uv run pytest
```

- Unit tests mock **BrandvoiceClient** and **Claude**; no real subprocess or API calls.
- The **`integration`** marker is registered in `pyproject.toml` for future opt-in tests (`uv run pytest -m integration`). There are no integration tests in the tree yet.

---

## Architecture (Phase 1)

```
User input (topic, platform, tone)
  → fetch_voice_context   (brandvoice-mcp over stdio)
  → generate_draft        (Claude via LLMProvider)
  → check_alignment       (brandvoice-mcp; normalized to score + feedback)
  → score ≥ threshold? → done
  → else retry (inject feedback + previous draft) until max_retries
```

---

## Roadmap

- **Phase 2:** FastAPI + SSE for live run progress  
- **Phase 3:** React UI (pipeline visualizer, editor, alignment panel)  
- **Phase 4 (optional):** Gmail / Calendar MCP  
