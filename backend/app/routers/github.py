from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.github.client import GitHubClient, get_github_token
from app.schemas import GitHubVerifyResponse, ReviewRequestItem

router = APIRouter(prefix="/api/github", tags=["github"])


@router.get("/review-requests", response_model=list[ReviewRequestItem])
def get_review_requests(days: int = Query(default=14, ge=0)):
    token = get_github_token()
    if not token:
        return JSONResponse(status_code=400, content={"detail": "GitHub token not available"})
    gh = GitHubClient(token)
    try:
        items = gh.get_review_requests(days=days)
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})

    results = []
    for item in items:
        repo_full = item.get("repository_url", "").split("repos/")[-1]
        pr_number = item.get("number")
        results.append(ReviewRequestItem(
            pr_url=item.get("html_url", ""),
            title=item.get("title", ""),
            repo_full_name=repo_full,
            pr_number=pr_number,
            author=item.get("user", {}).get("login", ""),
            updated_at=item.get("updated_at"),
            labels=[l.get("name", "") for l in item.get("labels", [])],
        ))
    return results


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
