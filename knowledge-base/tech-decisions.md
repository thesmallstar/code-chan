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
- **Status:** Decided
- **Decision:** `AIProvider` ABC in `app/ai/base.py` with `codex.py` (OpenAI) and `claude.py` (Anthropic) implementations
- **Why:** Lets user choose provider per review session; trivial to add new providers
- **Alternatives considered:** Hard-coded provider, LangChain abstraction (too heavy)

---

## Inline GitHub comments — nearest-line anchoring

- **Date:** 2026-03-01
- **Status:** Decided
- **Decision:** Build a diff line map from GitHub patch strings; validate AI-suggested lines against the map; auto-anchor to nearest commentable line if invalid
- **Why:** GitHub 422s on lines not in the diff; anchoring avoids silent failures
- **Alternatives considered:** Drop invalid comments (bad UX), let user pick (complex UX)

---

## Heuristic chunking (no embeddings in v0)

- **Date:** 2026-03-01
- **Status:** Decided
- **Decision:** Group files by test/source pairing, then by top-level directory; max 5 files or 600 diff lines per chunk
- **Why:** Fast, deterministic, no ML infra needed; good enough for 90% of PRs
- **Alternatives considered:** Embedding-based semantic clustering (planned for v1)
