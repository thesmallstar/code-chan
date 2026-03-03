"""Shared fixtures for all unit tests."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def engine():
    _engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=_engine)
    yield _engine
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture()
def db(engine):
    """Provide a transactional session that rolls back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db):
    """FastAPI TestClient with the test DB injected."""
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture()
def pr_and_review(db):
    """Seed a PullRequest + ReviewInstance and return both."""
    from app.models import PullRequest, ReviewInstance

    pr = PullRequest(
        owner="test-owner",
        repo="test-repo",
        pr_number=42,
        title="Test PR",
        head_sha="abc123",
        url="https://github.com/test-owner/test-repo/pull/42",
    )
    db.add(pr)
    db.flush()

    review = ReviewInstance(pull_request_id=pr.id, status="READY")
    db.add(review)
    db.flush()

    return pr, review


@pytest.fixture()
def chunk(db, pr_and_review):
    """Seed a ReviewChunk attached to the review."""
    import json
    from app.models import ReviewChunk

    _, review = pr_and_review
    c = ReviewChunk(
        review_instance_id=review.id,
        order_index=0,
        title="Auth layer",
        purpose="Sets up authentication",
        status="AI_DONE",
        file_paths=json.dumps(["auth.py"]),
        diff_content=json.dumps({"auth.py": "@@ -1 +1 @@\n+import jwt"}),
        line_map=json.dumps({"auth.py": [1]}),
    )
    db.add(c)
    db.flush()
    return c


@pytest.fixture()
def draft(db, chunk):
    """Seed a DraftComment on the chunk."""
    from app.models import DraftComment

    d = DraftComment(
        review_chunk_id=chunk.id,
        path="auth.py",
        line=1,
        side="RIGHT",
        body_md="This looks suspicious.",
        status="DRAFT",
    )
    db.add(d)
    db.flush()
    return d
