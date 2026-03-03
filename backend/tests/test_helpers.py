"""Unit tests for pure helper functions."""

import pytest
from app.routers.chunks import _body_with_label


class TestBodyWithLabel:
    def test_no_label_returns_body_unchanged(self):
        assert _body_with_label("looks good", None) == "looks good"

    def test_label_is_prepended(self):
        result = _body_with_label("fix this", "bug")
        assert result == "**[bug]** fix this"

    def test_critical_bug_label(self):
        result = _body_with_label("null pointer risk", "critical bug")
        assert result == "**[critical bug]** null pointer risk"

    def test_nit_label(self):
        assert _body_with_label("rename this var", "nit") == "**[nit]** rename this var"

    def test_empty_label_string_treated_as_falsy(self):
        assert _body_with_label("some comment", "") == "some comment"

    def test_body_content_preserved(self):
        body = "This is a **markdown** comment with `code` blocks."
        result = _body_with_label(body, "suggestion")
        assert result.endswith(body)
        assert result.startswith("**[suggestion]**")
