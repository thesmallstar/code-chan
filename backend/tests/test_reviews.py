"""Unit tests for review endpoints — submit review and human_done in chunk summaries."""

import pytest
from unittest.mock import patch


class TestSubmitReview:
    def test_approve_succeeds(self, client, pr_and_review):
        _, review = pr_and_review
        mock_result = {"id": 1, "state": "APPROVED", "html_url": "https://github.com/..."}
        with patch("app.github.client.get_github_token", return_value="tok"), \
             patch("app.github.client.GitHubClient") as MockGH:
            MockGH.return_value.submit_pull_request_review.return_value = mock_result
            resp = client.post(f"/api/reviews/{review.id}/submit", json={
                "event": "APPROVE",
                "body": "",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["github_review_id"] == 1
        assert data["state"] == "APPROVED"

    def test_comment_event_succeeds(self, client, pr_and_review):
        _, review = pr_and_review
        mock_result = {"id": 2, "state": "COMMENTED", "html_url": "https://github.com/..."}
        with patch("app.github.client.get_github_token", return_value="tok"), \
             patch("app.github.client.GitHubClient") as MockGH:
            MockGH.return_value.submit_pull_request_review.return_value = mock_result
            resp = client.post(f"/api/reviews/{review.id}/submit", json={
                "event": "COMMENT",
                "body": "Overall LGTM",
            })
        assert resp.status_code == 200

    def test_request_changes_requires_body(self, client, pr_and_review):
        _, review = pr_and_review
        resp = client.post(f"/api/reviews/{review.id}/submit", json={
            "event": "REQUEST_CHANGES",
            "body": "",
        })
        assert resp.status_code == 422

    def test_request_changes_with_body_succeeds(self, client, pr_and_review):
        _, review = pr_and_review
        mock_result = {"id": 3, "state": "CHANGES_REQUESTED", "html_url": "https://github.com/..."}
        with patch("app.github.client.get_github_token", return_value="tok"), \
             patch("app.github.client.GitHubClient") as MockGH:
            MockGH.return_value.submit_pull_request_review.return_value = mock_result
            resp = client.post(f"/api/reviews/{review.id}/submit", json={
                "event": "REQUEST_CHANGES",
                "body": "Please fix the null check.",
            })
        assert resp.status_code == 200

    def test_invalid_event_returns_422(self, client, pr_and_review):
        _, review = pr_and_review
        resp = client.post(f"/api/reviews/{review.id}/submit", json={
            "event": "MERGE",
            "body": "",
        })
        assert resp.status_code == 422

    def test_review_not_found_returns_404(self, client):
        resp = client.post("/api/reviews/999999/submit", json={"event": "APPROVE", "body": ""})
        assert resp.status_code == 404

    def test_missing_head_sha_returns_400(self, client, db):
        from app.models import PullRequest, ReviewInstance

        pr = PullRequest(owner="x", repo="y", pr_number=99, head_sha=None)
        db.add(pr)
        db.flush()
        review = ReviewInstance(pull_request_id=pr.id, status="READY")
        db.add(review)
        db.flush()

        resp = client.post(f"/api/reviews/{review.id}/submit", json={"event": "APPROVE", "body": ""})
        assert resp.status_code == 400
        assert "head SHA" in resp.json()["detail"]

    def test_no_github_token_returns_400(self, client, pr_and_review):
        _, review = pr_and_review
        with patch("app.github.client.get_github_token", return_value=None):
            resp = client.post(f"/api/reviews/{review.id}/submit", json={"event": "APPROVE", "body": ""})
        assert resp.status_code == 400
        assert "token" in resp.json()["detail"].lower()


class TestChunkHumanDoneInReview:
    def test_review_response_includes_human_done(self, client, pr_and_review, chunk):
        _, review = pr_and_review
        resp = client.get(f"/api/reviews/{review.id}")
        assert resp.status_code == 200
        chunks = resp.json()["chunks"]
        assert len(chunks) >= 1
        assert "human_done" in chunks[0]
        assert chunks[0]["human_done"] is False

    def test_human_done_reflected_in_review_after_toggle(self, client, pr_and_review, chunk):
        _, review = pr_and_review
        client.patch(f"/api/chunks/{chunk.id}/done")

        resp = client.get(f"/api/reviews/{review.id}")
        chunks = resp.json()["chunks"]
        done_chunk = next(c for c in chunks if c["id"] == chunk.id)
        assert done_chunk["human_done"] is True
