"""
Claude Code CLI provider.
Shells out to `claude -p` (non-interactive print mode).
When repo_path is provided, runs from that directory so Claude can read local files.
No ANTHROPIC_API_KEY needed — uses whatever `claude auth` is active.
"""

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

from app.ai.base import AIProvider
from app.github.diff_parser import nearest_commentable_line

logger = logging.getLogger(__name__)

_PLAN_CHUNKS_SYSTEM = """\
You are a senior software engineer structuring a code review session for a human reviewer.

Given all changed files in a PR, group them into logical review chunks that should be reviewed together.
Think about: what features/concerns do these files implement? What context does a reviewer need first?

Return ONLY valid JSON — no other text, no markdown fences:
{
  "chunks": [
    {
      "title": "short descriptive title (e.g., 'Auth middleware refactor')",
      "purpose": "1-2 sentences: what this chunk achieves and why these files belong together",
      "walkthrough": "2-4 sentences: how to approach reviewing this chunk — what the change is trying to do, what patterns to look for, what to be careful about",
      "summary": "3-6 markdown bullet points (- item) of what actually changed",
      "files": ["path/to/file1", "path/to/file2"],
      "review_order": ["path/to/file2", "path/to/file1"]
    }
  ]
}

Rules:
- Every changed file must appear in exactly one chunk
- Order chunks so the reviewer builds context progressively (foundations before features, models before routes, etc.)
- review_order within a chunk = best reading order (e.g., interfaces before implementations)
- 1-6 files per chunk; use judgment over rigid limits
- If only 1-3 files changed total, one chunk is fine"""

_PR_SUMMARY_SYSTEM = """\
You are a senior software engineer performing a code review.
Given a pull request, provide a concise markdown summary with:
1. A 2-3 sentence overview of what this PR does and why.
2. A bullet list of the key changes.
3. A brief "Areas to watch" section with any concerns or things that need attention.
You have access to the repository files — read them for full context if needed.
Keep it factual and useful for a reviewer skimming before diving in."""

_CHUNK_REVIEW_SYSTEM = """\
You are a senior software engineer reviewing a specific set of file changes (a "chunk") in a pull request.
You have access to the full repository — read the files to understand context beyond the diff.

Respond ONLY with valid JSON matching this schema exactly:
{
  "assessment": "<markdown string: overall assessment of this chunk>",
  "comments": [
    {
      "path": "<file path>",
      "line": <new-file line number as integer>,
      "side": "RIGHT",
      "body": "<markdown review comment body>"
    }
  ]
}

Rules:
- Only comment on lines that exist in the provided diff (additions and context lines on the RIGHT side).
- Each comment must be specific and actionable.
- Limit to the most important 3-5 issues. Do not nitpick style unless critical.
- If there are no issues, return an empty comments array and a positive assessment.
- Return ONLY the JSON object, no other text."""

_PLAN_CHUNKS_SCHEMA = {
    "type": "object",
    "properties": {
        "chunks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "purpose": {"type": "string"},
                    "walkthrough": {"type": "string"},
                    "summary": {"type": "string"},
                    "files": {"type": "array", "items": {"type": "string"}},
                    "review_order": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title", "purpose", "walkthrough", "summary", "files", "review_order"],
            },
        },
    },
    "required": ["chunks"],
}

_CHUNK_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "assessment": {"type": "string", "description": "Markdown overall assessment of this chunk"},
        "comments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "line": {"type": "integer"},
                    "side": {"type": "string", "enum": ["RIGHT"]},
                    "body": {"type": "string", "description": "Markdown review comment body"},
                },
                "required": ["path", "line", "side", "body"],
            },
        },
    },
    "required": ["assessment", "comments"],
}

_CHAT_SYSTEM = """\
You are a code review assistant helping a developer refine their review comments.
You have access to the repository files — read them if needed for better context.
Help the user craft clear, specific, and constructive review comments. Be direct and concise."""

_RE_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "changes_summary": {"type": "string"},
        "thread_opinions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "github_id": {"type": "integer"},
                    "should_resolve": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
                "required": ["github_id", "should_resolve", "reason"],
            },
        },
    },
    "required": ["changes_summary", "thread_opinions"],
}


