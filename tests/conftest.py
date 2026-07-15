"""Shared test setup.

TestClient(app) without a `with` block never fires FastAPI's startup event,
so nothing guarantees db.init_db() (which creates/migrates the runs table)
has run before a test touches it. Do it once here instead of leaving each
test file to remember.
"""

from web import db


def pytest_configure(config):
    db.init_db()
