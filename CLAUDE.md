# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Odysseus is a self-hosted AI workspace (chat, agent, deep research, documents, email, calendar, memory/skills, model cookbook) — a FastAPI backend serving a vanilla-JS single-page app. Python 3.11+. No frontend build step, no bundler.

## Commands

```bash
# Setup (native)
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python setup.py                      # first-time init (creates admin account, data/)

# Run the server
python -m uvicorn app:app --host 127.0.0.1 --port 7000

# Tests (pytest is in requirements.txt; config in pyproject.toml, asyncio_mode=auto)
python -m pytest                     # full suite
python -m pytest tests/test_agent_loop.py            # single file
python -m pytest tests/test_agent_loop.py -k name    # single test

# Quick syntax checks (used in lieu of a linter — there is no configured linter/formatter)
python -m py_compile app.py routes/*.py src/*.py
node --check static/js/<file-you-changed>.js

# Docker
docker compose up -d --build
docker compose logs --tail=120 odysseus
```

CI (`.github/workflows/tests.yml`) runs `pytest -q` on Linux **and Windows** (py3.11/3.12). Keep tests Windows-safe: pass `encoding="utf-8"` to every file read/write and don't rely on symlinks (see `tests/conftest.py` and past cp1252 collection failures).

Tests named `test_*_js.py` are Python tests that shell out to `node` via subprocess to exercise real `static/js/*.js` source (they skip if node is missing). `tests/conftest.py` stubs heavy optional deps (sqlalchemy, fastapi, etc.) with MagicMock **only when not installed** — many unit tests run without the full dependency stack.

## Architecture

### Backend layout

- **`app.py`** — slim orchestrator: middleware (auth, security headers, request hard-timeout), static serving, and route wiring. Every router module in `routes/` exposes a `setup_*_routes(deps...)` factory returning an `APIRouter`; `app.py` calls `src/app_initializer.py:initialize_managers()` to build the shared manager objects (session_manager, memory_manager, chat_handler, model_discovery, …) and injects them into the factories.
- **`core/`** — foundation: `auth.py` (AuthManager, privileges, TOTP), `database.py` (canonical SQLAlchemy models), `atomic_io.py` (crash-safe JSON writes: temp + fsync + `os.replace`), `middleware.py`, `constants.py`.
- **`src/`** — app-wired logic: LLM core, agent loop and tool machinery, chat processing, managers. `src/database.py` is only a re-export shim for `core/database.py`.
- **`routes/`** — one module per feature area; `*_helpers.py` siblings hold shared logic.
- **`services/`** — self-contained subsystem packages (`tts`, `stt`, `search`, `research`, `docs`, `shell`, `youtube`, `memory`, `hwfit`), each with a `service.py` singleton accessor. `src/` glue imports from here.
- **`mcp_servers/`** — built-in MCP servers (image gen, memory, rag, email) registered at startup by `src/builtin_mcp.py`; they run as stdio subprocesses that import the app's own managers.
- **`scripts/odysseus`** — git-style CLI dispatcher for `scripts/odysseus-*` subcommands (mail, memory, tasks, notes, …); these are how the agent's bash tool reaches app features from the terminal.
- **`companion/`** — read-only LAN pairing bridge (see its README for the CSRF posture).

### Chat / agent flow

`POST /api/chat_stream` (`routes/chat_routes.py`) → verify session ownership → `build_chat_context` (`routes/chat_helpers.py` → `src/chat_handler.py`/`chat_processor.py`: presets, memory, RAG, attachments) → branch on mode: plain chat calls `stream_llm_with_fallback`, agent mode calls `src/agent_loop.py:stream_agent_loop`, research runs via `research_handler`. Responses stream as SSE. Runs are **detached** (`src/agent_runs.py`) so they survive tab close; the client reconnects via `/api/chat/resume/{id}`.

`src/llm_core.py` is the single provider abstraction — an OpenAI-compatible `/chat/completions` client (llama.cpp, vLLM, Ollama incl. native URLs, OpenAI, OpenRouter, Anthropic) with fallback chains and dead-host cooldown.

