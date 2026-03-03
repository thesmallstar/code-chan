import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PullRequest, ReReview, ReviewInstance
from app.reviews.re_review_service import process_re_review
from app.schemas import ReReviewResponse, ThreadOpinion

router = APIRouter(tags=["re-reviews"])


def _build_response(rr: ReReview) -> ReReviewResponse:
    opinions = []
    for op in json.loads(rr.thread_opinions_json or "[]"):
        opinions.append(ThreadOpinion(
            github_id=op.get("github_id", 0),
            author=op.get("author"),
            body_preview=op.get("body_preview"),
            path=op.get("path"),
            line=op.get("line"),
            should_resolve=op.get("should_resolve", False),
            reason=op.get("reason"),
        ))
    return ReReviewResponse(
        id=rr.id,
        review_instance_id=rr.review_instance_id,
        status=rr.status,
        old_head_sha=rr.old_head_sha,
        new_head_sha=rr.new_head_sha,
        changes_summary_md=rr.changes_summary_md,
        thread_opinions=opinions,
        error_message=rr.error_message,
        created_at=rr.created_at,
    )


@router.post("/api/reviews/{review_id}/re-review")
def create_re_review(
    review_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    review = db.get(ReviewInstance, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    pr = db.get(PullRequest, review.pull_request_id)
    rr = ReReview(
        review_instance_id=review_id,
        status="PENDING",
        old_head_sha=pr.head_sha if pr else None,
    )
    db.add(rr)
    db.commit()
    db.refresh(rr)

    background_tasks.add_task(process_re_review, rr.id)
    return {"re_review_id": rr.id}


@router.get("/api/re-reviews/{re_review_id}", response_model=ReReviewResponse)
def get_re_review(re_review_id: int, db: Session = Depends(get_db)):
    rr = db.get(ReReview, re_review_id)
    if not rr:
        raise HTTPException(status_code=404, detail="Re-review not found")
    return _build_response(rr)
