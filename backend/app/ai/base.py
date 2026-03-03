"""Abstract base class for AI review providers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class AIProvider(ABC):
    @abstractmethod
    def plan_chunks(
        self,
        pr_data: dict,
        files: list[dict],
        repo_path: Optional[Path] = None,
    ) -> list[dict]:
        """
        Decide how to group changed files into logical review chunks.
        Returns a list of chunk plans ordered for progressive review:
        [
            {
                "title": str,
                "purpose": str,       # why these files belong together
                "walkthrough": str,   # how to approach reviewing this chunk
                "summary": str,       # markdown bullets: what changed
                "files": [str],       # file paths in this chunk
                "review_order": [str] # suggested reading order within chunk
            }
        ]
        """

    @abstractmethod
    def summarize_pr(
        self,
        pr_data: dict,
        files: list[dict],
        repo_path: Optional[Path] = None,
    ) -> str:
        """
        Generate a markdown summary of what this PR does.
        If repo_path is provided, the AI can read local files for full context.
        Returns markdown string.
        """

    @abstractmethod
    def review_chunk(
        self,
        chunk_title: str,
        file_diffs: dict[str, str],
        line_map: dict,
        repo_path: Optional[Path] = None,
    ) -> dict:
        """
        Review a code chunk and return structured suggestions.
        If repo_path is provided, the AI runs from that directory and can read files.

        Returns:
            {
                "assessment": str (markdown),
                "comments": [
                    {
                        "path": str,
                        "line": int,
                        "side": "RIGHT",
                        "body": str,
                        "anchored": bool
                    }
                ]
            }
        """

    @abstractmethod
    def chat(
        self,
        chunk_context: str,
        messages: list[dict],
        repo_path: Optional[Path] = None,
    ) -> str:
        """
        Continue a review chat for a given chunk context.
        `messages` is a list of {"role": "user"|"assistant", "content": str}.
        Returns the assistant's reply as a string.
        """

    @abstractmethod
    def re_review(
        self,
        pr_data: dict,
        diff_files: list[dict],
        root_threads: list[dict],
        issue_comments: list[dict],
    ) -> dict:
        """
        Analyse what changed since the last review and evaluate open threads.
        Returns:
            {
                "changes_summary": str (markdown),
                "thread_opinions": [
                    {"github_id": int, "should_resolve": bool, "reason": str}
                ]
            }
        """
