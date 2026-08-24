"""
SDK 0.6.0 db.model / db.scorecard / db.segments tests.
No running server required — HTTP is mocked. Response shapes below are
trimmed from real payloads captured against a live local platform server
(elasticity/driver/classification/segmentation journeys, export/predict/
compare/drift/score) during Phase 3 implementation.
"""

import sys
import os
import json

import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import MagicMock
from databubble.models import JourneyResult
from databubble.exceptions import SDKUsageError, SkillError
from databubble.model import ModelClient
from databubble.scorecard import ScorecardClient
from databubble.segments import SegmentsClient
from databubble._scoring_common import extract_ref, artifact_dict, df_to_records, MAX_SCORE_ROWS


# ---------------------------------------------------------------------------
# Fixtures — response shapes trimmed from real live-captured payloads
# ---------------------------------------------------------------------------

MOCK_CARD_RESPONSE = {
    "schema_version": "1.2",
    "model_family": "ols",
    "outcome": "ln_sales",
    "intercept": 6.9,
    "terms": [{"name": "ln_price", "coefficient": -1.50, "ci_lower": -1.6, "ci_upper": -1.4,
               "p_value": 0.0, "is_significant": True}],
    "recipe": {
        "raw_inputs": ["price"], "input_dtypes": {}, "log_transform_outcome": True,
        "log_transform_inputs": ["price"], "dummies": [], "interactions": [],
        "model_matrix_columns": ["ln_price"], "drop_first": True,
    },
    "provenance": {"journey_type": "elasticity", "mode": "interpret", "fit_n": 200,
                   "fit_r_squared": 0.98, "created_at": "2026-08-24T00:00:00Z", "source": "databubble"},
    "group_col": None, "group_value": None, "notes": [],
}

MOCK_BUNDLE_RESPONSE = {
    "schema_version": "1.2", "kind": "bundle", "group_col": "region",
    "cards": [
        {**MOCK_CARD_RESPONSE, "outcome": "sales", "group_value": "east",
         "terms": [{"name": "price", "coefficient": -2.0, "p_value": 0.01, "is_significant": True}]},
        {**MOCK_CARD_RESPONSE, "outcome": "sales", "group_value": "west",
         "terms": [{"name": "price", "coefficient": -1.5, "p_value": 0.02, "is_significant": True}]},
    ],
    "excluded_groups": [], "provenance": MOCK_CARD_RESPONSE["provenance"],
}

MOCK_PREDICT_RESPONSE = {
    "predictions": [12.5, 14.2], "n_scored": 2, "outcome": "ln_sales",
    "log_back_transformed": True, "warnings": [],
    "ci_lower": [12.1, 13.8], "ci_upper": [12.9, 14.6],
}

MOCK_IC_COMPARE_RESPONSE = {
    "outcome": "sales",
    "candidates": [
        {"label": "price, promo", "k": 2, "aic": 1019.2, "bic": 1026.1, "delta_aic": 0.0,
         "delta_bic": 0.0, "akaike_weight": 1.0},
        {"label": "price", "k": 1, "aic": 1276.6, "bic": 1279.9, "delta_aic": 257.5,
         "delta_bic": 254.2, "akaike_weight": 1.2e-56},
    ],
    "best_label": "price, promo", "notes": [],
}

MOCK_NESTED_COMPARE_RESPONSE = {
    "outcome": "sales", "reduced_label": "price", "full_label": "price, promo",
    "reduced_k": 1, "full_k": 2, "f_statistic": 312.4, "df_numerator": 1,
    "df_denominator": 197, "p_value": 2.1e-57, "full_model_preferred": True,
    "interpretation": "Adding 1 term(s) (promo) significantly improves the fit.",
}

MOCK_DRIFT_RESPONSE = {
    "applicable": True, "reason": None, "n_features_checked": 1, "n_features_drifted": 0,
    "drift_detected": False,
    "per_feature": [{"column": "price", "kind": "continuous", "n_observed": 20,
                      "reference": {}, "observed": {}, "drifted": False, "detail": "within range"}],
    "interpretation": "No drift detected.", "notes": [],
}

