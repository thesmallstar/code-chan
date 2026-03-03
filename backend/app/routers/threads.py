from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PullRequest, ReviewInstance, ReviewThread
from app.schemas import ReviewThreadResponse, ThreadDiscussCreate, ThreadDiscussResponse, ThreadReplyCreate

router = APIRouter(prefix="/api/threads", tags=["threads"])


@router.patch("/{thread_id}/resolve")
def resolve_thread(thread_id: int, db: Session = Depends(get_db)):
    thread = db.get(ReviewThread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    thread.is_resolved = not thread.is_resolved
    db.commit()
    return {"is_resolved": thread.is_resolved}


@router.post("/{thread_id}/reply")
def reply_to_thread(thread_id: int, body: ThreadReplyCreate, db: Session = Depends(get_db)):
    thread = db.get(ReviewThread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    review = db.get(ReviewInstance, thread.review_instance_id)
    pr = db.get(PullRequest, review.pull_request_id)

    from app.github.client import GitHubClient, get_github_token
    token = get_github_token()
    if not token:
        raise HTTPException(status_code=400, detail="GitHub token not available")

    gh = GitHubClient(token)
    try:
        if thread.type == "REVIEW_COMMENT":
            result = gh.reply_to_review_comment(
                owner=pr.owner,
                repo=pr.repo,
                pr_number=pr.pr_number,
                comment_id=thread.github_id,
                body=body.body_md,
            )
        else:
            result = gh.create_issue_comment(
                owner=pr.owner,
                repo=pr.repo,
                issue_number=pr.pr_number,
                body=body.body_md,
            )
        return {"ok": True, "github_comment_id": result.get("id")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to post reply: {e}")


@router.post("/{thread_id}/discuss", response_model=ThreadDiscussResponse)
def discuss_thread(thread_id: int, body: ThreadDiscussCreate, db: Session = Depends(get_db)):
    """Ask chan about a specific thread — gives chan full context: file, diff hunk, all comments."""
    thread = db.get(ReviewThread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    review = db.get(ReviewInstance, thread.review_instance_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    # Gather all replies to this thread
    replies = (
        db.query(ReviewThread)
        .filter(
            ReviewThread.review_instance_id == thread.review_instance_id,
            ReviewThread.in_reply_to_id == thread.github_id,
        )
        .order_by(ReviewThread.created_at)
        .all()
    )

    # Build rich thread context for chan
    ctx_parts = ["You are helping a developer discuss an existing code review comment."]

    if thread.path:
        ctx_parts.append(f"\nFile: `{thread.path}`" + (f" (line {thread.line})" if thread.line else ""))

    if thread.diff_hunk:
        ctx_parts.append(f"\nDiff context:\n```diff\n{thread.diff_hunk}\n```")

    ctx_parts.append(f"\n--- Thread ---")
    ctx_parts.append(f"**{thread.author or 'reviewer'}**: {thread.body or ''}")

    for r in replies:
        ctx_parts.append(f"**{r.author or 'reply'}**: {r.body or ''}")

    ctx_parts.append(
        "\nHelp the developer decide how to respond, whether the concern is valid, "
        "or how to address it in code. Be direct and practical."
    )

    chunk_context = "\n".join(ctx_parts)

    # Try to resolve local repo path for extra file context
    from app.github.clone_manager import REPOS_DIR
    pr = db.get(PullRequest, review.pull_request_id)
    repo_path = None
    if pr:
        candidate = REPOS_DIR / pr.owner / pr.repo
        if candidate.exists():
            repo_path = candidate

    from app.reviews.service import get_ai_provider
    ai = get_ai_provider(review.model_provider or "claude")

    # Build message history (include current message)
    messages = list(body.history) + [{"role": "user", "content": body.message}]

    try:
        reply = ai.chat(chunk_context, messages, repo_path=repo_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"chan unavailable: {e}")

    return ThreadDiscussResponse(reply=reply)
