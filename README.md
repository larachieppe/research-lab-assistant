# Research Lab Assistant

A small multi-agent research assistant: give it a research question, and it
searches PubMed and arXiv, extracts relevant findings from the retrieved
papers, and synthesizes a cited literature summary — orchestrated as a
[LangGraph](https://github.com/langchain-ai/langgraph) pipeline.

```
START -> planner -> search -> extract -> synthesize -> END
```

- **planner** — Claude turns your question into 2-4 targeted search queries.
- **search** — queries PubMed (NCBI E-utilities) and arXiv (Atom API) in
  parallel, then dedupes results across sources.
- **extract** — Claude pulls the findings relevant to your question out of
  each paper's abstract, run concurrently across papers.
- **synthesize** — Claude writes a short synthesis citing evidence inline
  (`[1]`, `[2]`, ...), with a deterministically-built reference list appended
  so citation numbers always line up with the sources.

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

- `--max-papers N` — total papers to retrieve across all sources (default 8)
- `--max-queries N` — number of search queries the planner generates (default 4)
- `--no-save` — skip writing the report to `outputs/`

Each run prints the synthesis to the terminal and saves a timestamped Markdown
report to `outputs/`.

## Tests

```bash
pytest tests/
```

Tests cover deduplication logic and PubMed/arXiv XML parsing against saved
fixtures — no network access or API key required.
