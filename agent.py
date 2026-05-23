import json
import os
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

import github_tools
from scalekit_shim import (
    ACTION_REQUIREMENTS,
    USER_SCOPES,
    ScopeDenied,
    get_token,
    require_scope,
)


load_dotenv()


MODEL = "claude-sonnet-4-5"
MAX_TOOL_LOOPS = 8


TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_issues",
        "description": "List open issues and pull requests in the shared code repo.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "read_issue",
        "description": "Read one issue or pull request from the shared code repo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "number": {"type": "integer", "description": "Issue or PR number."}
            },
            "required": ["number"],
            "additionalProperties": False,
        },
    },
    {
        "name": "comment_on_issue",
        "description": "Comment on an issue or pull request in the shared code repo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "number": {"type": "integer", "description": "Issue or PR number."},
                "body": {"type": "string", "description": "Comment body."},
            },
            "required": ["number", "body"],
            "additionalProperties": False,
        },
    },
    {
        "name": "assign_issue",
        "description": "Assign an issue or pull request in the shared code repo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "number": {"type": "integer", "description": "Issue or PR number."},
                "assignee": {"type": "string", "description": "GitHub username."},
            },
            "required": ["number", "assignee"],
            "additionalProperties": False,
        },
    },
    {
        "name": "label_issue",
        "description": "Add labels to an issue or pull request in the shared code repo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "number": {"type": "integer", "description": "Issue or PR number."},
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Labels to add.",
                },
            },
            "required": ["number", "labels"],
            "additionalProperties": False,
        },
    },
    {
        "name": "close_issue",
        "description": "Close an issue in the shared code repo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "number": {"type": "integer", "description": "Issue number."}
            },
            "required": ["number"],
            "additionalProperties": False,
        },
    },
    {
        "name": "merge_pr",
        "description": "Merge a pull request in the shared code repo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "number": {"type": "integer", "description": "Pull request number."}
            },
            "required": ["number"],
            "additionalProperties": False,
        },
    },
    {
        "name": "delete_branch",
        "description": "Delete a branch from the shared code repo after it is no longer needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "branch": {"type": "string", "description": "Branch name."}
            },
            "required": ["branch"],
            "additionalProperties": False,
        },
    },
    {
        "name": "post_to_handbook",
        "description": "Create a markdown summary file in the handbook repo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Markdown document title."},
                "body": {"type": "string", "description": "Markdown document body."},
            },
            "required": ["title", "body"],
            "additionalProperties": False,
        },
    },
]


def _system_prompt(user_id: str) -> str:
    return f"""
You are a GitHub agent acting as user_id "{user_id}".

The demo thesis: the same prompt should lead to different outcomes because each
employee's agent has a different role-bounded GitHub token.

Use tools when useful. If a tool result says ScopeDenied, do not crash and do not
pretend the action happened. Explain what you could see, what you could not do,
and draft the most useful next step for someone with permission.

Role behavior:
- founder: can administer the code repo. Close stale issues, merge approved PRs,
  and delete branches when the data supports it.
- sde: can write to the code repo. Comment, assign, and label, but do not merge
  or delete branches if denied.
- hr: can read the code repo and write handbook summaries.
- intern: can read the code repo only. Draft a Slack-style note to the SDE for
  actions that require write or admin permissions.

Keep replies concise and specific. Mention attempted denied actions when they
matter for the demo.
""".strip()


def _repo_for_action(action: str) -> str:
    repo_key, _required_scope = ACTION_REQUIREMENTS[action]
    if repo_key == "handbook_repo":
        repo = os.getenv("HANDBOOK_REPO")
        env_var = "HANDBOOK_REPO"
    else:
        repo = os.getenv("CODE_REPO")
        env_var = "CODE_REPO"

    if not repo:
        raise RuntimeError(f"{env_var} is not set")
    return repo


def _summarize_result(result: dict[str, Any]) -> str:
    if result.get("scope_denied"):
        return result["message"]

    if not result.get("ok"):
        error = result.get("error", "unknown error")
        status = result.get("status_code")
        if status:
            return f"GitHub error {status}: {error}"
        return f"Tool error: {error}"

    if "count" in result:
        return f"Returned {result['count']} open issues/PRs."
    if "comment_url" in result:
        return f"Created comment: {result['comment_url']}"
    if result.get("deleted"):
        return f"Deleted branch {result.get('branch')}."
    if "merged" in result:
        return f"Merge result: {result.get('message')}"
    if "path" in result:
        return f"Created handbook file {result['path']}."
    if "state" in result:
        return f"Updated item to {result['state']}."
    if "labels" in result:
        return f"Labels now include: {', '.join(result['labels'])}"
    if "assignees" in result:
        return f"Assignees now include: {', '.join(result['assignees'])}"

    return "Tool completed."


def _scope_denied_result(exc: ScopeDenied) -> dict[str, Any]:
    return {
        "ok": False,
        "scope_denied": True,
        "message": (
            f"ScopeDenied: this action requires {exc.required_scope} on "
            f"{exc.repo_key}; {exc.user_id} has {exc.user_scopes}"
        ),
        "user_id": exc.user_id,
        "action": exc.action,
        "repo_key": exc.repo_key,
        "required_scope": exc.required_scope,
        "user_scopes": exc.user_scopes,
    }


