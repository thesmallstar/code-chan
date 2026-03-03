"""Background task for re-reviewing a PR — compares commits and evaluates open threads."""

import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.github.client import GitHubClient, get_github_token
from app.models import PullRequest, ReReview, ReviewInstance, ReviewThread
from app.reviews.service import get_ai_provider

logger = logging.getLogger(__name__)


def process_re_review(re_review_id: int) -> None:
    db: Session = SessionLocal()
    try:
        _run(db, re_review_id)
    except Exception as exc:
        logger.exception("Re-review failed for id=%s", re_review_id)
        db.rollback()
        try:
            rr = db.get(ReReview, re_review_id)
            if rr:
                rr.status = "ERROR"
                rr.error_message = str(exc)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def _run(db: Session, re_review_id: int) -> None:
    rr = db.get(ReReview, re_review_id)
    if not rr:
        return

    rr.status = "RUNNING"
    db.commit()

    review = db.get(ReviewInstance, rr.review_instance_id)
    pr = db.get(PullRequest, review.pull_request_id)

    token = get_github_token()
    if not token:
        raise RuntimeError("GitHub token not available")

    gh = GitHubClient(token)

    pr_data = gh.get_pull_request(pr.owner, pr.repo, pr.pr_number)
    new_sha = pr_data["head"]["sha"]
    old_sha = rr.old_head_sha
    rr.new_head_sha = new_sha
    db.commit()

    diff_files = []
    if old_sha and old_sha != new_sha:
        try:
            compare = gh.get_commit_compare(pr.owner, pr.repo, old_sha, new_sha)
            diff_files = compare.get("files", [])
        except Exception as e:
            logger.warning("Could not fetch commit compare: %s", e)

    review_comments = gh.get_review_comments(pr.owner, pr.repo, pr.pr_number)
    issue_comments = gh.get_issue_comments(pr.owner, pr.repo, pr.pr_number)
    root_threads = [c for c in review_comments if not c.get("in_reply_to_id")]

    ai = get_ai_provider(review.model_provider or "claude")
    result = ai.re_review(pr_data, diff_files, root_threads, issue_comments)

    # Enrich opinions with thread metadata for the frontend
    thread_by_gh_id = {c["id"]: c for c in review_comments}
    enriched = []
    for op in result.get("thread_opinions", []):
        gh_id = op.get("github_id")
        raw = thread_by_gh_id.get(gh_id, {})
        enriched.append({
            "github_id": gh_id,
            "author": raw.get("user", {}).get("login"),
            "body_preview": (raw.get("body") or "")[:120],
            "path": raw.get("path"),
            "line": raw.get("line") or raw.get("original_line"),
            "should_resolve": op.get("should_resolve", False),
            "reason": op.get("reason", ""),
        })

    rr.changes_summary_md = result.get("changes_summary", "")
    rr.thread_opinions_json = json.dumps(enriched)
    rr.status = "DONE"
    db.commit()
