"""
SDK v0.2.0 journey method tests.
No running server required — HTTP is mocked.
"""

import pytest
import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import MagicMock
from databubble import DataBubble, JourneyResult
from databubble.exceptions import SDKUsageError
from databubble.journeys import _df_to_rows_payload, _parse_journey_result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

RNG = np.random.default_rng(42)

@pytest.fixture
def price_sales_df():
    n = 35
    price = RNG.uniform(8, 15, n)
    sales = 200 * price ** -0.85 + RNG.normal(0, 5, n)
    return pd.DataFrame({"price": price, "sales": sales})


@pytest.fixture
def driver_df():
    n = 40
    return pd.DataFrame({
        "sales":       RNG.normal(100, 20, n),
        "price":       RNG.uniform(8, 15, n),
        "promotion":   RNG.choice([0, 1], n),
        "region_code": RNG.choice([1, 2, 3, 4], n),
    })


@pytest.fixture
def segment_df():
    n = 60
    return pd.DataFrame({
        "recency":   RNG.integers(1, 365, n),
        "frequency": RNG.integers(1, 20, n),
        "spend":     RNG.uniform(10, 500, n),
        "segment":   RNG.choice(["High", "Mid", "Low"], n),
    })


@pytest.fixture
def ts_df():
    dates = pd.date_range("2022-01-01", periods=52, freq="W")
    values = 100 + np.arange(52) * 0.5 + RNG.normal(0, 5, 52)
    return pd.DataFrame({"week": dates.astype(str), "sales": values})


MOCK_ELASTICITY_RESPONSE = {
    "status": "ok",
    "journey_type": "elasticity",
    "result": {
        "primary_estimate": -0.847,
        "adj_r_squared": 0.612,
        "assumptions_met": True,
        "revenue_implication": "Demand is elastic. Price increases are likely to reduce total revenue.",
        "plain_english_summary": "A 1% increase in price is associated with a 0.85% decrease in demand.",
        "warnings": [],
        "halted": False,
        "halt_reason": None,
    },
    "_meta": {"journey": "elasticity", "tier": "business", "key_prefix": "dbk_test12"},
}

MOCK_DRIVER_RESPONSE = {
    "status": "ok",
    "journey_type": "driver",
    "result": {
        "primary_estimate": -8.2,
        "plain_english_summary": "Price is the strongest driver of sales.",
        "warnings": [],
        "halted": False,
        "halt_reason": None,
        "assumptions_met": True,
        "selection_output": {
            "recommended": ["price"],
            "caution": ["promotion"],
            "excluded": ["region_code"],
        },
    },
    "_meta": {"journey": "driver", "tier": "business", "key_prefix": "dbk_test12"},
}

MOCK_HALT_RESPONSE = {
    "status": "ok",
    "journey_type": "elasticity",
    "result": {
        "primary_estimate": None,
        "plain_english_summary": "",
        "warnings": ["post_campaign_spend flagged as leakage."],
        "halted": True,
        "halt_reason": "post_campaign_spend flagged as post-outcome leakage (r=0.71).",
        "assumptions_met": None,
    },
    "_meta": {"journey": "elasticity", "tier": "business", "key_prefix": "dbk_test12"},
}


@pytest.fixture
def mock_http_elasticity():
    http = MagicMock()
    http.post_json.return_value = MOCK_ELASTICITY_RESPONSE
    return http


@pytest.fixture
def db_elasticity(mock_http_elasticity):
    client = DataBubble.__new__(DataBubble)
    client._http = mock_http_elasticity
    from databubble.skills import SkillsClient
    from databubble.memory import MemoryClient
    from databubble.journeys import JourneysClient
    client.skills = SkillsClient(mock_http_elasticity)
    client.memory = MemoryClient(mock_http_elasticity)
    client.journeys = JourneysClient(mock_http_elasticity)
    return client


# ---------------------------------------------------------------------------
# Case 1: _df_to_rows_payload — correct shape
# ---------------------------------------------------------------------------

def test_df_to_rows_payload_shape(price_sales_df):
    payload = _df_to_rows_payload(price_sales_df, ["price", "sales"])
    assert payload["columns"] == ["price", "sales"]
    assert len(payload["rows"]) == 35
    assert len(payload["rows"][0]) == 2


# ---------------------------------------------------------------------------
# Case 2: NaN serialised as None in rows
# ---------------------------------------------------------------------------

