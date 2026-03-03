import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.github.diff_parser import nearest_commentable_line
from app.models import ChatMessage, DraftComment, ReviewChunk, ReviewInstance, PullRequest
from app.reviews.service import get_ai_provider
from app.schemas import (
    ChatMessageCreate,
    ChatMessageResponse,
    DraftCommentCreate,
    DraftCommentResponse,
    DraftCommentUpdate,
    ReviewChunkDetail,
)

router = APIRouter(prefix="/api/chunks", tags=["chunks"])


def _chunk_to_detail(chunk: ReviewChunk) -> ReviewChunkDetail:
    return ReviewChunkDetail(
        id=chunk.id,
        order_index=chunk.order_index or 0,
        title=chunk.title,
        purpose=chunk.purpose,
        walkthrough=chunk.walkthrough,
        chunk_summary=chunk.chunk_summary,
        review_order=chunk.get_review_order(),
        file_paths=chunk.get_file_paths(),
        diff_content=chunk.get_diff_content(),
        line_map=chunk.get_line_map(),
        status=chunk.status,
        ai_suggestions_md=chunk.ai_suggestions_md,
        ai_comments=chunk.get_ai_comments(),
        human_done=chunk.human_done or False,
    )


@router.patch("/{chunk_id}/done", response_model=ReviewChunkDetail)
def set_chunk_done(chunk_id: int, db: Session = Depends(get_db)):
    chunk = db.get(ReviewChunk, chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")
    chunk.human_done = not chunk.human_done
    db.commit()
    return _chunk_to_detail(chunk)


@router.get("/{chunk_id}", response_model=ReviewChunkDetail)
def get_chunk(chunk_id: int, db: Session = Depends(get_db)):
    chunk = db.get(ReviewChunk, chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")
    return _chunk_to_detail(chunk)


@router.post("/{chunk_id}/run-ai", status_code=202)
def run_ai_on_chunk(chunk_id: int, db: Session = Depends(get_db)):
    chunk = db.get(ReviewChunk, chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")

    review = db.get(ReviewInstance, chunk.review_instance_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    try:
        ai = get_ai_provider(review.model_provider or "claude")
        result = ai.review_chunk(
            chunk.title or "",
            chunk.get_diff_content(),
            chunk.get_line_map(),
        )
        chunk.ai_suggestions_md = result.get("assessment", "")
        chunk.ai_comments_json = json.dumps(result.get("comments", []))
        chunk.status = "AI_DONE"
        db.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI review failed: {e}")

    return _chunk_to_detail(chunk)


# ── Chat ──────────────────────────────────────────────────────────────────────

@router.get("/{chunk_id}/chat", response_model=list[ChatMessageResponse])
def get_chat(chunk_id: int, db: Session = Depends(get_db)):
    chunk = db.get(ReviewChunk, chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.review_chunk_id == chunk_id)
        .order_by(ChatMessage.created_at)
        .all()
    )
    return messages


@router.post("/{chunk_id}/chat", response_model=ChatMessageResponse)
def send_chat(chunk_id: int, body: ChatMessageCreate, db: Session = Depends(get_db)):
    chunk = db.get(ReviewChunk, chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")

    review = db.get(ReviewInstance, chunk.review_instance_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    # Save user message
    user_msg = ChatMessage(review_chunk_id=chunk_id, role="user", content=body.message)
    db.add(user_msg)
    db.commit()

    # Build history for AI
    history = (
        db.query(ChatMessage)
        .filter(ChatMessage.review_chunk_id == chunk_id)
        .order_by(ChatMessage.created_at)
        .all()
    )
    ai_messages = [{"role": m.role, "content": m.content} for m in history]

    # Build chunk context
    diff_parts = []
    for path, patch in chunk.get_diff_content().items():
        diff_parts.append(f"### {path}\n```diff\n{patch}\n```")
    chunk_context = "\n\n".join(diff_parts)
    if chunk.ai_suggestions_md:
        chunk_context += f"\n\nAI Assessment:\n{chunk.ai_suggestions_md}"

    # Try to find the local repo clone for file access
    from app.github.clone_manager import ensure_repo, REPOS_DIR
    pr = db.get(PullRequest, review.pull_request_id)
    repo_path = None
    if pr:
        candidate = REPOS_DIR / pr.owner / pr.repo
        if candidate.exists():
            repo_path = candidate

    try:
        ai = get_ai_provider(review.model_provider or "claude")
        reply = ai.chat(chunk_context, ai_messages, repo_path=repo_path)
    except Exception as e:
        reply = f"_AI unavailable: {e}_"

    assistant_msg = ChatMessage(review_chunk_id=chunk_id, role="assistant", content=reply)
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)
    return assistant_msg


def _body_with_label(body_md: str, label: str | None) -> str:
    if label:
        return f"**[{label}]** {body_md}"
    return body_md


# ── Draft Comments ────────────────────────────────────────────────────────────

@router.get("/{chunk_id}/drafts", response_model=list[DraftCommentResponse])
def get_drafts(chunk_id: int, db: Session = Depends(get_db)):
    chunk = db.get(ReviewChunk, chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")
    drafts = (
        db.query(DraftComment)
        .filter(DraftComment.review_chunk_id == chunk_id)
        .order_by(DraftComment.created_at)
        .all()
    )
    return drafts


@router.post("/{chunk_id}/drafts", response_model=DraftCommentResponse, status_code=201)
def create_draft(chunk_id: int, body: DraftCommentCreate, db: Session = Depends(get_db)):
    chunk = db.get(ReviewChunk, chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")

    # Validate / anchor line
    line_map = chunk.get_line_map()
    commentable = set(line_map.get(body.path, []))
    line = body.line
    if line not in commentable:
        nearest = nearest_commentable_line(line_map, body.path, line)
        if nearest is not None:
            line = nearest

    draft = DraftComment(
        review_chunk_id=chunk_id,
        path=body.path,
        line=line,
        side=body.side,
        start_line=body.start_line,
        start_side=body.start_side,
        body_md=body.body_md,
        label=body.label,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


@router.put("/drafts/{draft_id}", response_model=DraftCommentResponse)
def update_draft(draft_id: int, body: DraftCommentUpdate, db: Session = Depends(get_db)):
    draft = db.get(DraftComment, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    if body.body_md is not None:
        draft.body_md = body.body_md
    if body.path is not None:
        draft.path = body.path
    if body.line is not None:
        draft.line = body.line
    if body.label is not None:
        draft.label = body.label
    db.commit()
    db.refresh(draft)
    return draft


@router.delete("/drafts/{draft_id}", status_code=204)
def delete_draft(draft_id: int, db: Session = Depends(get_db)):
    draft = db.get(DraftComment, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    db.delete(draft)
    db.commit()


@router.post("/drafts/{draft_id}/send")
def send_draft(draft_id: int, db: Session = Depends(get_db)):
    draft = db.get(DraftComment, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    if draft.status == "SENT":
        raise HTTPException(status_code=400, detail="Draft already sent")

    chunk = db.get(ReviewChunk, draft.review_chunk_id)
    review = db.get(ReviewInstance, chunk.review_instance_id)
    pr = db.get(PullRequest, review.pull_request_id)

    from app.github.client import GitHubClient, get_github_token
    token = get_github_token()
    if not token:
        raise HTTPException(status_code=400, detail="GitHub token not available")

    gh = GitHubClient(token)
    try:
        result = gh.create_review_comment(
            owner=pr.owner,
            repo=pr.repo,
            pr_number=pr.pr_number,
            commit_id=pr.head_sha,
            path=draft.path,
            line=draft.line,
            body=_body_with_label(draft.body_md, draft.label),
            side=draft.side or "RIGHT",
            start_line=draft.start_line,
            start_side=draft.start_side,
        )
        draft.status = "SENT"
        draft.github_comment_id = result.get("id")
        db.commit()
        db.refresh(draft)
        return draft
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to post to GitHub: {e}")
