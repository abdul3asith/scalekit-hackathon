import os

from dotenv import load_dotenv


load_dotenv()


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


# This is a local mock of the future Scalekit authorization layer.
# It makes the demo boundary visible before any real GitHub action runs.
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
    "comment_on_issue": ("code_repo", "write"),
    "assign_issue": ("code_repo", "write"),
    "label_issue": ("code_repo", "write"),
    "close_issue": ("code_repo", "admin"),
    "merge_pr": ("code_repo", "admin"),
    "delete_branch": ("code_repo", "admin"),
    "post_to_handbook": ("handbook_repo", "write"),
}


TOKEN_ENV_VARS: dict[str, str] = {
    "founder": "GITHUB_PAT_FOUNDER",
    "sde": "GITHUB_PAT_SDE",
    "hr": "GITHUB_PAT_HR",
    "intern": "GITHUB_PAT_INTERN",
}


def check_scope(user_id: str, action: str) -> bool:
    if user_id not in USER_SCOPES:
        return False

    requirement = ACTION_REQUIREMENTS.get(action)
    if requirement is None:
        return False

    repo_key, required_scope = requirement
    return required_scope in USER_SCOPES[user_id].get(repo_key, [])


def get_token(user_id: str) -> str:
    env_var = TOKEN_ENV_VARS.get(user_id)
    if env_var is None:
        raise ValueError(f"Unknown user_id: {user_id}")

    token = os.getenv(env_var)
    if not token:
        raise RuntimeError(f"{env_var} is not set")

    return token


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
