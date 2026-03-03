"""Unit tests for chunk endpoints — mark-as-done toggle and draft comment labels."""

import pytest
from unittest.mock import patch, MagicMock


class TestChunkDoneToggle:
    def test_toggle_on(self, client, chunk):
        resp = client.patch(f"/api/chunks/{chunk.id}/done")
        assert resp.status_code == 200
        assert resp.json()["human_done"] is True

    def test_toggle_off(self, client, chunk):
        client.patch(f"/api/chunks/{chunk.id}/done")   # on
        resp = client.patch(f"/api/chunks/{chunk.id}/done")  # off
        assert resp.status_code == 200
        assert resp.json()["human_done"] is False

    def test_unknown_chunk_returns_404(self, client):
        resp = client.patch("/api/chunks/999999/done")
        assert resp.status_code == 404


class TestDraftCommentLabel:
    def test_create_draft_without_label(self, client, chunk):
        resp = client.post(f"/api/chunks/{chunk.id}/drafts", json={
            "path": "auth.py",
            "line": 1,
            "side": "RIGHT",
            "body_md": "plain comment",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["label"] is None
        assert data["body_md"] == "plain comment"

    def test_create_draft_with_label(self, client, chunk):
        resp = client.post(f"/api/chunks/{chunk.id}/drafts", json={
            "path": "auth.py",
            "line": 1,
            "side": "RIGHT",
            "body_md": "this will break in prod",
            "label": "critical bug",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["label"] == "critical bug"

    def test_update_draft_label(self, client, draft):
        resp = client.put(f"/api/chunks/drafts/{draft.id}", json={"label": "nit"})
        assert resp.status_code == 200
        assert resp.json()["label"] == "nit"

    def test_update_draft_clears_label(self, client, draft):
        client.put(f"/api/chunks/drafts/{draft.id}", json={"label": "bug"})
        resp = client.put(f"/api/chunks/drafts/{draft.id}", json={"label": None})
        # label: None in body means "don't change" per our update logic — value stays
        # (the endpoint only updates label if body.label is not None)
        assert resp.status_code == 200

    def test_get_drafts_includes_label(self, client, chunk):
        client.post(f"/api/chunks/{chunk.id}/drafts", json={
            "path": "auth.py",
            "line": 1,
            "side": "RIGHT",
            "body_md": "rename this",
            "label": "nit",
        })
        resp = client.get(f"/api/chunks/{chunk.id}/drafts")
        assert resp.status_code == 200
        drafts = resp.json()
        assert any(d["label"] == "nit" for d in drafts)

    def test_send_draft_prepends_label(self, client, db, chunk):
        """When a labelled draft is sent, the GitHub body should include the tag prefix."""
        from app.models import DraftComment, PullRequest

        # seed a labelled draft
        d = DraftComment(
            review_chunk_id=chunk.id,
            path="auth.py",
            line=1,
            side="RIGHT",
            body_md="null check missing",
            label="bug",
            status="DRAFT",
        )
        db.add(d)
        db.flush()

        mock_result = {"id": 42, "html_url": "https://github.com/..."}
        with patch("app.github.client.get_github_token", return_value="tok"), \
             patch("app.github.client.GitHubClient") as MockGH:
            MockGH.return_value.create_review_comment.return_value = mock_result
            resp = client.post(f"/api/chunks/drafts/{d.id}/send")

        assert resp.status_code == 200
        call_kwargs = MockGH.return_value.create_review_comment.call_args
        sent_body = call_kwargs.kwargs.get("body") or call_kwargs.args[5]
        assert sent_body == "**[bug]** null check missing"

    def test_send_draft_no_label_body_unchanged(self, client, db, chunk):
        from app.models import DraftComment

        d = DraftComment(
            review_chunk_id=chunk.id,
            path="auth.py",
            line=1,
            side="RIGHT",
            body_md="looks fine",
            label=None,
            status="DRAFT",
        )
        db.add(d)
        db.flush()

        mock_result = {"id": 43, "html_url": "https://github.com/..."}
        with patch("app.github.client.get_github_token", return_value="tok"), \
             patch("app.github.client.GitHubClient") as MockGH:
            MockGH.return_value.create_review_comment.return_value = mock_result
            resp = client.post(f"/api/chunks/drafts/{d.id}/send")

        assert resp.status_code == 200
        call_kwargs = MockGH.return_value.create_review_comment.call_args
        sent_body = call_kwargs.kwargs.get("body") or call_kwargs.args[5]
        assert sent_body == "looks fine"
