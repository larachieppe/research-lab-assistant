# Security Policy

This is a small personal/portfolio project, not a project with a dedicated
security team or an SLA - but reports are still welcome and taken seriously.

## Reporting a vulnerability

Please open a [GitHub issue](https://github.com/larachieppe/research-lab-assistant/issues)
or, for anything sensitive, use GitHub's
[private vulnerability reporting](https://github.com/larachieppe/research-lab-assistant/security/advisories/new)
instead of a public issue.

Include what you found, how to reproduce it, and its potential impact if
known. There's no bug bounty, but I'll credit reporters in the fix commit
unless asked not to.

## Scope

The live demo is a low-value target (no user accounts, no payment data, a
single shared owner login gating the only routes that cost real money), but
the things this project already takes seriously and would want to know about
regressing:

- Authentication/session handling (`web/auth.py`)
- XSS via LLM-generated content (`web/app.py`'s sanitization in `_render_run`)
- SQL injection (all queries are parameterized in `web/db.py`)
- Rate limiting / cost-exhaustion on routes that call the Anthropic API
