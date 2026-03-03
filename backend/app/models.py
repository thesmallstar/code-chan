import json
from datetime import datetime

from sqlalchemy import Boolean, Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint, func
from app.database import Base


class PullRequest(Base):
    __tablename__ = "pull_requests"

    id = Column(Integer, primary_key=True, index=True)
    owner = Column(String, nullable=False)
    repo = Column(String, nullable=False)
    pr_number = Column(Integer, nullable=False)
    title = Column(String)
    body = Column(Text)
    author = Column(String)
    head_sha = Column(String)
    base_sha = Column(String)
    url = Column(String)
    last_synced_at = Column(DateTime)

    __table_args__ = (UniqueConstraint("owner", "repo", "pr_number"),)


class ReviewInstance(Base):
    __tablename__ = "review_instances"

    id = Column(Integer, primary_key=True, index=True)
    pull_request_id = Column(Integer, ForeignKey("pull_requests.id"), nullable=False)
    status = Column(String, default="PENDING")
    summary_md = Column(Text)
    model_provider = Column(String, default="claude")
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class ReviewChunk(Base):
    __tablename__ = "review_chunks"

    id = Column(Integer, primary_key=True, index=True)
    review_instance_id = Column(Integer, ForeignKey("review_instances.id"), nullable=False)
    order_index = Column(Integer, default=0)       # position in the review sequence

    # LLM-planned chunk context
    title = Column(String)
    purpose = Column(Text)         # why these files belong together
    walkthrough = Column(Text)     # how to approach reviewing this chunk
    chunk_summary = Column(Text)   # what actually changed (markdown bullets)
    review_order = Column(Text, default="[]")  # JSON: suggested file reading order

    # Diff data
    file_paths = Column(Text, default="[]")       # JSON: list[str]
    diff_content = Column(Text, default="{}")     # JSON: {path: patch_text}
    line_map = Column(Text, default="{}")         # JSON: {path: [commentable_lines]}

    # AI review output
    status = Column(String, default="PENDING")
    ai_suggestions_md = Column(Text)
    ai_comments_json = Column(Text, default="[]") # JSON: list[{path, line, side, body}]

    # Human review progress
    human_done = Column(Boolean, default=False)

    def get_file_paths(self) -> list:
        return json.loads(self.file_paths or "[]")

    def get_diff_content(self) -> dict:
        return json.loads(self.diff_content or "{}")

    def get_line_map(self) -> dict:
        return json.loads(self.line_map or "{}")

    def get_ai_comments(self) -> list:
        return json.loads(self.ai_comments_json or "[]")

    def get_review_order(self) -> list:
        order = json.loads(self.review_order or "[]")
        return order if order else self.get_file_paths()


class ReviewThread(Base):
    __tablename__ = "review_threads"

    id = Column(Integer, primary_key=True, index=True)
    review_instance_id = Column(Integer, ForeignKey("review_instances.id"), nullable=False)
    github_id = Column(Integer)
    type = Column(String)          # ISSUE_COMMENT | REVIEW_COMMENT
    author = Column(String)
    body = Column(Text)
    path = Column(String, nullable=True)
    line = Column(Integer, nullable=True)
    diff_hunk = Column(Text, nullable=True)
    created_at = Column(DateTime)
    in_reply_to_id = Column(Integer, nullable=True)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    review_chunk_id = Column(Integer, ForeignKey("review_chunks.id"), nullable=False)
    role = Column(String)   # user | assistant
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class DraftComment(Base):
    __tablename__ = "draft_comments"

    id = Column(Integer, primary_key=True, index=True)
    review_chunk_id = Column(Integer, ForeignKey("review_chunks.id"), nullable=False)
    path = Column(String)
    line = Column(Integer)
    side = Column(String, default="RIGHT")
    start_line = Column(Integer, nullable=True)
    start_side = Column(String, nullable=True)
    body_md = Column(Text)
    label = Column(String, nullable=True)      # nit | bug | critical bug | suggestion | question
    status = Column(String, default="DRAFT")   # DRAFT | SENT
    github_comment_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
