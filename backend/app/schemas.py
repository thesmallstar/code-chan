from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# ── GitHub ──────────────────────────────────────────────────────────────────

class GitHubVerifyResponse(BaseModel):
    ok: bool
    username: Optional[str] = None
    method: Optional[str] = None   # "env" | "gh"
    error: Optional[str] = None


# ── Pull Request ─────────────────────────────────────────────────────────────

class PullRequestInfo(BaseModel):
    id: int
    owner: str
    repo: str
    pr_number: int
    title: Optional[str] = None
    body: Optional[str] = None
    author: Optional[str] = None
    head_sha: Optional[str] = None
    url: Optional[str] = None
    last_synced_at: Optional[datetime] = None
    pr_state: Optional[str] = None          # open | closed | merged
    review_decision: Optional[str] = None   # APPROVED | CHANGES_REQUESTED | REVIEW_REQUIRED

    class Config:
        from_attributes = True


# ── Review Instance ──────────────────────────────────────────────────────────

class ReviewCreate(BaseModel):
    pr_url: str
    model_provider: str = "claude"   # "codex" | "claude"


class ReviewChunkSummary(BaseModel):
    id: int
    order_index: int = 0
    title: Optional[str] = None
    purpose: Optional[str] = None
    chunk_summary: Optional[str] = None
    file_paths: list[str] = []
    status: str
    human_done: bool = False

    class Config:
        from_attributes = True


class ReviewInstanceResponse(BaseModel):
    id: int
    status: str
    model_provider: Optional[str] = None
    summary_md: Optional[str] = None
    pull_request: Optional[PullRequestInfo] = None
    chunks: list[ReviewChunkSummary] = []
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Chunks ───────────────────────────────────────────────────────────────────

class ReviewChunkDetail(BaseModel):
    id: int
    order_index: int = 0
    title: Optional[str] = None
    purpose: Optional[str] = None
    walkthrough: Optional[str] = None
    chunk_summary: Optional[str] = None
    review_order: list[str] = []
    file_paths: list[str] = []
    diff_content: dict = {}
    line_map: dict = {}
    status: str
    ai_suggestions_md: Optional[str] = None
    ai_comments: list[dict] = []
    human_done: bool = False

    class Config:
        from_attributes = True


# ── Chat ─────────────────────────────────────────────────────────────────────

class ChatMessageCreate(BaseModel):
    message: str


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Threads ──────────────────────────────────────────────────────────────────

class ReviewThreadResponse(BaseModel):
    id: int
    github_id: Optional[int] = None
    type: Optional[str] = None
    author: Optional[str] = None
    body: Optional[str] = None
    path: Optional[str] = None
    line: Optional[int] = None
    position: Optional[int] = None
    diff_hunk: Optional[str] = None
    created_at: Optional[datetime] = None
    in_reply_to_id: Optional[int] = None
    is_resolved: bool = False

    class Config:
        from_attributes = True


class ThreadReplyCreate(BaseModel):
    body_md: str


class ThreadDiscussCreate(BaseModel):
    message: str
    history: list[dict] = []   # [{role: "user"|"assistant", content: str}]


class ThreadDiscussResponse(BaseModel):
    reply: str


# ── Draft Comments ────────────────────────────────────────────────────────────

class DraftCommentCreate(BaseModel):
    path: str
    line: int
    side: str = "RIGHT"
    start_line: Optional[int] = None
    start_side: Optional[str] = None
    body_md: str
    label: Optional[str] = None


class DraftCommentUpdate(BaseModel):
    body_md: Optional[str] = None
    path: Optional[str] = None
    line: Optional[int] = None
    label: Optional[str] = None


class DraftCommentResponse(BaseModel):
    id: int
    path: Optional[str] = None
    line: Optional[int] = None
    side: Optional[str] = None
    start_line: Optional[int] = None
    start_side: Optional[str] = None
    body_md: Optional[str] = None
    label: Optional[str] = None
    status: str
    github_comment_id: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── PR Review Submission ───────────────────────────────────────────────────────

class SubmitReviewRequest(BaseModel):
    event: str   # APPROVE | REQUEST_CHANGES | COMMENT
    body: str = ""


class SubmitReviewResponse(BaseModel):
    github_review_id: int
    state: str
    html_url: Optional[str] = None


# ── Review Requests ───────────────────────────────────────────────────────────

class ReviewRequestItem(BaseModel):
    pr_url: str
    title: str
    repo_full_name: str
    pr_number: int
    author: str
    updated_at: Optional[str] = None
    labels: list[str] = []
    existing_review_id: Optional[int] = None
    existing_review_status: Optional[str] = None
    last_reviewed_at: Optional[str] = None


class ReviewRequestsResponse(BaseModel):
    items: list[ReviewRequestItem]
    last_synced_at: Optional[datetime] = None


# ── Re-Review ─────────────────────────────────────────────────────────────────

class ThreadOpinion(BaseModel):
    github_id: int
    author: Optional[str] = None
    body_preview: Optional[str] = None
    path: Optional[str] = None
    line: Optional[int] = None
    should_resolve: bool
    reason: Optional[str] = None


class ReReviewResponse(BaseModel):
    id: int
    review_instance_id: int
    status: str
    old_head_sha: Optional[str] = None
    new_head_sha: Optional[str] = None
    changes_summary_md: Optional[str] = None
    thread_opinions: list[ThreadOpinion] = []
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
