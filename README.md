# Role-Bounded GitHub Agent Demo

A hackathon MVP showing four employees with four AI agents acting on the same GitHub prompt with different blast radii.

The demo uses Scalekit connected accounts for fresh GitHub OAuth tokens, with local GitHub Personal Access Tokens kept as live-demo fallbacks. `scalekit_shim.py` is the boundary module that hides token lookup and app-layer scope checks from the rest of the codebase.

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

These PATs are fallbacks. STEP 2 will fetch fresh GitHub OAuth tokens from Scalekit first, then fall back to these PATs if a Scalekit call fails during the live demo.

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

## Scalekit Setup

Complete this checklist before enabling the real Scalekit integration.

### 1. Create a Scalekit dev environment

1. Go to https://www.scalekit.com/
2. Sign up or log in
3. Create a new dev environment for this hackathon demo
4. Open that environment in the Scalekit dashboard

### 2. Copy Scalekit app credentials

In the Scalekit dashboard, find your application/environment credentials and copy:

```bash
SCALEKIT_ENVIRONMENT_URL=
SCALEKIT_CLIENT_ID=
SCALEKIT_CLIENT_SECRET=
```

Put these in `.env`.

The environment URL usually looks like:

```text
https://your-company.scalekit.dev
```

### 3. Create a GitHub OAuth app

In GitHub:

1. Go to GitHub -> Settings -> Developer settings -> OAuth Apps
2. Click `New OAuth App`
3. Set `Application name` to something like `Role Bounded Agent Demo`
4. Set `Homepage URL` to your Scalekit environment URL
5. In Scalekit, open the GitHub connector setup and copy the redirect/callback URI
6. Paste that Scalekit redirect URI into GitHub as the `Authorization callback URL`
7. Create the OAuth app
8. Copy the GitHub OAuth app `Client ID`
9. Generate and copy the GitHub OAuth app `Client Secret`

Scalekit's GitHub connector docs describe the callback shape as:

```text
https://<SCALEKIT_ENVIRONMENT_URL>/sso/v1/oauth/<CONNECTION_ID>/callback
```

Use the exact callback URI shown in your Scalekit dashboard.

### 4. Add the GitHub connector in Scalekit

In Scalekit:

1. Open your dev environment
2. Go to Agent Auth or Connectors
3. Add a GitHub OAuth connector/connection
4. Paste the GitHub OAuth app `Client ID`
5. Paste the GitHub OAuth app `Client Secret`
6. Enable these GitHub OAuth scopes at minimum:

```text
repo
delete_repo
public_repo
```

If the Scalekit dashboard supports per-connected-account scopes, use the role-specific grants below. If your dashboard configures scopes only at the connection level, create separate GitHub connections for each scope set or use the broad connector scopes and keep the app-layer gate in `scalekit_shim.py` as the demo's per-action authority.

### 5. Create four connected accounts

Create connected accounts with identifiers exactly matching these `user_id` values:

```text
founder
sde
hr
intern
```

For each connected account, generate an authorization link, open it, and complete the GitHub OAuth consent flow with the intended test GitHub account.

### 6. Grant role-specific OAuth scopes

Use these grants for the connected accounts:

1. `founder`
   - Grant: `repo`, `delete_repo`, `public_repo`
   - Demo meaning: all code repo actions, including admin-style actions

2. `sde`
   - Grant: `repo`
   - Demo meaning: code repo read/write

3. `hr`
   - Grant: `public_repo`
   - Demo meaning: code repo read; handbook write is still controlled by the app-layer role model

4. `intern`
   - Grant: `public_repo`
   - Demo meaning: public read-only

Important: finer per-action gating still lives in `scalekit_shim.py` through `ACTION_REQUIREMENTS`. Scalekit provides fresh delegated GitHub tokens; the app enforces the demo's exact Founder/SDE/HR/Intern action boundaries before each tool call.

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
SCALEKIT_ENVIRONMENT_URL=
SCALEKIT_CLIENT_ID=
SCALEKIT_CLIENT_SECRET=
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
```
