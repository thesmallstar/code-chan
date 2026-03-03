# Contributing

Contributions are welcome — whether it's a bug fix, a new feature, better prompts, or docs improvements.

---

## Getting started

1. Fork and clone the repo
2. Follow [setup.md](setup.md) to get it running locally
3. Open an issue for larger changes before writing code (to avoid duplicate work or going in the wrong direction)

---

## Code structure

```
backend/app/
├── ai/
│   ├── base.py              ← AIProvider abstract class (5 abstract methods)
│   └── claude.py            ← ClaudeProvider (subprocess → claude CLI)
├── github/
│   ├── client.py            ← GitHub REST API calls
│   ├── diff_parser.py       ← Unified diff → commentable line map
│   └── clone_manager.py     ← Repo cloning, checkout
├── reviews/
│   ├── service.py           ← Orchestrates the full review pipeline
│   └── re_review_service.py ← Re-review background task
├── routers/
│   ├── reviews.py
│   ├── chunks.py
│   ├── threads.py
│   ├── re_reviews.py        ← POST create + GET poll
│   └── github.py            ← review requests sync/cache
├── models.py                ← SQLAlchemy ORM
├── schemas.py               ← Pydantic schemas
└── main.py

frontend/src/
├── pages/
│   ├── Landing.jsx          ← review requests + recent reviews
│   └── ReviewInstance.jsx   ← chunk view + threads + re-review tab
├── components/
│   ├── ChunkList.jsx
│   ├── DiffView.jsx
│   ├── ChatPanel.jsx
│   ├── DraftComments.jsx
│   ├── ThreadsPanel.jsx     ← colored diff hunks, outdated badge, resolve
│   └── StatusBadge.jsx
└── lib/api.js               ← HTTP client

backend/tests/
├── test_chunks.py
├── test_reviews.py
├── test_github.py
├── test_threads.py          ← resolve toggle
├── test_re_reviews.py       ← re-review create/poll, cache deletion
└── test_helpers.py
```

---

## Adding a new AI provider

1. Create `backend/app/ai/yourprovider.py`
2. Subclass `AIProvider` from `base.py` and implement all five methods:
   - `plan_chunks(pr_data, files, repo_path) -> list[dict]`
   - `summarize_pr(pr_data, files, repo_path) -> str`
   - `review_chunk(title, file_diffs, line_map, repo_path) -> dict`
   - `chat(chunk_context, messages, repo_path) -> str`
   - `re_review(pr_data, diff_files, root_threads, issue_comments) -> dict`
     Returns `{changes_summary: str, thread_opinions: [{github_id, should_resolve, reason}]}`
3. Register it in `backend/app/reviews/service.py`:
   ```python
   from app.ai.yourprovider import YourProvider
   PROVIDERS = {'claude': ClaudeProvider, 'yourprovider': YourProvider}
   ```
4. Expose it in the frontend's Landing page if it has a distinct name/auth requirement

The `repo_path` is a `Path` to the locally cloned repo. Pass it as the `cwd` for any subprocess you spawn. If your provider doesn't use a local CLI, you can ignore it.

---

## Improving prompts

All prompts live inside the AI provider files (`backend/app/ai/claude.py`). They're just Python strings. Some tips:

- `plan_chunks` returns structured JSON — if you change the schema, update `ReviewChunk` in `models.py` and `schemas.py` too
- `review_chunk` returns `{assessment, comments: [{path, line, side, body}]}` — the line anchoring in `reviews/service.py` depends on this shape
- Test with small PRs first (< 5 files, < 200 lines changed) to iterate quickly

---

## Frontend changes

The frontend uses Tailwind CSS v4. No custom config needed; just add utility classes.

All API calls go through `frontend/src/lib/api.js`. Add new endpoints there.

---

## Commit style

Use conventional commits (loosely):
- `feat: add gitlab support`
- `fix: handle empty PR description`
- `docs: update contributing guide`
- `refactor: extract diff parser`

---

## What would be really useful

- [ ] **More test coverage** — `diff_parser.py`, the re-review service, and the chunker are under-tested
- [ ] **GitLab / Bitbucket support** — the GitHub client is abstracted enough that a new `GitProvider` interface would work
- [ ] **Additional AI providers** — Codex (OpenAI), Gemini, local Ollama models
- [ ] **GitHub App** — so chan can run automatically on new PRs via webhook
- [ ] **Prompt tuning** — better chunk plans, better inline comment suggestions
- [ ] **Mobile / smaller viewport** — the layout assumes a wide screen
- [ ] **Theming** — dark mode, per-user preferences

---

## Issues and PRs

- Please include reproduction steps for bugs
- For features, describe the use case before the implementation
- For prompts, share example inputs and outputs to demonstrate improvement
