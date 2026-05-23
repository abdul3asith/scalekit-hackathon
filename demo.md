# Demo Script

## Before Going On Stage

1. Open `.env` and confirm these values are set:

```bash
ANTHROPIC_API_KEY=
GITHUB_PAT_FOUNDER=
GITHUB_PAT_SDE=
GITHUB_PAT_HR=
GITHUB_PAT_INTERN=
CODE_REPO=owner/code-repo
HANDBOOK_REPO=owner/handbook-repo
```

2. Confirm the code repo has open issues and at least one PR.

3. Start the server:

```bash
uvicorn main:app --reload
```

4. Open the app:

```text
http://127.0.0.1:8000
```

## Opening Line

"This demo shows four employees giving the same prompt to their own GitHub agent. The important part is not the prompt. The important part is that every agent has a different blast radius."

## Show The Boundary

Say:

"For the hackathon MVP, the Scalekit boundary is mocked in `scalekit_shim.py`. Every tool call goes through that layer before GitHub receives a request. If the user's role does not have the required scope, the tool returns `ScopeDenied` and Claude has to adapt."

## Prompt 1: Founder

1. Click `Founder`
2. Use this prompt:

```text
Triage open issues and act on what you can
```

3. Say:

"The founder has admin scope on the code repo, so this agent can perform high-risk actions like closing stale issues or merging approved PRs when the repo state supports it."

4. Point to:
   - Allowed tool badges
   - Any admin action attempted
   - Final reply

## Prompt 2: SDE

1. Click `SDE`
2. Use the same prompt:

```text
Triage open issues and act on what you can
```

3. Say:

"Same prompt, different token. The SDE can comment, label, and assign, but admin actions are denied before GitHub is called."

4. Point to:
   - Green write actions
   - Red denied admin actions
   - Claude's fallback response

## Prompt 3: HR

1. Click `HR`
2. Use this prompt:

```text
Summarize what the team is working on
```

3. Say:

"HR can read the code repo but cannot mutate it. HR can write to the handbook repo, so the agent turns engineering activity into a handbook summary."

4. Point to:
   - Code repo read action
   - Handbook write action
   - Created handbook file path

## Prompt 4: Intern

1. Click `Intern`
2. Use this prompt:

```text
Triage open issues and act on what you can
```

3. Say:

"The intern can read public repo state, but cannot act. The agent does not fail. It drafts a request for someone with more permission."

4. Point to:
   - Read action allowed
   - Write/admin actions denied
   - Slack-style escalation message

## Closing Line

"The model sees the same repo and the same prompt, but the authorization layer controls what actually happens. That is the product idea: AI agents should inherit the user's role boundary, not bypass it."

## If Something Fails

If the UI stays on `Waiting for response...`, check the uvicorn terminal:

```text
/chat start user_id=...
agent loop 1: calling Claude for ...
agent loop 1: tool ...
```

Use the last printed line to identify whether the issue is Anthropic, GitHub, or a tool loop.
