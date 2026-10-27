# Prompt plan: make pipeline failures explain themselves

## Why

Two outages on Oct 27, 2026 had the same shape: the real error existed, but nothing showed it.

| Outage | Real cause | What the user saw |
|---|---|---|
| Brand page | brandvoice-mcp crashed on import (`mcp` 2.x removed `mcp.server.FastMCP`) | `502 {"detail":"Connection closed"}` |
| Pipeline | `claude-sonnet-4-20250514` was retired, API returned 404 | Run “failed”, no reason, every node “succeeded” |

Root causes in the code:

1. Nodes catch exceptions and return `{"status": "failed"}` without the reason (`graph/nodes.py`).
2. The graph keeps going after a failure: `fetch_voice_context -> generate_draft -> check_alignment` are unconditional edges, so a failed draft still runs alignment.
3. A graph that ends with `status: failed` emits `run_complete`, and the UI shows a failed run with `error: null` (`useRunPipeline.ts`, `graphFailed`).
4. The MCP client discards the subprocess's stderr, so “Connection closed” hides the traceback.
5. Nothing checks at startup that the model ID or the brandvoice server actually works.
6. The deploy workflow has no `set -e` and no smoke test, so a broken deploy is green.

## How to use this

Run the prompts in order, one per session. Each one is self-contained, ends with tests, and should be its own commit. Before starting each prompt, paste this preamble:

> Smallest change that fully solves it. Keep the existing structure (node factory, `BrandvoiceClient`, SSE event shapes). No new dependencies. Add or update tests for every new branch. Run `pytest` and show it passing.

---

## Prompt 1: carry the error through graph state

> In `src/content_app/graph/state.py`, add an optional `error: str` field to `ContentState` (`total=False` already covers optional).
>
> In `src/content_app/graph/nodes.py`, every `except` block that returns `{"status": "failed"}` must also return `"error": f"<node_name>: {type(e).__name__}: {e}"`. Keep the existing `logger` calls, but use `logger.exception` so tracebacks reach the logs. In `generate_draft`, when the agent path throws and the fallback also throws, include both messages in `error`.
>
> In `check_alignment`, when the run fails because `retry_count >= max_retries`, set `error` to `"check_alignment: score {score} below threshold {threshold} after {retry_count} drafts"`.
>
> Tests in `tests/test_graph.py`: make the provider raise `anthropic.NotFoundError` (or a plain `Exception("model not found")`) and assert the final state has `status == "failed"` and `error` contains `generate_draft` and the message.

## Prompt 2: stop the graph at the first failure

> In `src/content_app/graph/builder.py`, replace the two unconditional edges with conditional ones: after `fetch_voice_context` and after `generate_draft`, route to `END` when `state["status"] == "failed"`, otherwise to the next node. Reuse one small router function for both instead of writing two.
>
> Test: when `fetch_voice_context` fails, `generate_draft` and `check_alignment` are never called (assert on the mocks), and `error` mentions `fetch_voice_context`.

## Prompt 3: send the reason to the UI

> In `src/content_app/runner.py`, include `"error": result.get("error")` in the `run_complete` event. In `_background_run`, replace the generic `"Pipeline error; see server logs."` with `f"{type(e).__name__}: {e}"`, truncated to 500 characters. Never include API keys or headers. Add a test that a message containing the `ANTHROPIC_API_KEY` value gets redacted.
>
> In `frontend/src/hooks/useRunPipeline.ts`, when `run_complete` arrives with `status === "failed"`, set `error` from `data.error` (fallback `"Run failed"`), not `null`. Render it in `PipelinePage.tsx` wherever `RUN_FAILED` errors already show, and reuse that component.
>
> Also show it on the History page for stored runs, since `save_run` persists the whole state.

## Prompt 4: surface MCP subprocess crashes

> In `src/content_app/mcp/brandvoice.py`, `stdio_client` takes an `errlog` argument. Pass a temp file (`tempfile.TemporaryFile(mode="w+")`) owned by the `AsyncExitStack`. When `initialize()` or any `call_tool` raises, read the last ~20 lines of that file and raise `RuntimeError(f"brandvoice-mcp failed: {e}\n--- server stderr ---\n{tail}")` from the original exception.
>
> `routes_brand.py` already turns exceptions into 502 with `str(e)`, so the traceback will show up there. Add a test that runs `BrandvoiceClient` against a fake server command (`python -c "import sys; sys.stderr.write('ImportError: boom'); sys.exit(1)"`) and asserts the error text contains `ImportError: boom`.

## Prompt 5: fail fast at startup and on /health

> Add a `GET /health/deep` endpoint next to `/health` in `src/main.py`. Keep `/health` cheap, because the Docker healthcheck calls it. `/health/deep` checks:
> 1. Model: `await AsyncAnthropic().models.retrieve(settings.default_model)`. Report `ok` or the error.
> 2. brandvoice: open a `BrandvoiceClient`, call `list_tools`, and check the tool names the app uses (`get_voice_context`, `check_alignment`, `ingest_samples`, `list_samples`, `get_profile`, `set_guidelines`, `delete_samples`) are present. Report missing names. That catches the old `fetch_voice_context` typo class too.
>
> Return 200 with `{"model": ..., "brandvoice": ...}` when both pass, otherwise 503 with the same body. Also run the same check in `lifespan` at startup and log one ERROR line per failure. Don't crash the app, so the UI still loads and can show the problem.
>
> Note: `src/main.py` and `src/content_app/api/app.py` both build a FastAPI app. Check which one uvicorn serves (`src.main:app` per `supervisord.conf`) and add the endpoint there. Flag the duplicate in your summary instead of refactoring it.

## Prompt 6: make deploys honest

> In `.github/workflows/deploy.yml`, start the SSH script with `set -euo pipefail`. After `docker compose up -d --build`, poll `curl -fsS http://localhost/health/deep` up to 12 times, 5 seconds apart. If it never passes, print `docker compose logs --tail 100 app` and exit 1 so the workflow goes red.

## Prompt 7: handle the new stop reasons

> In `src/content_app/agent/executor.py` and `providers/claude.py`, handle `stop_reason` values other than `tool_use` and `end_turn`: `refusal` (include `stop_details` if present), `max_tokens`, and `model_context_window_exceeded`. Raise a `ValueError` with the stop reason and let Prompt 1's `error` field carry it. Don't silently return the “Agent produced no output.” string. Keep the fallback path for ordinary text-only `end_turn`.

---

## Done when

- Breaking each thing on purpose shows the real cause in the UI within one click:
  - `DEFAULT_MODEL=claude-sonnet-4-20250514` shows `generate_draft: NotFoundError ...` on the Pipeline page, and `/health/deep` returns 503.
  - `BRANDVOICE_ARGS='["--with","mcp>=2","brandvoice-mcp==0.2.0"]'` shows the `ImportError` on the Brand page.
- A push with a broken model ID turns the deploy workflow red.

## Out of scope

- Retry or backoff for transient API errors.
- An error-tracking service (Sentry and similar).
- Porting brandvoice-mcp to `mcp` 2.x. The real fix is the `mcp>=1.0.0,<2` pin plus a 0.2.1 release.
