import base64
import os
from datetime import UTC, datetime
from typing import Any

import httpx
from dotenv import load_dotenv


load_dotenv()


GITHUB_API_BASE = "https://api.github.com"


def _headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _request(
    method: str,
    path: str,
    token: str,
    *,
    json: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{GITHUB_API_BASE}{path}"

    try:
        with httpx.Client(timeout=20) as client:
            response = client.request(
                method,
                url,
                headers=_headers(token),
                json=json,
                params=params,
            )
    except httpx.HTTPError as exc:
        return {
            "ok": False,
            "status_code": None,
            "error": str(exc),
            "url": url,
        }

    try:
        data = response.json() if response.content else None
    except ValueError:
        data = response.text

    if response.status_code >= 400:
        return {
            "ok": False,
            "status_code": response.status_code,
            "error": data,
            "url": url,
        }

    return {
        "ok": True,
        "status_code": response.status_code,
        "data": data,
        "url": url,
    }


def _label_names(labels: list[dict[str, Any]]) -> list[str]:
    return [label.get("name", "") for label in labels if label.get("name")]


def _assignee_login(issue: dict[str, Any]) -> str | None:
    assignee = issue.get("assignee")
    if not assignee:
        return None
    return assignee.get("login")


def list_issues(token: str, repo: str) -> dict[str, Any]:
    response = _request(
        "GET",
        f"/repos/{repo}/issues",
        token,
        params={"state": "open", "per_page": 20},
    )
    if not response["ok"]:
        return response

    issues = []
    for issue in response["data"]:
        issues.append(
            {
                "number": issue.get("number"),
                "title": issue.get("title"),
                "state": issue.get("state"),
                "labels": _label_names(issue.get("labels", [])),
                "assignee": _assignee_login(issue),
                "is_pull_request": "pull_request" in issue,
            }
        )

    return {
        "ok": True,
        "issues": issues,
        "count": len(issues),
    }


def read_issue(token: str, repo: str, number: int) -> dict[str, Any]:
    response = _request("GET", f"/repos/{repo}/issues/{number}", token)
    if not response["ok"]:
        return response

    issue = response["data"]
    return {
        "ok": True,
        "issue": {
            "number": issue.get("number"),
            "title": issue.get("title"),
            "body": issue.get("body"),
            "state": issue.get("state"),
            "labels": _label_names(issue.get("labels", [])),
            "assignee": _assignee_login(issue),
            "comments_count": issue.get("comments", 0),
            "is_pull_request": "pull_request" in issue,
        },
    }


def comment_on_issue(token: str, repo: str, number: int, body: str) -> dict[str, Any]:
    response = _request(
        "POST",
        f"/repos/{repo}/issues/{number}/comments",
        token,
        json={"body": body},
    )
    if not response["ok"]:
        return response

    return {
        "ok": True,
        "comment_url": response["data"].get("html_url"),
    }


def assign_issue(token: str, repo: str, number: int, assignee: str) -> dict[str, Any]:
    response = _request(
        "POST",
        f"/repos/{repo}/issues/{number}/assignees",
        token,
        json={"assignees": [assignee]},
    )
    if not response["ok"]:
        return response

    return {
        "ok": True,
        "number": response["data"].get("number"),
        "assignees": [
            user.get("login")
            for user in response["data"].get("assignees", [])
            if user.get("login")
        ],
    }


def label_issue(token: str, repo: str, number: int, labels: list[str]) -> dict[str, Any]:
    response = _request(
        "POST",
        f"/repos/{repo}/issues/{number}/labels",
        token,
        json={"labels": labels},
    )
    if not response["ok"]:
        return response

    return {
        "ok": True,
        "labels": _label_names(response["data"]),
    }


def close_issue(token: str, repo: str, number: int) -> dict[str, Any]:
    response = _request(
        "PATCH",
        f"/repos/{repo}/issues/{number}",
        token,
        json={"state": "closed"},
    )
    if not response["ok"]:
        return response

    return {
        "ok": True,
        "number": response["data"].get("number"),
        "state": response["data"].get("state"),
    }


def merge_pr(token: str, repo: str, number: int) -> dict[str, Any]:
    response = _request("PUT", f"/repos/{repo}/pulls/{number}/merge", token)
    if not response["ok"]:
        return response

    return {
        "ok": True,
        "merged": response["data"].get("merged"),
        "message": response["data"].get("message"),
        "sha": response["data"].get("sha"),
    }


def delete_branch(token: str, repo: str, branch: str) -> dict[str, Any]:
    safe_branch = branch.removeprefix("refs/heads/")
    response = _request("DELETE", f"/repos/{repo}/git/refs/heads/{safe_branch}", token)
    if not response["ok"]:
        return response

    return {
        "ok": True,
        "branch": safe_branch,
        "deleted": True,
    }


def post_to_handbook(token: str, repo: str, title: str, body: str) -> dict[str, Any]:
    now = datetime.now(UTC)
    slug = "".join(
        char.lower() if char.isalnum() else "-"
        for char in title.strip()
    ).strip("-")
    slug = slug or "agent-summary"
    path = f"agent-summaries/{now:%Y-%m-%d-%H%M%S}-{slug}.md"
    markdown = f"# {title}\n\n{body}\n"
    encoded_content = base64.b64encode(markdown.encode("utf-8")).decode("ascii")

    response = _request(
        "PUT",
        f"/repos/{repo}/contents/{path}",
        token,
        json={
            "message": f"Add handbook summary: {title}",
            "content": encoded_content,
        },
    )
    if not response["ok"]:
        return response

    content = response["data"].get("content", {})
    return {
        "ok": True,
        "path": path,
        "html_url": content.get("html_url"),
    }


if __name__ == "__main__":
    code_repo = os.getenv("CODE_REPO")
    founder_token = os.getenv("GITHUB_PAT_FOUNDER")

    if not code_repo:
        raise SystemExit("CODE_REPO is not set in .env")
    if not founder_token:
        raise SystemExit("GITHUB_PAT_FOUNDER is not set in .env")

    result = list_issues(founder_token, code_repo)
    if not result.get("ok"):
        print("GitHub request failed")
        print(result)
        raise SystemExit(1)

    print(f"Open issues and PRs in {code_repo}:")
    for issue in result["issues"]:
        item_type = "PR" if issue["is_pull_request"] else "issue"
        labels = ", ".join(issue["labels"]) or "no labels"
        assignee = issue["assignee"] or "unassigned"
        print(
            f"#{issue['number']} [{item_type}] {issue['title']} "
            f"({issue['state']}, {labels}, {assignee})"
        )
