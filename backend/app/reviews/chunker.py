"""
Heuristic chunker that groups changed files into logical review chunks.

Strategy:
1. Pair test files with their source files (foo.py + test_foo.py)
2. Group remaining files by their top-level directory
3. Split oversized groups (>5 files or >600 diff lines) into sub-chunks
"""

from pathlib import Path


MAX_FILES_PER_CHUNK = 5
MAX_DIFF_LINES_PER_CHUNK = 600


def _diff_line_count(patch: str) -> int:
    if not patch:
        return 0
    return sum(1 for l in patch.splitlines() if l.startswith(("+", "-")) and not l.startswith(("+++", "---")))


def _base_name(filename: str) -> str:
    """Strip leading 'test_' / trailing '_test' and extension to find source name."""
    stem = Path(filename).stem
    if stem.startswith("test_"):
        stem = stem[5:]
    elif stem.endswith("_test"):
        stem = stem[:-5]
    elif stem.startswith("Test"):
        stem = stem[4:]
    return stem.lower()


def _is_test_file(filename: str) -> bool:
    stem = Path(filename).stem.lower()
    return stem.startswith("test_") or stem.endswith("_test") or stem.startswith("test")


def create_chunks(files: list[dict]) -> list[dict]:
    """
    Group files into review chunks.

    Args:
        files: GitHub PR files API response (each has 'filename', 'patch', etc.)

    Returns:
        List of chunks: [{"title": str, "files": [filename], "file_diffs": {filename: patch}}]
    """
    if not files:
        return []

    file_map = {f["filename"]: f for f in files}
    assigned = set()
    chunks = []

    # Pass 1: pair test files with source files
    test_files = [f["filename"] for f in files if _is_test_file(f["filename"])]
    for test_path in test_files:
        if test_path in assigned:
            continue
        test_base = _base_name(test_path)
        matched_source = None
        for source_path in file_map:
            if source_path in assigned or source_path == test_path:
                continue
            if not _is_test_file(source_path) and _base_name(source_path) == test_base:
                matched_source = source_path
                break
        group = [test_path]
        if matched_source:
            group.append(matched_source)
            assigned.add(matched_source)
        assigned.add(test_path)
        chunks.append(_make_chunk(group, file_map, f"Tests: {Path(test_path).name}"))

    # Pass 2: group remaining files by top-level directory
    remaining = [f["filename"] for f in files if f["filename"] not in assigned]
    dir_groups: dict[str, list[str]] = {}
    for path in remaining:
        parts = Path(path).parts
        top = parts[0] if len(parts) > 1 else "(root)"
        dir_groups.setdefault(top, []).append(path)

    for dir_name, paths in dir_groups.items():
        # Split oversized groups
        for sub_chunk in _split_group(paths, file_map):
            title = _chunk_title(dir_name, sub_chunk)
            chunks.append(_make_chunk(sub_chunk, file_map, title))

    return chunks


def _make_chunk(file_paths: list[str], file_map: dict, title: str) -> dict:
    file_diffs = {}
    for path in file_paths:
        f = file_map.get(path, {})
        file_diffs[path] = f.get("patch", "")
    return {"title": title, "files": file_paths, "file_diffs": file_diffs}


def _split_group(paths: list[str], file_map: dict) -> list[list[str]]:
    """Split a list of paths into sub-groups respecting size limits."""
    result = []
    current: list[str] = []
    current_lines = 0

    for path in paths:
        patch = file_map.get(path, {}).get("patch", "")
        lines = _diff_line_count(patch)
        if current and (len(current) >= MAX_FILES_PER_CHUNK or current_lines + lines > MAX_DIFF_LINES_PER_CHUNK):
            result.append(current)
            current = []
            current_lines = 0
        current.append(path)
        current_lines += lines

    if current:
        result.append(current)
    return result or [[]]


def _chunk_title(dir_name: str, paths: list[str]) -> str:
    if len(paths) == 1:
        return Path(paths[0]).name
    return f"{dir_name}/ ({len(paths)} files)"
