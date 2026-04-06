# content-app

Agentic content generation: a **LangGraph** pipeline that pulls brand voice context from **[brandvoice-mcp](https://github.com/jinsungpark/brandvoice-mcp)** (stdio), drafts with a **ReAct agent** (Claude tool-use loop), checks alignment, and retries with feedback until the score clears the threshold or max retries.

**Phases 1–3 are complete:** CLI + LangGraph + SQLite + pytest; **FastAPI** with run registry, **SSE** (`/api/runs/.../events`), snapshots, and per-node **`node_start` / `node_end`** events; and a **React + TypeScript + Vite** UI (**react-router**) with three areas: **Pipeline** (run form, **React Flow** visualizer, live SSE), **Brand dashboard** (voice profile, samples ingest, guidelines via brandvoice-mcp), and **Run history** (recent runs from SQLite). The draft node now runs a **ReAct tool-use loop** — the agent can call `web_search` (Tavily) and `get_writing_examples` before submitting the final post via `draft_content`.

---

## Requirements

- **Python 3.12+**
- **[uv](https://github.com/astral-sh/uv)** for installs and running commands
- **Node.js 20+** and **npm** (for the `frontend/` dev server and build)
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
├── frontend/                    # React + Vite UI (Tailwind, @xyflow/react)
│   ├── package.json
│   ├── vite.config.ts           # dev proxy: /api → http://localhost:8000
│   ├── index.html
│   ├── public/
│   └── src/
│       ├── App.tsx                # Routes + nav
│       ├── pages/                 # PipelinePage, BrandPage, HistoryPage
│       ├── components/            # RunForm, PipelineVisualizer, ContentPanel, …
│       ├── hooks/
│       ├── api/
│       │   ├── runs.ts
│       │   └── brand.ts           # overview, profile, samples, guidelines
│       └── types/
├── src/
│   └── content_app/
│       ├── __init__.py
│       ├── cli.py                 # Click CLI → run_pipeline_blocking
│       ├── runner.py              # Queue + history + start_run_async / blocking run
│       ├── config.py              # Pydantic Settings (.env)
│       ├── api/
│       │   ├── app.py             # FastAPI factory + /health
│       │   ├── schemas.py         # Request/response models
│       │   ├── routes_runs.py     # POST/GET runs, list runs, SSE events
│       │   └── routes_brand.py    # brandvoice-mcp proxy (overview, profile, samples, guidelines)
│       ├── agent/
│       │   ├── executor.py        # run_draft_agent — ReAct tool-use loop
│       │   ├── tools.py           # AGENT_TOOLS definitions (web_search, get_writing_examples, draft_content)
│       │   └── handlers.py        # handle_web_search (Tavily), build_get_writing_examples_handler
│       ├── graph/
│       │   ├── state.py           # ContentState (TypedDict + reducers)
│       │   ├── nodes.py           # create_nodes(..., emit=...); generate_draft uses agent loop w/ fallback
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
    ├── test_db.py
    ├── test_agent_executor.py
    ├── test_agent_handlers.py
    └── test_config.py
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

Optional settings (see `.env.example`): `BRANDVOICE_COMMAND`, `BRANDVOICE_ARGS`, `DEFAULT_MODEL`, `MAX_RETRIES`, `ALIGNMENT_THRESHOLD`, `DATABASE_URL`, `LOG_LEVEL`, `TAVILY_API_KEY` (enables `web_search` in the draft agent).

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

## Run the HTTP API

```bash
uv run uvicorn content_app.api.app:app --reload --host 0.0.0.0 --port 8000
```

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Liveness |
| `POST /api/runs` | Body: `{"topic","platform","tone"}` → `201` + `{ "run_id" }` (pipeline runs in a **background asyncio task**) |
| `GET /api/runs` | List recent runs from SQLite (`?limit=20` default) |
| `GET /api/runs/{run_id}/events` | **SSE** stream (JSON lines in `data:`); includes `run_started`, per-node `node_start` / `node_end`, `run_complete` or `run_failed` |
| `GET /api/runs/{run_id}` | Snapshot: `phase`, `result` (if any), and `events` (history) |
| `GET /api/brand/overview` | Voice **profile** + **samples** in one MCP session (used by the Brand page) |
| `GET /api/brand/profile` | Voice profile (brandvoice-mcp) |
| `GET /api/brand/samples` | List ingested samples |
| `POST /api/brand/samples` | Ingest writing samples (JSON body: `content`) |
| `POST /api/brand/samples/delete` | Delete samples: body `{"sample_ids":["…"]}` or `{"all": true}` (proxies brandvoice-mcp `delete_samples`) |
| `PUT /api/brand/guidelines` | Update brand guidelines (JSON body: `guidelines`) |

The SSE handler replays from an in-memory **event history** (and short-polls until `phase` is `complete` or `failed`). A per-run **asyncio.Queue** remains for compatibility with the runner; subscribers should use the SSE endpoint rather than reading the queue directly.

---

## Run the frontend

Start the API on **port 8000** first (see above). In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (default **http://localhost:5173**). Browser calls to **`/api/...`** are proxied to **`http://localhost:8000`**, so the UI and API share the same origin during development.

**Pages:** **Pipeline** (`/`) — start runs and watch the graph + SSE; **Brand** (`/brand`) — profile, samples, guidelines; **History** (`/history`) — past runs from the API.

| Script | Description |
|--------|-------------|
| `npm run dev` | Vite dev server with HMR |
| `npm run build` | Typecheck + production build to `frontend/dist/` |
| `npm run preview` | Serve the production build locally |
| `npm run lint` | ESLint |

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
  → generate_draft        (ReAct tool-use loop via ClaudeProvider.generate_with_tools)
      ├─ [optional] web_search          → Tavily (requires TAVILY_API_KEY)
      ├─ [optional] get_writing_examples → brandvoice-mcp RAG
      └─ draft_content                  → final post (exits loop)
      fallback: plain provider.generate() if agent fails or provider lacks tool support
  → check_alignment       (brandvoice-mcp; normalized to score + feedback)
  → score ≥ threshold? → done
  → else retry (inject feedback + previous draft) until max_retries
```

API runs use the same graph with an optional **`emit`** callback so each node emits **`node_start`** / **`node_end`** (plus **`run_started`** / **`run_complete`** from the runner). The **`frontend`** consumes **`POST /api/runs`**, **`GET /api/runs/{id}`**, and the **SSE** stream for the pipeline page; **`GET /api/runs`** and **`GET /api/brand/overview`** (and related brand routes) power history and the brand dashboard.

---

## Roadmap

- **Phase 4 (optional):** Gmail / Calendar MCP  
- **Deployment / polish:** hosting, auth, richer editor and alignment UX as needed  
