import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PullRequest, ReviewChunk, ReviewInstance, ReviewThread
from app.reviews.service import parse_pr_url, process_review
from app.schemas import (
    ReviewChunkSummary,
    ReviewCreate,
    ReviewInstanceResponse,
    ReviewThreadResponse,
    SubmitReviewRequest,
    SubmitReviewResponse,
)

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


def _chunk_summary(chunk: ReviewChunk) -> ReviewChunkSummary:
    return ReviewChunkSummary(
        id=chunk.id,
        title=chunk.title,
        file_paths=chunk.get_file_paths(),
        status=chunk.status,
        human_done=chunk.human_done or False,
    )


def _build_review_response(review: ReviewInstance, db: Session) -> ReviewInstanceResponse:
    pr = db.get(PullRequest, review.pull_request_id)
    chunks = (
        db.query(ReviewChunk)
        .filter(ReviewChunk.review_instance_id == review.id)
        .order_by(ReviewChunk.id)
        .all()
    )
    from app.schemas import PullRequestInfo
    pr_info = None
    if pr:
        pr_info = PullRequestInfo(
            id=pr.id,
            owner=pr.owner,
            repo=pr.repo,
            pr_number=pr.pr_number,
            title=pr.title,
            body=pr.body,
            author=pr.author,
            head_sha=pr.head_sha,
            url=pr.url,
            last_synced_at=pr.last_synced_at,
            pr_state=pr.pr_state,
            review_decision=pr.review_decision,
        )
    return ReviewInstanceResponse(
        id=review.id,
        status=review.status,
        model_provider=review.model_provider,
        summary_md=review.summary_md,
        pull_request=pr_info,
        chunks=[_chunk_summary(c) for c in chunks],
        error_message=review.error_message,
        created_at=review.created_at,
    )


@router.get("", response_model=list[ReviewInstanceResponse])
def list_reviews(db: Session = Depends(get_db)):
    reviews = (
        db.query(ReviewInstance)
        .order_by(ReviewInstance.created_at.desc())
        .limit(50)
        .all()
    )
    return [_build_review_response(r, db) for r in reviews]


@router.post("", status_code=201)
def create_review(data: ReviewCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        owner, repo, pr_number = parse_pr_url(data.pr_url)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Reuse existing PR record or create one
    pr = (
        db.query(PullRequest)
        .filter_by(owner=owner, repo=repo, pr_number=pr_number)
        .first()
    )
    if not pr:
        pr = PullRequest(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            url=data.pr_url,
        )
        db.add(pr)
        db.commit()
        db.refresh(pr)

    review = ReviewInstance(
        pull_request_id=pr.id,
        status="PENDING",
        model_provider=data.model_provider,
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    background_tasks.add_task(process_review, review.id)

    return {"review_id": review.id}


@router.get("/{review_id}", response_model=ReviewInstanceResponse)
def get_review(review_id: int, db: Session = Depends(get_db)):
    review = db.get(ReviewInstance, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return _build_review_response(review, db)


@router.post("/{review_id}/sync", status_code=202)
def sync_review(review_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    review = db.get(ReviewInstance, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    review.status = "PENDING"
    db.commit()
    background_tasks.add_task(process_review, review_id)
    return {"status": "sync started"}


@router.post("/{review_id}/submit", response_model=SubmitReviewResponse)
def submit_review(review_id: int, body: SubmitReviewRequest, db: Session = Depends(get_db)):
    if body.event not in {"APPROVE", "REQUEST_CHANGES", "COMMENT"}:
        raise HTTPException(status_code=422, detail="event must be APPROVE, REQUEST_CHANGES, or COMMENT")
    if body.event == "REQUEST_CHANGES" and not body.body.strip():
        raise HTTPException(status_code=422, detail="body is required when requesting changes")

    review = db.get(ReviewInstance, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    pr = db.get(PullRequest, review.pull_request_id)
    if not pr:
        raise HTTPException(status_code=404, detail="Pull request not found")
    if not pr.head_sha:
        raise HTTPException(status_code=400, detail="PR head SHA not available — re-sync first")

    from app.github.client import GitHubClient, get_github_token
    token = get_github_token()
    if not token:
        raise HTTPException(status_code=400, detail="GitHub token not available")

    gh = GitHubClient(token)
    try:
        result = gh.submit_pull_request_review(
            owner=pr.owner,
            repo=pr.repo,
            pr_number=pr.pr_number,
            commit_id=pr.head_sha,
            event=body.event,
            body=body.body,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit review: {e}")

    return SubmitReviewResponse(
        github_review_id=result["id"],
        state=result.get("state", body.event),
        html_url=result.get("html_url"),
    )


@router.get("/{review_id}/threads", response_model=list[ReviewThreadResponse])
def get_threads(review_id: int, db: Session = Depends(get_db)):
    review = db.get(ReviewInstance, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    threads = (
        db.query(ReviewThread)
        .filter(ReviewThread.review_instance_id == review_id)
        .order_by(ReviewThread.created_at)
        .all()
    )
    return threads
