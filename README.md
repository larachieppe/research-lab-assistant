# Research Lab Assistant

A small multi-agent research assistant: give it a research question, and it
searches PubMed and arXiv, extracts relevant findings from the retrieved
papers, and synthesizes a cited literature summary — orchestrated as a
[LangGraph](https://github.com/langchain-ai/langgraph) pipeline.

```
START -> planner -> search -> filter -> extract -> synthesize -> END
```

- **planner** — Claude turns your question into 2-4 targeted search queries.
- **search** — queries PubMed (NCBI E-utilities) and arXiv (Atom API) in
  parallel, dedupes results across sources, and drops any paper PubMed
  flags as a retracted publication before it can be used as evidence.
- **filter** — a single batched Claude call screens all retrieved papers by
  title + full abstract, keeping only papers with direct, substantive
  evidence for the question (not just topical overlap) before the more
  expensive per-paper extraction step runs.
- **extract** — Claude pulls the findings relevant to your question out of
  each remaining paper's full abstract, run concurrently across papers.
- **synthesize** — Claude writes a short synthesis citing evidence inline
  (`[1]`, `[2]`, ...), with a deterministically-built reference list appended
  so citation numbers always line up with the sources. Each reference also
  shows its publication type from PubMed (e.g. "Randomized Controlled
  Trial", "Review") or "Preprint — not peer-reviewed" for arXiv, so you can
  judge how much weight to give it.

On the web app, each answer also gets an **evidence map**: papers cited
together in the same paragraph are connected in a small interactive graph,
and clicking a paper, a `[n]` marker in the text, or a reference highlights
the other two — a quick way to see exactly what's backing any given claim.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then add your ANTHROPIC_API_KEY
```

`NCBI_API_KEY` / `NCBI_EMAIL` are optional but recommended — they raise your
PubMed rate limit from 3 to 10 requests/sec. Get a free key at
[ncbi.nlm.nih.gov/account/settings](https://www.ncbi.nlm.nih.gov/account/settings/).

## Usage

```bash
python -m src.main "How does CRISPR-Cas9 off-target activity vary with guide RNA design?"
```

Options:

- `--max-papers N` — total papers to retrieve across all sources (default 12)
- `--max-queries N` — number of search queries the planner generates (default 5)
- `--no-save` — skip writing the report to `outputs/`

Each run prints the synthesis to the terminal and saves a timestamped Markdown
report to `outputs/`.

## Web app

A small FastAPI app (`web/`) wraps the same pipeline with a browser UI: submit
a question, watch it run, and browse past runs. It's a separate consumer of
`src/graph.py` — the CLI above is untouched and keeps working exactly as
before.

```bash
cp .env.example .env   # if you haven't already
# add ANTHROPIC_API_KEY, SITE_USERNAME / SITE_PASSWORD, and a SESSION_SECRET
# (generate one with: python -c "import secrets; print(secrets.token_hex(32))")
uvicorn web.app:app --reload --port 8000
```

Open `http://localhost:8000` — you'll land on a login page (not a browser
popup). **Every route requires logging in**, since each run costs real
Anthropic API calls and this is meant to be deployed publicly.

Run history is stored in a local `runs.db` SQLite file (separate from the
CLI's `outputs/*.md` files).

### Adding "Sign in with Google" (optional)

The login page always has the username/password form; you can additionally
enable a "Sign in with Google" button, restricted to one email address so a
stranger's Google account can't get in:

1. Go to [console.cloud.google.com](https://console.cloud.google.com) ->
   create or select a project -> **APIs & Services -> OAuth consent screen**.
   Choose **External**, and under "Test users" add your own email — while
   the app is unpublished ("Testing" status), only emails added here can
   complete the login at all, which doubles as a second layer of protection.
2. **APIs & Services -> Credentials -> Create Credentials -> OAuth client ID**,
   type **Web application**. Add these **Authorized redirect URIs**:
   - `http://localhost:8000/auth/google/callback` (local dev)
   - `https://<your-service>.onrender.com/auth/google/callback` (once deployed)
3. Copy the generated **Client ID** and **Client Secret** into
   `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` in `.env` (or Render's env vars).
4. Set `ALLOWED_EMAIL` to the one address allowed to sign in via Google —
   this is checked in the app in addition to Google's own test-user list.

Leave all three blank to skip Google login entirely — the app falls back to
username/password only.

### Deploying it on Render

This repo includes a [`render.yaml`](render.yaml) Blueprint, so Render can
configure everything from the file instead of manual dashboard setup:

1. Push this repo to GitHub (already done if you're reading this from there).
2. On [Render](https://render.com), sign in and choose **New + -> Blueprint**,
   then connect this GitHub repo. Render detects `render.yaml` automatically.
3. It'll prompt you for the secrets kept out of the repo: `ANTHROPIC_API_KEY`,
   `SITE_USERNAME`, `SITE_PASSWORD`, and (optional) `GOOGLE_CLIENT_ID` /
   `GOOGLE_CLIENT_SECRET` / `ALLOWED_EMAIL` — leave the Google ones blank to
   skip that step for now and add them later from the service's Environment
   tab. `SESSION_SECRET` is generated for you automatically.
4. That's it — Render builds and starts the service, and gives you a public
   `https://<your-service>.onrender.com` URL behind the login page.

This uses Render's **free tier** by default, which has no persistent disk —
`runs.db` (your run history) resets on every redeploy and on free-tier idle
restarts. That's fine for demoing live pipeline runs; if you want history to
accumulate over time, upgrade `plan: free` to `plan: starter` in
`render.yaml` (~$7/mo), uncomment the `disk:` block, and set
`RUNS_DB_PATH=/data/runs.db`.

Any other host that runs a standard ASGI app (Railway, Fly.io, etc.) works
the same way — same build/start commands, same persistent-disk requirement.

## Tests

```bash
pytest tests/
```

Tests cover deduplication logic, PubMed/arXiv XML parsing against saved
fixtures, and the paper-relevance filter agent (with the LLM call mocked) —
no network access or API key required.
