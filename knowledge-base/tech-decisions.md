# Tech Decisions

## SQLite over PostgreSQL (v0)

- **Date:** 2026-03-01
- **Status:** Decided
- **Decision:** Use SQLite with SQLAlchemy sync engine
- **Why:** Local dev tool with single-user workload; no infrastructure needed, zero config, fast iteration
- **Alternatives considered:** PostgreSQL (overkill for v0), async SQLAlchemy (unnecessary complexity)
- **Trade-offs:** Not suitable for multi-user deployment; easy to swap via `DATABASE_URL` env var later

---

## Sync background tasks (not async)

- **Date:** 2026-03-01
- **Status:** Decided
- **Decision:** FastAPI `BackgroundTasks` with sync `def` functions; `httpx.Client` (sync) for HTTP
- **Why:** Avoids SQLAlchemy sync/async boundary issues; simpler mental model for v0
- **Alternatives considered:** Celery, asyncio fully async pipeline
- **Trade-offs:** Long AI calls block a thread; acceptable for single-user local tool

---

## Pluggable AI provider via base class

- **Date:** 2026-03-01
- **Status:** Superseded by factory pattern (2026-03-08)
- **Decision:** `AIProvider` ABC in `app/ai/base.py` with `codex.py` (OpenAI) and `claude.py` (Anthropic) implementations
- **Why:** Lets user choose provider per review session; trivial to add new providers
- **Alternatives considered:** Hard-coded provider, LangChain abstraction (too heavy)

---

## Factory pattern with ProviderRegistry

- **Date:** 2026-03-08
- **Status:** Decided
- **Decision:** `ProviderRegistry` class in `app/ai/base.py` with `register` decorator, `create(name)`, and `available()` methods. Each provider self-registers via `@ProviderRegistry.register("name", label="Label")`. Auto-registration via `app/ai/__init__.py` imports.
- **Why:** Eliminates manual if/else dispatch in `service.py`; adding a new provider requires zero changes to routing or service code — just a new file with a decorator. `GET /api/providers` endpoint exposes available providers for the frontend.
- **Alternatives considered:** Manual if/else (what we had — doesn't scale), plugin discovery via `importlib` (overkill for 2-3 providers)
- **Trade-offs:** Providers must be imported for registration; handled by `__init__.py`

---

## Codex CLI: `codex exec` non-interactive mode

- **Date:** 2026-03-08
- **Status:** Decided
- **Decision:** Use `codex exec "prompt" -s read-only --ephemeral` for all Codex AI calls. Structured JSON output via `--output-schema <temp_file.json>` (file path, not inline).
- **Why:** The old `codex -q` flag is legacy (TypeScript CLI). Modern Codex CLI (Rust) uses `codex exec` for non-interactive mode. `-s read-only` keeps it safe; `--ephemeral` avoids session file clutter.
- **Key difference from Claude:** `--output-schema` takes a file path, not inline JSON — requires writing temp schema files and cleaning up.
- **Alternatives considered:** OpenAI Python SDK fallback (removed for simplicity; assume CLI is authenticated, same pattern as Claude provider)

---

## Inline GitHub comments — nearest-line anchoring

- **Date:** 2026-03-01
- **Status:** Decided
- **Decision:** Build a diff line map from GitHub patch strings; validate AI-suggested lines against the map; auto-anchor to nearest commentable line if invalid
- **Why:** GitHub 422s on lines not in the diff; anchoring avoids silent failures
- **Alternatives considered:** Drop invalid comments (bad UX), let user pick (complex UX)

---

## Re-review as a tab, not a separate page/route

- **Date:** 2026-03-03
- **Status:** Decided
- **Decision:** Re-review results (changes summary + thread opinions) are shown inside a "Re-review" tab on the existing ReviewInstance page, not as a separate `/re-review/:id` route
- **Why:** The user wants continuity — "built on top of the review view". Navigating to a new page loses context (which chunk was selected, thread state, etc.). A tab preserves layout and sidepanel while adding new context.
- **Alternatives considered:** Separate `/re-review/:id` page (built first, then removed per user feedback)
- **Trade-offs:** `ReReviewPanel` holds its own state (re-review job ID + polling) independently; if user leaves and returns to the tab, state is reset — acceptable for v0

---

## GitHub `position` field for outdated thread detection

- **Date:** 2026-03-03
- **Status:** Decided
- **Decision:** Store `position` from GitHub review comment API on `ReviewThread`; `position === null` means the comment is on a stale/outdated diff
- **Why:** GitHub itself uses `null` position to indicate an outdated comment; no extra API calls needed
- **Trade-offs:** `position` only available for `REVIEW_COMMENT` type, not `ISSUE_COMMENT`

---

## Heuristic chunking (no embeddings in v0)

- **Date:** 2026-03-01
- **Status:** Decided
- **Decision:** Group files by test/source pairing, then by top-level directory; max 5 files or 600 diff lines per chunk
- **Why:** Fast, deterministic, no ML infra needed; good enough for 90% of PRs
- **Alternatives considered:** Embedding-based semantic clustering (planned for v1)
