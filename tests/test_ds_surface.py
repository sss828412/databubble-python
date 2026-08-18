"""
0.5.0 — data-scientist-first result surface.

The fixtures here are built from the REAL envelope shape (api/envelope.py),
not from the assumed shape used in tests/test_sdk_journeys.py. That difference
is the whole point: the old MOCK_DRIVER_RESPONSE contains a
`result.selection_output` key that the live API has never produced, which is
why `.recommended` returning [] in production went unnoticed for months.
"""

import os
import sys
import warnings

import pandas as pd
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from databubble import DataBubble, JourneyResult          # noqa: E402
from databubble.exceptions import SDKUsageError, ServerError  # noqa: E402
from databubble.journeys import _df_to_rows_payload, _parse_journey_result  # noqa: E402
from databubble.skills import SkillsClient                # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures — real envelope shape
# ---------------------------------------------------------------------------

REAL_DRIVER_RESPONSE = {
    "status": "ok",
    "journey_type": "driver",
    # Sibling of `result` — this is where the selection reasoning actually lives.
    "selection": {
        "recommended": ["price"],
        "caution": ["promotion"],
        "excluded": ["region_code"],
    },
    "result": {
        "journey_type": "driver",
        "mode": "api",
        "halted": False,
        "halt_reason": None,
        "plain_english_summary": "Price is the strongest driver of sales.",
        "warnings": ["Mild heteroscedasticity detected."],
        "assumptions_met": True,
        "adj_r_squared": 0.612,
        "n_observations": 40,
        "primary_estimate": -8.2,
        "primary_label": "Driver analysis — sales",
        "focus_predictor": "price",
        "ci_lower": -10.64,
        "ci_upper": -5.76,
        "significant": True,
        # Real envelope names — NOT selection_output/recommended/caution/excluded
        "selected_predictors": ["price", "promotion"],
        "excluded_predictors": ["region_code"],
        "estimates": [
            {"name": "price", "coefficient": -8.2, "std_error": 1.21,
             "t_statistic": -6.777, "p_value": 0.0001, "ci_lower": -10.64,
             "ci_upper": -5.76, "vif": 1.4, "is_significant": True},
            {"name": "promotion", "coefficient": 3.1, "std_error": 2.05,
             "t_statistic": 1.512, "p_value": 0.139, "ci_lower": -1.05,
             "ci_upper": 7.25, "vif": 1.1, "is_significant": False},
        ],
        "standardized_coefficients": {"price": -0.71, "promotion": 0.18},
        "partial_r_squared": {"price": 0.44, "promotion": 0.03},
        "partial_r_squared_dominance": {"price": 0.93, "promotion": 0.07},
    },
    "_meta": {"journey": "driver", "tier": "pro", "key_prefix": "dbk_test12"},
}

GRAPH_JOURNEY_RESPONSE = {
    "status": "ok",
    "journey_type": "mmm",
    "result": {
        "journey_type": "mmm",
        "halted": False,
        "halt_reason": None,
        "plain_english_summary": "Search carries the highest marginal ROI.",
        "warnings": [],
        "assumptions_met": None,
        "primary_estimate": None,
        "handoffs": {
            "channel_roi": [{"channel": "search", "roi": 2.4}],
            "contribution_share": {"search": 0.42},
        },
    },
    "_meta": {"journey": "mmm", "tier": "business", "key_prefix": "dbk_test12"},
}


def _result(payload) -> JourneyResult:
    return _parse_journey_result(payload, payload["journey_type"])


# ---------------------------------------------------------------------------
# Estimates / coefficients / effects
# ---------------------------------------------------------------------------

def test_estimates_is_a_dataframe_with_regression_columns():
    r = _result(REAL_DRIVER_RESPONSE)
    frame = r.estimates
    assert isinstance(frame, pd.DataFrame)
    assert len(frame) == 2
    # canonical order: predictor name first, then coef / std err / t / p / CI
    assert list(frame.columns)[:6] == [
        "name", "coefficient", "std_error", "t_statistic", "p_value", "ci_lower",
    ]
    assert frame.loc[frame["name"] == "price", "p_value"].iloc[0] == 0.0001


def test_to_frame_is_an_alias_for_estimates():
    r = _result(REAL_DRIVER_RESPONSE)
    assert r.to_frame().equals(r.estimates)


def test_coefficients_series():
    r = _result(REAL_DRIVER_RESPONSE)
    coefs = r.coefficients
    assert isinstance(coefs, pd.Series)
    assert coefs["price"] == -8.2
    assert coefs["promotion"] == 3.1


