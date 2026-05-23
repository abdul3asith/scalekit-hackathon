import os
from datetime import UTC, datetime
from typing import Any

from dotenv import load_dotenv


load_dotenv()


try:
    from scalekit import ScalekitClient
except ImportError:
    ScalekitClient = None


GITHUB_CONNECTION_NAME = "github-23"
AUDIT_LOG: list[dict[str, Any]] = []


class ScopeDenied(Exception):
    def __init__(
        self,
        user_id: str,
        action: str,
        repo_key: str,
        required_scope: str,
        user_scopes: list[str],
    ) -> None:
        self.user_id = user_id
        self.action = action
        self.repo_key = repo_key
        self.required_scope = required_scope
        self.user_scopes = user_scopes
        super().__init__(
            f"{user_id} cannot {action}: requires {required_scope} on {repo_key}; "
            f"has {user_scopes}"
        )


USER_SCOPES: dict[str, dict[str, list[str]]] = {
    "founder": {
        "code_repo": ["read", "write", "admin"],
        "handbook_repo": ["read"],
    },
    "sde": {
        "code_repo": ["read", "write"],
        "handbook_repo": ["read"],
    },
    "hr": {
        "code_repo": ["read"],
        "handbook_repo": ["read", "write"],
    },
    "intern": {
        "code_repo": ["read"],
        "handbook_repo": [],
    },
}


ACTION_REQUIREMENTS: dict[str, tuple[str, str]] = {
    "list_issues": ("code_repo", "read"),
    "read_issue": ("code_repo", "read"),
    "create_issue": ("code_repo", "write"),
    "comment_on_issue": ("code_repo", "write"),
    "assign_issue": ("code_repo", "write"),
    "label_issue": ("code_repo", "write"),
    "close_issue": ("code_repo", "admin"),
    "merge_pr": ("code_repo", "admin"),
    "delete_branch": ("code_repo", "admin"),
    "post_to_handbook": ("handbook_repo", "write"),
}


# Scalekit gives us fresh delegated GitHub tokens. This dict is still the
# app-layer policy gate because our demo actions do not map 1:1 to GitHub OAuth
# scopes. Every tool call checks this before GitHub sees a request.
TOKEN_ENV_VARS: dict[str, str] = {
    "founder": "GITHUB_PAT_FOUNDER",
    "sde": "GITHUB_PAT_SDE",
    "hr": "GITHUB_PAT_HR",
    "intern": "GITHUB_PAT_INTERN",
}


def _init_scalekit_client() -> Any | None:
    environment_url = os.getenv("SCALEKIT_ENVIRONMENT_URL")
    client_id = os.getenv("SCALEKIT_CLIENT_ID")
    client_secret = os.getenv("SCALEKIT_CLIENT_SECRET")

    if ScalekitClient is None:
        print(
            "WARNING: scalekit-sdk-python is not installed; falling back to local PATs.",
            flush=True,
        )
        return None

    if not environment_url or not client_id or not client_secret:
        print(
            "WARNING: Scalekit env vars are incomplete; falling back to local PATs.",
            flush=True,
        )
        return None

    return ScalekitClient(environment_url, client_id, client_secret)


SCALEKIT_CLIENT = _init_scalekit_client()


def check_scope(user_id: str, action: str) -> bool:
    if user_id not in USER_SCOPES:
        return False

    requirement = ACTION_REQUIREMENTS.get(action)
    if requirement is None:
        return False

    repo_key, required_scope = requirement
    return required_scope in USER_SCOPES[user_id].get(repo_key, [])


def _fallback_pat(user_id: str, reason: str) -> str:
    env_var = TOKEN_ENV_VARS.get(user_id)
    if env_var is None:
        raise ValueError(f"Unknown user_id: {user_id}")

    token = os.getenv(env_var)
    if not token:
        raise RuntimeError(f"{reason}; {env_var} fallback is not set")

    print(f"WARNING: {reason}; using {env_var} fallback.", flush=True)
    return token


def _extract_access_token(response: Any) -> str:
    connected_account = getattr(response, "connected_account", None)
    if connected_account is None:
        raise RuntimeError("Scalekit response did not include connected_account")

    status = getattr(connected_account, "status", None)
    if status and status not in {"ACTIVE", "CONNECTOR_STATUS_ACTIVE"}:
        raise RuntimeError(f"Scalekit connected account is not active: {status}")

    auth_details = getattr(connected_account, "authorization_details", None)
    if not auth_details:
        raise RuntimeError("Scalekit connected account has no authorization_details")

    oauth_token = auth_details.get("oauth_token")
    if not oauth_token:
        raise RuntimeError("Scalekit connected account has no oauth_token details")

    access_token = oauth_token.get("access_token")
    if not access_token:
        raise RuntimeError("Scalekit oauth_token has no access_token")

    return access_token


def get_token(user_id: str) -> str:
    if user_id not in USER_SCOPES:
        raise ValueError(f"Unknown user_id: {user_id}")

    if SCALEKIT_CLIENT is None:
        return _fallback_pat(user_id, "Scalekit client is unavailable")

    try:
        response = SCALEKIT_CLIENT.actions.get_connected_account(
            connection_name=GITHUB_CONNECTION_NAME,
            identifier=user_id,
        )
        return _extract_access_token(response)
    except Exception as exc:
        return _fallback_pat(user_id, f"Scalekit token fetch failed: {exc}")


def require_scope(user_id: str, action: str) -> None:
    requirement = ACTION_REQUIREMENTS.get(action)
    if requirement is None:
        raise ValueError(f"Unknown action: {action}")

    repo_key, required_scope = requirement
    user_scopes = USER_SCOPES.get(user_id, {}).get(repo_key, [])

    if required_scope not in user_scopes:
        raise ScopeDenied(
            user_id=user_id,
            action=action,
            repo_key=repo_key,
            required_scope=required_scope,
            user_scopes=user_scopes,
        )


def audit_event(user_id: str, action: str, allowed: bool, result_summary: str) -> None:
    repo_key, required_scope = ACTION_REQUIREMENTS.get(action, ("unknown", "unknown"))
    AUDIT_LOG.append(
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "user_id": user_id,
            "action": action,
            "allowed": allowed,
            "repo_key": repo_key,
            "required_scope": required_scope,
            "result_summary": result_summary,
        }
    )


if __name__ == "__main__":
    users = ["founder", "sde", "hr", "intern"]
    actions = list(ACTION_REQUIREMENTS.keys())

    first_col_width = max(len("user"), *(len(user) for user in users))
    action_width = max(len(action) for action in actions)

    print("Permission matrix")
    print("=" * 18)
    print(f"{'user':<{first_col_width}}  action{' ' * (action_width - len('action'))}  allowed")
    print(f"{'-' * first_col_width}  {'-' * action_width}  -------")

    for user_id in users:
        for action in actions:
            allowed = "yes" if check_scope(user_id, action) else "no"
            print(f"{user_id:<{first_col_width}}  {action:<{action_width}}  {allowed}")

    print("\nScalekit token check")
    print("====================")
    token = get_token("founder")
    masked = f"{token[:8]}...{token[-4:]}" if len(token) > 12 else token
    print(f"founder GitHub token: {masked}")
