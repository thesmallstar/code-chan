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
