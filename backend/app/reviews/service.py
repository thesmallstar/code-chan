"""
Core business logic for creating and processing review instances.
Runs as a synchronous background task (called from FastAPI BackgroundTasks).
"""

import json
import logging
import re
from datetime import datetime

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.github.client import GitHubClient, get_github_token
from app.github.clone_manager import ensure_repo
from app.github.diff_parser import build_line_maps
from app.models import (
    DraftComment,
    PullRequest,
    ReviewChunk,
    ReviewInstance,
    ReviewThread,
)
from app.reviews.chunker import create_chunks  # kept as fallback

logger = logging.getLogger(__name__)

PR_URL_RE = re.compile(
    r"https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>\d+)"
)


def parse_pr_url(url: str) -> tuple[str, str, int]:
    m = PR_URL_RE.match(url.strip())
    if not m:
        raise ValueError(f"Invalid GitHub PR URL: {url}")
    return m.group("owner"), m.group("repo"), int(m.group("number"))


def get_ai_provider(model_provider: str):
    if model_provider == "codex":
        from app.ai.codex import CodexProvider
        return CodexProvider()
    from app.ai.claude import ClaudeProvider
    return ClaudeProvider()


def _set_status(db: Session, review: ReviewInstance, status: str, error: str = None):
    review.status = status
    if error:
        review.error_message = error
    db.commit()


def process_review(review_id: int) -> None:
    """
    Full pipeline: fetch PR → summarize → chunk → AI review per chunk.
    Runs in FastAPI's background task thread pool (sync).
    """
    db: Session = SessionLocal()
    try:
        _run_pipeline(db, review_id)
    except Exception as exc:
        logger.exception("Review pipeline failed for review_id=%s", review_id)
        db.rollback()
        try:
            review = db.get(ReviewInstance, review_id)
            if review:
                _set_status(db, review, "ERROR", str(exc))
        except Exception:
            pass
    finally:
        db.close()


