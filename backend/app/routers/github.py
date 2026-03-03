import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.github.client import GitHubClient, get_github_token
from app.models import ReviewRequestCache
from app.schemas import GitHubVerifyResponse, ReviewRequestItem, ReviewRequestsResponse

router = APIRouter(prefix="/api/github", tags=["github"])


def _parse_github_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _cache_row_to_item(row: ReviewRequestCache) -> ReviewRequestItem:
    return ReviewRequestItem(
        pr_url=row.pr_url,
        title=row.title or "",
        repo_full_name=row.repo_full_name or "",
        pr_number=row.pr_number or 0,
        author=row.author or "",
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
        labels=row.get_labels(),
    )


def _query_cached_items(days: int, db: Session) -> ReviewRequestsResponse:
    q = db.query(ReviewRequestCache)
    if days > 0:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
        q = q.filter(ReviewRequestCache.updated_at >= cutoff)
    rows = q.order_by(ReviewRequestCache.updated_at.desc()).all()
    last_synced = db.query(func.max(ReviewRequestCache.last_synced_at)).scalar()
    return ReviewRequestsResponse(
        items=[_cache_row_to_item(r) for r in rows],
        last_synced_at=last_synced,
    )


@router.get("/review-requests", response_model=ReviewRequestsResponse)
def get_review_requests(days: int = Query(default=14, ge=0), db: Session = Depends(get_db)):
    return _query_cached_items(days, db)


@router.post("/review-requests/sync", response_model=ReviewRequestsResponse)
def sync_review_requests(days: int = Query(default=14, ge=0), db: Session = Depends(get_db)):
    token = get_github_token()
    if not token:
        raise HTTPException(status_code=400, detail="GitHub token not available")
    gh = GitHubClient(token)
    try:
        raw_items = gh.get_review_requests(days=0)  # fetch all, filter in DB
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    now = datetime.utcnow()
    db.query(ReviewRequestCache).delete()
    for item in raw_items:
        repo_full = item.get("repository_url", "").split("repos/")[-1]
        db.add(ReviewRequestCache(
            pr_url=item.get("html_url", ""),
            title=item.get("title", ""),
            repo_full_name=repo_full,
            pr_number=item.get("number"),
            author=item.get("user", {}).get("login", ""),
            updated_at=_parse_github_datetime(item.get("updated_at")),
            labels_json=json.dumps([l.get("name", "") for l in item.get("labels", [])]),
            last_synced_at=now,
        ))
    db.commit()
    return _query_cached_items(days, db)


@router.post("/verify", response_model=GitHubVerifyResponse)
def verify_github():
    token = get_github_token()
    if not token:
        return GitHubVerifyResponse(
            ok=False,
            error="GitHub token not found. Set GITHUB_TOKEN env var or run `gh auth login`.",
        )
    try:
        gh = GitHubClient(token)
        info = gh.verify()
        method = "env" if __import__("os").getenv("GITHUB_TOKEN") or __import__("os").getenv("GH_TOKEN") else "gh"
        return GitHubVerifyResponse(ok=True, username=info["username"], method=method)
    except Exception as e:
        return GitHubVerifyResponse(ok=False, error=str(e))
