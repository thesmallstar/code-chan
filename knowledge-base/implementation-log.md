# Implementation Log

## v0 Initial Build

- **Date:** 2026-03-01
- **What:** Full end-to-end v0 — GitHub verification, PR ingestion, AI review pipeline, inline comments, chat, draft management
- **How:**
  - **Backend** (`backend/app/`):
    - `github/client.py` — `GitHubClient` using httpx; falls back from `GITHUB_TOKEN` env to `gh auth token` CLI
    - `github/diff_parser.py` — unified diff parser; builds `(path, new_line) → commentable` maps
    - `ai/base.py`, `ai/codex.py`, `ai/claude.py` — `AIProvider` ABC with OpenAI and Anthropic implementations; structured JSON output for inline comments
    - `reviews/chunker.py` — heuristic grouper: test↔source pairing + directory grouping, max 5 files/600 lines per chunk
    - `reviews/service.py` — `process_review()` background task: SYNCING → SUMMARIZING → CHUNKING → AI_RUNNING → READY
    - `routers/` — full CRUD for reviews, chunks, chat, drafts, threads
  - **Frontend** (`frontend/src/`):
    - `pages/Landing.jsx` — GitHub status widget, PR URL input, model selector
    - `pages/ReviewInstance.jsx` — 3-column layout: chunk sidebar + diff/overview + chat/drafts right panel; polls `GET /api/reviews/:id` while active
    - `components/DiffView.jsx` — client-side unified diff parser, color-coded table with hover comment buttons
    - `components/ChatPanel.jsx` — streaming-style chat with AI per chunk
    - `components/DraftComments.jsx` — list/edit/delete/send-to-GitHub draft comments
    - `components/ThreadsPanel.jsx` — existing PR threads with inline reply
- **Depends on:** GitHub `gh` CLI or `GITHUB_TOKEN`; `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`
- **Notes:**
  - All data in SQLite at `./data/code-chan.db` (gitignored)
  - Frontend polls every 3s while review is processing
  - AI-suggested inline comments are pre-populated as DRAFT records

## v0.1 — Human Progress & PR Actions

- **Date:** 2026-03-03
- **What:** `human_done` per chunk (DB-persisted), progress bar, PR approval/request-changes/comment from UI, comment labels, PR state on landing page, review requests section
- **Key files changed:**
  - `models.py` — `human_done` on `ReviewChunk`, `label` on `DraftComment`, `pr_state`/`review_decision` on `PullRequest`
  - `routers/chunks.py` — `PATCH /{id}/done` toggle; label persisted on drafts; `_body_with_label()` prepends label to GitHub body at send time
  - `routers/reviews.py` — `POST /{id}/submit` for PR review events (APPROVE/REQUEST_CHANGES/COMMENT)
  - `ReviewInstance.jsx` — progress bar, `SubmitReviewPanel`, `LabelPicker`
  - `Landing.jsx` — PR state badges, review decision badges, `ReviewRequestRow`
- **Alembic migrations:** `a904c1266c2c`, `9970c026bb25`
- **Tests:** 26 passing unit tests (`test_chunks.py`, `test_reviews.py`, `test_helpers.py`)

## v0.3 — Re-review Tab + Thread Improvements + Bug Fixes

- **Date:** 2026-03-03
- **What:** Re-review feature (changes summary + thread opinions), thread panel improvements (outdated badge, resolve, colored diff), UTC date fix across app, cache-delete fix on review create, all-done badge suppression
- **Key files changed:**
  - `models.py` — `ReReview` model; `position` + `is_resolved` added to `ReviewThread`
  - `schemas.py` — `ThreadOpinion`, `ReReviewResponse`; `ReviewThreadResponse` gets `position`/`is_resolved`; `ReviewRequestItem` gets `existing_review_id`/`last_reviewed_at`
  - `github/client.py` — `get_commit_compare(owner, repo, base, head)` → `GET /repos/{owner}/{repo}/compare/{base}...{head}`
  - `ai/base.py` — abstract `re_review(pr_data, diff_files, root_threads, issue_comments) -> dict`
  - `ai/claude.py` — `re_review()` implementation using `_RE_REVIEW_SCHEMA` and `claude -p` structured output
  - `reviews/re_review_service.py` (new) — `process_re_review()` background task: loads ReReview → PR → fetches current head SHA → compare diff → AI re-review → enrich opinions → DONE
  - `routers/re_reviews.py` (new) — `POST /api/reviews/{id}/re-review` (create + queue) and `GET /api/re-reviews/{id}` (poll)
  - `routers/reviews.py` — delete `ReviewRequestCache` row matching `pr_url` when review is created
  - `routers/threads.py` — `PATCH /{id}/resolve` toggles `is_resolved`, returns `{is_resolved: bool}`
  - `routers/github.py` — `_attach_existing_reviews()` bulk-queries PRs + latest ReviewInstance per PR; attaches to `ReviewRequestItem` via `model_copy(update={})`
  - `main.py` — registers `re_reviews` router
  - `ReviewInstance.jsx` — `ReReviewPanel` + `ThreadOpinionCard` components; "Re-review" sidebar tab; tab state updated to `'overview' | 'chunk' | 'threads' | 're-review'`
  - `ThreadsPanel.jsx` — `DiffHunk` (colored lines); `parseUtc`/`fmtDate` UTC fix; outdated pill when `position === null`; resolve button + optimistic toggle
  - `Landing.jsx` — `parseUtc`/`fmtDate`/`relativeDate` UTC helpers; "chan reviewed · Xd ago" badge on RequestRow; "re-review it" label; `handleStartReview` navigates to `/review/{id}` for existing reviews
