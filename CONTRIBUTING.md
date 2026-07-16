# Contributing

This is primarily a personal/portfolio project, but issues and PRs are welcome.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install pre-commit ruff pytest-cov
pre-commit install
```

## Before opening a PR

```bash
ruff format .
ruff check .
pytest tests/
```

CI runs the test suite (Python 3.12/3.13/3.14) and a dependency vulnerability
scan (`pip-audit`) on every push and PR - both need to pass.

## Style

- No comments explaining *what* code does - only *why*, when it's non-obvious
  (a workaround, a subtle invariant, a constraint from an external API).
- Prefer fail-open over fail-closed for non-critical steps (see `filter_node`
  in `src/graph.py` for the existing pattern) - a screening step that breaks
  shouldn't take down the whole pipeline.
- Keep the CLI (`src/main.py`) and the web app (`web/`) as separate consumers
  of `src/graph.py` - don't couple pipeline logic to either one.
