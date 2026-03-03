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
    diff_hunk: Optional[str] = None
    created_at: Optional[datetime] = None
    in_reply_to_id: Optional[int] = None

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


class DraftCommentUpdate(BaseModel):
    body_md: Optional[str] = None
    path: Optional[str] = None
    line: Optional[int] = None


class DraftCommentResponse(BaseModel):
    id: int
    path: Optional[str] = None
    line: Optional[int] = None
    side: Optional[str] = None
    start_line: Optional[int] = None
    start_side: Optional[str] = None
    body_md: Optional[str] = None
    status: str
    github_comment_id: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
