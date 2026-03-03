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