MOCK_SCORECARD_RESPONSE = {
    "schema_version": "1.0", "kind": "classification_scorecard", "outcome": "churned",
    "pipeline": {}, "provenance": {"journey_type": "classification", "outcome": "churned", "auc": 0.73,
                                    "created_at": "2026-08-24T00:00:00Z", "source": "databubble"},
    "notes": [],
}

MOCK_SCORE_RESPONSE = {
    "labels": [1, 0], "probabilities": [{"0": 0.17, "1": 0.83}, {"0": 0.57, "1": 0.43}],
    "low_confidence": [False, True], "low_confidence_count": 1,
    "class_distribution": {"0": 1, "1": 1}, "threshold_used": 0.5, "n_scored": 2,
}

MOCK_SEGMENT_SCORER_RESPONSE = {
    "schema_version": "1.0", "kind": "segment_scorer", "pipeline": {},
    "cluster_label_map": {"0": "Segment 1", "1": "Segment 2"}, "profiles": [],
    "provenance": {"journey_type": "segmentation", "created_at": "2026-08-24T00:00:00Z", "source": "databubble"},
    "notes": [],
}

MOCK_SEGMENT_SCORE_RESPONSE = {
    "assignments": [{"segment": "Segment 2", "raw_label": "1"}, {"segment": "Segment 1", "raw_label": "0"}],
    "probabilities": [{"Segment 2": 0.8}, {"Segment 1": 0.6}],
    "low_confidence": [False, False], "low_confidence_count": 0,
    "segment_distribution": {"Segment 2": 1, "Segment 1": 1}, "n_scored": 2,
}


def _journey_result(result_dict: dict) -> JourneyResult:
    return JourneyResult(
        journey_type="elasticity", halted=False, halt_reason=None, primary_estimate=None,
        plain_english_summary="", warnings=[], assumptions_met=True,
        raw={"result": result_dict},
    )


@pytest.fixture
def new_rows_df():
    return pd.DataFrame({"price": [10.0, 12.0]})


# ---------------------------------------------------------------------------
# _scoring_common — shared plumbing
# ---------------------------------------------------------------------------

def test_extract_ref_from_journey_result():
    result = _journey_result({"model_export_ref": {"findings": {"x": 1}}})
    ref = extract_ref(result, "model_export_ref", "test")
    assert ref == {"findings": {"x": 1}}


def test_extract_ref_missing_raises():
    result = _journey_result({})
    with pytest.raises(SDKUsageError, match="model_export_ref"):
        extract_ref(result, "model_export_ref", "db.model.export")


def test_extract_ref_from_dict_passthrough():
    ref = extract_ref({"findings": {"x": 1}}, "model_export_ref", "test")
    assert ref == {"findings": {"x": 1}}


def test_extract_ref_wrong_type_raises():
    with pytest.raises(SDKUsageError):
        extract_ref(42, "model_export_ref", "test")


def test_artifact_dict_from_result_wrapper():
    class Fake:
        raw = {"a": 1}
    assert artifact_dict(Fake(), "test", "card") == {"a": 1}


def test_artifact_dict_from_plain_dict():
    assert artifact_dict({"a": 1}, "test", "card") == {"a": 1}


def test_artifact_dict_wrong_type_raises():
    with pytest.raises(SDKUsageError):
        artifact_dict(42, "test", "card")


def test_df_to_records_shape(new_rows_df):
    records = df_to_records(new_rows_df, "test")
    assert records == [{"price": 10.0}, {"price": 12.0}]


def test_df_to_records_nan_to_none():
    df = pd.DataFrame({"price": [10.0, np.nan]})
    records = df_to_records(df, "test")
    assert records[1]["price"] is None


def test_df_to_records_empty_raises():
    with pytest.raises(SDKUsageError, match="empty"):
        df_to_records(pd.DataFrame({"price": []}), "test")


def test_df_to_records_row_ceiling():
    big = pd.DataFrame({"price": range(MAX_SCORE_ROWS + 1)})
    with pytest.raises(SDKUsageError, match="exceeds the platform ceiling"):
        df_to_records(big, "test")


