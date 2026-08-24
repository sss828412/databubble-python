# databubble/segments.py
"""
SegmentsClient — db.segments.* : portable JSON segment scorers for
segmentation journeys.

    scorer = db.segments.export(result)
    scorer.save("customer_segments.json")
    assigned = db.segments.score(scorer, new_df)
"""

from __future__ import annotations

from typing import Any
from databubble.models import SegmentScorerResult, SegmentScoreResult
from databubble._scoring_common import extract_ref, artifact_dict, df_to_records


class SegmentsClient:
    def __init__(self, http_client):
        self._http = http_client

    def export(self, source: Any) -> SegmentScorerResult:
        """
        Export the fitted segment classifier from a segmentation JourneyResult
        as a portable JSON scorer.

        Args:
            source: a JourneyResult, or the raw segment_scorer_export_ref dict
                    (result.raw["result"]["segment_scorer_export_ref"]).

        Example:
            result = db.journeys.segmentation(df, feature_cols=[...])
            scorer = db.segments.export(result)

        Tier: same tier gate as the journey that produced the model.
        """
        ref = extract_ref(source, "segment_scorer_export_ref", "db.segments.export")
        response = self._http.post_json(
            "/v1/segment-scorer/export", {"segment_scorer_export_ref": ref}
        )
        return SegmentScorerResult(raw=response)

    def score(self, scorer: Any, rows, low_confidence_threshold: float = 0.60) -> SegmentScoreResult:
        """
        Assign new rows to segments — no session, no re-fitting.

        Args:
            scorer: a SegmentScorerResult (from .export()) or a dict.
            rows:   a pd.DataFrame containing the scorer's feature columns.
            low_confidence_threshold: probability below which an assignment
                    is flagged low_confidence (default 0.60).

        Example:
            assigned = db.segments.score(scorer, new_customers_df)
            assigned.assignments
            assigned.segment_distribution
        """
        sc_dict = artifact_dict(scorer, "db.segments.score", "scorer")
        payload = {
            "scorer": sc_dict,
            "rows": df_to_records(rows, "db.segments.score"),
            "low_confidence_threshold": low_confidence_threshold,
        }
        response = self._http.post_json("/v1/segment-scorer/score", payload)
        return SegmentScoreResult(n_scored=response.get("n_scored", 0), raw=response)