- **Alembic migration:** `94eacd111d09`
- **Tests:** 51 passing — 13 new tests across `test_threads.py` and `test_re_reviews.py`
  - `test_threads.py` — resolve toggle: marks resolved, toggles back, 404 on missing
  - `test_re_reviews.py` — create (returns id, captures old SHA, 404), get (pending, done with opinions, 404), cache deletion on review create (removes matching, leaves others), existing_review_id in review requests (present when review exists, null when not)
- **Key UX decisions:**
  - Re-review is a tab inside ReviewInstance, NOT a separate page/route
  - "chan reviewed · Xd ago" badge on ReviewRequestRow is a clickable link to the old review (overview tab)
  - "re-review it" button navigates to `/review/{id}` with `{ state: { tab: 're-review' } }` so ReviewInstance auto-selects the Re-review tab on mount
  - Thread opinions sorted: "respond first" before "can resolve"
  - Old SHA stored at re-review creation time; compare API used to get diff; if same SHA → AI told "no new commits"

## v0.2 — Review Requests Cache + Refresh UX

- **Date:** 2026-03-03
- **What:** Cache GitHub review-requested PRs in SQLite; smart refresh (only if >1hr stale); show "synced X ago" with manual refresh button; correct UTC→local time display
- **Key files changed:**
  - `models.py` — `ReviewRequestCache` model
  - `routers/github.py` — `GET /review-requests` (DB cache) + `POST /review-requests/sync` (GitHub fetch → DB)
  - `schemas.py` — `ReviewRequestsResponse` wraps items + `last_synced_at`
  - `Landing.jsx` — `isStale()`/`saveLastSync()` helpers using localStorage; `setInterval` for 1hr auto-sync; UTC suffix fix for `formatLastSync`
  - `api.js` — added `syncReviewRequests`
- **Alembic migration:** `6fca07df826e`
- **Bug fixed:** `last_synced_at` stored as naive UTC in SQLite; frontend appended `Z` so browser parses it correctly as UTC instead of local time
- **Tests:** 12 new tests in `test_github.py` (38 total passing)
- **UX change:** Starting a review from "Requested Reviews" no longer navigates away — it removes the item from the list and appends to "Recent Reviews" in-place

## v0.4 — Codex Provider + Factory Pattern + Provider Switcher

- **Date:** 2026-03-08
- **What:** Dual AI provider support (Claude Code + Codex) with factory pattern; user picks provider from frontend
- **Key files changed:**
  - `ai/base.py` — added `ProviderRegistry` (register decorator, create, available)
  - `ai/__init__.py` — new file; auto-registers providers on import
  - `ai/claude.py` — added `@ProviderRegistry.register("claude", label="Claude Code")` decorator
  - `ai/codex.py` — full rewrite: `codex exec` non-interactive mode, `--output-schema` via temp files, all 5 `AIProvider` methods implemented natively (was delegating `re_review` to Claude)
  - `reviews/service.py` — `get_ai_provider()` now uses `ProviderRegistry.create()` instead of manual if/else
  - `main.py` — added `GET /api/providers` endpoint
  - `Landing.jsx` — provider switcher (segmented toggle), selection persisted in localStorage, wired into both `handleSubmit` and `handleStartReview`
  - `api.js` — added `getProviders()`
- **Tests:** 51 passing (no regressions)
- **No DB migration needed** — `model_provider` column already stored as free-form string