def _run_pipeline(db: Session, review_id: int) -> None:
    review = db.get(ReviewInstance, review_id)
    if not review:
        return

    pr = db.get(PullRequest, review.pull_request_id)
    if not pr:
        _set_status(db, review, "ERROR", "Associated PR record not found")
        return

    token = get_github_token()
    if not token:
        _set_status(db, review, "ERROR", "GitHub token not found. Set GITHUB_TOKEN env or run `gh auth login`.")
        return

    gh = GitHubClient(token)

    # ── 1. Sync PR metadata ────────────────────────────────────────────────
    _set_status(db, review, "SYNCING")

    try:
        pr_data = gh.get_pull_request(pr.owner, pr.repo, pr.pr_number)
        files_data = gh.get_pull_request_files(pr.owner, pr.repo, pr.pr_number)
        review_comments = gh.get_review_comments(pr.owner, pr.repo, pr.pr_number)
        issue_comments = gh.get_issue_comments(pr.owner, pr.repo, pr.pr_number)
    except Exception as e:
        _set_status(db, review, "ERROR", f"GitHub fetch failed: {e}")
        return

    pr.title = pr_data.get("title")
    pr.body = pr_data.get("body")
    pr.author = pr_data.get("user", {}).get("login")
    pr.head_sha = pr_data.get("head", {}).get("sha")
    pr.base_sha = pr_data.get("base", {}).get("sha")
    pr.last_synced_at = datetime.utcnow()
    pr.pr_state = "merged" if pr_data.get("merged") else pr_data.get("state", "open")
    try:
        pr.review_decision = gh.get_pull_request_review_decision(pr.owner, pr.repo, pr.pr_number)
    except Exception:
        pr.review_decision = None
    db.commit()

    # ── 1b. Clone / update repo so AI can read files ───────────────────────
    repo_path = None
    try:
        repo_path = ensure_repo(pr.owner, pr.repo, pr.head_sha)
        logger.info("Repo available at %s", repo_path)
    except Exception as e:
        logger.warning("Could not clone repo (AI will work from diff only): %s", e)

    # Store existing threads (clear old ones for this review instance first)
    db.query(ReviewThread).filter(ReviewThread.review_instance_id == review_id).delete()
    for c in review_comments:
        db.add(ReviewThread(
            review_instance_id=review_id,
            github_id=c.get("id"),
            type="REVIEW_COMMENT",
            author=c.get("user", {}).get("login"),
            body=c.get("body", ""),
            path=c.get("path"),
            line=c.get("line") or c.get("original_line"),
            diff_hunk=c.get("diff_hunk"),
            created_at=_parse_dt(c.get("created_at")),
            in_reply_to_id=c.get("in_reply_to_id"),
        ))
    for c in issue_comments:
        db.add(ReviewThread(
            review_instance_id=review_id,
            github_id=c.get("id"),
            type="ISSUE_COMMENT",
            author=c.get("user", {}).get("login"),
            body=c.get("body", ""),
            created_at=_parse_dt(c.get("created_at")),
        ))
    db.commit()

    # ── 2. Summarize ────────────────────────────────────────────────────────
    _set_status(db, review, "SUMMARIZING")
    try:
        ai = get_ai_provider(review.model_provider)
        summary = ai.summarize_pr(pr_data, files_data, repo_path=repo_path)
        review.summary_md = summary
        db.commit()
    except Exception as e:
        logger.warning("PR summary failed: %s", e)
        review.summary_md = f"_Summary generation failed: {e}_"
        db.commit()

    # ── 3. LLM plans the chunk structure ────────────────────────────────────
    _set_status(db, review, "CHUNKING")
    line_maps = build_line_maps(files_data)
    file_map = {f["filename"]: f for f in files_data}

    ai = get_ai_provider(review.model_provider)
    try:
        logger.info("Asking chan to plan review chunks…")
        chunk_plans = ai.plan_chunks(pr_data, files_data, repo_path=repo_path)
        logger.info("chan planned %d chunks", len(chunk_plans))
    except Exception as e:
        logger.warning("LLM chunk planning failed (%s), falling back to heuristic", e)
        # Fallback: use heuristic chunker, minimal metadata
        raw_fallback = create_chunks(files_data)
        chunk_plans = [
            {
                "title": r["title"],
                "purpose": "",
                "walkthrough": "",
                "summary": "",
                "files": r["files"],
                "review_order": r["files"],
            }
            for r in raw_fallback
        ]

    # Clear existing chunks for this review
    db.query(ReviewChunk).filter(ReviewChunk.review_instance_id == review_id).delete()
    db.commit()

    chunk_records = []
    for idx, plan in enumerate(chunk_plans):
        file_paths = plan.get("files", [])
        file_diffs = {p: file_map.get(p, {}).get("patch", "") for p in file_paths}
        chunk_line_map = {p: line_maps.get(p, []) for p in file_paths}

        chunk = ReviewChunk(
            review_instance_id=review_id,
            order_index=idx,
            title=plan.get("title", f"Chunk {idx + 1}"),
            purpose=plan.get("purpose", ""),
            walkthrough=plan.get("walkthrough", ""),
            chunk_summary=plan.get("summary", ""),
            review_order=json.dumps(plan.get("review_order", file_paths)),
            file_paths=json.dumps(file_paths),
            diff_content=json.dumps(file_diffs),
            line_map=json.dumps(chunk_line_map),
        )
        db.add(chunk)
        chunk_records.append((chunk, file_diffs, chunk_line_map))
    db.commit()

    # ── 4. AI review per chunk (inline comments) ─────────────────────────────
    _set_status(db, review, "AI_RUNNING")

    for chunk, file_diffs, chunk_line_map in chunk_records:
        try:
            result = ai.review_chunk(
                chunk.title or "",
                file_diffs,
                chunk_line_map,
                repo_path=repo_path,
            )
            chunk.ai_suggestions_md = result.get("assessment", "")
            chunk.ai_comments_json = json.dumps(result.get("comments", []))

            for c in result.get("comments", []):
                db.add(DraftComment(
                    review_chunk_id=chunk.id,
                    path=c["path"],
                    line=c["line"],
                    side=c.get("side", "RIGHT"),
                    body_md=c.get("body", ""),
                ))

            chunk.status = "AI_DONE"
        except Exception as e:
            logger.warning("AI review failed for chunk %s: %s", chunk.id, e)
            chunk.status = "ERROR"
            chunk.ai_suggestions_md = f"_chan couldn't review this chunk: {e}_"
        db.commit()

    _set_status(db, review, "READY")


def _parse_dt(s: str) -> datetime:
    if not s:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return datetime.utcnow()