def test_effects_merges_standardised_partial_and_dominance():
    r = _result(REAL_DRIVER_RESPONSE)
    effects = r.effects
    assert set(effects.columns) == {"predictor", "std_coefficient", "partial_r2", "dominance"}
    row = effects[effects["predictor"] == "price"].iloc[0]
    assert row["std_coefficient"] == -0.71
    assert row["partial_r2"] == 0.44
    assert row["dominance"] == 0.93


def test_diagnostics_only_includes_returned_fields():
    r = _result(REAL_DRIVER_RESPONSE)
    diagnostics = r.diagnostics
    assert diagnostics["n_observations"] == 40
    assert diagnostics["adj_r_squared"] == 0.612
    assert diagnostics["assumptions_met"] is True
    assert "transformation_applied" not in diagnostics.index


def test_scalar_accessors():
    r = _result(REAL_DRIVER_RESPONSE)
    assert r.focus_predictor == "price"
    assert r.n_observations == 40
    assert r.confidence_interval == (-10.64, -5.76)
    assert r.significant is True


def test_empty_response_degrades_to_empty_frames_not_exceptions():
    r = _parse_journey_result({"status": "ok", "result": {}, "_meta": {}}, "elasticity")
    assert r.estimates.empty
    assert r.effects.empty
    assert r.coefficients.empty
    assert r.selected_predictors == []
    assert r.confidence_interval is None
    assert isinstance(r.summary(), str)


# ---------------------------------------------------------------------------
# The bug this release exists to fix
# ---------------------------------------------------------------------------

def test_selected_predictors_reads_the_real_envelope_field():
    r = _result(REAL_DRIVER_RESPONSE)
    assert r.selected_predictors == ["price", "promotion"]
    assert r.excluded_predictors == ["region_code"]


def test_selected_predictors_falls_back_to_the_estimate_names():
    payload = {
        "status": "ok",
        "journey_type": "driver",
        "result": {"estimates": [{"name": "price", "coefficient": -8.2}]},
        "_meta": {},
    }
    assert _parse_journey_result(payload, "driver").selected_predictors == ["price"]


def test_deprecated_recommended_warns_but_now_returns_real_data():
    r = _result(REAL_DRIVER_RESPONSE)
    with pytest.warns(DeprecationWarning, match="selected_predictors"):
        assert r.recommended == ["price"]
    with pytest.warns(DeprecationWarning):
        assert r.caution == ["promotion"]
    with pytest.warns(DeprecationWarning):
        assert r.excluded == ["region_code"]


def test_deprecated_accessors_do_not_fire_on_the_new_surface():
    r = _result(REAL_DRIVER_RESPONSE)
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        assert r.selected_predictors
        assert r.summary()
        assert not r.estimates.empty


# ---------------------------------------------------------------------------
# Graph journeys
# ---------------------------------------------------------------------------

def test_handoffs_exposed_for_graph_journeys():
    r = _result(GRAPH_JOURNEY_RESPONSE)
    assert r.handoffs["contribution_share"] == {"search": 0.42}
    assert r.estimates.empty
    # the summary must point the user at .handoffs rather than looking empty
    assert "handoffs" in r.summary()


def test_handoffs_is_empty_dict_not_none_for_direct_journeys():
    assert _result(REAL_DRIVER_RESPONSE).handoffs == {}


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def test_repr_is_the_regression_table_not_a_one_liner():
    text = repr(_result(REAL_DRIVER_RESPONSE))
    assert "Driver analysis — sales" in text
    assert "coef" in text and "std err" in text and "P>|t|" in text
    assert "price" in text and "promotion" in text
    assert "Adj. R²: 0.612" in text
    assert text.count("\n") > 5


def test_halted_repr_leads_with_the_halt_reason():
    payload = {
        "status": "ok", "journey_type": "elasticity",
        "result": {"halted": True, "halt_reason": "leakage detected", "warnings": []},
        "_meta": {},
    }
    text = repr(_parse_journey_result(payload, "elasticity"))
    assert "HALTED" in text and "leakage detected" in text


def test_explain_carries_the_business_narrative():
    r = _result(REAL_DRIVER_RESPONSE)
    assert "strongest driver" in r.explain()
    # ...and the narrative is no longer what repr() leads with
    assert "strongest driver" not in repr(r)


def test_repr_html_renders_a_table():
    html = _result(REAL_DRIVER_RESPONSE)._repr_html_()
    assert "<table" in html and "price" in html
    assert "explain()" in html


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def test_journey_charts_are_empty_but_never_none():
    charts = _result(REAL_DRIVER_RESPONSE).charts
    assert len(charts) == 0
    assert bool(charts) is False


def test_journey_charts_populate_when_the_api_returns_them():
    payload = dict(REAL_DRIVER_RESPONSE)
    payload["result"] = {**REAL_DRIVER_RESPONSE["result"],
                         "charts": {"residuals": "<svg xmlns='x'/>"}}
    charts = _parse_journey_result(payload, "driver").charts
    assert list(charts) == ["residuals"]
    assert charts["residuals"].svg.startswith("<svg")


