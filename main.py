from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agent import run_agent
from scalekit_shim import (
    AUDIT_LOG,
    approve_scope_upgrade,
    is_user_revoked,
    list_scope_requests,
    request_scope_upgrade,
    revoke_user,
)


app = FastAPI(title="Role-Bounded GitHub Agent Demo")
STATIC_DIR = Path(__file__).parent / "static"


class ChatRequest(BaseModel):
    user_id: str
    message: str


class ScopeRequestCreate(BaseModel):
    user_id: str
    repo_key: str
    scope: str
    reason: str = ""


class ScopeRequestApproval(BaseModel):
    approver_id: str


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/audit")
def audit(since: str | None = None) -> list[dict[str, Any]]:
    events = AUDIT_LOG
    if since:
        events = [event for event in events if event["timestamp"] > since]

    return sorted(events, key=lambda event: event["timestamp"], reverse=True)


@app.get("/scope-requests")
def scope_requests() -> list[dict[str, Any]]:
    return list_scope_requests()


@app.post("/scope-requests")
def create_scope_request(request: ScopeRequestCreate) -> dict[str, Any]:
    return request_scope_upgrade(
        user_id=request.user_id,
        repo_key=request.repo_key,
        scope=request.scope,
        reason=request.reason,
    )


@app.post("/scope-requests/{request_id}/approve")
def approve_scope_request(
    request_id: str,
    approval: ScopeRequestApproval,
) -> dict[str, Any]:
    try:
        return approve_scope_upgrade(request_id, approval.approver_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/users/{user_id}/revoke")
def revoke_agent_access(user_id: str) -> dict[str, Any]:
    try:
        return revoke_user(user_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    print(f"/chat start user_id={request.user_id} message={request.message!r}", flush=True)
    if is_user_revoked(request.user_id):
        raise HTTPException(status_code=403, detail=f"Agent access revoked for {request.user_id}")

    try:
        result = run_agent(request.user_id, request.message)
    except Exception as exc:
        print(f"/chat failed user_id={request.user_id} error={exc}", flush=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    tool_log = result.get("tool_log", [])
    denials = [entry for entry in tool_log if not entry.get("allowed")]
    print(
        f"/chat done user_id={request.user_id} tool_calls={len(tool_log)} denials={len(denials)}",
        flush=True,
    )

    return {
        "final_reply": result.get("final_reply", ""),
        "tool_log": tool_log,
        "denials": denials,
    }
