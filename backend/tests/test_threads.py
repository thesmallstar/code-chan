"""Unit tests for thread endpoints — resolve toggle."""

import pytest
from app.models import ReviewThread


@pytest.fixture()
def thread(db, pr_and_review):
    _, review = pr_and_review
    t = ReviewThread(
        review_instance_id=review.id,
        github_id=111,
        type="REVIEW_COMMENT",
        body="Please add a test here.",
        author="alice",
        path="auth.py",
        line=42,
        is_resolved=False,
    )
    db.add(t)
    db.flush()
    return t


class TestResolveThread:
    def test_resolve_marks_as_resolved(self, client, thread):
        resp = client.patch(f"/api/threads/{thread.id}/resolve")
        assert resp.status_code == 200
        assert resp.json() == {"is_resolved": True}

    def test_resolve_twice_toggles_back(self, client, thread):
        client.patch(f"/api/threads/{thread.id}/resolve")
        resp = client.patch(f"/api/threads/{thread.id}/resolve")
        assert resp.status_code == 200
        assert resp.json() == {"is_resolved": False}

    def test_resolve_not_found_returns_404(self, client):
        resp = client.patch("/api/threads/999999/resolve")
        assert resp.status_code == 404
