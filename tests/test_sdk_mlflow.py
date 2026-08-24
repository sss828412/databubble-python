"""
db.model / db.scorecard / db.segments .to_mlflow() — Phase 5 SDK wiring.

Requires databubble-scoring[mlflow] installed locally (editable, sibling
checkout — see pyproject.toml's `mlflow` extra comment); skipped entirely
otherwise, same convention as test_smoke_live.py's live-server skip.

Proves two things: (1) .to_mlflow() never touches the network — it's a pure
local artifact write, no HTTP client call, unlike every other db.model/
db.scorecard/db.segments method; (2) the artifact it writes is real and
scores correctly when reloaded via mlflow.pyfunc.load_model(), not just
"didn't crash".
"""
import sys
import os

import pytest
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

mlflow = pytest.importorskip("mlflow")
pytest.importorskip("databubble_scoring.mlflow_pyfunc")

from unittest.mock import MagicMock
from databubble.models import JourneyResult, ModelCardResult, ScorecardResult, SegmentScorerResult
from databubble.exceptions import SDKUsageError
from databubble.model import ModelClient
from databubble.scorecard import ScorecardClient
from databubble.segments import SegmentsClient


MOCK_CARD_RESPONSE = {
    "schema_version": "2.0", "model_family": "ols", "outcome": "sales", "intercept": 50.0,
    "terms": [{"name": "price", "coefficient": -1.2}, {"name": "ad_spend", "coefficient": 0.8}],
    "recipe": {"raw_inputs": ["price", "ad_spend"], "input_dtypes": {}, "log_transform_outcome": False,
               "log_transform_inputs": [], "dummies": [], "interactions": [],
               "model_matrix_columns": ["price", "ad_spend"], "drop_first": True},
    "provenance": {"journey_type": "elasticity", "mode": "predict", "fit_n": 250,
                   "created_at": "2026-08-24T00:00:00Z", "source": "databubble"},
    "group_col": None, "group_value": None, "notes": [],
}

MOCK_PIPELINE = {
    "model_type": "binary", "feature_names": ["tenure_months", "monthly_spend"],
    "scaler_mean": [24.0, 60.0], "scaler_scale": [12.0, 20.0],
    "classes_": ["retained", "churned"], "coef_": [[-0.6, 0.4]], "intercept_": [-0.2], "threshold": 0.5,
}

MOCK_SCORECARD_RESPONSE = {
    "schema_version": "2.0", "kind": "classification_scorecard", "outcome": "churned",
    "pipeline": MOCK_PIPELINE, "recipe": None,
    "provenance": {"journey_type": "classification", "outcome": "churned", "auc": 0.73,
                   "created_at": "2026-08-24T00:00:00Z", "source": "databubble"},
    "notes": [],
}

MOCK_SEGMENT_SCORER_RESPONSE = {
    "schema_version": "2.0", "kind": "segment_scorer", "pipeline": MOCK_PIPELINE, "recipe": None,
    "cluster_label_map": {"retained": "Loyal", "churned": "At Risk"}, "profiles": [],
    "provenance": {"journey_type": "segmentation", "created_at": "2026-08-24T00:00:00Z", "source": "databubble"},
    "notes": [],
}


def _journey_result(result_dict: dict) -> JourneyResult:
    return JourneyResult(
        journey_type="elasticity", halted=False, halt_reason=None, primary_estimate=None,
        plain_english_summary="", warnings=[], assumptions_met=True,
        raw={"result": result_dict},
    )


def _classifier_rows():
    return pd.DataFrame({"tenure_months": [3.0, 36.0], "monthly_spend": [90.0, 40.0]})


class TestZeroHttpCalls:
    """
    .to_mlflow() is a pure local operation on the already-exported .raw dict
    — export() itself is the one call that talks to the server; the mlflow
    write must never issue a second one.
    """

    def test_model_card_to_mlflow_issues_no_http_call(self, tmp_path):
        http = MagicMock()
        http.post_json.return_value = MOCK_CARD_RESPONSE
        client = ModelClient(http)
        card = client.export(_journey_result({"model_export_ref": {}}))
        assert http.post_json.call_count == 1  # the export() call itself

        card.to_mlflow(str(tmp_path / "card_model"))

        assert http.post_json.call_count == 1  # unchanged — to_mlflow() made no network call

    def test_scorecard_to_mlflow_issues_no_http_call(self, tmp_path):
        http = MagicMock()
        http.post_json.return_value = MOCK_SCORECARD_RESPONSE
        client = ScorecardClient(http)
        scorecard = client.export(_journey_result({"scorecard_export_ref": {}}))
        assert http.post_json.call_count == 1

        scorecard.to_mlflow(str(tmp_path / "scorecard_model"))

        assert http.post_json.call_count == 1

    def test_segment_scorer_to_mlflow_issues_no_http_call(self, tmp_path):
        http = MagicMock()
        http.post_json.return_value = MOCK_SEGMENT_SCORER_RESPONSE
        client = SegmentsClient(http)
        scorer = client.export(_journey_result({"segment_scorer_export_ref": {}}))
        assert http.post_json.call_count == 1

        scorer.to_mlflow(str(tmp_path / "segment_scorer_model"))

        assert http.post_json.call_count == 1


class TestArtifactIsReal:
    """The written artifact isn't a stub — it reloads and scores correctly."""

    def test_model_card_artifact_predicts_after_reload(self, tmp_path):
        card = ModelCardResult(outcome="sales", kind="card", model_family="ols", raw=MOCK_CARD_RESPONSE)
        path = str(tmp_path / "card_model")
        card.to_mlflow(path)

        loaded = mlflow.pyfunc.load_model(path)
        rows = pd.DataFrame({"price": [10.0, 20.0], "ad_spend": [100.0, 50.0]})
        preds = loaded.predict(rows)

        expected = [50.0 - 1.2 * 10.0 + 0.8 * 100.0, 50.0 - 1.2 * 20.0 + 0.8 * 50.0]
        assert list(preds["prediction"]) == pytest.approx(expected)

    def test_scorecard_artifact_scores_after_reload(self, tmp_path):
        scorecard = ScorecardResult(outcome="churned", raw=MOCK_SCORECARD_RESPONSE)
        path = str(tmp_path / "scorecard_model")
        scorecard.to_mlflow(path)

        loaded = mlflow.pyfunc.load_model(path)
        result = loaded.predict(_classifier_rows())

        assert len(result) == 2
        assert "probability_retained" in result.columns
        assert "probability_churned" in result.columns

    def test_segment_scorer_artifact_scores_after_reload(self, tmp_path):
        scorer = SegmentScorerResult(raw=MOCK_SEGMENT_SCORER_RESPONSE)
        path = str(tmp_path / "segment_scorer_model")
        scorer.to_mlflow(path)

        loaded = mlflow.pyfunc.load_model(path)
        result = loaded.predict(_classifier_rows())

        assert set(result["segment"]) <= {"Loyal", "At Risk"}


class TestBundleRejected:
    def test_bundle_to_mlflow_raises_sdk_usage_error(self, tmp_path):
        bundle = ModelCardResult(outcome="sales", kind="bundle", raw={"kind": "bundle", "cards": []})
        with pytest.raises(SDKUsageError, match="bundle"):
            bundle.to_mlflow(str(tmp_path / "bundle_model"))
