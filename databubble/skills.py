# databubble/skills.py
"""
SkillsClient — typed methods for every DataBubble skill.

Column rules:
  Single-column skills (univariate, outliers):
    - Pass a pd.Series → SDK serialises it
    - Pass a pd.DataFrame + column="price" → SDK extracts and serialises
    - Pass a pd.DataFrame without column= → SDKUsageError (never auto-pick)

  Whole-dataset skills (missing_values, leakage):
    - Pass a pd.DataFrame → SDK serialises all columns

  Two-column skills (bivariate, correlation):
    - Pass a pd.DataFrame + x="price", y="sales"
    - Or pass two pd.Series as positional args
"""

from __future__ import annotations

from typing import Optional, Union
import json

from databubble.models import SkillResult
from databubble.exceptions import SDKUsageError


def _sanitise_value(v, col_name: str):
    """
    Convert a single value for JSON transport.
    NaN / pd.NA / None → None (documented: treated as missing by the API).
    Inf/-Inf → SDKUsageError (JSON cannot represent infinity; caller must handle it).

    M-4: pd.NA (nullable Int64/boolean/string dtypes) breaks `v != v` because
    `pd.NA != pd.NA` returns pd.NA, which raises TypeError in a boolean context.
    Use pd.isna() which handles float NaN, pd.NA, numpy.nan, and None uniformly.
    """
    import math
    try:
        import pandas as pd
        if pd.isna(v):
            return None
    except (ImportError, TypeError, ValueError):
        # pd.isna raises TypeError for unhashable types (dicts, lists) — not missing
        pass
    if isinstance(v, float) and math.isinf(v):
        raise SDKUsageError(
            f"Column '{col_name}' contains infinite values (inf or -inf). "
            "Remove or replace them before calling skills. "
            "Note: NaN values are accepted and treated as missing."
        )
    return v


def _series_to_payload(series, col_name: str) -> dict:
    """
    Serialise a pd.Series to the JSON body format.
    NaN → null (documented API contract: treated as missing value).
    Inf raises SDKUsageError — JSON has no Infinity representation.
    """
    return {
        "column": col_name,
        "data": [_sanitise_value(v, col_name) for v in series.tolist()],
    }


def _df_to_payload(df, columns: list[str]) -> dict:
    """Serialise selected DataFrame columns to JSON body format."""
    return {
        "columns": columns,
        "data": {col: [_sanitise_value(v, col) for v in df[col].tolist()] for col in columns},
    }


def _parse_skill_result(response: dict) -> SkillResult:
    """Build a SkillResult from the API response dict."""
    result = response.get("result", response)
    meta = response.get("_meta", {})
    return SkillResult(
        summary=result.get("summary", ""),
        findings=result.get("findings", {}),
        warnings=result.get("warnings", []),
        recommendations=result.get("recommendations", []),
        chapter_ref=result.get("chapter_ref", ""),
        skill_name=result.get("skill_name", meta.get("skill", "")),
        column=result.get("column"),
        n_rows=response.get("n_rows"),
        tier=meta.get("tier"),
        key_prefix=meta.get("key_prefix"),
        halted=result.get("halted", False),
        halt_reason=result.get("halt_reason"),
        raw=response,
    )


class SkillsClient:
    def __init__(self, http_client):
        self._http = http_client   # injected from DataBubble root client

    def _call(self, skill_name: str, payload: dict) -> SkillResult:
        response = self._http.post_json(f"/v1/skills/{skill_name}", payload)
        return _parse_skill_result(response)

    # -----------------------------------------------------------------------
    # Single-column skills
    # -----------------------------------------------------------------------

    def univariate(
        self,
        data,
        column: Optional[str] = None,
    ) -> SkillResult:
        """
        Univariate distribution analysis on one column.

        Args:
            data:   pd.Series, or pd.DataFrame (requires column= arg)
            column: Column name — required when data is a DataFrame.

        Returns:
            SkillResult with skewness, kurtosis, mean, median, std,
            bounded_ordinal detection, MNAR flags, and recommendations.
        """
        payload = _resolve_single_column(data, column, skill="univariate")
        return self._call("univariate", payload)

    def outliers(
        self,
        data,
        column: Optional[str] = None,
    ) -> SkillResult:
        """
        Univariate outlier detection (IQR + Z-score).
        For relational/Type 2 outliers, use a bivariate or regression skill.

        Args:
            data:   pd.Series, or pd.DataFrame (requires column= arg)
            column: Column name — required when data is a DataFrame.
        """
        payload = _resolve_single_column(data, column, skill="outliers")
        return self._call("outliers", payload)

    # -----------------------------------------------------------------------
    # Whole-dataset skills
    # -----------------------------------------------------------------------

    def missing_values(self, df) -> SkillResult:
        """
        Missing value profiling across all columns.
        Detects MCAR / MAR / POSSIBLE_MNAR per column.
        Recommends treatment per column.

        Args:
            df: pd.DataFrame — all columns profiled.
        """
        _require_dataframe(df, skill="missing_values")
        payload = _df_to_payload(df, list(df.columns))
        return self._call("missing_values", payload)

    def leakage(self, df, outcome: str) -> SkillResult:
        """
        Data leakage detection.
        Checks for post-outcome timing patterns and high-correlation proxies.

        Args:
            df:      pd.DataFrame
            outcome: Name of the outcome column.
        """
        _require_dataframe(df, skill="leakage")
        if outcome not in df.columns:
            raise SDKUsageError(
                f"outcome='{outcome}' not found in DataFrame columns: {list(df.columns)}"
            )
        predictor_cols = [c for c in df.columns if c != outcome]
        payload = {
            **_df_to_payload(df, list(df.columns)),
            "params": {"outcome": outcome, "predictor_cols": predictor_cols},
        }
        return self._call("leakage", payload)

    # -----------------------------------------------------------------------
    # Two-column skills
    # -----------------------------------------------------------------------

    def bivariate(
        self,
        data,
        x: Optional[str] = None,
        y: Optional[str] = None,
        y_series=None,
    ) -> SkillResult:
        """
        Bivariate relationship analysis.
        Detects linearity, non-linearity, and correlation strength.

        Args:
            data: pd.DataFrame (requires x= and y=) or pd.Series for x
            x:    Column name for x variable (predictor)
            y:    Column name for y variable (outcome)
            y_series: pd.Series for y when data is a Series for x
        """
        payload = _resolve_two_columns(data, x, y, y_series, skill="bivariate")
        return self._call("bivariate", payload)

    def correlation(
        self,
        data,
        x: Optional[str] = None,
        y: Optional[str] = None,
        y_series=None,
    ) -> SkillResult:
        """
        Correlation analysis between two columns.
        Reports Pearson + Spearman, flags non-linearity risk.

        Args:
            data: pd.DataFrame (requires x= and y=) or pd.Series for x
            x:    Column name for x variable
            y:    Column name for y variable
            y_series: pd.Series for y when data is a Series for x
        """
        payload = _resolve_two_columns(data, x, y, y_series, skill="correlation")
        return self._call("correlation", payload)