def test_skill_charts_resolve_server_paths_to_fetchable_names():
    http = MagicMock()
    http.post_json.return_value = {
        "status": "ok", "skill_name": "univariate",
        "result": {
            "skill_name": "univariate", "column": "price", "summary": "Right skew",
            "findings": {"skewness": 2.31,
                         "chart_histogram": {"svg": "/srv/out/charts/hist_9f3a1c04.svg",
                                             "png": "/srv/out/charts/hist_9f3a1c04.png"}},
            "warnings": [], "recommendations": [], "chapter_ref": "Chapter 04",
        },
        "n_rows": 30, "_meta": {"skill": "univariate", "tier": "pro"},
    }
    http.get_text.return_value = "<svg xmlns='x'/>"
    result = SkillsClient(http).univariate(pd.DataFrame({"price": [1.0, 2.0, 3.0]}), column="price")

    assert list(result.charts) == ["histogram"]
    chart = result.charts["histogram"]
    assert chart.name == "hist_9f3a1c04.svg"      # basename only, not the server path
    assert chart.svg.startswith("<svg")
    http.get_text.assert_called_once_with("/v1/charts/hist_9f3a1c04.svg")


def test_skill_to_frame_drops_chart_keys():
    from databubble.models import SkillResult

    result = SkillResult(
        summary="", findings={"skewness": 2.31, "chart_histogram": {"svg": "/a.svg"}},
        warnings=[], recommendations=[], chapter_ref="", skill_name="univariate",
    )
    frame = result.to_frame()
    assert list(frame["metric"]) == ["skewness"]


# ---------------------------------------------------------------------------
# Serialisation + guardrails
# ---------------------------------------------------------------------------

def test_payload_serialisation_maps_nan_to_none():
    df = pd.DataFrame({"a": [1.0, float("nan"), 3.0], "b": ["x", None, "z"]})
    payload = _df_to_rows_payload(df, ["a", "b"])
    assert payload["rows"] == [[1.0, "x"], [None, None], [3.0, "z"]]


def test_row_ceiling_is_checked_client_side():
    from databubble.journeys import MAX_ANALYSIS_ROWS, _check_row_ceiling

    big = pd.DataFrame({"a": range(3)})
    with pytest.raises(SDKUsageError, match="exceeds the platform ceiling"):
        _check_row_ceiling(_FakeLen(MAX_ANALYSIS_ROWS + 1), "driver")
    _check_row_ceiling(big, "driver")   # under the ceiling: no raise


class _FakeLen:
    def __init__(self, n):
        self._n = n

    def __len__(self):
        return self._n


# ---------------------------------------------------------------------------
# Client behaviour
# ---------------------------------------------------------------------------

def test_journeys_client_uses_the_long_timeout():
    http = MagicMock()
    http.post_json.return_value = REAL_DRIVER_RESPONSE
    db = DataBubble.__new__(DataBubble)
    db._http = http
    from databubble.journeys import JourneysClient

    JourneysClient(http, timeout=300.0).driver(
        pd.DataFrame({"sales": [1.0, 2.0], "price": [3.0, 4.0]}),
        outcome_col="sales", candidate_cols=["price"],
    )
    assert http.post_json.call_args.kwargs["timeout"] == 300.0


def test_include_charts_flag_is_sent_as_an_option():
    http = MagicMock()
    http.post_json.return_value = REAL_DRIVER_RESPONSE
    from databubble.journeys import JourneysClient

    client = JourneysClient(http, include_charts=True)
    client.driver(pd.DataFrame({"sales": [1.0, 2.0], "price": [3.0, 4.0]}),
                  outcome_col="sales", candidate_cols=["price"])
    payload = http.post_json.call_args.args[1]
    assert payload["options"]["include_charts"] is True


def test_string_detail_is_surfaced_not_swallowed():
    from databubble.client import _HTTPClient

    client = _HTTPClient.__new__(_HTTPClient)
    with pytest.raises(ServerError, match="Server at capacity"):
        client._raise_for_status(503, {"detail": "Server at capacity (compute pool). Retry shortly."})


def test_non_json_error_body_does_not_mask_the_status():
    from databubble.client import _HTTPClient

    body = _HTTPClient._parse_body("<html>502 Bad Gateway</html>", 502)
    assert "502" in body["error"] or "Bad Gateway" in body["error"]


def test_default_transforms_list_matches_the_server():
    assert SkillsClient.TRANSFORMS == ("log", "sqrt", "box-cox", "reflect-log", "reflect-sqrt")
