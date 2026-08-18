# databubble/models.py
"""
Typed return objects for the DataBubble SDK.

Deliberately lightweight — plain dataclasses, no Pydantic dependency.
Every object exposes `.raw` for full API response access.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SkillResult:
    """
    Return type for all skill calls.

    Attributes:
        summary         Plain-English summary of the finding (token-efficient).
        findings        Dict of structured findings — skewness, mean, mechanism etc.
        warnings        List of warning strings — assumption violations, data issues.
        recommendations List of recommendation strings — what to do next.
        chapter_ref     Knowledge chapter reference e.g. "Chapter 04".
        skill_name      Which skill was called.
        column          Column analysed (None for whole-dataset skills).
        n_rows          Row count of the input data.
        tier            API tier used for this call.
        key_prefix      Key prefix for audit trail.
        raw             Full API response dict — access anything not surfaced above.
    """
    summary: str
    findings: dict[str, Any]
    warnings: list[str]
    recommendations: list[str]
    chapter_ref: str
    skill_name: str
    column: Optional[str] = None
    n_rows: Optional[int] = None
    tier: Optional[str] = None
    key_prefix: Optional[str] = None
    halted: bool = False
    halt_reason: Optional[str] = None
    raw: dict = field(default_factory=dict)
    # Injected by SkillsClient so .charts can lazily fetch by filename.
    _http: Any = field(default=None, repr=False, compare=False)

    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def has_blocking_issues(self) -> bool:
        """True if any warning uses the word 'blocking' or 'halt'."""
        lower = [w.lower() for w in self.warnings]
        return any("blocking" in w or "halt" in w for w in lower)

    # -- data-scientist surface (0.5.0) -----------------------------------
    @property
    def charts(self):
        """
        ChartSet built from the chart_* keys the skill returned inside
        `findings` (univariate, bivariate, outliers, correlation, transformations).
        Charts are fetched lazily from GET /v1/charts/{filename}.
        """
        from databubble.charts import from_response

        payload = self.findings if isinstance(self.findings, dict) else {}
        return from_response(payload, http=self._http)

    def to_frame(self):
        """
        Findings as a two-column DataFrame (metric, value). Nested/None values
        and chart references are dropped — use .findings for those.
        """
        import pandas as pd

        if not isinstance(self.findings, dict):
            return pd.DataFrame({"value": self.findings or []})
        rows = [
            (key, value)
            for key, value in self.findings.items()
            if not key.startswith("chart_") and not isinstance(value, (dict, list))
        ]
        return pd.DataFrame(rows, columns=["metric", "value"])

    def _repr_html_(self) -> str:
        from databubble.tables import escape, frame_to_html

        title = f"{self.skill_name}" + (f" — {self.column}" if self.column else "")
        head = (
            "<div style='font-family:system-ui'>"
            f"<p style='margin:0 0 6px 0'><strong>{escape(title)}</strong></p>"
        )
        body = frame_to_html(self.to_frame(), "")
        warn = ""
        if self.warnings:
            warn = "<ul style='margin:6px 0'>" + "".join(
                f"<li>{escape(w)}</li>" for w in self.warnings[:10]
            ) + "</ul>"
        chart_note = ""
        if len(self.charts):
            chart_note = (
                "<p style='color:#666;margin:4px 0 0 0'>"
                f"{len(self.charts)} chart(s) available — <code>.charts.show()</code></p>"
            )
        return head + body + warn + chart_note + "</div>"

    def __repr__(self) -> str:
        warn_str = f", {len(self.warnings)} warnings" if self.warnings else ""
        col_str = f" on '{self.column}'" if self.column else ""
        return f"SkillResult({self.skill_name}{col_str}{warn_str})"


@dataclass
class TreatmentRecord:
    """One platform recommendation on one column."""
    column: str
    issue: str
    recommendation: str
    severity: str          # "blocking" / "warning" / "informational"
    status: str            # "open" / "applied" / "deferred" / "overridden"


@dataclass
class ColumnMemory:
    """Analytical record for one column from a memory file."""
    name: str
    skewness: Optional[float]
    mean: Optional[float]
    median: Optional[float]
    missing_pct: float
    missing_mechanism: Optional[str]
    variable_type: Optional[str]
    is_bounded_ordinal: bool
    blocking_issues: list[str]
    treatments: list[TreatmentRecord]

    @property
    def has_blocking_issues(self) -> bool:
        return len(self.blocking_issues) > 0

    @property
    def open_treatments(self) -> list[TreatmentRecord]:
        return [t for t in self.treatments if t.status == "open"]


@dataclass
class MemoryResult:
    """
    Return type for db.memory.export().

    Attributes:
        memory_id       UUID for this memory file.
        label           User-given label.
        memory_json     Full memory dict — pass to save() or load back later.
        memory_markdown Human-readable narrative string.
        open_count      Number of unresolved recommendations.
        blocking_count  Number of columns with blocking issues.
        columns_covered Number of columns with univariate coverage.
        raw             Full API response.
    """
    memory_id: str
    label: str
    memory_json: dict
    memory_markdown: str
    open_count: int
    blocking_count: int
    columns_covered: int
    raw: dict = field(default_factory=dict)

    def save(self, path: str) -> None:
        """Write memory_json to disk as a .json file."""
        import json
        with open(path, "w") as f:
            json.dump(self.memory_json, f, indent=2)
        print(f"Memory saved to {path}")

    def save_markdown(self, path: str) -> None:
        """Write human-readable narrative to disk as a .md file."""
        with open(path, "w") as f:
            f.write(self.memory_markdown)
        print(f"Markdown summary saved to {path}")

    def __repr__(self) -> str:
        return (
            f"MemoryResult('{self.label}', "
            f"{self.columns_covered} columns covered, "
            f"{self.open_count} open items)"
        )


@dataclass
class ColumnReconciliation:
    name: str
    status: str            # matched / missing_in_new / new_column / stats_shifted
    memory_source: Optional[str]
    shift_note: Optional[str]


@dataclass
class ReconciliationResult:
    """
    Return type for db.memory.reconcile().

    Attributes:
        memories_loaded         Labels of loaded memory files.
        columns_matched         Per-column reconciliation status.
        open_items              Unresolved recommendations from all memories.
        verified_treatments     Treatments user claimed that platform could verify.
        unverifiable_treatments Treatments platform could not confirm from data.
        ready_to_advance        True when all columns have univariate coverage (Option A).
        suggested_next          Plain-English suggestion for next analysis step.
        inherited_column_memories  Dict of col_name → column facts for EDA orchestrator.
        raw                     Full API response.
    """
    memories_loaded: list[str]
    columns_matched: list[ColumnReconciliation]
    open_items: list[str]
    verified_treatments: list[str]
    unverifiable_treatments: list[str]
    ready_to_advance: bool
    suggested_next: str
    inherited_column_memories: dict
    raw: dict = field(default_factory=dict)

    @property
    def new_columns(self) -> list[str]:
        return [c.name for c in self.columns_matched if c.status == "new_column"]

    @property
    def shifted_columns(self) -> list[str]:
        return [c.name for c in self.columns_matched if c.status == "stats_shifted"]

    def to_frame(self):
        """Per-column reconciliation status as a DataFrame."""
        import pandas as pd

        return pd.DataFrame(
            [
                {
                    "column": c.name,
                    "status": c.status,
                    "memory_source": c.memory_source,
                    "shift_note": c.shift_note,
                }
                for c in self.columns_matched
            ]
        )

    def __repr__(self) -> str:
        return (
            f"ReconciliationResult("
            f"{len(self.memories_loaded)} memories, "
            f"ready={self.ready_to_advance}, "
            f"open={len(self.open_items)})"
        )




# ---------------------------------------------------------------------------
# JourneyResult — data-scientist-first surface (0.5.0)
# ---------------------------------------------------------------------------

_DEPRECATED_SELECTION = (
    "JourneyResult.{old} is deprecated and will be removed in 1.0. "
    "It never worked against the live API: the envelope names these fields "
    "`selected_predictors` / `excluded_predictors`, and the selection reasoning "
    "is a sibling of `result`, not inside it. Use .{new} instead."
)


@dataclass
class JourneyResult:
    """
    Return type for all db.journeys.* calls.

    The primary surface is quantitative:

        r = db.journeys.driver(df, outcome_col="sales", candidate_cols=[...])
        print(r)                # statsmodels-style regression table
        r.estimates             # DataFrame: coef, std err, t, p, CI, VIF
        r.coefficients          # Series: predictor -> coefficient
        r.effects               # DataFrame: standardised coef, effect size, partial R2
        r.diagnostics           # Series: n, adj R2, assumptions_met, transformation...
        r.charts                # ChartSet (empty until the API returns charts)

    The business narrative is still there, it is just no longer the default view:

        r.explain()             # plain-English summary + revenue implication
        r.plain_english_summary # the raw narrative string

    Everything the API returned is always available at r.raw.
    """

    journey_type: str
    halted: bool
    halt_reason: Optional[str]
    primary_estimate: Optional[float]
    plain_english_summary: str
    warnings: list[str]
    assumptions_met: Optional[bool]
    adj_r_squared: Optional[float] = None
    revenue_implication: Optional[str] = None
    tier: Optional[str] = None
    key_prefix: Optional[str] = None
    raw: dict = field(default_factory=dict)
    # Injected by JourneysClient so .charts can lazily fetch by filename.
    _http: Any = field(default=None, repr=False, compare=False)

    # -- raw navigation ---------------------------------------------------
    @property
    def result(self) -> dict:
        """The `result` envelope — every field the API returned for this journey."""
        value = self.raw.get("result")
        return value if isinstance(value, dict) else {}

    @property
    def handoffs(self) -> dict:
        """
        Domain payload for the graph-based journeys (mmm, pay_equity,
        cross_price, spc_monitoring, latent_factors, causal_inference,
        churn_clv_at_risk, forecast_inventory, intervention_lift).
        Empty dict for the direct-function journeys.
        """
        value = self.result.get("handoffs")
        return value if isinstance(value, dict) else {}

    # -- quantitative surface ---------------------------------------------
    @property
    def estimates(self):
        """Per-predictor coefficient table as a DataFrame (empty if absent)."""
        from databubble.tables import ESTIMATE_COLUMNS, rows_to_frame

        rows = self.result.get("estimates") or self.handoffs.get("estimates")
        return rows_to_frame(rows, ESTIMATE_COLUMNS)

    @property
    def coefficients(self):
        """Series mapping predictor name -> coefficient."""
        import pandas as pd

        frame = self.estimates
        if frame.empty or "name" not in frame.columns or "coefficient" not in frame.columns:
            return pd.Series(dtype="float64")
        return pd.Series(
            frame["coefficient"].values, index=frame["name"].values, name="coefficient"
        )

    @property
    def effects(self):
        """
        Effect-size table: standardised coefficients, effect sizes, partial R²
        and dominance, merged on predictor name where the API provides them.
        """
        import pandas as pd
        from databubble.tables import mapping_to_frame, rows_to_frame

        frames = []
        for key, label in (
            ("standardized_coefficients", "std_coefficient"),
            ("effect_sizes", "effect_size"),
            ("partial_r_squared", "partial_r2"),
        ):
            value = self.result.get(key)
            if isinstance(value, dict):
                frames.append(mapping_to_frame(value, "predictor", label))
            elif isinstance(value, list):
                frame = rows_to_frame(value)
                if not frame.empty:
                    name_col = "predictor" if "predictor" in frame.columns else "name"
                    if name_col in frame.columns:
                        frame = frame.rename(columns={name_col: "predictor"})
                    frames.append(frame)

        dominance = self.result.get("partial_r_squared_dominance")
        if isinstance(dominance, dict) and dominance:
            frames.append(mapping_to_frame(dominance, "predictor", "dominance"))

        frames = [f for f in frames if not f.empty and "predictor" in f.columns]
        if not frames:
            return pd.DataFrame()

        merged = frames[0]
        for frame in frames[1:]:
            merged = merged.merge(frame, on="predictor", how="outer")
        return merged

    @property
    def diagnostics(self):
        """Model-level diagnostics as a Series (only fields the API returned)."""
        import pandas as pd
        from databubble.tables import DIAGNOSTIC_FIELDS

        data = {}
        for key in DIAGNOSTIC_FIELDS:
            if key in self.result and self.result[key] is not None:
                data[key] = self.result[key]
        for key in ("shapiro_pvalue", "bp_pvalue", "durbin_watson", "normality_ok",
                    "homoscedasticity_ok", "residual_std"):
            source = self.result.get("residual_diagnostics")
            if isinstance(source, dict) and key in source:
                data[key] = source[key]
        return pd.Series(data, dtype="object")

    @property
    def selected_predictors(self) -> list[str]:
        """Predictors that were actually fitted."""
        for source in (self.result, self.raw.get("selection") or {}):
            if isinstance(source, dict):
                value = source.get("selected_predictors") or source.get("recommended")
                if isinstance(value, list):
                    return value
        frame = self.estimates
        if not frame.empty and "name" in frame.columns:
            return [str(n) for n in frame["name"].tolist()]
        return []

    @property
    def excluded_predictors(self) -> list[str]:
        for source in (self.result, self.raw.get("selection") or {}):
            if isinstance(source, dict):
                value = source.get("excluded_predictors") or source.get("excluded")
                if isinstance(value, list):
                    return value
        return []

    @property
    def focus_predictor(self) -> Optional[str]:
        return self.result.get("focus_predictor")

    @property
    def n_observations(self) -> Optional[int]:
        value = self.result.get("n_observations") or self.result.get("n_clean")
        return int(value) if isinstance(value, (int, float)) else None

    @property
    def confidence_interval(self) -> Optional[tuple]:
        low = self.result.get("ci_lower", self.result.get("primary_ci_lower"))
        high = self.result.get("ci_upper", self.result.get("primary_ci_upper"))
        if low is None and high is None:
            return None
        return (low, high)

    @property
    def significant(self) -> Optional[bool]:
        value = self.result.get("significant", self.result.get("primary_significant"))
        return value if isinstance(value, bool) else None

    @property
    def charts(self):
        """
        ChartSet for this journey.

        Empty until the platform returns chart content on /v1/journeys/* — see
        the Track B spec. When it does, no SDK change is needed: inline SVG and
        filename shapes are both handled here already.
        """
        from databubble.charts import from_response

        merged = dict(self.result)
        merged.update({k: v for k, v in self.raw.items() if k.startswith("chart") or k == "charts"})
        return from_response(merged, http=self._http)

    # -- gates ------------------------------------------------------------
    def is_reliable(self) -> bool:
        """True when the journey completed and assumptions were not violated."""
        return not self.halted and self.assumptions_met is not False

    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    # -- views ------------------------------------------------------------
    def to_frame(self):
        """Alias for .estimates — the tabular view of this result."""
        return self.estimates

    def summary(self, max_rows: int = 50) -> str:
        """statsmodels-style text summary. This is what repr() shows."""
        from databubble.tables import estimate_table, header_block, warnings_block

        if self.halted:
            return (
                f"{self.journey_type} — HALTED\n"
                + "=" * 78
                + f"\n{self.halt_reason or 'no reason given'}\n"
                + warnings_block(self.warnings)
            )

        pairs = [
            ("Observations", self.n_observations),
            ("Adj. R²", self.adj_r_squared),
            ("Assumptions met", self.assumptions_met),
            ("Focus predictor", self.focus_predictor),
            ("Estimate", self.primary_estimate),
            ("Significant", self.significant),
            ("Transformation", self.result.get("transformation_applied")),
            ("Tier", self.tier),
        ]
        interval = self.confidence_interval
        if interval and interval[0] is not None:
            pairs.append(("95% CI", f"[{interval[0]:.4g}, {interval[1]:.4g}]"))

        title = self.result.get("primary_label") or f"{self.journey_type} journey"
        blocks = [header_block(title, pairs) + "\n", estimate_table(self.estimates, max_rows)]

        if self.estimates.empty and self.handoffs:
            blocks.append(
                "  Domain output for this journey is in .handoffs — keys: "
                + ", ".join(sorted(self.handoffs)[:12])
            )

        blocks.append(warnings_block(self.warnings))
        blocks.append("\nNarrative: r.explain()   Full response: r.raw")
        return "\n".join(b for b in blocks if b != "")

    def explain(self) -> str:
        """The business-facing narrative — now opt-in rather than the default."""
        parts = [self.plain_english_summary or "(no narrative returned)"]
        if self.revenue_implication:
            parts.append(f"\nRevenue implication: {self.revenue_implication}")
        if self.result.get("causal_limitation"):
            parts.append(f"\nCausal limitation: {self.result['causal_limitation']}")
        if self.warnings:
            parts.append("\nWarnings:\n" + "\n".join(f"  - {w}" for w in self.warnings))
        return "\n".join(parts)

    def _repr_html_(self) -> str:
        from databubble.tables import escape, frame_to_html

        if self.halted:
            return (
                f"<div><strong>{escape(self.journey_type)} — HALTED</strong>"
                f"<p>{escape(self.halt_reason)}</p></div>"
            )

        rows = "".join(
            f"<td style='padding:2px 12px 2px 0'><strong>{escape(label)}</strong> {escape(value)}</td>"
            for label, value in (
                ("n", self.n_observations),
                ("Adj. R²", self.adj_r_squared),
                ("Assumptions", self.assumptions_met),
                ("Estimate", self.primary_estimate),
            )
            if value is not None
        )
        head = (
            f"<div style='font-family:system-ui'><p style='margin:0 0 6px 0'>"
            f"<strong>{escape(self.result.get('primary_label') or self.journey_type)}</strong></p>"
            f"<table style='margin-bottom:8px'><tr>{rows}</tr></table>"
        )
        body = frame_to_html(self.estimates, "Estimates")
        if not body and self.handoffs:
            body = f"<em>Domain output in <code>.handoffs</code>: {escape(', '.join(sorted(self.handoffs)[:12]))}</em>"
        warn = ""
        if self.warnings:
            warn = "<ul style='margin:6px 0'>" + "".join(
                f"<li>{escape(w)}</li>" for w in self.warnings[:10]
            ) + "</ul>"
        foot = "<p style='color:#666;margin:6px 0 0 0'><code>.explain()</code> for the narrative, <code>.raw</code> for everything.</p></div>"
        return head + body + warn + foot

    def __repr__(self) -> str:
        return self.summary()

    # -- deprecated -------------------------------------------------------
    @property
    def recommended(self) -> list[str]:
        import warnings as _w

        _w.warn(
            _DEPRECATED_SELECTION.format(old="recommended", new="selected_predictors"),
            DeprecationWarning,
            stacklevel=2,
        )
        selection = self.raw.get("selection")
        if isinstance(selection, dict) and isinstance(selection.get("recommended"), list):
            return selection["recommended"]
        legacy = self.result.get("selection_output")
        if isinstance(legacy, dict) and isinstance(legacy.get("recommended"), list):
            return legacy["recommended"]
        return self.selected_predictors

    @property
    def caution(self) -> list[str]:
        import warnings as _w

        _w.warn(
            _DEPRECATED_SELECTION.format(old="caution", new="raw['selection']['caution']"),
            DeprecationWarning,
            stacklevel=2,
        )
        for source in (self.raw.get("selection"), self.result.get("selection_output")):
            if isinstance(source, dict) and isinstance(source.get("caution"), list):
                return source["caution"]
        return []

    @property
    def excluded(self) -> list[str]:
        import warnings as _w

        _w.warn(
            _DEPRECATED_SELECTION.format(old="excluded", new="excluded_predictors"),
            DeprecationWarning,
            stacklevel=2,
        )
        for source in (self.raw.get("selection"), self.result.get("selection_output")):
            if isinstance(source, dict) and isinstance(source.get("excluded"), list):
                return source["excluded"]
        return self.excluded_predictors