def _target_for_tool(action: str, args: dict[str, Any]) -> str:
    if action in {"read_issue", "comment_on_issue", "assign_issue", "label_issue", "close_issue"}:
        return f"issue/PR #{args.get('number')}"
    if action == "merge_pr":
        return f"PR #{args.get('number')}"
    if action == "delete_branch":
        return f"branch {args.get('branch')}"
    if action == "post_to_handbook":
        return f"handbook: {args.get('title')}"
    if action == "list_issues":
        return "code repo"
    return "unknown target"


def _scope_decision(user_id: str, action: str, allowed: bool, result: dict[str, Any]) -> str:
    if result.get("scope_denied"):
        return result["message"]

    requirement = ACTION_REQUIREMENTS.get(action)
    if requirement is None:
        return "Denied: unknown action"

    repo_key, required_scope = requirement
    if allowed:
        return f"Allowed: {user_id} has {required_scope} on {repo_key}"
    return f"Denied: {user_id} lacks {required_scope} on {repo_key}"


def _call_tool(user_id: str, action: str, args: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    try:
        require_scope(user_id, action)
    except ScopeDenied as exc:
        return False, _scope_denied_result(exc)
    except ValueError as exc:
        return False, {
            "ok": False,
            "error": str(exc),
        }

    try:
        token = get_token(user_id)
        repo = _repo_for_action(action)

        if action == "list_issues":
            return True, github_tools.list_issues(token, repo)
        if action == "read_issue":
            return True, github_tools.read_issue(token, repo, int(args["number"]))
        if action == "comment_on_issue":
            return True, github_tools.comment_on_issue(
                token,
                repo,
                int(args["number"]),
                str(args["body"]),
            )
        if action == "assign_issue":
            return True, github_tools.assign_issue(
                token,
                repo,
                int(args["number"]),
                str(args["assignee"]),
            )
        if action == "label_issue":
            return True, github_tools.label_issue(
                token,
                repo,
                int(args["number"]),
                list(args["labels"]),
            )
        if action == "close_issue":
            return True, github_tools.close_issue(token, repo, int(args["number"]))
        if action == "merge_pr":
            return True, github_tools.merge_pr(token, repo, int(args["number"]))
        if action == "delete_branch":
            return True, github_tools.delete_branch(token, repo, str(args["branch"]))
        if action == "post_to_handbook":
            return True, github_tools.post_to_handbook(
                token,
                repo,
                str(args["title"]),
                str(args["body"]),
            )

        return False, {
            "ok": False,
            "error": f"Unknown tool action: {action}",
        }
    except Exception as exc:
        return True, {
            "ok": False,
            "error": str(exc),
        }


def _text_from_content(content: list[Any]) -> str:
    parts = []
    for block in content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "\n".join(parts).strip()


def _assistant_content_params(content: list[Any]) -> list[dict[str, Any]]:
    params = []
    for block in content:
        block_type = getattr(block, "type", None)
        if block_type == "text":
            params.append(
                {
                    "type": "text",
                    "text": block.text,
                }
            )
        elif block_type == "tool_use":
            params.append(
                {
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                }
            )
    return params


def run_agent(user_id: str, message: str) -> dict[str, Any]:
    if user_id not in USER_SCOPES:
        raise ValueError(f"Unknown user_id: {user_id}")

    client = Anthropic()
    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": message,
        }
    ]
    tool_log: list[dict[str, Any]] = []

    for loop_number in range(MAX_TOOL_LOOPS):
        print(f"agent loop {loop_number + 1}: calling Claude for {user_id}", flush=True)
        response = client.messages.create(
            model=MODEL,
            max_tokens=1200,
            system=_system_prompt(user_id),
            tools=TOOLS,
            messages=messages,
        )

        tool_uses = [
            block
            for block in response.content
            if getattr(block, "type", None) == "tool_use"
        ]

        if not tool_uses:
            print(f"agent loop {loop_number + 1}: Claude returned final reply", flush=True)
            return {
                "final_reply": _text_from_content(response.content),
                "tool_log": tool_log,
            }

        messages.append(
            {
                "role": "assistant",
                "content": _assistant_content_params(response.content),
            }
        )

        tool_results = []
        for tool_use in tool_uses:
            action = tool_use.name
            args = dict(tool_use.input or {})
            print(f"agent loop {loop_number + 1}: tool {action} args={args}", flush=True)
            allowed, result = _call_tool(user_id, action, args)
            summary = _summarize_result(result)
            print(
                f"agent loop {loop_number + 1}: tool {action} allowed={allowed} summary={summary}",
                flush=True,
            )

            tool_log.append(
                {
                    "action": action,
                    "args": args,
                    "target": _target_for_tool(action, args),
                    "allowed": allowed,
                    "scope_decision": _scope_decision(user_id, action, allowed, result),
                    "result_summary": summary,
                }
            )

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": json.dumps(result),
                }
            )

        messages.append(
            {
                "role": "user",
                "content": tool_results,
            }
        )

    return {
        "final_reply": "Stopped after too many tool calls. Review the tool log for partial results.",
        "tool_log": tool_log,
    }


if __name__ == "__main__":
    prompt = "Triage what's open and act on it."

    for demo_user_id in ["founder", "sde", "hr", "intern"]:
        print(f"\n=== {demo_user_id.upper()} ===")
        try:
            result = run_agent(demo_user_id, prompt)
        except Exception as exc:
            print(f"Agent failed: {exc}")
            continue

        print(result["final_reply"])
        print("\nTool log:")
        for entry in result["tool_log"]:
            status = "allowed" if entry["allowed"] else "denied"
            print(f"- {entry['action']} [{status}]: {entry['result_summary']}")
