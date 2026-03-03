"""
Codex CLI provider.
Shells out to `codex -q` (quiet / non-interactive mode).
No OPENAI_API_KEY needed when using the authenticated Codex CLI.

Falls back to OpenAI Python SDK if OPENAI_API_KEY is set and the `codex`
binary is not available.
"""

import json
import os
import subprocess

from app.ai.base import AIProvider
from app.github.diff_parser import nearest_commentable_line

_PR_SUMMARY_SYSTEM = """\
You are a senior software engineer performing a code review.
Given a pull request, provide a concise markdown summary with:
1. A 2-3 sentence overview of what this PR does and why.
2. A bullet list of the key changes.
3. A brief "Areas to watch" section with any concerns or things that need attention.
Keep it factual and useful for a reviewer skimming before diving in."""

_CHUNK_REVIEW_SYSTEM = """\
You are a senior software engineer reviewing a specific set of file changes in a pull request.

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
- Only comment on lines that exist in the provided diff (additions and context lines).
- Each comment must be specific and actionable.
- Limit to the most important 3-5 issues.
- If there are no issues, return an empty comments array.
- Return ONLY the JSON object, no other text."""

_CHAT_SYSTEM = """\
You are a code review assistant helping a developer refine their review comments.
You have access to a code diff. Help the user craft clear, specific, constructive comments."""


def _run_codex(prompt: str) -> str:
    """Try `codex -q <prompt>`, fall back to OpenAI SDK if CLI not found."""
    try:
        result = subprocess.run(
            ["codex", "-q", "--no-ansi", prompt],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        # If codex errors, fall through to SDK fallback
    except FileNotFoundError:
        pass

    # SDK fallback (requires OPENAI_API_KEY)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "`codex` CLI not found and OPENAI_API_KEY is not set. "
            "Install Codex CLI or set OPENAI_API_KEY."
        )
    from openai import OpenAI
    model = os.getenv("OPENAI_MODEL", "gpt-4o")
    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL") or None,
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return resp.choices[0].message.content or ""


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


_PLAN_CHUNKS_SYSTEM = """\
You are a senior software engineer structuring a code review session for a human reviewer.

Given all changed files in a PR, group them into logical review chunks that should be reviewed together.

Return ONLY valid JSON — no other text, no markdown fences:
{
  "chunks": [
    {
      "title": "short descriptive title",
      "purpose": "1-2 sentences: what this chunk achieves and why these files belong together",
      "walkthrough": "2-4 sentences: how to approach reviewing this chunk",
      "summary": "3-6 markdown bullet points of what actually changed",
      "files": ["path/to/file1"],
      "review_order": ["path/to/file1"]
    }
  ]
}

Rules: every file in exactly one chunk; order chunks for progressive context-building."""


class CodexProvider(AIProvider):
    def plan_chunks(self, pr_data: dict, files: list[dict], repo_path=None) -> list[dict]:
        from app.ai.claude import _parse_chunk_plan
        file_context = "\n\n".join(
            f"### {f['filename']}  (+{f.get('additions',0)}/-{f.get('deletions',0)})\n"
            f"```diff\n{_truncate_patch(f.get('patch',''))}\n```"
            for f in files
        )
        prompt = (
            f"{_PLAN_CHUNKS_SYSTEM}\n\n"
            f"PR: {pr_data.get('title','')}\n"
            f"Description: {pr_data.get('body') or '(none)'}\n\n"
            f"Changed files ({len(files)}):\n\n{file_context}"
        )
        raw = _run_codex(prompt)
        return _parse_chunk_plan(raw, files)

    def summarize_pr(self, pr_data: dict, files: list[dict], repo_path=None) -> str:
        file_list = "\n".join(
            f"- {f['filename']} (+{f.get('additions',0)}/-{f.get('deletions',0)})"
            for f in files
        )
        prompt = (
            f"{_PR_SUMMARY_SYSTEM}\n\n"
            f"PR Title: {pr_data.get('title', '')}\n\n"
            f"PR Description:\n{pr_data.get('body') or '(no description)'}\n\n"
            f"Files changed ({len(files)}):\n{file_list}"
        )
        return _run_codex(prompt)

    def review_chunk(self, chunk_title: str, file_diffs: dict[str, str], line_map: dict, repo_path=None) -> dict:
        diff_ctx = _build_diff_context(file_diffs)
        commentable = {path: sorted(lines) for path, lines in line_map.items() if lines}
        prompt = (
            f"{_CHUNK_REVIEW_SYSTEM}\n\n"
            f"Chunk: {chunk_title}\n\n"
            f"Commentable lines per file: {json.dumps(commentable)}\n\n"
            f"Diffs:\n{diff_ctx}"
        )
        raw = _run_codex(prompt)
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            result = {"assessment": raw, "comments": []}
        return _validate_and_anchor_comments(result, line_map)

    def chat(self, chunk_context: str, messages: list[dict], repo_path=None) -> str:
        history = "\n".join(
            f"[{m['role'].capitalize()}]: {m['content']}" for m in messages
        )
        prompt = (
            f"{_CHAT_SYSTEM}\n\n"
            f"Chunk diff context:\n{chunk_context}\n\n"
            f"Conversation:\n{history}\n\n"
            f"[Assistant]:"
        )
        return _run_codex(prompt)

    def re_review(self, pr_data, diff_files, root_threads, issue_comments) -> dict:
        # Delegate to the Claude provider implementation since it handles structured JSON well
        from app.ai.claude import ClaudeProvider
        return ClaudeProvider().re_review(pr_data, diff_files, root_threads, issue_comments)


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
