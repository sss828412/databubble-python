# databubble/scorecard.py
"""
ScorecardClient — db.scorecard.* : portable JSON scorecards for
classification-family journeys (classification, predictive_model).

    card = db.scorecard.export(result)
    card.save("churn_scorecard.json")
    scored = db.scorecard.score(card, new_df)
"""

from __future__ import annotations

from typing import Any
from databubble.models import ScorecardResult, ScoreResult
from databubble._scoring_common import extract_ref, artifact_dict, df_to_records


class ScorecardClient:
    def __init__(self, http_client):
        self._http = http_client

    def export(self, source: Any) -> ScorecardResult:
        """
        Export the fitted classifier from a classification/predictive_model
        JourneyResult as a portable JSON scorecard.

        Args:
            source: a JourneyResult, or the raw scorecard_export_ref dict
                    (result.raw["result"]["scorecard_export_ref"]).

        Example:
            result = db.journeys.classification(df, outcome_col="churned", candidate_cols=[...])
            card = db.scorecard.export(result)

        Tier: same tier gate as the journey that produced the model.
        """
        ref = extract_ref(source, "scorecard_export_ref", "db.scorecard.export")
        response = self._http.post_json("/v1/scorecard/export", {"scorecard_export_ref": ref})
        return ScorecardResult(outcome=response.get("outcome", ""), raw=response)

    def score(self, scorecard: Any, rows, low_confidence_threshold: float = 0.60) -> ScoreResult:
        """
        Score new rows for labels + probabilities — no session, no re-fitting.

        Args:
            scorecard: a ScorecardResult (from .export()) or a dict.
            rows:      a pd.DataFrame containing the scorecard's feature columns.
            low_confidence_threshold: probability below which a prediction is
                       flagged low_confidence (default 0.60).

        Example:
            scored = db.scorecard.score(card, new_customers_df)
            scored.predictions
        """
        sc_dict = artifact_dict(scorecard, "db.scorecard.score", "scorecard")
        payload = {
            "scorecard": sc_dict,
            "rows": df_to_records(rows, "db.scorecard.score"),
            "low_confidence_threshold": low_confidence_threshold,
        }
        response = self._http.post_json("/v1/scorecard/score", payload)
        return ScoreResult(
            n_scored=response.get("n_scored", 0),
            low_confidence_count=response.get("low_confidence_count", 0),
            threshold_used=response.get("threshold_used"),
            raw=response,
        )
