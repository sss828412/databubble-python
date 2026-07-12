"""
Live smoke test — hits a real running DataBubble API server, no mocks.

Skipped automatically unless both env vars are set, so `pytest` (CI or local)
runs clean with no server up.

Run with:
    DATABUBBLE_SMOKE_URL=http://localhost:8000 \\
    DATABUBBLE_SMOKE_KEY=dbk_... \\
    pytest tests/test_smoke_live.py -v
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd

from databubble import DataBubble
from databubble.exceptions import AuthError

SMOKE_URL = os.environ.get("DATABUBBLE_SMOKE_URL")
SMOKE_KEY = os.environ.get("DATABUBBLE_SMOKE_KEY")

pytestmark = pytest.mark.skipif(
    not (SMOKE_URL and SMOKE_KEY),
    reason="DATABUBBLE_SMOKE_URL and DATABUBBLE_SMOKE_KEY must be set for live smoke tests",
)


@pytest.fixture(scope="module")
def db():
    client = DataBubble(api_key=SMOKE_KEY, base_url=SMOKE_URL)
    yield client
    client.close()


@pytest.fixture(scope="module")
def df():
    return pd.DataFrame({
        "price": [9.99, 12.50, 8.75, 15.00, 11.25, 14.99, 10.50, 13.25, 9.50, 12.00],
        "sales": [120, 95, 140, 80, 110, 85, 130, 90, 125, 100],
    })


def test_health():
    import urllib.request
    with urllib.request.urlopen(f"{SMOKE_URL}/v1/health", timeout=10) as resp:
        assert resp.status == 200


def test_univariate(db, df):
    result = db.skills.univariate(df["price"])
    assert result.summary
    assert isinstance(result.findings, dict)
    assert isinstance(result.warnings, list)


def test_outliers(db, df):
    result = db.skills.outliers(df["price"])
    assert result.summary
    assert isinstance(result.findings, dict)


def test_missing_values(db, df):
    result = db.skills.missing_values(df)
    assert result.summary
    assert isinstance(result.findings, dict)


def test_memory_export(db, df):
    result = db.memory.export(df, label="smoke-test")
    assert result.memory_id
    assert result.memory_json
    assert result.memory_markdown


def test_auth_error():
    bad_client = DataBubble(api_key="dbk_invalid_smoke_test_key", base_url=SMOKE_URL)
    with pytest.raises(AuthError):
        bad_client.skills.univariate(pd.Series([1, 2, 3], name="x"))
    bad_client.close()


def test_rate_limit_header(db, df):
    result = db.skills.univariate(df["price"])
    assert result.tier
    assert result.key_prefix
