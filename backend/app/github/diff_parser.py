"""
Parse GitHub unified diff patches into structured line maps.

Each file's `patch` field from the GitHub PR files API looks like:
  @@ -1,7 +1,7 @@
   context line
  -removed line
  +added line
   context line
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DiffLine:
    type: str           # "context" | "addition" | "deletion" | "hunk_header"
    old_line: Optional[int]
    new_line: Optional[int]
    content: str


@dataclass
class FileDiff:
    path: str
    lines: list[DiffLine] = field(default_factory=list)
    commentable_lines: set[int] = field(default_factory=set)  # new line numbers


HUNK_HEADER_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)")


def parse_patch(patch: str, path: str) -> FileDiff:
    """
    Parse a single file's unified diff patch string into a FileDiff.
    Returns structured line data and the set of commentable (new-side) line numbers.
    """
    diff = FileDiff(path=path)
    if not patch:
        return diff

    old_line = 0
    new_line = 0

    for raw in patch.splitlines():
        hunk_match = HUNK_HEADER_RE.match(raw)
        if hunk_match:
            old_line = int(hunk_match.group(1))
            new_line = int(hunk_match.group(3))
            diff.lines.append(DiffLine(
                type="hunk_header",
                old_line=None,
                new_line=None,
                content=raw,
            ))
            continue

        if raw.startswith("+") and not raw.startswith("+++"):
            diff.lines.append(DiffLine(
                type="addition",
                old_line=None,
                new_line=new_line,
                content=raw[1:],
            ))
            diff.commentable_lines.add(new_line)
            new_line += 1

        elif raw.startswith("-") and not raw.startswith("---"):
            diff.lines.append(DiffLine(
                type="deletion",
                old_line=old_line,
                new_line=None,
                content=raw[1:],
            ))
            old_line += 1

        else:
            # Context line (starts with " " or empty in some edge cases)
            content = raw[1:] if raw.startswith(" ") else raw
            diff.lines.append(DiffLine(
                type="context",
                old_line=old_line,
                new_line=new_line,
                content=content,
            ))
            diff.commentable_lines.add(new_line)
            old_line += 1
            new_line += 1

    return diff


def build_line_maps(files: list[dict]) -> dict[str, list[int]]:
    """
    Build a map of {path: [commentable_new_line_numbers]} for all files.
    `files` is the GitHub PR files API response list.
    """
    line_map: dict[str, list[int]] = {}
    for f in files:
        path = f.get("filename", "")
        patch = f.get("patch", "")
        if not patch:
            line_map[path] = []
            continue
        parsed = parse_patch(patch, path)
        line_map[path] = sorted(parsed.commentable_lines)
    return line_map


def nearest_commentable_line(line_map: dict, path: str, desired_line: int) -> Optional[int]:
    """
    Find the nearest commentable line to `desired_line` for `path`.
    Returns None if no commentable lines exist for that file.
    """
    lines = line_map.get(path, [])
    if not lines:
        return None
    return min(lines, key=lambda l: abs(l - desired_line))


def diff_lines_to_json(diff: FileDiff) -> list[dict]:
    """Serialize DiffLine objects to plain dicts for JSON transport."""
    return [
        {
            "type": dl.type,
            "old_line": dl.old_line,
            "new_line": dl.new_line,
            "content": dl.content,
        }
        for dl in diff.lines
    ]