def _run_claude(
    prompt: str,
    cwd: Optional[Path] = None,
    json_schema: Optional[dict] = None,
) -> str:
    """
    Run `claude -p <prompt>` and return stdout.
    Unsets CLAUDECODE so nested invocations from inside a Claude Code session work.
    Runs from `cwd` when provided so Claude can navigate the repo files.
    When json_schema is provided, enforces structured JSON output via --json-schema.
    """
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    cmd = ["claude", "-p", prompt]
    if json_schema:
        cmd += ["--output-format", "json", "--json-schema", json.dumps(json_schema)]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
            cwd=str(cwd) if cwd else None,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "`claude` CLI not found. Install Claude Code: https://claude.ai/code"
        )
    if result.returncode != 0:
        logger.error("claude CLI failed (exit %d):\n%s", result.returncode, result.stderr.strip())
        raise RuntimeError(f"claude CLI exited {result.returncode}: {result.stderr.strip()}")

    # Log stderr even on success — useful for seeing tool calls, warnings, etc.
    if result.stderr.strip():
        logger.debug("claude stderr:\n%s", result.stderr.strip())

    output = result.stdout.strip()
    logger.debug("claude output (%d chars): %s…", len(output), output[:200])
    return output


def _build_diff_context(file_diffs: dict[str, str]) -> str:
    parts = []
    for path, patch in file_diffs.items():
        parts.append(f"### File: {path}\n```diff\n{patch}\n```")
    return "\n\n".join(parts)


def _truncate_patch(patch: str, max_lines: int = 40) -> str:
    if not patch:
        return "(no diff)"
    lines = patch.splitlines()
    if len(lines) <= max_lines:
        return patch
    return "\n".join(lines[:max_lines]) + f"\n  … ({len(lines) - max_lines} more lines)"


class ClaudeProvider(AIProvider):
    def plan_chunks(
        self,
        pr_data: dict,
        files: list[dict],
        repo_path: Optional[Path] = None,
    ) -> list[dict]:
        file_context = "\n\n".join(
            f"### {f['filename']}  (+{f.get('additions',0)}/-{f.get('deletions',0)}, status: {f.get('status','modified')})\n"
            f"```diff\n{_truncate_patch(f.get('patch',''))}\n```"
            for f in files
        )
        repo_note = (
            f"\nRepository is checked out at {repo_path} — you may read files for additional context.\n"
            if repo_path else ""
        )
        prompt = (
            f"{_PLAN_CHUNKS_SYSTEM}{repo_note}\n\n"
            f"PR: {pr_data.get('title','')}\n"
            f"Description: {pr_data.get('body') or '(none)'}\n\n"
            f"Changed files ({len(files)}):\n\n{file_context}"
        )
        raw = _run_claude(prompt, cwd=repo_path, json_schema=_PLAN_CHUNKS_SCHEMA)
        return _parse_chunk_plan(raw, files)

    def summarize_pr(
        self,
        pr_data: dict,
        files: list[dict],
        repo_path: Optional[Path] = None,
    ) -> str:
        file_list = "\n".join(
            f"- {f['filename']} (+{f.get('additions',0)}/-{f.get('deletions',0)})"
            for f in files
        )
        repo_note = (
            f"\nThe repository is available at: {repo_path}\nFeel free to read the changed files for full context.\n"
            if repo_path else ""
        )
        prompt = (
            f"{_PR_SUMMARY_SYSTEM}{repo_note}\n\n"
            f"PR Title: {pr_data.get('title', '')}\n\n"
            f"PR Description:\n{pr_data.get('body') or '(no description)'}\n\n"
            f"Files changed ({len(files)}):\n{file_list}"
        )
        return _run_claude(prompt, cwd=repo_path)

    def review_chunk(
        self,
        chunk_title: str,
        file_diffs: dict[str, str],
        line_map: dict,
        repo_path: Optional[Path] = None,
    ) -> dict:
        diff_ctx = _build_diff_context(file_diffs)
        commentable = {path: sorted(lines) for path, lines in line_map.items() if lines}
        repo_note = (
            f"\nThe repository is checked out at: {repo_path}\nYou can read any file for additional context.\n"
            if repo_path else ""
        )
        prompt = (
            f"{_CHUNK_REVIEW_SYSTEM}{repo_note}\n\n"
            f"Chunk: {chunk_title}\n\n"
            f"Commentable lines per file (only comment on these): {json.dumps(commentable)}\n\n"
            f"Diffs:\n{diff_ctx}"
        )
        raw = _run_claude(prompt, cwd=repo_path, json_schema=_CHUNK_REVIEW_SCHEMA)
        try:
            result = _unwrap_json_envelope(raw)
        except (json.JSONDecodeError, AttributeError):
            logger.warning("Failed to parse review JSON (%d chars): %s…", len(raw), raw[:200])
            result = {"assessment": raw, "comments": []}
        return _validate_and_anchor_comments(result, line_map)

    def chat(
        self,
        chunk_context: str,
        messages: list[dict],
        repo_path: Optional[Path] = None,
    ) -> str:
        history = "\n".join(
            f"[{m['role'].capitalize()}]: {m['content']}" for m in messages
        )
        repo_note = (
            f"\nRepository is available at: {repo_path} — read files if helpful.\n"
            if repo_path else ""
        )
        prompt = (
            f"{_CHAT_SYSTEM}{repo_note}\n\n"
            f"Chunk diff context:\n{chunk_context}\n\n"
            f"Conversation so far:\n{history}\n\n"
            f"[Assistant]:"
        )
        return _run_claude(prompt, cwd=repo_path)

    def re_review(
        self,
        pr_data: dict,
        diff_files: list[dict],
        root_threads: list[dict],
        issue_comments: list[dict],
    ) -> dict:
        diff_ctx = _build_diff_context(
            {f["filename"]: f.get("patch", "") for f in diff_files}
        ) if diff_files else "No new commits since the last review."

        threads_ctx = ""
        if root_threads:
            parts = []
            for t in root_threads:
                loc = f"{t.get('path', '')}:{t.get('line', '')}" if t.get("path") else "general"
                parts.append(
                    f"[github_id={t['id']}] {t.get('user',{}).get('login','?')} at {loc}:\n{t.get('body','')[:300]}"
                )
            threads_ctx = "\n\n".join(parts)
        else:
            threads_ctx = "No open review threads."

        issue_ctx = "\n\n".join(
            f"{c.get('user',{}).get('login','?')}: {c.get('body','')[:200]}"
            for c in issue_comments
        ) or "None."

        prompt = f"""\
You are re-reviewing a pull request that was previously reviewed.

PR: {pr_data.get('title','')}
Description: {pr_data.get('body') or '(none)'}

NEW CHANGES SINCE LAST REVIEW:
{diff_ctx}

OPEN REVIEW THREADS (inline comments from reviewers):
{threads_ctx}

GENERAL PR DISCUSSION COMMENTS:
{issue_ctx}

Please:
1. Write a concise markdown summary of what changed since the last review (2-5 bullet points). If no new changes, say so.
2. For each open review thread listed above, decide:
   - should_resolve: true if the concern was addressed in the new changes or is no longer relevant; false if it still needs attention or a response
   - reason: 1-sentence explanation

Return ONLY valid JSON matching the schema."""

        raw = _run_claude(prompt, json_schema=_RE_REVIEW_SCHEMA)
        try:
            return _unwrap_json_envelope(raw)
        except (json.JSONDecodeError, AttributeError):
            return {"changes_summary": raw, "thread_opinions": []}


