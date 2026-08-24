# databubble/_scoring_common.py
"""
Shared plumbing for db.model / db.scorecard / db.segments — the portable
model-artifact surface. Export an artifact once from a fitted JourneyResult,
then predict/score from the artifact alone: no session_id, no server state
(the SDK is Mode 1 / stateless-only — see journeys.py — so unlike the
platform's own routes, there is no session_id branch to support here).
"""

from __future__ import annotations

from typing import Any
from databubble.exceptions import SDKUsageError

# Matches MAX_PREDICT_ROWS / MAX_SCORE_ROWS on the platform's model/scorecard/
# segment-scorer routes — checked client-side too so an oversized frame fails
# in milliseconds instead of after a multi-hundred-MB upload.
MAX_SCORE_ROWS = 50_000


def extract_ref(source: Any, ref_field: str, method: str) -> dict:
    """
    source is either a JourneyResult (pull `ref_field` out of its `.result`
    envelope) or the raw ref dict itself — e.g. saved off
    result.raw["result"][ref_field] earlier, or round-tripped from disk.
    """
    from databubble.models import JourneyResult

    if isinstance(source, JourneyResult):
        ref = source.result.get(ref_field)
        if ref is None:
            raise SDKUsageError(
                f"{method}(): this JourneyResult has no '{ref_field}' — either "
                "the journey didn't fit a model, or it halted before producing "
                "one. Check result.halted / result.warnings first."
            )
        return ref
    if isinstance(source, dict):
        return source
    raise SDKUsageError(
        f"{method}() expects a JourneyResult or a dict (the '{ref_field}' "
        f"payload from result.raw['result']['{ref_field}']). "
        f"Got {type(source).__name__}."
    )


def artifact_dict(artifact: Any, method: str, arg_name: str) -> dict:
    """
    artifact is either one of this module's own Result wrappers (has .raw,
    the portable card/scorecard/scorer dict) or a plain dict — loaded
    straight back from a saved JSON file. Cards/scorecards/scorers are
    designed to be portable and reusable outside the session that exported
    them, so both forms have to work here, not just the freshly-returned one.
    """
    if hasattr(artifact, "raw") and isinstance(artifact.raw, dict):
        return artifact.raw
    if isinstance(artifact, dict):
        return artifact
    raise SDKUsageError(
        f"{method}(): {arg_name} must be a dict or a previously-exported "
        f"result object with .raw. Got {type(artifact).__name__}."
    )


def df_to_records(df: Any, method: str) -> list[dict]:
    """
    rows: list[dict] payload shape — model/predict, model/drift,
    scorecard/score and segment-scorer/score all take this (unlike
    journeys.py's columns/rows shape). NaN -> None, since JSON has no NaN.
    """
    import pandas as pd

    if not isinstance(df, pd.DataFrame):
        raise SDKUsageError(f"{method}() requires a pd.DataFrame. Got {type(df).__name__}.")
    n = len(df)
    if n == 0:
        raise SDKUsageError(f"{method}(): DataFrame is empty — nothing to score.")
    if n > MAX_SCORE_ROWS:
        raise SDKUsageError(
            f"{method}(): {n:,} rows exceeds the platform ceiling of "
            f"{MAX_SCORE_ROWS:,} rows per call. Score in batches."
        )
    cleaned = df.astype(object).where(pd.notna(df), None)
    return cleaned.to_dict(orient="records")
