"""Tests for the AI provider registry and /api/providers endpoint."""

import pytest

from app.ai.base import AIProvider, ProviderRegistry


class TestProviderRegistry:
    def test_claude_is_registered(self):
        names = [p["name"] for p in ProviderRegistry.available()]
        assert "claude" in names

    def test_codex_is_registered(self):
        names = [p["name"] for p in ProviderRegistry.available()]
        assert "codex" in names

    def test_available_returns_labels(self):
        providers = ProviderRegistry.available()
        by_name = {p["name"]: p for p in providers}
        assert by_name["claude"]["label"] == "Claude Code"
        assert by_name["codex"]["label"] == "Codex"

    def test_create_claude_returns_ai_provider(self):
        provider = ProviderRegistry.create("claude")
        assert isinstance(provider, AIProvider)

    def test_create_codex_returns_ai_provider(self):
        provider = ProviderRegistry.create("codex")
        assert isinstance(provider, AIProvider)

    def test_create_unknown_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            ProviderRegistry.create("nonexistent")


class TestProvidersEndpoint:
    def test_list_returns_both_providers(self, client):
        resp = client.get("/api/providers")
        assert resp.status_code == 200
        data = resp.json()
        names = [p["name"] for p in data]
        assert "claude" in names
        assert "codex" in names

    def test_list_includes_labels(self, client):
        resp = client.get("/api/providers")
        data = resp.json()
        by_name = {p["name"]: p for p in data}
        assert by_name["claude"]["label"] == "Claude Code"
        assert by_name["codex"]["label"] == "Codex"


class TestReviewCreatedWithProvider:
    def test_review_stores_model_provider(self, client, db):
        from unittest.mock import patch
        from app.models import ReviewInstance

        with patch("app.routers.reviews.process_review"):
            resp = client.post("/api/reviews", json={
                "pr_url": "https://github.com/owner/repo/pull/1",
                "model_provider": "codex",
            })
        assert resp.status_code == 201
        review_id = resp.json()["review_id"]
        review = db.get(ReviewInstance, review_id)
        assert review.model_provider == "codex"

    def test_review_response_includes_model_provider(self, client, pr_and_review):
        _, review = pr_and_review
        review.model_provider = "codex"

        resp = client.get(f"/api/reviews/{review.id}")
        assert resp.status_code == 200
        assert resp.json()["model_provider"] == "codex"
