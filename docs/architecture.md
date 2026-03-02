# Architecture

## Overview

code-chan is a local web app with a React frontend and a FastAPI backend. Everything runs on your machine — no cloud infra, no database servers. The only external calls are to the GitHub API and the `claude` CLI.

```
Browser (localhost:3000)
        │
        │  HTTP / JSON
        ▼
FastAPI backend (localhost:8000)
        │
        ├── GitHub API (REST, via gh CLI token)
        ├── claude CLI  (subprocess, no API key)
        └── SQLite DB   (data/code-chan.db)
                        + local repo clones (repos/)
```

---

## Review Pipeline

When a PR URL is submitted, a background task runs the following stages. The frontend polls `GET /api/reviews/:id` every 3 seconds and shows live status.

```
POST /api/reviews
        │
        ▼
[SYNCING]
  - parse PR URL → owner/repo/number
  - fetch PR metadata, files+patches, existing comments via GitHub API
  - store ReviewThread records (existing comments + replies)
  - clone repo shallowly: repos/{owner}/{repo}/ (--depth 1)
  - checkout PR head SHA
        │
        ▼
[SUMMARIZING]
  - call: claude -p "<PR title + description + file list>"
  - cwd: repos/{owner}/{repo}/  ← claude can read local files
  - store: ReviewInstance.summary_md
        │
        ▼
[CHUNKING]
  - call: claude -p "<all file diffs (truncated to 40 lines each)>"
  - claude decides: which files belong together, why, and how to review them
  - returns JSON: [{title, purpose, walkthrough, summary, files, review_order}]
  - store: ReviewChunk records with all metadata
  - fallback: heuristic grouper if LLM call fails
        │
        ▼
[AI_RUNNING]  (one call per chunk)
  - call: claude -p "<chunk diff + commentable line map>"
  - cwd: repos/{owner}/{repo}/
  - returns JSON: {assessment, comments: [{path, line, side, body}]}
  - line anchoring: if a suggested line isn't in the diff, move to nearest commentable line
  - store: ReviewChunk.ai_suggestions_md, ai_comments_json
  - pre-populate DraftComment records from AI suggestions
        │
        ▼
[READY]
```

---

## Data Model

```
PullRequest
  owner, repo, pr_number, title, body, author, head_sha, base_sha

ReviewInstance
  pull_request_id, status, summary_md, model_provider

ReviewChunk
  review_instance_id, order_index
  title, purpose, walkthrough, chunk_summary, review_order (JSON)
  file_paths (JSON), diff_content (JSON), line_map (JSON)
  status, ai_suggestions_md, ai_comments_json (JSON)

ReviewThread          ← existing GitHub PR comments
  review_instance_id, github_id, type (REVIEW_COMMENT | ISSUE_COMMENT)
  author, body, path, line, diff_hunk, in_reply_to_id

ChatMessage           ← per-chunk chat with chan
  review_chunk_id, role (user | assistant), content

DraftComment          ← inline comments ready to post to GitHub
  review_chunk_id, path, line, side, body_md, status (DRAFT | SENT)
```

---

## AI Provider Interface

All AI calls go through `app/ai/base.py`:

```python
class AIProvider(ABC):
    def plan_chunks(pr_data, files, repo_path) -> list[dict]
    def summarize_pr(pr_data, files, repo_path) -> str
    def review_chunk(title, file_diffs, line_map, repo_path) -> dict
    def chat(chunk_context, messages, repo_path) -> str
```

Currently implemented: `ClaudeProvider` (shells out to `claude -p`).

The `repo_path` parameter sets the working directory for the subprocess, giving claude access to read any file in the cloned repo. `CLAUDECODE` env var is stripped before each call to allow nested sessions.

---

## Diff Line Anchoring

GitHub only allows inline comments on lines that appear in the PR diff. To handle this:

1. `diff_parser.py` parses each file's unified diff patch into a set of commentable `(path, new_line)` pairs (additions + context lines on the RIGHT side).
2. When claude suggests a comment at a line not in this set, `nearest_commentable_line()` finds the closest valid line in the same file.
3. The `anchored: true` flag is set on the comment to indicate it was moved.

---

## Frontend Polling

```
ReviewInstance status: PENDING → SYNCING → SUMMARIZING → CHUNKING → AI_RUNNING → READY
```

While status is in `[PENDING, SYNCING, SUMMARIZING, CHUNKING, AI_RUNNING]`, the frontend polls every 3 seconds. A blue banner shows "chan is on it". Once READY (or ERROR), polling stops.

---

## Repo Clones

Repos are cloned to `repos/{owner}/{repo}/` using `gh repo clone -- --depth 1 --no-tags`. This gives claude access to:
- Full file content beyond just the diff
- Other files for cross-reference
- Package manifests, configs, type definitions

The `repos/` directory is gitignored and never committed. Re-syncing a review fetches and checks out the latest head SHA.