def _unwrap_json_envelope(raw: str) -> dict:
    """Parse JSON from claude output, handling the --output-format json envelope."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    data = json.loads(text)
    # --output-format json + --json-schema puts data in "structured_output"
    result = data.get("structured_output") or data.get("result") or data
    if isinstance(result, str):
        result = json.loads(result)
    return result


def _parse_chunk_plan(raw: str, files: list[dict]) -> list[dict]:
    """Parse LLM chunk plan JSON; fall back gracefully if malformed."""
    try:
        data = _unwrap_json_envelope(raw)
        chunks = data.get("chunks", [])
    except (json.JSONDecodeError, AttributeError):
        logger.warning("Could not parse chunk plan JSON, falling back to single chunk")
        chunks = []

    # Validate: make sure all files are covered
    all_files = {f["filename"] for f in files}
    covered = {fp for chunk in chunks for fp in chunk.get("files", [])}
    uncovered = all_files - covered

    if uncovered:
        chunks.append({
            "title": "Remaining changes",
            "purpose": "Files not grouped into another chunk.",
            "walkthrough": "Review these remaining file changes.",
            "summary": "\n".join(f"- {f}" for f in sorted(uncovered)),
            "files": sorted(uncovered),
            "review_order": sorted(uncovered),
        })

    # If nothing came back, single chunk with everything
    if not chunks:
        all_filenames = [f["filename"] for f in files]
        chunks = [{
            "title": "All changes",
            "purpose": "All changed files in this PR.",
            "walkthrough": "Review all changed files.",
            "summary": "\n".join(f"- {f['filename']}" for f in files),
            "files": all_filenames,
            "review_order": all_filenames,
        }]

    return chunks


def _validate_and_anchor_comments(result: dict, line_map: dict) -> dict:
    comments = result.get("comments", [])
    validated = []
    for c in comments:
        path = c.get("path", "")
        line = c.get("line")
        if not path or line is None:
            continue
        commentable = set(line_map.get(path, []))
        anchored = False
        if line not in commentable:
            nearest = nearest_commentable_line(line_map, path, line)
            if nearest is None:
                continue
            line = nearest
            anchored = True
        validated.append({**c, "line": line, "anchored": anchored})
    return {**result, "comments": validated}
