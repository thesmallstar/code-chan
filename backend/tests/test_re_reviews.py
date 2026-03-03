"""Unit tests for re-review endpoints and related side-effects."""

import json
from unittest.mock import patch

import pytest

from app.models import ReReview, ReviewRequestCache


class TestCreateReReview:
    def test_returns_re_review_id(self, client, pr_and_review):
        _, review = pr_and_review
        with patch("app.routers.re_reviews.process_re_review"):
            resp = client.post(f"/api/reviews/{review.id}/re-review")
        assert resp.status_code == 200
        assert "re_review_id" in resp.json()

    def test_creates_pending_record_with_old_sha(self, client, db, pr_and_review):
        pr, review = pr_and_review
        with patch("app.routers.re_reviews.process_re_review"):
            resp = client.post(f"/api/reviews/{review.id}/re-review")
        rr = db.get(ReReview, resp.json()["re_review_id"])
        assert rr.status == "PENDING"
        assert rr.old_head_sha == pr.head_sha

    def test_review_not_found_returns_404(self, client):
        resp = client.post("/api/reviews/999999/re-review")
        assert resp.status_code == 404


class TestGetReReview:
    def test_returns_pending_status(self, client, db, pr_and_review):
        _, review = pr_and_review
        rr = ReReview(review_instance_id=review.id, status="PENDING")
        db.add(rr)
        db.flush()

        resp = client.get(f"/api/re-reviews/{rr.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "PENDING"
        assert data["thread_opinions"] == []

    def test_returns_done_with_opinions(self, client, db, pr_and_review):
        _, review = pr_and_review
        opinions = [
            {"github_id": 1, "should_resolve": True, "reason": "addressed", "path": "foo.py", "line": 5},
            {"github_id": 2, "should_resolve": False, "reason": "still open"},
        ]
        rr = ReReview(
            review_instance_id=review.id,
            status="DONE",
            changes_summary_md="## Summary\n\nFixed the bug.",
            thread_opinions_json=json.dumps(opinions),
        )
        db.add(rr)
        db.flush()

        resp = client.get(f"/api/re-reviews/{rr.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "DONE"
        assert data["changes_summary_md"] == "## Summary\n\nFixed the bug."
        assert len(data["thread_opinions"]) == 2
        assert data["thread_opinions"][0]["should_resolve"] is True
        assert data["thread_opinions"][0]["path"] == "foo.py"
        assert data["thread_opinions"][1]["reason"] == "still open"

    def test_not_found_returns_404(self, client):
        resp = client.get("/api/re-reviews/999999")
        assert resp.status_code == 404


class TestCacheDeletedOnReviewCreate:
    def test_review_create_removes_matching_cache_entry(self, client, db):
        pr_url = "https://github.com/org/repo/pull/5"
        cache = ReviewRequestCache(pr_url=pr_url, pr_number=5, repo_full_name="org/repo",
                                   title="Some PR", author="dev", labels_json="[]")
        db.add(cache)
        db.flush()

        with patch("app.routers.reviews.process_review"):
            resp = client.post("/api/reviews", json={"pr_url": pr_url, "model_provider": "claude"})
        assert resp.status_code == 201

        remaining = db.query(ReviewRequestCache).filter_by(pr_url=pr_url).all()
        assert remaining == []

    def test_review_create_leaves_other_cache_entries(self, client, db):
        pr_url = "https://github.com/org/repo/pull/6"
        other_url = "https://github.com/org/repo/pull/7"
        db.add(ReviewRequestCache(pr_url=pr_url, pr_number=6, repo_full_name="org/repo",
                                  title="PR 6", author="dev", labels_json="[]"))
        db.add(ReviewRequestCache(pr_url=other_url, pr_number=7, repo_full_name="org/repo",
                                  title="PR 7", author="dev", labels_json="[]"))
        db.flush()

        with patch("app.routers.reviews.process_review"):
            client.post("/api/reviews", json={"pr_url": pr_url, "model_provider": "claude"})

        remaining = db.query(ReviewRequestCache).filter_by(pr_url=other_url).all()
        assert len(remaining) == 1


class TestExistingReviewInRequests:
    def test_review_requests_include_existing_review_id(self, client, db):
        from app.models import PullRequest, ReviewInstance

        pr_url = "https://github.com/org/myrepo/pull/77"
        pr = PullRequest(owner="org", repo="myrepo", pr_number=77, head_sha="deadbeef", url=pr_url)
        db.add(pr)
        db.flush()

        review = ReviewInstance(pull_request_id=pr.id, status="READY")
        db.add(review)
        db.flush()

        db.add(ReviewRequestCache(pr_url=pr_url, pr_number=77, repo_full_name="org/myrepo",
                                  title="My PR", author="alice", labels_json="[]"))
        db.flush()

        resp = client.get("/api/github/review-requests?days=0")
        assert resp.status_code == 200
        items = resp.json()["items"]
        match = next((i for i in items if i["pr_number"] == 77), None)
        assert match is not None
        assert match["existing_review_id"] == review.id

    def test_review_requests_without_existing_review_have_null_id(self, client, db):
        db.add(ReviewRequestCache(
            pr_url="https://github.com/org/newrepo/pull/1",
            pr_number=1, repo_full_name="org/newrepo",
            title="Brand new PR", author="bob", labels_json="[]",
        ))
        db.flush()

        resp = client.get("/api/github/review-requests?days=0")
        assert resp.status_code == 200
        items = resp.json()["items"]
        match = next((i for i in items if i["pr_number"] == 1 and i["repo_full_name"] == "org/newrepo"), None)
        assert match is not None
        assert match["existing_review_id"] is None
