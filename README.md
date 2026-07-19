# Research Lab Assistant

A multi-agent research assistant that searches biomedical/scientific literature,
filters low-quality evidence, extracts paper-specific findings, generates a
cited plain-language summary, and visualizes how each source supports the
answer — orchestrated as a [LangGraph](https://github.com/langchain-ai/langgraph)
pipeline over PubMed and arXiv, backed by Claude.

**[Live demo](https://research-lab-assistant.onrender.com/)** · [Source](https://github.com/larachieppe/research-lab-assistant)

<!-- TODO: screenshot of the live showcase / a completed run once captured -->

## Problem

Asking an LLM a research question directly gets you a fluent-sounding answer
with no way to check it. This project is not a ChatGPT wrapper around a single
prompt: it actually retrieves real papers from PubMed and arXiv, screens them
for relevance before spending money extracting from them, keeps citations
deterministic (never LLM-generated) so they can't drift from the source list,
flags retracted publications and unreviewed preprints, and — when the
evidence disagrees — says so instead of blending everything into one
confident-sounding paragraph.

## Demo

<!-- TODO: real sample output excerpt from an actual run, once the API key
     issue below is resolved and a good demo question has been run -->

Try it yourself at the [live demo](https://research-lab-assistant.onrender.com/) —
the homepage has a few featured example runs you can open without logging in,
since running a *new* question costs real Anthropic API calls and requires
logging in.

## Architecture

```mermaid
flowchart LR
    User([User asks a question]) --> Web[FastAPI web app]
    Web -->|background task| Planner

    subgraph Pipeline["LangGraph pipeline (also runnable as a CLI)"]
        direction TB
        Planner["planner<br/>1 Claude call"] --> Search["search<br/>PubMed + arXiv"]
        Search --> Filter["filter<br/>1 batched Claude call"]
        Filter --> Extract["extract<br/>1 Claude call per paper"]
        Extract --> Synth["synthesize<br/>1 Claude call"]
    end

    Search -.->|"up to 8 concurrent requests<br/>(ThreadPoolExecutor)"| PubMed[(PubMed E-utilities)]
    Search -.->|"up to 8 concurrent requests"| ArXiv[(arXiv Atom API)]
    Extract -.->|"up to 8 concurrent requests"| Claude[(Anthropic Claude API)]
    Planner -.-> Claude
    Filter -.-> Claude
    Synth -.-> Claude

    Synth --> Store[("runs table<br/>SQLite locally /<br/>Postgres in production")]
    Web -->|polls status + stage| Store
```

A **follow-up question** skips `planner`/`search` entirely and re-enters the
graph at `filter`, reusing the parent run's already-retrieved paper pool —
cheaper and faster than a fresh search, and still grounded in real evidence
rather than just the model's memory of the earlier answer.

**External services**: Anthropic's Claude API (every LLM call), PubMed
E-utilities and the arXiv Atom API (retrieval, no API key required for either,
though an NCBI key raises the PubMed rate limit), Postgres via a free
[Neon](https://neon.tech) project in production (SQLite locally, zero setup),
and optionally Google OAuth for login.

**Concurrency**: `search` fans out across PubMed + arXiv per query, and
`extract` fans out across papers — both via a `ThreadPoolExecutor` capped at
8 concurrent requests. The pipeline itself runs in a FastAPI `BackgroundTask`
so submitting a question returns immediately; the frontend polls
`/api/runs/{id}` every 2s and shows the actual current stage (e.g.
"Screening 24 papers for relevance"), not just a generic spinner.

**Failure handling**:
- Only genuinely transient Anthropic errors (rate limits, connection blips,
  5xx) are retried; auth/config errors fail immediately instead of being
  masked by retries.
- If the relevance-screening call itself errors, or flags zero of several
  candidates as relevant, the pipeline **fails open** — it runs extraction on
  every candidate rather than silently returning an empty answer.
- Each paper's extraction is isolated: one paper failing produces an empty
  `Finding` for that paper instead of aborting the whole run.
- A single PubMed/arXiv query failing (timeout, rate limit) is tolerated —
  the run continues with whatever other queries/sources succeeded.
- Any unhandled exception in the background task marks the run `failed` with
  the error message, rather than leaving it stuck or crashing the server.

## Key engineering decisions

- **LangGraph over a single prompt** — the task is a real pipeline with
  distinct concerns (plan, retrieve, screen, extract, write) and two
  concurrency points; a single mega-prompt can't screen 24 papers down to 9
  before deciding which are worth extracting from, and can't isolate one
  paper's failure from the rest.
- **References are built deterministically, never by the LLM** — citation
  numbers are assigned in code from the papers that actually had findings
  extracted, so `[3]` in the text always means the same paper as reference
  3 in the list. The model only writes prose using the numbers it's handed.
- **Relevance screening happens before extraction, not after** — a single
  batched call screens all retrieved papers by title + abstract before the
  much more expensive per-paper extraction step runs, so irrelevant papers
  never reach the costlier call.
- **Extraction is parallelized, screening is not** — extraction is naturally
  independent per paper (embarrassingly parallel), while screening needs to
  see all candidates together in one call to make a consistent relevance
  judgment across them.
- **Follow-ups reuse the original evidence pool** — a follow-up question
  re-enters the pipeline at `filter` against the parent run's full retrieved
  pool instead of re-planning and re-searching, so digging deeper stays fast
  and grounded in evidence already gathered, while still letting the new
  question surface different papers from that same pool.
- **Partial failures degrade the answer, they don't abort the run** — see
  "Failure handling" above; almost every step is written to fail open rather
  than fail closed, since a worse answer is better than no answer for a tool
  like this.

## Reliability and safety

- **Retraction filtering** — papers PubMed flags as retracted (either
  directly or via a linked retraction notice) are excluded before they can
  ever be used as evidence, not just flagged after the fact.
- **XSS sanitization** — the synthesizer's markdown output is sanitized
  (`bleach`, allowlisted tags/attributes) before being marked safe in a
  template, since untrusted paper abstracts flow into the LLM's context and
  a prompt-injection payload could otherwise get echoed back as raw HTML.
- **Rate limiting** — an in-memory limiter throttles login attempts and
  run-creation, so a leaked session or brute-force attempt can't silently
  run up the Anthropic bill or credential-stuff the login form.
- **Session security** — signed, `httponly`, `SameSite=Lax` cookies, marked
  `Secure` automatically in production; security response headers
  (`Content-Security-Policy`, `X-Frame-Options`, HSTS, etc.) on every
  response.
- **Server-side input clamping** — `max_papers`/`max_queries` are clamped
  server-side regardless of what a request claims, so a crafted request
  can't demand an arbitrarily expensive run.

## Evaluation

Not yet built — see Roadmap. There's no fabricated precision/recall numbers
here; the metrics below are genuinely measured, but they're pipeline-level
(latency, dedup, filter efficiency), not answer-quality metrics like
retrieval precision/recall or citation correctness against a labeled
benchmark. That would need a real 20-30 question benchmark with hand-labeled
ground truth, which is a project of its own.

## Measured metrics

<!-- TODO: fill in with real numbers from actual local runs (real
     ANTHROPIC_API_KEY required) -->

- Test count: 49 passing tests (`pytest tests/`), covering deduplication,
  PubMed/arXiv XML parsing against saved fixtures, retraction detection, the
  relevance filter (LLM call mocked), evidence-graph construction, auth/rate
  limiting, and XSS sanitization — no network access or API key required to
  run them.
- Number of supported sources: 2 (PubMed, arXiv).
- Concurrency: up to 8 simultaneous requests per fan-out step (search,
  extraction) — see `ThreadPoolExecutor(max_workers=8)` in `src/graph.py`.

## Roadmap

Deliberately out of scope for now — each is a real project of its own, not
something to bolt on silently:

- **A real evaluation suite**: 20-30 hand-picked questions with labeled
  ground truth, measuring retrieval precision/recall, citation correctness,
  and unsupported-claim rate.
- **Claim-level source tracing**: clicking a sentence shows the exact
  supporting passage, paper section, and study type, not just which paper.
- **Durable background jobs**: replace in-process `BackgroundTasks` with
  Celery/Dramatiq/RQ + Redis, with real retries, idempotency, and job
  recovery — meaningful for a multi-instance deployment, overkill for a
  single free-tier instance today.
- **An observability dashboard**: per-stage latency, token usage, cost, and
  retrieval/filter counts over time, not just per-run.
- **Hybrid retrieval + reranking**: lexical search plus semantic reranking
  across PubMed/arXiv, instead of relying on each source's own ranking.
- **Docker/docker-compose** and **typed config validation** (e.g.
  `pydantic-settings` instead of the current plain dataclass) for easier
  self-hosting.

Known limitation worth being deliberate about: `run_detail.html` has a few
sections (the follow-up form, "Feature on homepage" button, children list)
that live outside the `#result` div `poll.js` patches, and are only
rendered server-side at initial page load. A run that transitions from
pending to completed on an already-open page now triggers a full reload
so those sections reflect the real final state — but any *future* addition
with a similar "only show once completed" condition will have the same
fragility unless it also lives inside `#result` or the reload-on-completion
behavior is kept in place.

## Local setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then add your ANTHROPIC_API_KEY
```

`NCBI_API_KEY` / `NCBI_EMAIL` are optional but recommended — they raise your
PubMed rate limit from 3 to 10 requests/sec. Get a free key at
[ncbi.nlm.nih.gov/account/settings](https://www.ncbi.nlm.nih.gov/account/settings/).

## CLI usage

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
a question, watch it run stage-by-stage, browse past runs, and ask follow-up
questions against the same evidence pool. It's a separate consumer of
`src/graph.py` — the CLI above is untouched and keeps working exactly as
before.

```bash
cp .env.example .env   # if you haven't already
# add ANTHROPIC_API_KEY, SITE_USERNAME / SITE_PASSWORD, and a SESSION_SECRET
# (generate one with: python -c "import secrets; print(secrets.token_hex(32))")
uvicorn web.app:app --reload --port 8000
```

Open `http://localhost:8000` — you'll land on a public showcase page (see
"Public showcase" below). Click **Log in** to reach `/ask` and actually run
the pipeline; every route that costs an Anthropic API call stays behind a
real login page (not a browser popup), since this is meant to be deployed
publicly.

Run history is stored in a local `runs.db` SQLite file by default (separate
from the CLI's `outputs/*.md` files) — see "Persistent history" below for
why you'd want to change that before deploying.

### Public showcase (for sharing a demo link)

`/` is public — no login needed — and shows a small curated list of
**featured** example runs, so you can share the plain root URL (e.g. on a
resume) without handing out credentials or exposing your Anthropic budget
to strangers. Everything that actually costs an API call (`/ask`,
submitting a question, asking a follow-up) still requires logging in.

To curate it:

1. Log in and ask a few genuinely good questions from `/ask`.
2. Open one of the resulting `/runs/{id}` pages while logged in — there's a
   small **"☆ Feature on homepage"** button near the top. Click it.
3. That run now shows up in the public list at `/` and its page is viewable
   by anyone, logged in or not. Click the button again to unfeature it.

`/history` stays private (it's your full run log, including test/junk
questions) — only explicitly featured runs are ever public.

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

### Persistent history (optional but recommended once deployed)

By default, run history (`web/db.py`) lives in a local SQLite file. That's
fine locally, but Render's free tier has no persistent disk — that file
resets on every redeploy and on free-tier idle-restarts, so history won't
actually accumulate once deployed.

To fix that for free, point the app at a small hosted Postgres database
instead:

1. Create a free account at [neon.tech](https://neon.tech) and a new
   project (their free tier doesn't expire, unlike Render's own free
   Postgres which auto-deletes after 30 days).
2. Copy the connection string it gives you (looks like
   `postgresql://user:password@host/dbname?sslmode=require`).
3. Set it as `DATABASE_URL` — in `.env` locally, and as an env var on
   Render. The app detects it automatically and switches from SQLite to
   Postgres; the table is created on first startup.

Leave `DATABASE_URL` unset to keep using local SQLite — everything still
works, history just won't survive a redeploy.

### Deploying it on Render

This repo includes a [`render.yaml`](render.yaml) Blueprint, so Render can
configure everything from the file instead of manual dashboard setup:

1. Push this repo to GitHub (already done if you're reading this from there).
2. On [Render](https://render.com), sign in and choose **New + -> Blueprint**,
   then connect this GitHub repo. Render detects `render.yaml` automatically.
3. It'll prompt you for the secrets kept out of the repo: `ANTHROPIC_API_KEY`,
   `SITE_USERNAME`, `SITE_PASSWORD`, and (optional) `GOOGLE_CLIENT_ID` /
   `GOOGLE_CLIENT_SECRET` / `ALLOWED_EMAIL` / `DATABASE_URL` — leave the
   optional ones blank to skip for now and add them later from the
   service's Environment tab. `SESSION_SECRET` is generated for you
   automatically.
4. That's it — Render builds and starts the service, and gives you a public
   `https://<your-service>.onrender.com` URL behind the login page.

This uses Render's **free tier** by default, which has no persistent disk —
see "Persistent history" above (`DATABASE_URL`, free) for the recommended
fix, or `render.yaml`'s commented-out `disk:` block for the paid
alternative (upgrade `plan` to `starter`, ~$7/mo).

Any other host that runs a standard ASGI app (Railway, Fly.io, etc.) works
the same way — same build/start commands, same `DATABASE_URL` story.

**Verifying a deploy actually landed**: `GET /version` returns the deployed
commit (`{"commit": "abc1234", "on_render": true}`), read from Render's
auto-populated `RENDER_GIT_COMMIT` env var. Also worth checking that
**Auto-Deploy** is enabled for the service (Settings → Build & Deploy) —
without it, pushes to `main` sit there until someone manually clicks
Deploy in the dashboard.

## Tests

```bash
pytest tests/
ruff check . && ruff format --check .   # lint + format
```

Tests cover deduplication logic, PubMed/arXiv XML parsing against saved
fixtures, retraction detection, the paper-relevance filter agent (with the
LLM call mocked), evidence-graph construction, auth/rate limiting, and XSS
sanitization — no network access or API key required. CI
(`.github/workflows/tests.yml`) runs the suite across Python 3.12/3.13/3.14,
lint/format checks, and a `pip-audit` dependency vulnerability scan on every
push and PR.