def test_df_to_records_requires_dataframe():
    with pytest.raises(SDKUsageError, match="pd.DataFrame"):
        df_to_records([{"price": 1}], "test")


# ---------------------------------------------------------------------------
# db.model
# ---------------------------------------------------------------------------

@pytest.fixture
def model_client():
    http = MagicMock()
    return ModelClient(http), http


def test_model_export_card(model_client, new_rows_df):
    client, http = model_client
    http.post_json.return_value = MOCK_CARD_RESPONSE
    result = _journey_result({"model_export_ref": {"findings": {}}})

    card = client.export(result)

    http.post_json.assert_called_once_with(
        "/v1/model/export", {"model_export_ref": {"findings": {}}, "format": "json"}
    )
    assert card.kind == "card"
    assert card.outcome == "ln_sales"
    assert card.coefficients["ln_price"] == pytest.approx(-1.50)


def test_model_export_bundle(model_client):
    client, http = model_client
    http.post_json.return_value = MOCK_BUNDLE_RESPONSE
    result = _journey_result({"model_export_ref": {"findings": {}}})

    card = client.export(result)

    assert card.kind == "bundle"
    assert card.outcome == "sales"  # pulled from cards[0]
    coeffs = card.coefficients
    assert set(coeffs["group"]) == {"east", "west"}


def test_model_export_from_raw_dict(model_client):
    """Mode 1 caller can also pass the ref dict straight from result.raw."""
    client, http = model_client
    http.post_json.return_value = MOCK_CARD_RESPONSE
    ref = {"findings": {}}

    client.export(ref)

    http.post_json.assert_called_once_with(
        "/v1/model/export", {"model_export_ref": ref, "format": "json"}
    )


def test_model_predict(model_client, new_rows_df):
    client, http = model_client
    http.post_json.return_value = MOCK_PREDICT_RESPONSE

    preds = client.predict(MOCK_CARD_RESPONSE, new_rows_df)

    assert preds.n_scored == 2
    assert preds.log_back_transformed is True
    frame = preds.predictions
    assert list(frame["prediction"]) == [12.5, 14.2]
    assert "ci_lower" in frame.columns


def test_model_predict_accepts_result_wrapper(model_client, new_rows_df):
    """.predict() takes the ModelCardResult from a prior .export(), not just a dict."""
    client, http = model_client
    http.post_json.return_value = MOCK_CARD_RESPONSE
    card = client.export({"findings": {}})
    http.post_json.return_value = MOCK_PREDICT_RESPONSE

    preds = client.predict(card, new_rows_df)

    called_payload = http.post_json.call_args[0][1]
    assert called_payload["card"] == MOCK_CARD_RESPONSE
    assert preds.n_scored == 2


def test_model_predict_row_ceiling(model_client):
    client, _ = model_client
    big = pd.DataFrame({"price": range(MAX_SCORE_ROWS + 1)})
    with pytest.raises(SDKUsageError):
        client.predict(MOCK_CARD_RESPONSE, big)


def test_model_compare_ic(model_client):
    client, http = model_client
    http.post_json.return_value = MOCK_IC_COMPARE_RESPONSE

    cmp = client.compare([MOCK_CARD_RESPONSE, MOCK_CARD_RESPONSE], mode="ic")

    assert cmp.mode == "ic"
    assert cmp.best_label == "price, promo"
    assert len(cmp.candidates) == 2


def test_model_compare_nested(model_client):
    client, http = model_client
    http.post_json.return_value = MOCK_NESTED_COMPARE_RESPONSE

    cmp = client.compare([MOCK_CARD_RESPONSE, MOCK_CARD_RESPONSE], mode="nested")

    assert cmp.mode == "nested"
    assert cmp.raw["full_model_preferred"] is True
    assert cmp.candidates.empty  # nested mode has no candidates table


def test_model_drift(model_client, new_rows_df):
    client, http = model_client
    http.post_json.return_value = MOCK_DRIFT_RESPONSE

    d = client.drift(MOCK_CARD_RESPONSE, new_rows_df)

    assert d.applicable is True
    assert d.drift_detected is False
    assert len(d.per_feature) == 1


