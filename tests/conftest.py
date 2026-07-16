"""Shared test setup.

TestClient(app) without a `with` block never fires FastAPI's startup event,
so nothing guarantees db.init_db() (which creates/migrates the runs table)
has run before a test touches it. Do it once here instead of leaving each
test file to remember.
"""

import pytest

from web import db, ratelimit


def pytest_configure(config):
    db.init_db()


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    # TestClient requests all report the same client host ("testclient"),
    # so without resetting between tests, hits from one test's login/run
    # attempts would count against another test's rate-limit assertions.
    ratelimit._hits.clear()
    yield
