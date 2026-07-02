# databubble/journeys.py
"""
JourneysClient — typed methods for DataBubble journey endpoints.

Journey endpoints require business or enterprise tier.
Each method runs a complete end-to-end analytical workflow
in a single API call and returns a typed JourneyResult.

Column map rules (same for all journeys):
  - Keys are role names defined by the journey (e.g. "price_col")
  - Values are actual column names in your DataFrame
  - The SDK builds the row-oriented data payload automatically

All methods accept a pd.DataFrame and keyword args for the column map.
The SDK serialises the DataFrame to the row-oriented JSON format the
API expects — callers never need to think about the wire format.
"""

from __future__ import annotations

from typing import Optional
from databubble.models import JourneyResult
from databubble.exceptions import SDKUsageError


def _df_to_rows_payload(df, columns: list[str]) -> dict:
    """
    Serialise selected DataFrame columns to row-oriented JSON payload.
    NaN → None (JSON has no NaN concept).
    """
    rows = []
    subset = df[columns]
    for _, row in subset.iterrows():
        rows.append([
            None if (v != v) else v   # NaN check without numpy
            for v in row.tolist()
        ])
    return {
        "columns": columns,
        "rows": rows,
    }


def _parse_journey_result(response: dict, journey_type: str) -> JourneyResult:
    """Build a JourneyResult from the API response dict."""
    result = response.get("result", {})
    meta = response.get("_meta", {})

    # Driver-specific fields
    selection = result.get("selection_output", {})
    recommended = selection.get("recommended", []) or result.get("recommended", [])
    caution = selection.get("caution", []) or result.get("caution", [])
    excluded = selection.get("excluded", []) or result.get("excluded", [])

    return JourneyResult(
        journey_type=journey_type,
        halted=result.get("halted", False),
        halt_reason=result.get("halt_reason"),
        primary_estimate=result.get("primary_estimate"),
        plain_english_summary=result.get("plain_english_summary", ""),
        warnings=result.get("warnings", []),
        assumptions_met=result.get("assumptions_met"),
        adj_r_squared=result.get("adj_r_squared"),
        revenue_implication=result.get("revenue_implication"),
        recommended=recommended if isinstance(recommended, list) else [],
        caution=caution if isinstance(caution, list) else [],
        excluded=excluded if isinstance(excluded, list) else [],
        tier=meta.get("tier"),
        key_prefix=meta.get("key_prefix"),
        raw=response,
    )


def _require_dataframe(data, method: str):
    try:
        import pandas as pd
    except ImportError:
        raise SDKUsageError("pandas is required. pip install pandas")
    if not isinstance(data, pd.DataFrame):
        raise SDKUsageError(
            f"db.journeys.{method}() requires a pd.DataFrame. "
            f"Got {type(data).__name__}."
        )


def _require_col(df, col: str, arg_name: str, method: str) -> str:
    if col not in df.columns:
        raise SDKUsageError(
            f"db.journeys.{method}(): {arg_name}='{col}' not found in DataFrame. "
            f"Available columns: {list(df.columns)}"
        )
    return col


def _require_col_list(df, cols, arg_name: str, method: str) -> list[str]:
    if isinstance(cols, str):
        cols = [cols]
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise SDKUsageError(
            f"db.journeys.{method}(): {arg_name} contains columns not in DataFrame: "
            f"{missing}. Available: {list(df.columns)}"
        )
    return list(cols)