# ---------------------------------------------------------------------------
# Input resolution helpers — used by SkillsClient methods
# ---------------------------------------------------------------------------

def _resolve_single_column(data, column: Optional[str], skill: str) -> dict:
    """
    Resolve single-column input to a JSON payload dict.

    Accepts:
      - pd.Series → use Series.name or raise if unnamed
      - pd.DataFrame + column= → extract that column
      - pd.DataFrame without column= → SDKUsageError
    """
    try:
        import pandas as pd
    except ImportError:
        raise SDKUsageError("pandas is required. Install with: pip install pandas")

    if isinstance(data, pd.Series):
        col_name = column or data.name
        if not col_name:
            raise SDKUsageError(
                f"{skill}() received an unnamed Series. "
                f"Either name the Series (series.name = 'price') "
                f"or pass column='price' as an argument."
            )
        return _series_to_payload(data, col_name)

    if isinstance(data, pd.DataFrame):
        if column is None:
            raise SDKUsageError(
                f"{skill}() received a DataFrame but no column was specified. "
                f"Pass column='price' or pass a Series directly: df['price']"
            )
        if column not in data.columns:
            raise SDKUsageError(
                f"column='{column}' not found in DataFrame. "
                f"Available columns: {list(data.columns)}"
            )
        return _series_to_payload(data[column], column)

    raise SDKUsageError(
        f"{skill}() expects a pd.Series or pd.DataFrame. Got {type(data).__name__}."
    )


def _resolve_two_columns(data, x, y, y_series, skill: str) -> dict:
    """
    Resolve two-column input to a JSON payload dict.

    Accepts:
      - pd.DataFrame + x= + y=
      - pd.Series (as data) + pd.Series (as y_series)
    """
    try:
        import pandas as pd
    except ImportError:
        raise SDKUsageError("pandas is required. Install with: pip install pandas")

    if isinstance(data, pd.DataFrame):
        if x is None or y is None:
            raise SDKUsageError(
                f"{skill}() requires x= and y= column names when passing a DataFrame. "
                f"Example: db.skills.{skill}(df, x='price', y='sales')"
            )
        for col in (x, y):
            if col not in data.columns:
                raise SDKUsageError(
                    f"Column '{col}' not found in DataFrame. "
                    f"Available: {list(data.columns)}"
                )
        return {
            **_df_to_payload(data, [x, y]),
            "params": {"x": x, "y": y},
        }

    if isinstance(data, pd.Series):
        if y_series is None or not isinstance(y_series, pd.Series):
            raise SDKUsageError(
                f"{skill}() with two Series: pass x Series as first arg "
                f"and y Series as y_series=. "
                f"Example: db.skills.{skill}(df['price'], y_series=df['sales'])"
            )
        x_name = x or data.name or "x"
        y_name = y or y_series.name or "y"
        payload = {
            "columns": [x_name, y_name],
            "data": {
                x_name: _series_to_payload(data, x_name)["data"],
                y_name: _series_to_payload(y_series, y_name)["data"],
            },
            "params": {"x": x_name, "y": y_name},
        }
        return payload

    raise SDKUsageError(
        f"{skill}() expects a pd.DataFrame or pd.Series. Got {type(data).__name__}."
    )


def _require_dataframe(data, skill: str) -> None:
    try:
        import pandas as pd
    except ImportError:
        raise SDKUsageError("pandas is required. Install with: pip install pandas")
    if not isinstance(data, pd.DataFrame):
        raise SDKUsageError(
            f"{skill}() requires a pd.DataFrame. Got {type(data).__name__}. "
            f"Pass the full DataFrame — this skill analyses all columns."
        )
