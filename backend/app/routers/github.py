from fastapi import APIRouter

from app.github.client import GitHubClient, get_github_token
from app.schemas import GitHubVerifyResponse

router = APIRouter(prefix="/api/github", tags=["github"])


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