class JourneysClient:
    def __init__(self, http_client):
        self._http = http_client

    def _call(self, endpoint: str, payload: dict, journey_type: str) -> JourneyResult:
        response = self._http.post_json(f"/v1/journeys/{endpoint}", payload)
        return _parse_journey_result(response, journey_type)

    # -----------------------------------------------------------------------
    # Elasticity
    # -----------------------------------------------------------------------

    def elasticity(
        self,
        df,
        price_col: str,
        sales_col: str,
        confounder_cols: Optional[list[str]] = None,
    ) -> JourneyResult:
        """
        Price elasticity of demand — log-log regression with full assumption checking.

        Detects non-linearity, applies log-log transformation if warranted,
        runs OLS, checks RESET + Durbin-Watson + normality, applies HAC
        standard errors when autocorrelation detected, and surfaces a plain-
        English revenue implication.

        Args:
            df:               DataFrame containing price, sales, and any confounders.
            price_col:        Column name for the price variable (predictor).
            sales_col:        Column name for the sales/demand variable (outcome).
            confounder_cols:  Optional list of confounder column names
                              (promotions, regional dummies, seasonality flags).

        Returns:
            JourneyResult with:
              primary_estimate    — elasticity coefficient β (log-log)
              revenue_implication — plain-English revenue direction
              assumptions_met     — False when RESET, DW, or normality fails
              is_reliable()       — quick gate: not halted AND assumptions_met

        Example:
            result = db.journeys.elasticity(
                df,
                price_col="price",
                sales_col="revenue",
                confounder_cols=["region", "promo_flag"],
            )
            if result.is_reliable():
                print(result.revenue_implication)
            else:
                print(result.warnings)

        Tier: Business and Enterprise only.
        """
        _require_dataframe(df, "elasticity")
        _require_col(df, price_col, "price_col", "elasticity")
        _require_col(df, sales_col, "sales_col", "elasticity")
        confounders = confounder_cols or []
        if confounders:
            _require_col_list(df, confounders, "confounder_cols", "elasticity")

        all_cols = list(dict.fromkeys([price_col, sales_col] + confounders))
        payload = {
            "column_map": {
                "price_col": price_col,
                "sales_col": sales_col,
                "confounder_cols": confounders,
            },
            "data": _df_to_rows_payload(df, all_cols),
            "options": {},
        }
        return self._call("elasticity", payload, "elasticity")

    # -----------------------------------------------------------------------
    # Driver analysis
    # -----------------------------------------------------------------------

    def driver(
        self,
        df,
        outcome_col: str,
        candidate_cols: list[str],
    ) -> JourneyResult:
        """
        Driver analysis — which variables drive the outcome?

        Screens candidates for signal, collinearity, and leakage.
        Elects one representative from each collinear cluster.
        Returns recommended, caution, and excluded lists with reasons.

        Args:
            df:             DataFrame containing outcome and all candidates.
            outcome_col:    Column name for the variable to explain.
            candidate_cols: List of candidate predictor column names.

        Returns:
            JourneyResult with:
              recommended  — predictors with clean signal
              caution      — predictors with collinearity or leakage concerns
              excluded     — predictors without sufficient signal
              primary_estimate — effect size of top recommended driver

        Example:
            result = db.journeys.driver(
                df,
                outcome_col="sales",
                candidate_cols=["price", "promotion", "region", "advertising"],
            )
            print(result.recommended)
            print(result.caution)
            print(result.primary_estimate)

        Tier: Business and Enterprise only.
        """
        _require_dataframe(df, "driver")
        _require_col(df, outcome_col, "outcome_col", "driver")
        candidates = _require_col_list(df, candidate_cols, "candidate_cols", "driver")

        all_cols = list(dict.fromkeys([outcome_col] + candidates))
        payload = {
            "column_map": {
                "outcome_col": outcome_col,
                "candidate_cols": candidates,
            },
            "data": _df_to_rows_payload(df, all_cols),
            "options": {},
        }
        return self._call("driver", payload, "driver")

    # -----------------------------------------------------------------------
    # Segmentation
    # -----------------------------------------------------------------------

    def segmentation(
        self,
        df,
        feature_cols: list[str],
        label_col: Optional[str] = None,
    ) -> JourneyResult:
        """
        Customer segmentation — discovery or classification mode.

        Discovery mode (no label_col): finds natural groups via clustering.
        Classification mode (with label_col): trains a classifier to predict
        pre-defined segments and scores new observations.

        Args:
            df:           DataFrame containing features and optionally labels.
            feature_cols: Columns to use as segmentation features.
            label_col:    Pre-defined segment column (classification mode).
                          Omit for discovery mode.

        Returns:
            JourneyResult with:
              Discovery:       silhouette score, cluster profiles in plain_english_summary
              Classification:  accuracy, F1, confusion matrix summary in plain_english_summary

        Example:
            # Discovery
            result = db.journeys.segmentation(
                df, feature_cols=["recency", "frequency", "spend"]
            )

            # Classification
            result = db.journeys.segmentation(
                df,
                feature_cols=["recency", "frequency", "spend"],
                label_col="segment",
            )

        Tier: Business and Enterprise only.
        """
        _require_dataframe(df, "segmentation")
        features = _require_col_list(df, feature_cols, "feature_cols", "segmentation")
        if label_col:
            _require_col(df, label_col, "label_col", "segmentation")

        all_cols = list(dict.fromkeys(
            features + ([label_col] if label_col else [])
        ))
        column_map = {"feature_cols": features}
        if label_col:
            column_map["label_col"] = label_col

        payload = {
            "column_map": column_map,
            "data": _df_to_rows_payload(df, all_cols),
            "options": {},
        }
        return self._call("segmentation", payload, "segmentation")

    # -----------------------------------------------------------------------
    # Time series
    # -----------------------------------------------------------------------

    def time_series(
        self,
        df,
        date_col: str,
        value_col: str,
        objective: str = "forecast",
    ) -> JourneyResult:
        """
        Time series forecasting and decomposition.

        Validates the time index, fills gaps, selects between ETS and SARIMA
        via AICc, produces prediction intervals from the model's native PI
        method, and validates against a seasonal naïve benchmark via walk-
        forward cross-validation.

        Args:
            df:         DataFrame with date and value columns.
            date_col:   Column name for the date/timestamp variable.
            value_col:  Column name for the series to model.
            objective:  "forecast" (default) or "decompose".
                        Decompose returns trend, seasonal, and remainder components.

        Returns:
            JourneyResult with:
              Forecast:   primary_estimate = horizon-1 point forecast,
                          plain_english_summary includes PI and benchmark comparison
              Decompose:  plain_english_summary describes trend and seasonal pattern

        Example:
            result = db.journeys.time_series(
                df,
                date_col="week",
                value_col="weekly_sales",
                objective="forecast",
            )
            print(result.primary_estimate)   # h=1 point forecast
            print(result.plain_english_summary)

        Tier: Business and Enterprise only.
        """
        _require_dataframe(df, "time_series")
        _require_col(df, date_col, "date_col", "time_series")
        _require_col(df, value_col, "value_col", "time_series")
        if objective not in ("forecast", "decompose"):
            raise SDKUsageError(
                f"objective must be 'forecast' or 'decompose'. Got: '{objective}'"
            )

        payload = {
            "column_map": {
                "date_col": date_col,
                "value_col": value_col,
            },
            "data": _df_to_rows_payload(df, [date_col, value_col]),
            "options": {"objective": objective},
        }
        return self._call("time_series", payload, "time_series")
