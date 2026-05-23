# Role-Bounded GitHub Agent Demo

A hackathon MVP showing four employees with four AI agents acting on the same GitHub prompt with different blast radii.

The demo uses GitHub Personal Access Tokens directly for now. `scalekit_shim.py` will mock the future Scalekit authorization layer by mapping each user to declared scopes before any GitHub action runs.

## Required Repos

Create two GitHub repositories before the real GitHub steps:

1. Code repo
   - Put this repo name in `.env` as `CODE_REPO`
   - Format: `owner/repo`
   - Seed it with issues and pull requests for the demo

2. Handbook repo
   - Put this repo name in `.env` as `HANDBOOK_REPO`
   - Format: `owner/repo`
   - HR will post team summaries here later

## Create The Four GitHub PATs

Create classic Personal Access Tokens here:

GitHub -> Settings -> Developer settings -> Personal access tokens -> Tokens (classic) -> Generate new token -> Generate new token (classic)

Use these scopes:

1. Founder token
   - Env var: `GITHUB_PAT_FOUNDER`
   - Scopes: `repo`, `delete_repo`
   - Demo role: admin-level access on the code repo, read access on the handbook repo

2. SDE token
   - Env var: `GITHUB_PAT_SDE`
   - Scopes: `repo`, `public_repo`
   - Demo role: read/write access on the code repo, read-only access on the handbook repo

3. HR token
   - Env var: `GITHUB_PAT_HR`
   - Scopes: `public_repo`, `repo`
   - Demo role: read-only access on the code repo, read/write access on the handbook repo

4. Intern token
   - Env var: `GITHUB_PAT_INTERN`
   - Scopes: `public_repo`
   - Demo role: public read-only access

For a private repo demo, GitHub classic PAT scopes are broad at the account level. The app still enforces the role boundary in `scalekit_shim.py` before each action so the demo behavior matches the four roles.

## Anthropic API Key

Create an Anthropic API key:

1. Go to https://console.anthropic.com/settings/keys
2. Create a key
3. Put it in `.env` as `ANTHROPIC_API_KEY`

## Local Setup

Use Python 3.11 or newer.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:

```bash
ANTHROPIC_API_KEY=
GITHUB_PAT_FOUNDER=
GITHUB_PAT_SDE=
GITHUB_PAT_HR=
GITHUB_PAT_INTERN=
CODE_REPO=owner/code-repo
HANDBOOK_REPO=owner/handbook-repo
```

## Run

```bash
uvicorn main:app --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
# Team Handbook

The single source of truth for how we work.

This repo is owned by the People Ops team. Engineering, design, and other
functions read from here; only People Ops can publish to it.

## What lives here

- **weekly-updates/** — Weekly summaries of what each team is shipping
- **policies/** — Time off, expenses, equipment, remote work
- **onboarding/** — First-week guides for new hires
- **org/** — Org chart, team rosters, on-call rotations

## How to use this

Most updates are written by People Ops, sometimes with help from automated
tools that read the engineering repo and summarize activity here.

If something is wrong or out of date, open an issue or ping #people-ops.

---

_Last updated by People Ops_
```
