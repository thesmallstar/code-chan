import os
import subprocess
from typing import Optional

import httpx


def get_github_token() -> Optional[str]:
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if token:
        return token
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


class GitHubClient:
    BASE_URL = "https://api.github.com"

    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _get(self, path: str, params: dict = None) -> dict | list:
        url = f"{self.BASE_URL}{path}"
        with httpx.Client(timeout=30) as client:
            resp = client.get(url, headers=self.headers, params=params or {})
            resp.raise_for_status()
            return resp.json()

    def _post(self, path: str, body: dict) -> dict:
        url = f"{self.BASE_URL}{path}"
        with httpx.Client(timeout=30) as client:
            resp = client.post(url, headers=self.headers, json=body)
            resp.raise_for_status()
            return resp.json()

    def verify(self) -> dict:
        user = self._get("/user")
        return {"ok": True, "username": user["login"]}

    def get_pull_request(self, owner: str, repo: str, pr_number: int) -> dict:
        return self._get(f"/repos/{owner}/{repo}/pulls/{pr_number}")

    def get_pull_request_files(self, owner: str, repo: str, pr_number: int) -> list:
        files = []
        page = 1
        while True:
            page_data = self._get(
                f"/repos/{owner}/{repo}/pulls/{pr_number}/files",
                params={"per_page": 100, "page": page},
            )
            if not page_data:
                break
            files.extend(page_data)
            if len(page_data) < 100:
                break
            page += 1
        return files

    def get_review_comments(self, owner: str, repo: str, pr_number: int) -> list:
        comments = []
        page = 1
        while True:
            page_data = self._get(
                f"/repos/{owner}/{repo}/pulls/{pr_number}/comments",
                params={"per_page": 100, "page": page},
            )
            if not page_data:
                break
            comments.extend(page_data)
            if len(page_data) < 100:
                break
            page += 1
        return comments

    def get_issue_comments(self, owner: str, repo: str, pr_number: int) -> list:
        comments = []
        page = 1
        while True:
            page_data = self._get(
                f"/repos/{owner}/{repo}/issues/{pr_number}/comments",
                params={"per_page": 100, "page": page},
            )
            if not page_data:
                break
            comments.extend(page_data)
            if len(page_data) < 100:
                break
            page += 1
        return comments

    def create_review_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        commit_id: str,
        path: str,
        line: int,
        body: str,
        side: str = "RIGHT",
        start_line: int = None,
        start_side: str = None,
    ) -> dict:
        payload: dict = {
            "body": body,
            "commit_id": commit_id,
            "path": path,
            "line": line,
            "side": side,
        }
        if start_line is not None:
            payload["start_line"] = start_line
            payload["start_side"] = start_side or side
        return self._post(f"/repos/{owner}/{repo}/pulls/{pr_number}/comments", payload)

    def reply_to_review_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        comment_id: int,
        body: str,
    ) -> dict:
        return self._post(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/comments/{comment_id}/replies",
            {"body": body},
        )

    def create_issue_comment(self, owner: str, repo: str, issue_number: int, body: str) -> dict:
        return self._post(
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            {"body": body},
        )

    def get_pull_request_review_decision(self, owner: str, repo: str, pr_number: int) -> str:
        """Return APPROVED, CHANGES_REQUESTED, or REVIEW_REQUIRED based on latest reviews."""
        reviews = self._get(f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews")
        # Keep only the most recent review state per reviewer
        latest: dict[str, str] = {}
        for r in reviews:
            login = r.get("user", {}).get("login", "")
            state = r.get("state", "")
            if state not in ("DISMISSED", "PENDING"):
                latest[login] = state
        states = set(latest.values())
        if "CHANGES_REQUESTED" in states:
            return "CHANGES_REQUESTED"
        if states == {"APPROVED"} or ("APPROVED" in states and "CHANGES_REQUESTED" not in states):
            return "APPROVED"
        return "REVIEW_REQUIRED"

    def submit_pull_request_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        commit_id: str,
        event: str,
        body: str = "",
    ) -> dict:
        return self._post(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
            {"commit_id": commit_id, "event": event, "body": body},
        )
