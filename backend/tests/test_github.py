"""Tests for the GitHub review-requests cache endpoints."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_github_item(html_url, title, number, repo_full, author, updated_at, labels=None):
    return {
        "html_url": html_url,
        "title": title,
        "number": number,
        "repository_url": f"https://api.github.com/repos/{repo_full}",
        "user": {"login": author},
        "updated_at": updated_at,
        "labels": [{"name": l} for l in (labels or [])],
    }


def _ago(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


ITEM_RECENT = _make_github_item(
    "https://github.com/org/repo/pull/1", "Fix auth", 1, "org/repo", "alice", _ago(3),
)
ITEM_OLD = _make_github_item(
    "https://github.com/org/repo/pull/2", "Add tests", 2, "org/repo", "bob", _ago(20),
    labels=["nit"],
)
MOCK_ITEMS = [ITEM_RECENT, ITEM_OLD]

PATCH_TOKEN = "app.routers.github.get_github_token"
PATCH_GH = "app.routers.github.GitHubClient"


# ── GET /api/github/review-requests (empty cache) ────────────────────────────

def test_get_review_requests_empty(client):
    resp = client.get("/api/github/review-requests")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["last_synced_at"] is None


# ── POST /api/github/review-requests/sync — no token ─────────────────────────

def test_sync_no_token(client):
    with patch(PATCH_TOKEN, return_value=None):
        resp = client.post("/api/github/review-requests/sync")
    assert resp.status_code == 400
    assert "token" in resp.json()["detail"].lower()


# ── POST /api/github/review-requests/sync — GitHub error ─────────────────────

def test_sync_github_error(client):
    with patch(PATCH_TOKEN, return_value="tok"), patch(PATCH_GH) as MockGH:
        MockGH.return_value.get_review_requests.side_effect = RuntimeError("rate limited")
        resp = client.post("/api/github/review-requests/sync")
    assert resp.status_code == 500
    assert "rate limited" in resp.json()["detail"]


# ── POST /api/github/review-requests/sync — happy path ───────────────────────

def test_sync_returns_recent_items_by_default(client):
    with patch(PATCH_TOKEN, return_value="tok"), patch(PATCH_GH) as MockGH:
        MockGH.return_value.get_review_requests.return_value = MOCK_ITEMS
        resp = client.post("/api/github/review-requests/sync")

    assert resp.status_code == 200
    body = resp.json()
    assert body["last_synced_at"] is not None
    # default days=14 → item updated 20d ago excluded
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "Fix auth"
    assert body["items"][0]["author"] == "alice"


def test_sync_days_zero_returns_all(client):
    with patch(PATCH_TOKEN, return_value="tok"), patch(PATCH_GH) as MockGH:
        MockGH.return_value.get_review_requests.return_value = MOCK_ITEMS
        resp = client.post("/api/github/review-requests/sync?days=0")

    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 2


def test_sync_stores_labels(client):
    with patch(PATCH_TOKEN, return_value="tok"), patch(PATCH_GH) as MockGH:
        MockGH.return_value.get_review_requests.return_value = MOCK_ITEMS
        client.post("/api/github/review-requests/sync?days=0")

    resp = client.get("/api/github/review-requests?days=0")
    items_by_number = {i["pr_number"]: i for i in resp.json()["items"]}
    assert items_by_number[2]["labels"] == ["nit"]
    assert items_by_number[1]["labels"] == []


def test_get_returns_cached_after_sync(client):
    with patch(PATCH_TOKEN, return_value="tok"), patch(PATCH_GH) as MockGH:
        MockGH.return_value.get_review_requests.return_value = MOCK_ITEMS
        client.post("/api/github/review-requests/sync?days=0")

    resp = client.get("/api/github/review-requests?days=0")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 2


def test_sync_replaces_stale_data(client):
    with patch(PATCH_TOKEN, return_value="tok"), patch(PATCH_GH) as MockGH:
        MockGH.return_value.get_review_requests.return_value = MOCK_ITEMS
        client.post("/api/github/review-requests/sync?days=0")

    new_items = [_make_github_item(
        "https://github.com/org/repo/pull/99", "Brand new PR", 99, "org/repo", "carol",
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )]
    with patch(PATCH_TOKEN, return_value="tok"), patch(PATCH_GH) as MockGH:
        MockGH.return_value.get_review_requests.return_value = new_items
        resp = client.post("/api/github/review-requests/sync?days=0")

    assert len(resp.json()["items"]) == 1
    assert resp.json()["items"][0]["pr_number"] == 99


def test_sync_sets_last_synced_at(client):
    with patch(PATCH_TOKEN, return_value="tok"), patch(PATCH_GH) as MockGH:
        MockGH.return_value.get_review_requests.return_value = [ITEM_RECENT]
        resp = client.post("/api/github/review-requests/sync?days=0")

    assert resp.json()["last_synced_at"] is not None


# ── _parse_github_datetime helper ────────────────────────────────────────────

def test_parse_github_datetime_valid():
    from app.routers.github import _parse_github_datetime
    dt = _parse_github_datetime("2024-06-15T10:30:00Z")
    assert dt == datetime(2024, 6, 15, 10, 30, 0)


def test_parse_github_datetime_none():
    from app.routers.github import _parse_github_datetime
    assert _parse_github_datetime(None) is None


def test_parse_github_datetime_invalid():
    from app.routers.github import _parse_github_datetime
    assert _parse_github_datetime("not-a-date") is None