# ---------------------------------------------------------------------------
# db.scorecard
# ---------------------------------------------------------------------------

@pytest.fixture
def scorecard_client():
    http = MagicMock()
    return ScorecardClient(http), http


def test_scorecard_export(scorecard_client):
    client, http = scorecard_client
    http.post_json.return_value = MOCK_SCORECARD_RESPONSE
    result = _journey_result({"scorecard_export_ref": {"pipeline": {}}})

    card = client.export(result)

    http.post_json.assert_called_once_with(
        "/v1/scorecard/export", {"scorecard_export_ref": {"pipeline": {}}}
    )
    assert card.outcome == "churned"
    assert card.auc == pytest.approx(0.73)


def test_scorecard_score(scorecard_client, new_rows_df):
    client, http = scorecard_client
    http.post_json.return_value = MOCK_SCORE_RESPONSE

    scored = client.score(MOCK_SCORECARD_RESPONSE, new_rows_df)

    assert scored.n_scored == 2
    assert scored.low_confidence_count == 1
    frame = scored.predictions
    assert list(frame["label"]) == [1, 0]
    assert frame["probability"].iloc[0] == pytest.approx(0.83)


def test_scorecard_score_low_confidence_threshold_forwarded(scorecard_client, new_rows_df):
    client, http = scorecard_client
    http.post_json.return_value = MOCK_SCORE_RESPONSE

    client.score(MOCK_SCORECARD_RESPONSE, new_rows_df, low_confidence_threshold=0.75)

    payload = http.post_json.call_args[0][1]
    assert payload["low_confidence_threshold"] == 0.75


# ---------------------------------------------------------------------------
# db.segments
# ---------------------------------------------------------------------------

@pytest.fixture
def segments_client():
    http = MagicMock()
    return SegmentsClient(http), http


def test_segments_export(segments_client):
    client, http = segments_client
    http.post_json.return_value = MOCK_SEGMENT_SCORER_RESPONSE
    result = _journey_result({"segment_scorer_export_ref": {"pipeline": {}}})

    scorer = client.export(result)

    http.post_json.assert_called_once_with(
        "/v1/segment-scorer/export", {"segment_scorer_export_ref": {"pipeline": {}}}
    )
    assert scorer.segments == ["Segment 1", "Segment 2"]


def test_segments_score(segments_client, new_rows_df):
    client, http = segments_client
    http.post_json.return_value = MOCK_SEGMENT_SCORE_RESPONSE

    assigned = client.score(MOCK_SEGMENT_SCORER_RESPONSE, new_rows_df)

    assert assigned.n_scored == 2
    assert assigned.segment_distribution == {"Segment 2": 1, "Segment 1": 1}
    frame = assigned.assignments
    assert list(frame["segment"]) == ["Segment 2", "Segment 1"]


# ---------------------------------------------------------------------------
# Client wiring — db.model / db.scorecard / db.segments exist on DataBubble
# ---------------------------------------------------------------------------

def test_client_exposes_all_three_namespaces():
    from databubble import DataBubble

    db = DataBubble(api_key="dbk_test1234567890")
    assert isinstance(db.model, ModelClient)
    assert isinstance(db.scorecard, ScorecardClient)
    assert isinstance(db.segments, SegmentsClient)


# ---------------------------------------------------------------------------
# ModelCardResult.save() / round-trip
# ---------------------------------------------------------------------------

def test_model_card_save_and_reload(model_client, tmp_path, new_rows_df):
    client, http = model_client
    http.post_json.return_value = MOCK_CARD_RESPONSE
    card = client.export({"findings": {}})

    path = tmp_path / "card.json"
    card.save(str(path))
    reloaded = json.loads(path.read_text())

    assert reloaded == MOCK_CARD_RESPONSE

    http.post_json.return_value = MOCK_PREDICT_RESPONSE
    preds = client.predict(reloaded, new_rows_df)
    assert preds.n_scored == 2
