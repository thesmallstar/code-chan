"""
Manages local clones of GitHub repos under <project-root>/repos/{owner}/{repo}.
Uses shallow clones (--depth 1) for speed. Streams progress to the logger
so you can see what's happening in the backend console.
"""

import logging
import subprocess
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

REPOS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "repos"
CLONE_TIMEOUT = 300   # seconds — increase if you have very large repos


def _stream(pipe, log_fn):
    """Read lines from a pipe and forward to log_fn."""
    try:
        for line in iter(pipe.readline, ""):
            stripped = line.rstrip()
            if stripped:
                log_fn(stripped)
    finally:
        pipe.close()


def _run_streaming(cmd: list[str], cwd: Path = None, timeout: int = CLONE_TIMEOUT) -> tuple[int, str]:
    """
    Run a command, stream stdout+stderr to the logger in real-time,
    and return (returncode, combined_stderr_text).
    """
    label = " ".join(str(c) for c in cmd)
    logger.info("▶ %s", label)

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(cwd) if cwd else None,
    )

    stderr_lines: list[str] = []

    def capture_stderr(pipe):
        try:
            for line in iter(pipe.readline, ""):
                stripped = line.rstrip()
                if stripped:
                    stderr_lines.append(stripped)
                    logger.info("  [git] %s", stripped)
        finally:
            pipe.close()

    t_out = threading.Thread(target=_stream, args=(proc.stdout, lambda l: logger.info("  [git] %s", l)))
    t_err = threading.Thread(target=capture_stderr, args=(proc.stderr,))
    t_out.start()
    t_err.start()

    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        t_out.join(timeout=2)
        t_err.join(timeout=2)
        raise RuntimeError(
            f"Command timed out after {timeout}s: {label}\n"
            "Tip: increase CLONE_TIMEOUT in clone_manager.py, or check your network."
        )

    t_out.join()
    t_err.join()
    return proc.returncode, "\n".join(stderr_lines)


def ensure_repo(owner: str, repo: str, head_sha: str = None) -> Path:
    """
    Clone (shallow, --depth 1) or update the repo.
    Fetches the specific head_sha when provided so Claude sees the PR state.
    Returns the path to the local clone.

    All git output is streamed to the backend console (INFO level).
    """
    REPOS_DIR.mkdir(exist_ok=True)
    owner_dir = REPOS_DIR / owner
    owner_dir.mkdir(exist_ok=True)
    repo_path = owner_dir / repo

    if not repo_path.exists():
        logger.info("Cloning %s/%s (shallow) → %s", owner, repo, repo_path)
        rc, err = _run_streaming([
            "gh", "repo", "clone", f"{owner}/{repo}", str(repo_path),
            "--", "--depth", "1", "--no-tags",
        ])
        if rc != 0:
            raise RuntimeError(f"Clone failed (exit {rc}):\n{err}")
    else:
        logger.info("Repo already cloned at %s, fetching latest", repo_path)
        _run_streaming(["git", "fetch", "--depth", "1", "--no-tags", "-q"], cwd=repo_path)

    if head_sha:
        logger.info("Checking out %s", head_sha)
        rc, err = _run_streaming(
            ["git", "fetch", "--depth", "1", "origin", head_sha],
            cwd=repo_path,
        )
        if rc == 0:
            _run_streaming(["git", "checkout", "FETCH_HEAD"], cwd=repo_path)
        else:
            # Shallow fetch of a specific SHA sometimes needs --unshallow first
            logger.warning("Direct SHA fetch failed, trying checkout: %s", err)
            _run_streaming(["git", "checkout", head_sha], cwd=repo_path)

    logger.info("✓ Repo ready at %s", repo_path)
    return repo_path