def test_nan_in_rows_becomes_none():
    df = pd.DataFrame({"a": [1.0, float("nan"), 3.0]})
    payload = _df_to_rows_payload(df, ["a"])
    assert payload["rows"][1][0] is None
    assert payload["rows"][0][0] == 1.0


# ---------------------------------------------------------------------------
# Case 3: elasticity — correct payload sent to API
# ---------------------------------------------------------------------------

def test_elasticity_payload(db_elasticity, price_sales_df):
    result = db_elasticity.journeys.elasticity(
        price_sales_df,
        price_col="price",
        sales_col="sales",
    )
    call_args = db_elasticity._http.post_json.call_args
    assert call_args[0][0] == "/v1/journeys/elasticity"
    payload = call_args[0][1]
    assert payload["column_map"]["price_col"] == "price"
    assert payload["column_map"]["sales_col"] == "sales"
    assert "rows" in payload["data"]
    assert len(payload["data"]["rows"]) == 35


# ---------------------------------------------------------------------------
# Case 4: elasticity — JourneyResult fields correct
# ---------------------------------------------------------------------------

def test_elasticity_result_fields(db_elasticity, price_sales_df):
    result = db_elasticity.journeys.elasticity(
        price_sales_df, price_col="price", sales_col="sales"
    )
    assert isinstance(result, JourneyResult)
    assert result.journey_type == "elasticity"
    assert result.primary_estimate == -0.847
    assert result.adj_r_squared == 0.612
    assert result.assumptions_met is True
    assert result.halted is False
    assert result.is_reliable() is True
    assert "elastic" in result.revenue_implication.lower()
    assert result.tier == "business"


# ---------------------------------------------------------------------------
# Case 5: halted journey — is_reliable() returns False
# ---------------------------------------------------------------------------

def test_halted_journey_not_reliable(price_sales_df):
    http = MagicMock()
    http.post_json.return_value = MOCK_HALT_RESPONSE
    client = DataBubble.__new__(DataBubble)
    client._http = http
    from databubble.journeys import JourneysClient
    from databubble.skills import SkillsClient
    from databubble.memory import MemoryClient
    client.skills = SkillsClient(http)
    client.memory = MemoryClient(http)
    client.journeys = JourneysClient(http)

    result = client.journeys.elasticity(
        price_sales_df, price_col="price", sales_col="sales"
    )
    assert result.halted is True
    assert result.is_reliable() is False
    assert result.primary_estimate is None
    assert "leakage" in result.halt_reason.lower()


# ---------------------------------------------------------------------------
# Case 6: driver — recommended/caution/excluded parsed
# ---------------------------------------------------------------------------

def test_driver_result_lists(driver_df):
    http = MagicMock()
    http.post_json.return_value = MOCK_DRIVER_RESPONSE
    client = DataBubble.__new__(DataBubble)
    client._http = http
    from databubble.journeys import JourneysClient
    from databubble.skills import SkillsClient
    from databubble.memory import MemoryClient
    client.skills = SkillsClient(http)
    client.memory = MemoryClient(http)
    client.journeys = JourneysClient(http)

    result = client.journeys.driver(
        driver_df,
        outcome_col="sales",
        candidate_cols=["price", "promotion", "region_code"],
    )
    assert result.recommended == ["price"]
    assert result.caution == ["promotion"]
    assert result.excluded == ["region_code"]
    assert result.primary_estimate == -8.2


# ---------------------------------------------------------------------------
# Case 7: SDKUsageError on missing column
# ---------------------------------------------------------------------------

def test_elasticity_missing_column_raises(db_elasticity, price_sales_df):
    with pytest.raises(SDKUsageError) as exc_info:
        db_elasticity.journeys.elasticity(
            price_sales_df,
            price_col="price",
            sales_col="revenue",   # not in df
        )
    assert "revenue" in str(exc_info.value)
    assert "not found" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Case 8: time_series — invalid objective raises SDKUsageError
# ---------------------------------------------------------------------------

def test_time_series_invalid_objective(ts_df):
    http = MagicMock()
    client = DataBubble.__new__(DataBubble)
    client._http = http
    from databubble.journeys import JourneysClient
    from databubble.skills import SkillsClient
    from databubble.memory import MemoryClient
    client.skills = SkillsClient(http)
    client.memory = MemoryClient(http)
    client.journeys = JourneysClient(http)

    with pytest.raises(SDKUsageError) as exc_info:
        client.journeys.time_series(
            ts_df,
            date_col="week",
            value_col="sales",
            objective="predict",   # invalid
        )
    assert "forecast" in str(exc_info.value)
    assert "decompose" in str(exc_info.value)