### Agent tools

`src/agent_tools.py` is a facade over four modules: `tool_parsing.py` (parse fenced tool blocks), `tool_schemas.py` (native function-call schemas), `tool_execution.py` (`execute_tool_block` dispatcher, path confinement), `tool_implementations.py` (`do_*` functions). `tool_index.py` does RAG-based tool selection (top-K per message + `ALWAYS_AVAILABLE`). Tools route to an MCP server or the in-process direct fallback.

**When adding a new agent tool, always check** (recurring defect class — see `QA_LEDGER.md`):
1. Should it be in `NON_ADMIN_BLOCKED_TOOLS` (`src/tool_security.py`)? Compare with peers like `manage_memory`/`manage_calendar` — new tools must not default to more exposure than comparable ones.
2. Do destructive/cascading operations belong on an agent-reachable surface at all? The agent processes untrusted content (email, web, transcripts), so irreversible ops are a prompt-injection data-loss path.

### Auth & owner scoping

`AuthMiddleware` in `app.py` sets `request.state.current_user` from session cookie, `Bearer ody_` API token, or the internal loopback token. Routes use `src/auth_helpers.py`: `require_user`, `require_privilege`, and `owner_filter(query, model, user)` — the standard per-row `owner == user OR owner IS NULL` scoping. Any new route or query touching user data must be owner-scoped; a large share of the test suite exists to pin this (`test_*_owner_scope*.py`). Client-workspace data (`src/clients.py`) is stricter: creator-only, no null-owner fallback. Key env flags: `AUTH_ENABLED` (default true), `LOCALHOST_BYPASS` (dev-only loopback bypass). Admins bypass privilege/tool gates.

### Persistence

- **SQLite via SQLAlchemy** (`core/database.py`, `data/app.db`): sessions, messages, documents, gallery, model endpoints, MCP servers, API tokens, memory, scheduled tasks, client workspaces. Secret columns use the `EncryptedText` (Fernet) type.
- **JSON files in `data/`** (gitignored): `auth.json`, `sessions.json`, `settings.json`, etc. — always written through `core/atomic_io.py`.
- **ChromaDB** (HTTP client, `src/chroma_client.py`) backs vector memory, RAG, and tool selection. Everything must degrade gracefully when Chroma is unreachable (keyword fallback / 503, never a crash).

### Frontend

`static/index.html` + `static/app.js` (module entry) + `static/js/*` — native ES modules loaded via `<script type="module">`, served with no-cache revalidation and CSP nonces. Talks to the backend with `fetch` + SSE parsing (`chatStream.js`). All deep-link routes (`/email`, `/gallery`, …) serve the same SPA. `static/js/MODULE_SUMMARY.md` is a partial historical inventory only.

## Conventions (from CONTRIBUTING.md — enforced in review)

- Keep changes small and focused; no broad rewrites or formatting-only churn.
- The app has an intentional visual style. For anything visual: reuse existing CSS variables (`--red`, `--fg`, `--bg`, `--card`, `--border`, …) — never introduce new color values, font sizes, or spacing units; reuse existing button/input/card classes rather than adding parallel components; **no Unicode emoji in UI or code** (use inline SVG matching the monochrome icon style in `static/index.html`); primary UI text is monospaced (`Fira Code`); dark theme is the default and light-mode work goes through the theme system.
- Visual changes must be verified in a running browser (with screenshots for PRs), not just via tests.
- Update `QA_LEDGER.md` when a review surfaces a new recurring defect class.

## Security posture

This is effectively an admin console (shell access, file I/O, tokens). Defaults are deliberately conservative: bind `127.0.0.1`, `AUTH_ENABLED=true`, non-admins get no shell/python/file tools. Never weaken these defaults, and never let `data/`, `logs/`, `.env`, uploads, or databases into commits (they are gitignored). Security reports go through `SECURITY.md`; the threat model is in `THREAT_MODEL.md`.
